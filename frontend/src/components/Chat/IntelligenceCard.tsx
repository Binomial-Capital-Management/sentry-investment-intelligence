import { useState, useMemo, memo, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Copy, Check, FileText, Presentation, Sheet, Loader2, Pencil, CheckCircle2 } from 'lucide-react';
import SegmentedTabs from '@components/core/SegmentedTabs';
import type { Message as MessageType } from '@/types';
import PlotlyChart from '../Charts/PlotlyChart';
import SourcePill from '../Common/SourcePill';
import TraceDrawer from '../TraceDrawer/TraceDrawer';
import WorkingContentRenderer from './WorkingContentRenderer';
import CodeExecutionDisplay from './CodeExecutionDisplay';
import { copyMessageContent } from '@/utils/export';
import { useAuth, useUser, useOrganization } from '@clerk/clerk-react';
import { API_BASE } from '@/services/api';
import IntelligenceLoader from './IntelligenceLoader';
import StreamingProgress from './StreamingProgress';

interface IntelligenceCardProps {
  message: MessageType;
}

// Agent metadata configuration
const AGENT_CONFIG = {
  generalist: {
    label: 'Generalist',
    color: 'var(--accent)',
    icon: 'G',
    description: 'General conversation and routing',
  },
  risk_specialist: {
    label: 'Risk Specialist',
    color: '#37B679',
    icon: 'R',
    description: 'Risk calculations and analysis',
  },
  orchestrator: {
    label: 'Orchestrator',
    color: '#E9B949',
    icon: 'O',
    description: 'Coordinating multiple agents',
  },
  document_analyst: {
    label: 'Document Analyst',
    color: '#8b5cf6',
    icon: 'D',
    description: 'SEC filings and document analysis',
  },
  comparable_companies: {
    label: 'Comparable Companies',
    color: '#10b981',
    icon: 'C',
    description: 'Peer valuation analysis',
  },
  chart_analyst: {
    label: 'Chart Analyst',
    color: '#3b82f6',
    icon: 'T',
    description: 'Technical analysis and charts',
  },
  quant_coding: {
    label: 'Quant Coding',
    color: '#ec4899',
    icon: 'Q',
    description: 'Custom quantitative implementations',
  },
  alternatives_coding: {
    label: 'Alternatives Data',
    color: '#f59e0b',
    icon: '₿',
    description: 'Cryptocurrency, forex, and commodities data',
  },
  institutional_activity: {
    label: 'Institutional Activity',
    color: '#8b5cf6',
    icon: '⚖',
    description: 'Insider trading, institutional ownership, congressional data',
  },
  dcf_valuation: {
    label: 'DCF Valuation',
    color: '#059669',
    icon: 'V',
    description: 'Discounted Cash Flow valuation models',
  },
  screener: {
    label: 'Market Screener',
    color: '#6366f1',
    icon: 'S',
    description: 'Stock and crypto screening',
  },
  options_analyst: {
    label: 'Options Analyst',
    color: '#d946ef',
    icon: 'Op',
    description: 'Options pricing and Greeks',
  },
  funds_analyst: {
    label: 'Funds Analyst',
    color: '#0ea5e9',
    icon: 'F',
    description: 'ETF and Mutual Fund analysis',
  },
  prediction_markets: {
    label: 'Prediction Markets',
    color: '#84cc16',
    icon: 'P',
    description: 'Event contracts and probabilities',
  },
  private_markets: {
    label: 'Private Markets',
    color: '#a855f7',
    icon: 'PM',
    description: 'VC and PE insights',
  },
} as const;

