import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Library, ChevronRight, Sparkles, Zap, TrendingUp, FileText, BarChart3, LineChart, Code, Calculator, Bitcoin, Scale, Brain, TrendingDown, Target } from 'lucide-react';

interface AgentPrompt {
  id: string;
  name: string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; style?: React.CSSProperties }>;
  color: string;
  prompts: string[];
  comingSoon?: boolean;
}

const agentPrompts: AgentPrompt[] = [
  {
    id: 'generalist',
    name: 'Agentic Search',
    icon: Sparkles,
    color: '#3b82f6',
    prompts: [
      'What are the latest market trends for tech stocks?',
      'Analyze the performance of my portfolio over the last quarter',
      'Get me the earnings calendar for next week',
      'What are the key economic indicators I should watch?',
      'Compare the sector allocations in my portfolio',
    ],
  },
  {
    id: 'risk',
    name: 'Risk Analysis',
    icon: Zap,
    color: '#ef4444',
    prompts: [
      'Calculate VaR and CVaR for my portfolio using Monte Carlo simulation with 10,000 paths',
      'Perform Barra factor decomposition and identify systematic risk exposures in my holdings',
      'Build an optimal hedge portfolio to achieve market neutrality while preserving alpha',
      'Run a stress test on my portfolio with a 30% market downturn scenario',
      'Optimize my portfolio for maximum Sharpe ratio with a 15% volatility constraint',
    ],
  },
  {
    id: 'document',
    name: 'Filing Search',
    icon: FileText,
    color: '#f59e0b',
    prompts: [
      'Analyze the latest 10-K filing for Apple and extract key financial metrics',
      'Summarize the risk factors from Tesla\'s most recent 10-Q',
      'Compare management discussion sections across the last 3 earnings calls',
      'Extract guidance and forward-looking statements from recent earnings transcripts',
      'Analyze SEC filings for insider trading activity and significant events',
    ],
  },
  {
    id: 'comparable',
    name: 'Comparable Companies',
    icon: BarChart3,
    color: '#8b5cf6',
    prompts: [
      'Run comparative valuation analysis against sector peers using EV/EBITDA and P/E multiples',
      'Find comparable companies for AAPL and analyze their trading multiples',
      'Compare Microsoft to its peers using valuation metrics',
      'Identify undervalued stocks in the technology sector based on peer analysis',
      'Analyze Tesla against automotive and tech sector comparables',
    ],
  },
  {
    id: 'chart',
    name: 'Chart Analysis',
    icon: LineChart,
    color: '#06b6d4',
    prompts: [
      'Analyze this chart and identify key support and resistance levels',
      'What technical patterns do you see in this chart? Provide entry and exit points',
      'Analyze the trend, volume, and momentum indicators visible in this chart',
      'Identify chart patterns like head and shoulders, double tops, triangles, or flags',
      'What does this chart suggest about future price movement? Bull or bear case?',
    ],
  },
  {
    id: 'quant',
    name: 'Quantitative Coding',
    icon: Code,
    color: '#ec4899',
    prompts: [
      'Calculate rolling Sharpe ratios for my portfolio over the last 2 years',
      'Build a mean-reversion strategy and backtest it on SPY',
      'Create a custom indicator combining RSI and Bollinger Bands',
      'Run statistical arbitrage analysis on pair trades',
      'Calculate beta-adjusted returns for all positions in my portfolio',
    ],
  },
  {
    id: 'dcf',
    name: 'DCF Valuation',
    icon: Calculator,
    color: '#059669',
    prompts: [
      'Build a DCF model for Apple with 5-year projections',
      'Calculate intrinsic value for MSFT using discounted cash flow analysis',
      'Perform sensitivity analysis on WACC and terminal growth rate assumptions',
      'Compare DCF valuation to current market price for GOOGL',
      'Build a sum-of-the-parts valuation for a diversified company',
    ],
  },
  {
    id: 'alternatives',
    name: 'Alternatives Data',
    icon: Bitcoin,
    color: '#f59e0b',
    prompts: [
      'Analyze Bitcoin price trends and key support/resistance levels',
      'Compare cryptocurrency market cap trends across major coins',
      'What are the correlations between crypto markets and traditional equities?',
      'Analyze gold and crude oil price movements in current macro environment',
      'Track major forex pair trends and central bank policy impacts',
    ],
  },
  {
    id: 'institutional',
    name: 'Institutional Activity',
    icon: Scale,
    color: '#8b5cf6',
    prompts: [
      'Show me the latest 13F filings from major hedge funds',
      'What stocks are seeing the most insider buying recently?',
      'Analyze congressional trading activity in tech stocks',
      'Track institutional ownership changes in my portfolio holdings',
      'Identify stocks with unusual ETF flow activity',
    ],
  },
  {
    id: 'options',
    name: 'Options Analytics',
    icon: TrendingDown,
    color: '#f97316',
    prompts: [
      'Discover the most active options chains on SPY and compare IV percentiles',
      'Build a call spread on NVDA with target payoff and show scenario table',
      'Analyze the implied volatility smile for TSLA around next earnings date',
      'Generate payoff diagrams for an iron condor on QQQ with 1% wings',
      'Compare realized vs implied volatility for MSFT and recommend hedges',
    ],
  },
  {
    id: 'prediction_markets',
    name: 'Prediction Markets',
    icon: Target,
    color: '#06b6d4',
    prompts: [
      'What are the current odds on Polymarket for major economic events?',
      'Analyze prediction market trends for upcoming elections',
      'Compare forecast accuracy between Polymarket, Kalshi, and PredictIt',
      'Track sentiment shifts in prediction markets for crypto regulation',
      'Identify arbitrage opportunities across different prediction platforms',
    ],
  },
];

interface PromptLibraryProps {
  onPromptSelect: (prompt: string) => void;
}

const PromptLibrary = ({ onPromptSelect }: PromptLibraryProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const portalRef = useRef<HTMLDivElement>(null);
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const agentRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});
  const isClickingRef = useRef<boolean>(false);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const isInsideDropdown = dropdownRef.current?.contains(target);
      const isInsidePortal = portalRef.current?.contains(target);

      if (!isInsideDropdown && !isInsidePortal) {
        setIsOpen(false);
        setHoveredAgent(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handlePromptClick = (prompt: string) => {
    onPromptSelect(prompt);

    // Small delay to allow the input area to update before closing menus
    setTimeout(() => {
      setIsOpen(false);
      setHoveredAgent(null);
      setMenuPosition(null);
    }, 50);
  };

  const handleAgentHover = (agentId: string) => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    setHoveredAgent(agentId);

    // Calculate position for the prompt menu
    const agentElement = agentRefs.current[agentId];
    if (agentElement) {
      const rect = agentElement.getBoundingClientRect();
      const position = {
        top: rect.top,
        left: rect.right + 4,
      };
      setMenuPosition(position);
    }
  };

  const handleAgentLeave = () => {
    if (isClickingRef.current) {
      return;
    }
    hoverTimeoutRef.current = setTimeout(() => {
      setHoveredAgent(null);
      setMenuPosition(null);
    }, 500); // Increased from 100ms to 500ms to allow click to complete
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 transition-all duration-200"
        style={{
          padding: '6px 12px',
          background: isOpen ? '#F5F5F5' : 'transparent',
          border: '1px solid #E5E5E5',
          borderRadius: '6px',
          cursor: 'pointer',
          color: '#323130',
          fontSize: '14px',
          fontWeight: '500',
        }}
        onMouseEnter={(e) => {
          if (!isOpen) {
            e.currentTarget.style.background = '#FAFAFA';
            e.currentTarget.style.borderColor = '#D1D1D1';
          }
        }}
        onMouseLeave={(e) => {
          if (!isOpen) {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.borderColor = '#E5E5E5';
          }
        }}
      >
        <Library size={16} strokeWidth={2} />
        Prompt Library
      </button>

      {isOpen && (
        <div
          className="absolute left-0 mt-2 z-50"
          style={{
            width: 'min(280px, 90vw)',
            background: '#FFFFFF',
            border: '1px solid #E1DFDD',
            borderRadius: '12px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
            maxHeight: '500px',
            overflow: 'visible',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '10px 14px',
              borderBottom: '1px solid #E1DFDD',
              fontSize: '13px',
              fontWeight: '600',
              color: '#323130',
            }}
          >
            Prompt Library
          </div>

          <div style={{ padding: '8px', maxHeight: '450px', overflowY: 'auto' }}>
            {/* Agent List */}
            <div>
              {agentPrompts.map((agent) => (
                <div
                  key={agent.id}
                  ref={(el) => {
                    agentRefs.current[agent.id] = el;
                  }}
                  onMouseEnter={() => !agent.comingSoon && handleAgentHover(agent.id)}
                  onMouseLeave={handleAgentLeave}
                  style={{ cursor: agent.comingSoon ? 'not-allowed' : 'pointer' }}
                >
                  {/* Agent Header */}
                  <div
                    className="w-full text-left transition-all duration-200"
                    style={{
                      padding: '8px 10px',
                      background: hoveredAgent === agent.id ? '#FAFAFA' : 'transparent',
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '4px',
                      opacity: agent.comingSoon ? 0.5 : 1,
                    }}
                  >
                    <div className="flex items-center gap-2" style={{ flex: 1 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: '28px',
                          height: '28px',
                          borderRadius: '6px',
                          background: `${agent.color}15`,
                          color: agent.color,
                        }}
                      >
                        <agent.icon size={16} strokeWidth={2} style={{ color: agent.color }} />
                      </div>
                      <span
                        style={{
                          fontSize: '13px',
                          fontWeight: '600',
                          color: '#1A1A1A',
                        }}
                      >
                        {agent.name}
                      </span>
                      {agent.comingSoon && (
                        <div
                          style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            background: '#EF4444',
                            marginLeft: '6px',
                          }}
                        />
                      )}
                    </div>
                    {!agent.comingSoon && (
                      <ChevronRight
                        size={16}
                        style={{
                          color: '#666',
                        }}
                      />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Prompt Menu Portal - Renders outside dropdown to escape clipping */}
      {hoveredAgent && menuPosition && !agentPrompts.find((a) => a.id === hoveredAgent)?.comingSoon &&
        createPortal(
          <div
            ref={portalRef}
            onMouseEnter={() => {
              if (hoverTimeoutRef.current) {
                clearTimeout(hoverTimeoutRef.current);
                hoverTimeoutRef.current = null;
              }
            }}
            onMouseLeave={() => {
              handleAgentLeave();
            }}
            onMouseDown={() => {
              isClickingRef.current = true;
              // Cancel any pending close timeout when clicking
              if (hoverTimeoutRef.current) {
                clearTimeout(hoverTimeoutRef.current);
                hoverTimeoutRef.current = null;
              }
            }}
            onMouseUp={() => {
              setTimeout(() => {
                isClickingRef.current = false;
              }, 100);
            }}
            style={{
              position: 'fixed',
              top: `${menuPosition.top}px`,
              left: `max(16px, min(${menuPosition.left}px, calc(100vw - min(440px, calc(100vw - 32px)) - 16px)))`,
              width: 'min(440px, calc(100vw - 32px))',
              background: '#FFFFFF',
              border: '1px solid #E5E5E5',
              borderRadius: '8px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              padding: '8px',
              zIndex: 10000,
            }}
          >
            {(() => {
              const agent = agentPrompts.find((a) => a.id === hoveredAgent);
              const prompts = agent?.prompts || [];
              console.log('[PromptLibrary] Rendering', prompts.length, 'buttons for agent:', hoveredAgent);
              return prompts.map((prompt, index) => {
                console.log('[PromptLibrary] Creating button', index, 'for prompt:', prompt.substring(0, 50) + '...');
                return (
                  <button
                    key={index}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      console.log('[PromptLibrary] Button clicked! Prompt:', prompt);
                      handlePromptClick(prompt);
                    }}
                    onMouseDown={(e) => {
                      console.log('[PromptLibrary] Button mouseDown! Prompt:', prompt.substring(0, 30));
                    }}
                    type="button"
                    className="w-full text-left transition-all duration-200"
                    style={{
                      padding: '10px 12px',
                      background: 'transparent',
                      border: '1px solid #E5E5E5',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      marginTop: index === 0 ? '0' : '6px',
                      fontSize: '13px',
                      color: '#323130',
                      lineHeight: '1.5',
                      pointerEvents: 'auto',
                    }}
                    onMouseEnter={(e) => {
                      console.log('[PromptLibrary] Button hover:', index);
                      e.currentTarget.style.background = `${agent!.color}08`;
                      e.currentTarget.style.borderColor = agent!.color;
                      e.currentTarget.style.transform = 'translateX(4px)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                      e.currentTarget.style.borderColor = '#E5E5E5';
                      e.currentTarget.style.transform = 'translateX(0)';
                    }}
                  >
                    {prompt}
                  </button>
                );
              });
            })()}
          </div>,
          document.body,
        )}
    </div>
  );
};

export default PromptLibrary;