const IntelligenceCard = memo(({ message }: IntelligenceCardProps) => {
  const [activeTab, setActiveTab] = useState<'response' | 'sources' | 'metrics'>('response');
  const [showTrace, setShowTrace] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportingPpt, setExportingPpt] = useState(false);
  const [exportingWorkbook, setExportingWorkbook] = useState(false);
  const [showStyleSelector, setShowStyleSelector] = useState(false);
  const [availableStyles, setAvailableStyles] = useState<Array<{style_name: string, is_default: boolean}>>([]);
  const [selectedStyleName, setSelectedStyleName] = useState<string | null>(null);
  const messageContentRef = useRef<HTMLDivElement>(null);
  const styleSelectorRef = useRef<HTMLDivElement>(null);
  const { getToken, isLoaded } = useAuth();
  const { user } = useUser();
  const { organization } = useOrganization();

  const isUser = message.role === 'user';
  // Extract agent info from message extras or reasoning
  const { agentInfo, agentType } = useMemo(() => {
    // Check for agent handoff in reasoning trace
    const lastHandoff = message.reasoning?.handoffs?.[message.reasoning.handoffs.length - 1];
    const type = lastHandoff?.to || message.extras?.agent || 'generalist';
    const info = AGENT_CONFIG[type as keyof typeof AGENT_CONFIG] || AGENT_CONFIG.generalist;
    return { agentInfo: info, agentType: type };
  }, [message]);

  // Determine the current active tool for loader context
  const activeTool = useMemo(() => {
    if (!message.toolEvents || message.toolEvents.length === 0) return undefined;
    // Find the last tool event
    const lastEvent = message.toolEvents[message.toolEvents.length - 1];

    // Only show interesting statuses
    if (lastEvent.status === 'completed' || lastEvent.status === 'failed') return undefined;

    return {
      name: lastEvent.toolName || 'Tool',
      status: lastEvent.status,
      type: lastEvent.toolType,
    };
  }, [message.toolEvents]);

  // Calculate confidence score (mock for now, should come from backend)
  const confidenceScore = useMemo(() => {
    if (message.extras?.confidence) return message.extras.confidence as number;
    // Mock calculation based on sources and content length
    const baseScore = 0.75;
    const sourceBonus = message.sources ? Math.min(message.sources.length * 0.05, 0.15) : 0;
    const contentBonus = message.content ? Math.min(message.content.length / 5000, 0.1) : 0;
    return Math.min(baseScore + sourceBonus + contentBonus, 1);
  }, [message]);

  // Extract key metrics for inline display
  const inlineMetrics = useMemo(() => {
    if (!message.extras?.metrics) return null;
    const metrics = message.extras.metrics as any;
    return {
      var95: metrics.var_95,
      sharpe: metrics.sharpe_ratio,
      volatility: metrics.volatility,
    };
  }, [message]);

  // Load available export styles when auth is ready
  useEffect(() => {
    if (!isLoaded) return;
    const loadStyles = async () => {
      try {
        const token = await getToken();
        const response = await fetch(`${API_BASE}/api/user-settings/export-styles`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await response.json();
        setAvailableStyles(data.styles || []);
        // Set default style as selected, or first available if no default
        const defaultStyle = data.styles?.find((s: any) => s.is_default);
        if (defaultStyle) {
          setSelectedStyleName(defaultStyle.style_name);
        } else if (data.styles && data.styles.length > 0) {
          setSelectedStyleName(data.styles[0].style_name);
        }
      } catch (error) {
        console.error('Failed to load export styles:', error);
      }
    };
    loadStyles();
  }, [isLoaded]);

  // Close style selector when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (styleSelectorRef.current && !styleSelectorRef.current.contains(event.target as Node)) {
        setShowStyleSelector(false);
      }
    };

    if (showStyleSelector) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showStyleSelector]);

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="intelligence-card user-card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          padding: '12px 16px',
          borderRadius: '12px',
          background: '#F8F8F8',
          border: '1px solid #E1DFDD',
        }}
      >
        <div className="flex items-center gap-2">
          {user?.imageUrl ? (
            <img
              src={user.imageUrl}
              alt={user.fullName || 'User'}
              className="user-avatar"
              style={{
                width: '30px',
                height: '30px',
                borderRadius: '50%',
                objectFit: 'cover',
                flexShrink: 0,
              }}
            />
          ) : (
            <div
              className="user-avatar"
              style={{
                width: '30px',
                height: '30px',
                borderRadius: '50%',
                background: 'color-mix(in oklab, var(--bg-subtle), white 6%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--text-secondary)' }}>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
          )}
          <span style={{ fontSize: 'var(--fs-12)', color: 'var(--text-muted)', fontWeight: 'var(--fw-medium)' }}>You</span>
          <span style={{ fontSize: 'var(--fs-11)', color: 'var(--text-muted)' }}>
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <div style={{
          color: 'var(--text-primary)',
          fontSize: '16px',
          lineHeight: '1.75',
          paddingLeft: '32px',
          fontFamily: 'var(--font-sans)',
          wordWrap: 'break-word',
          overflowWrap: 'break-word',
          whiteSpace: 'pre-wrap',
        }}>
          {/* Strip /search prefix and citation blocks from displayed content */}
          {(() => {
            let content = message.content || '';
            // Strip /search prefix
            if (content.startsWith('/search ')) {
              content = content.slice(8);
            }
            // Strip citation blocks: <!-- CITATION:...:... -->...<!-- /CITATION -->
            content = content.replace(/\n*<!-- CITATION:[^>]*-->[\s\S]*?<!-- \/CITATION -->/g, '').trim();
            return content;
          })()}
        </div>
        {/* Display portfolio and attached files for user message */}
        {(message.portfolio || (message.attachments && message.attachments.length > 0)) && (
          <div style={{
            marginTop: '8px',
            paddingLeft: '32px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '6px',
          }}>
            {/* Portfolio pill */}
            {message.portfolio && (
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                background: '#FFFFFF',
                border: '1px solid #E1DFDD',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#605E5C',
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                <span>
                  {message.portfolio.tickers.slice(0, 3).join(', ')}
                  {message.portfolio.tickers.length > 3 && ` +${message.portfolio.tickers.length - 3}`}
                </span>
              </div>
            )}

            {/* File attachments */}
            {message.attachments && message.attachments.map((file, idx) => (
              <div key={idx} style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                background: '#FFFFFF',
                border: '1px solid #E1DFDD',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#605E5C',
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.828a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                <span>{file.original_name}</span>
                <span style={{ color: '#8B8A89' }}>
                  ({(file.size / 1024).toFixed(1)} KB)
                </span>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    );
  }


  // Assistant intelligence card - No box, just content on background
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="intelligence-card assistant-card"
      style={{
        // No background, border, or shadow - content sits directly on page
        padding: '16px 0',
      }}
    >
      {/* Card Header - No background or borders */}
      <div
        className="card-header"
        style={{
          padding: '0 0 12px 0',
          marginBottom: '8px',
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>

            {/* Confidence Score - Only show if low confidence */}
            {confidenceScore > 0 && confidenceScore < 0.75 && (
              <div
                className="confidence-score"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: 'var(--fs-11)',
                  color: 'var(--text-muted)',
                  opacity: 0.8,
                }}
              >
                <span
                  style={{
                    color: confidenceScore > 0.6
                      ? 'var(--warning)'
                      : 'var(--danger)',
                    fontWeight: 'var(--fw-medium)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  Low confidence ({Math.round(confidenceScore * 100)}%)
                </span>
              </div>
            )}

            {/* Handoff Indicator */}
            {message.reasoning?.handoffs && message.reasoning.handoffs.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="handoff-indicator"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: 'var(--fs-11)',
                  color: 'var(--warning)',
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                </svg>
                <span>Handoff from {message.reasoning.handoffs[0].from}</span>
              </motion.div>
            )}
          </div>

        </div>

        {/* Inline Metrics - Simplified */}
        {inlineMetrics && (
          <div
            className="inline-metrics"
            style={{
              marginTop: '8px',
              display: 'flex',
              gap: '8px',
              flexWrap: 'wrap',
            }}
          >
            {Object.entries(inlineMetrics).filter(([_, value]) => value !== undefined).map(([key, value]) => (
              <div
                key={key}
                className="metric-pill"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: 'var(--fs-11)',
                  marginRight: '12px',
                }}
              >
                <span style={{ color: 'var(--text-muted)' }}>
                  {key === 'var95' ? 'VaR 95%' : key === 'sharpe' ? 'Sharpe' : 'Vol'}:
                </span>
                <span style={{
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 'var(--fw-medium)',
                }}>
                  {typeof value === 'number' ? value.toFixed(2) : value}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Card Body - No padding since no box */}
      <div className="card-body">
        {message.isStreaming ? (
          <div>
            {/* Content area */}
            {!message.content ? (
              <>
                <IntelligenceLoader
                  text={message.extras?.statusMessage as string | undefined}
                  agent={agentType}
                  currentTool={activeTool}
                />
                {/* Pills under loader, before content */}
                <StreamingProgress
                  toolEvents={message.toolEvents}
                  reasoningStreaming={message.reasoningStreaming ?? ((message.reasoningStream?.length ?? 0) > 0)}
                  reasoningText={
                    message.reasoningText ??
                    (message.reasoningStream && message.reasoningStream.length > 0
                      ? message.reasoningStream.join('')
                      : '')
                  }
                  isComplete={!message.isStreaming}
                />
              </>
            ) : (
              <>
                {/* Pills above content */}
                <StreamingProgress
                  toolEvents={message.toolEvents}
                  reasoningStreaming={message.reasoningStreaming ?? ((message.reasoningStream?.length ?? 0) > 0)}
                  reasoningText={
                    message.reasoningText ??
                    (message.reasoningStream && message.reasoningStream.length > 0
                      ? message.reasoningStream.join('')
                      : '')
                  }
                  isComplete={!message.isStreaming}
                />
                <WorkingContentRenderer content={message.content} />
                <IntelligenceLoader
                  text={(message.extras?.statusMessage as string | undefined) ?? (activeTool ? undefined : 'Analyzing data')}
                  compact={true}
                  updatesReceived={message.sources?.length || 0}
                  currentTool={activeTool}
                />
              </>
            )}
          </div>
        ) : (
          <>
            {/* Tab Navigation - Only show if we have additional content */}
            {message.sources && message.sources.length > 3 && (
              <div className="mb-3">
                <SegmentedTabs
                  items={[
                    { id: 'response', label: 'Response' },
                    {
                      id: 'sources',
                      label: `Sources (${message.sources.length})`,
                    },
                  ]}
                  activeId={activeTab}
                  onChange={setActiveTab as any}
                />
              </div>
            )}

            {/* Tab Content */}
            <AnimatePresence mode="wait">
              {activeTab === 'response' ? (
                <motion.div
                  key="response"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="response-content"
                >
                  {/* Always show the agent's explanatory text */}
                  <div ref={messageContentRef}>
                    <WorkingContentRenderer
                      content={message.content}
                      onLocalFileLinkClick={(filename) => {
                        // If the agent mentions a local file link (e.g., sandbox:/mnt/data/foo.png),
                        // try to download it using the discovered container/files from extras.
                        try {
                          const extras = message.extras as any;
                          const containerId = extras?.container_id as string | undefined;
                          const files = (extras?.generated_files as any[]) || [];
                          const matched = files.find((f) => f?.filename === filename);
                          if (!containerId || !matched?.file_id) return;
                          const sessionId = localStorage.getItem('session_id') || undefined;
                          const buildQuery = () => {
                            const params = new URLSearchParams({ filename });
                            if (sessionId) params.set('session_id', sessionId);
                            return params.toString();
                          };
                          // Defer actual download to avoid router interceptors
                          queueMicrotask(async () => {
                            try {
                              const token = await getToken();
                              const q = buildQuery();
                              const res = await fetch(`/v6/containers/${containerId}/files/${matched.file_id}?${q}`, {
                                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
                              });
                              if (!res.ok) return;
                              const blob = await res.blob();
                              const { saveAs } = await import('file-saver');
                              saveAs(blob, filename);
                            } catch (authError) {
                              console.log('Auth failed, trying without token:', authError);
                              // Try without auth as fallback
                              const q = buildQuery();
                              const res = await fetch(`/v6/containers/${containerId}/files/${matched.file_id}?${q}`);
                              if (!res.ok) return;
                              const blob = await res.blob();
                              const { saveAs } = await import('file-saver');
                              saveAs(blob, filename);
                            }
                          });
                        } catch (error) {
                          console.error('File download failed:', error);
                        }
                      }}
                    />
                  </div>

                  {/* Code Execution Display - Show if we have code execution data */}
                  {message.extras?.container_id && (
                    <div style={{ marginTop: '16px' }}>
                      <CodeExecutionDisplay
                        codeBlocks={(message.extras?.code_blocks as any[]) || []}
                        generatedFiles={(message.extras?.generated_files as any[]) || []}
                        containerId={message.extras?.container_id as string}
                      />
                    </div>
                  )}

                  {/* Charts */}
                  {message.charts && message.charts.length > 0 && (
                    <div className="charts-container" style={{ marginTop: '16px', gap: '16px' }}>
                      {message.charts.map((chart) => (
                        <PlotlyChart key={chart.id} chart={chart} />
                      ))}
                    </div>
                  )}

                  {/* Source Pills - Compact inline display */}
                  {message.sources && message.sources.length > 0 && (
                    <div className="sources-inline" style={{
                      marginTop: '12px',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px',
                    }}>
                      {message.sources.slice(0, 3).map((source, idx) => (
                        <SourcePill key={source.id} source={source} index={idx} />
                      ))}
                      {message.sources.length > 3 && (
                        <span style={{
                          fontSize: 'var(--fs-11)',
                          color: 'var(--text-muted)',
                          fontStyle: 'italic',
                        }}>
                          +{message.sources.length - 3} more
                        </span>
                      )}
                    </div>
                  )}
                </motion.div>
              ) : activeTab === 'sources' ? (
                <motion.div
                  key="sources"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="sources-content"
                >
                  <div className="flex items-center gap-2 mb-4" style={{ color: '#323130', fontSize: '14px', fontWeight: '600' }}>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    Sources
                  </div>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                      gap: '12px',
                    }}
                  >
                    {message.sources?.map((source) => {
                      const domain = new URL(source.url).hostname.replace('www.', '');
                      const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;

                      return (
                        <a
                          key={source.id}
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="block p-3 rounded-lg transition-all"
                          style={{
                            background: '#FFFFFF',
                            border: '1px solid #E1E1E1',
                            textDecoration: 'none',
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
                            e.currentTarget.style.borderColor = '#0078D4';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.boxShadow = 'none';
                            e.currentTarget.style.borderColor = '#E1E1E1';
                          }}
                        >
                          <div
                            style={{
                              fontSize: '13px',
                              fontWeight: '500',
                              color: '#323130',
                              marginBottom: '8px',
                              lineHeight: '1.4',
                              height: '38px',
                              overflow: 'hidden',
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                            }}
                            title={source.title}
                          >
                            {source.title}
                          </div>
                          <div className="flex items-center gap-2" style={{ marginTop: 'auto' }}>
                            <img
                              src={faviconUrl}
                              alt=""
                              style={{
                                width: '16px',
                                height: '16px',
                                borderRadius: '2px',
                              }}
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                              }}
                            />
                            <span
                              style={{
                                fontSize: '11px',
                                color: '#605E5C',
                              }}
                            >
                              {domain}
                            </span>
                          </div>
                        </a>
                      );
                    })}
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="metrics"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="metrics-content"
                >
                  {/* Metrics display would go here */}
                  <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-13)' }}>
                    Detailed metrics visualization coming soon...
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}

        {/* Error State */}
        {message.error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="error-message"
            style={{
              marginTop: '12px',
              padding: '8px 0',
              color: 'var(--danger)',
              fontSize: 'var(--fs-13)',
              borderLeft: '3px solid var(--danger)',
              paddingLeft: '12px',
            }}
          >
            {message.error}
          </motion.div>
        )}

        {/* Export buttons below content */}
        <div className="flex items-center gap-2" style={{ marginTop: '16px' }}>
          {/* Copy */}
          <button
            onClick={async () => {
              if (messageContentRef.current) {
                const success = await copyMessageContent(messageContentRef.current);
                if (success) {
                  setCopyFeedback(true);
                  setTimeout(() => setCopyFeedback(false), 2000);
                }
              }
            }}
            className="export-icon-button"
            title="Copy message"
            style={{
              padding: '5px',
              background: 'transparent',
              border: '1px solid #0051cc',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s ease',
              borderRadius: '4px',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(0, 81, 204, 0.08)';
              e.currentTarget.style.transform = 'scale(1.05)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            {copyFeedback ? (
              <Check size={14} color="#10B981" strokeWidth={2.5} />
            ) : (
              <Copy size={14} color="#0051cc" strokeWidth={2} />
            )}
          </button>

          {/* PDF */}
          <button
            onClick={async () => {
              if (exportingPdf) return;

              try {
                setExportingPdf(true);
                const { chatAPI } = await import('@services/api');
                const payload = {
                  mode: 'chat',
                  content: message.content,
                  metadata: {
                    sources: message.sources || [],
                    charts: message.charts || [],
                    extras: message.extras || {},
                  },
                };
                // Use Gamma PDF (with fallback to free PDF if Gamma unavailable)
                console.log('Starting Gamma PDF export with style:', selectedStyleName);
                console.log('Available styles:', availableStyles);
                const blob = await chatAPI.exportPdf(payload, 'gamma_pdf', selectedStyleName || undefined);
                console.log('Gamma PDF export successful, downloading...');

                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `analysis_${new Date().toISOString().split('T')[0]}.pdf`;
                a.click();
                URL.revokeObjectURL(url);
              } catch (error) {
                console.error('Gamma PDF export failed:', error);
                alert('Export failed. This may be due to a timeout. Please try again or use the Export Modal for more options.');
              } finally {
                setExportingPdf(false);
              }
            }}
            className="export-icon-button"
            title={exportingPdf ? 'Generating institutional PDF... This may take 2-3 minutes' : 'Export as Gamma Document PDF (institutional format)'}
            disabled={exportingPdf}
            style={{
              padding: '5px',
              background: 'transparent',
              border: '1px solid #0051cc',
              cursor: exportingPdf ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s ease',
              borderRadius: '4px',
              opacity: exportingPdf ? 0.6 : 1,
            }}
            onMouseEnter={(e) => {
              if (!exportingPdf) {
                e.currentTarget.style.background = 'rgba(0, 81, 204, 0.08)';
                e.currentTarget.style.transform = 'scale(1.05)';
              }
            }}
            onMouseLeave={(e) => {
              if (!exportingPdf) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.transform = 'scale(1)';
              }
            }}
          >
            {exportingPdf ? (
              <Loader2 size={14} color="#0051cc" strokeWidth={2.5} className="animate-spin" />
            ) : (
              <FileText size={14} color="#0051cc" strokeWidth={2} />
            )}
          </button>

          {/* PowerPoint */}
          <button
            onClick={async () => {
              if (exportingPpt) return;

              try {
                setExportingPpt(true);
                const { chatAPI } = await import('@services/api');
                const payload = {
                  mode: 'chat',
                  content: message.content,
                  metadata: {
                    sources: message.sources || [],
                    charts: message.charts || [],
                    extras: message.extras || {},
                  },
                };
                // Use Gamma PPTX (with fallback to free PDF if Gamma unavailable)
                const blob = await chatAPI.exportPowerpoint(payload, 'gamma_pptx', selectedStyleName || undefined);

                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `presentation_${new Date().toISOString().split('T')[0]}.pptx`;
                a.click();
                URL.revokeObjectURL(url);
              } catch (error) {
                console.error('PowerPoint export failed:', error);
              } finally {
                setExportingPpt(false);
              }
            }}
            className="export-icon-button"
            title={exportingPpt ? 'Generating presentation...' : 'Export as Gamma PowerPoint (PPTX)'}
            disabled={exportingPpt}
            style={{
              padding: '5px',
              background: 'transparent',
              border: '1px solid #0051cc',
              cursor: exportingPpt ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s ease',
              borderRadius: '4px',
              opacity: exportingPpt ? 0.6 : 1,
            }}
            onMouseEnter={(e) => {
              if (!exportingPpt) {
                e.currentTarget.style.background = 'rgba(0, 81, 204, 0.08)';
                e.currentTarget.style.transform = 'scale(1.05)';
              }
            }}
            onMouseLeave={(e) => {
              if (!exportingPpt) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.transform = 'scale(1)';
              }
            }}
          >
            {exportingPpt ? (
              <Loader2 size={14} color="#0051cc" strokeWidth={2.5} className="animate-spin" />
            ) : (
              <Presentation size={14} color="#0051cc" strokeWidth={2} />
            )}
          </button>

          {/* Workbook Export */}
          <button
            onClick={async () => {
              if (exportingWorkbook) return;

              try {
                setExportingWorkbook(true);
                const { chatAPI } = await import('@services/api');

                const payload = {
                  message_id: message.id,
                  content: message.content,
                  metadata: {
                    extras: message.extras || {},
                  },
                };

                const blob = await chatAPI.exportWorkbook(payload);
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `workbooks_${message.id.substring(0, 8)}_${new Date().toISOString().split('T')[0]}.zip`;
                a.click();
                URL.revokeObjectURL(url);
              } catch (error) {
                console.error('Workbook export failed:', error);
                alert('Failed to generate workbook. Please try again.');
              } finally {
                setExportingWorkbook(false);
              }
            }}
            className="export-icon-button"
            title={exportingWorkbook ? 'Generating workbooks... (~30-60 seconds)' : 'Export as Excel/CSV'}
            disabled={exportingWorkbook}
            style={{
              padding: '5px',
              background: 'transparent',
              border: '1px solid #0051cc',
              cursor: exportingWorkbook ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s ease',
              borderRadius: '4px',
              opacity: exportingWorkbook ? 0.6 : 1,
            }}
            onMouseEnter={(e) => {
              if (!exportingWorkbook) {
                e.currentTarget.style.background = 'rgba(0, 81, 204, 0.08)';
                e.currentTarget.style.transform = 'scale(1.05)';
              }
            }}
            onMouseLeave={(e) => {
              if (!exportingWorkbook) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.transform = 'scale(1)';
              }
            }}
          >
            {exportingWorkbook ? (
              <Loader2 size={14} color="#0051cc" strokeWidth={2.5} className="animate-spin" />
            ) : (
              <Sheet size={14} color="#0051cc" strokeWidth={2} />
            )}
          </button>

          {/* Export Style Selector */}
          <div ref={styleSelectorRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setShowStyleSelector(!showStyleSelector)}
              className="export-icon-button"
              title={selectedStyleName ? `Current style: ${selectedStyleName}` : 'Select export style'}
              style={{
                padding: '5px',
                background: selectedStyleName ? 'rgba(0, 81, 204, 0.08)' : 'transparent',
                border: selectedStyleName ? '1px solid #10B981' : '1px solid #0051cc',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease',
                borderRadius: '4px',
                position: 'relative',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(0, 81, 204, 0.08)';
                e.currentTarget.style.transform = 'scale(1.05)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = selectedStyleName ? 'rgba(0, 81, 204, 0.08)' : 'transparent';
                e.currentTarget.style.transform = 'scale(1)';
              }}
            >
              <Pencil size={14} color="#0051cc" strokeWidth={2} />
              {/* Active indicator dot */}
              {selectedStyleName && (
                <div style={{
                  position: 'absolute',
                  top: '2px',
                  right: '2px',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: '#10B981',
                  border: '1px solid white',
                }}/>
              )}
            </button>

            {/* Style Selector Dropdown */}
            {showStyleSelector && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 'calc(100% + 4px)',
                  background: 'white',
                  border: '1px solid #E1DFDD',
                  borderRadius: '8px',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                  minWidth: '220px',
                  maxWidth: '320px',
                  zIndex: 1000,
                  padding: '8px',
                }}
              >
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#666', padding: '8px', borderBottom: '1px solid #E1DFDD' }}>
                  Select Export Style
                </div>
                {availableStyles.length > 0 ? (
                  availableStyles.map((style) => (
                    <button
                      key={style.style_name}
                      onClick={() => {
                        console.log('STYLE SELECTED:', style.style_name);
                        setSelectedStyleName(style.style_name);
                        setShowStyleSelector(false);
                        console.log('Selected style state updated to:', style.style_name);
                      }}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        textAlign: 'left',
                        background: selectedStyleName === style.style_name ? 'rgba(0, 81, 204, 0.08)' : 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        borderRadius: '4px',
                        fontSize: '13px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        transition: 'background 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (selectedStyleName !== style.style_name) {
                          e.currentTarget.style.background = 'rgba(0, 81, 204, 0.04)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (selectedStyleName !== style.style_name) {
                          e.currentTarget.style.background = 'transparent';
                        }
                      }}
                    >
                      {/* Organization/User Logo */}
                      <div style={{ width: '18px', height: '18px', flexShrink: 0 }}>
                        {organization?.imageUrl ? (
                          <img
                            src={organization.imageUrl}
                            alt={organization.name}
                            style={{
                              width: '18px',
                              height: '18px',
                              borderRadius: '3px',
                              objectFit: 'cover',
                              border: '1px solid #E1DFDD',
                            }}
                          />
                        ) : user?.imageUrl ? (
                          <img
                            src={user.imageUrl}
                            alt={user.fullName || 'User'}
                            style={{
                              width: '18px',
                              height: '18px',
                              borderRadius: '50%',
                              objectFit: 'cover',
                              border: '1px solid #E1DFDD',
                            }}
                          />
                        ) : (
                          <FileText size={18} color="#6B7280" strokeWidth={2} />
                        )}
                      </div>

                      {/* Style name */}
                      <span style={{ flex: 1 }}>{style.style_name}</span>

                      {/* Default badge */}
                      {style.is_default && (
                        <span style={{ fontSize: '10px', color: '#0051cc', fontWeight: 600, flexShrink: 0 }}>DEFAULT</span>
                      )}

                      {/* Checkmark for selected style */}
                      {selectedStyleName === style.style_name && (
                        <CheckCircle2 size={16} color="#10B981" strokeWidth={2.5} style={{ flexShrink: 0 }} />
                      )}
                    </button>
                  ))
                ) : (
                  <div style={{
                    padding: '16px',
                    textAlign: 'center',
                    fontSize: '12px',
                    color: '#666',
                  }}>
                    <div style={{ marginBottom: '8px' }}>No export styles configured</div>
                    <a
                      href="/settings"
                      onClick={() => setShowStyleSelector(false)}
                      style={{
                        color: '#0051cc',
                        textDecoration: 'none',
                        fontWeight: 600,
                      }}
                    >
                      Create one in Settings →
                    </a>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Reasoning Drawer */}
      {message.reasoning && showTrace && (
        <TraceDrawer trace={message.reasoning} onClose={() => setShowTrace(false)} />
      )}

      {/* Minimal Animation Styles */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        .action-button:hover {
          background: rgba(0, 0, 0, 0.05) !important;
        }

        .markdown-link:hover {
          border-bottom-color: var(--accent) !important;
        }

        .source-card:hover {
          background: rgba(0, 0, 0, 0.02) !important;
        }
      `}</style>
    </motion.div>
  );
});

IntelligenceCard.displayName = 'IntelligenceCard';

export default IntelligenceCard;
