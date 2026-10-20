import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Zap, Search, TrendingUp, FileText, Brain, BarChart3, LineChart, Code, Calculator, Bitcoin, Scale, Sparkles, TrendingDown, Target, Briefcase, Layers } from 'lucide-react';
import type { AgentMode } from '@/types';

interface AgentModeSelectorProps {
  mode: AgentMode;
  onModeChange: (mode: AgentMode) => void;
  disabled?: boolean;
  direction?: 'up' | 'down';
}

const agentModes = [
  {
    id: 'auto' as AgentMode,
    name: 'Auto',
    shortName: 'Auto',
    description: 'System intelligently routes to appropriate agent',
    icon: Brain,
    color: '#111827',
    badge: 'Default',
    dataTypes: 'All data sources',
  },
  {
    id: 'generalist' as AgentMode,
    name: 'Agentic Search',
    shortName: 'Agentic Search',
    description: 'Generalist agent with web search and market data access',
    icon: Sparkles,
    color: '#3b82f6',
    badge: 'Live Web',
    dataTypes: 'Web, news, market data',
  },
  {
    id: 'risk' as AgentMode,
    name: 'Risk Analysis',
    shortName: 'Risk',
    description: 'Direct access to risk calculation modules',
    icon: Zap,
    color: '#ef4444',
    badge: 'Specialist',
    dataTypes: 'Market data, portfolios',
  },
  {
    id: 'filings' as AgentMode,
    name: 'Filing Search',
    shortName: 'Filing',
    description: 'Search earnings transcripts, insider trades, and financial news',
    icon: FileText,
    color: '#f59e0b',
    badge: 'Documents',
    dataTypes: 'SEC filings, transcripts',
  },
  {
    id: 'multiples' as AgentMode,
    name: 'Comparable Companies',
    shortName: 'Comps',
    description: 'Analyze companies using trading multiples and peer comparison',
    icon: BarChart3,
    color: '#8b5cf6',
    badge: 'Valuation',
    dataTypes: 'Valuations, ratios',
  },
  {
    id: 'charts' as AgentMode,
    name: 'Chart Analysis',
    shortName: 'Charts',
    description: 'Technical analysis with GPT-5 vision • Use: chart-analyst',
    icon: LineChart,
    color: '#06b6d4',
    badge: 'Technical',
    dataTypes: 'Price data, images',
  },
  {
    id: 'quant' as AgentMode,
    name: 'Quantitative Coding',
    shortName: 'Quant',
    description: 'Custom quant implementations with Code Interpreter • Use: quant-agent',
    icon: Code,
    color: '#ec4899',
    badge: 'Code',
    dataTypes: 'Code execution, files',
  },
  {
    id: 'structuring' as AgentMode,
    name: 'Derivatives Structuring',
    shortName: 'Structuring',
    description: 'IRS, swaptions, CDS, variance swaps, exotic options, structured products',
    icon: Layers,
    color: '#6366f1',
    badge: 'Derivatives',
    dataTypes: 'Market, rates, vol surface',
  },
  {
    id: 'dcf' as AgentMode,
    name: 'DCF Valuation',
    shortName: 'DCF',
    description: 'Discounted cash flow and intrinsic value analysis',
    icon: Calculator,
    color: '#059669',
    badge: 'Valuation',
    dataTypes: 'Financials, modeling',
  },
  {
    id: 'options' as AgentMode,
    name: 'Options Analytics',
    shortName: 'Options',
    description: 'Listed options chains, Greeks, volatility, and payoff modelling',
    icon: TrendingDown,
    color: '#f97316',
    badge: 'Options',
    dataTypes: 'Polygon options, Greeks, IV, scenarios',
  },
  {
    id: 'alternatives' as AgentMode,
    name: 'Alternatives Data',
    shortName: 'Alternatives',
    description: 'Cryptocurrency, forex, and commodities data',
    icon: Bitcoin,
    color: '#f59e0b',
    badge: 'Crypto/FX',
    dataTypes: 'Crypto, forex, commodities',
  },
  {
    id: 'institutional' as AgentMode,
    name: 'Institutional Activity',
    shortName: 'Institutional Activity',
    description: 'Insider trading, 13F filings, congressional trades, ETF flows',
    icon: Scale,
    color: '#8b5cf6',
    badge: 'Smart Money',
    dataTypes: '13F, insider, congressional',
  },
  {
    id: 'prediction_markets' as AgentMode,
    name: 'Prediction Markets',
    shortName: 'Predictions',
    description: 'Analyze prediction markets and event probabilities • Use: prediction-markets-agent',
    icon: Target,
    color: '#06b6d4',
    badge: 'Forecast',
    dataTypes: 'Kalshi, Polymarket, PredictIt',
  },
  {
    id: 'funds_products' as AgentMode,
    name: 'Funds & Products',
    shortName: 'Funds',
    description: 'Mutual funds, ETFs, hedge funds analysis • Use: funds-agent',
    icon: TrendingUp,
    color: '#10b981',
    badge: 'Products',
    dataTypes: 'Funds, ETFs, products',
  },
  {
    id: 'private_markets' as AgentMode,
    name: 'Private Markets',
    shortName: 'Private Mkts',
    description: 'Private equity, M&A deals, LBOs, infrastructure • Use: private-markets-agent',
    icon: Briefcase,
    color: '#7c3aed',
    badge: 'PE/M&A',
    dataTypes: 'Web, M&A data, economic',
  },
];

const AgentModeSelector: React.FC<AgentModeSelectorProps> = ({
  mode,
  onModeChange,
  disabled = false,
  direction = 'down',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const currentMode = agentModes.find((m) => m.id === mode) || agentModes[0];
  const Icon = currentMode.icon;

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen(!isOpen)}
        title={currentMode.shortName}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '2px',
          padding: '6px 8px',
          background: 'transparent',
          border: 'none',
          borderRadius: '6px',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          transition: 'all 0.2s',
        }}
        onMouseEnter={(e) => {
          if (!disabled) {
            e.currentTarget.style.background = '#f3f4f6';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent';
        }}
      >
        <Icon size={18} style={{ color: currentMode.color }} />
        <ChevronDown size={12} style={{ color: '#9ca3af' }} />
      </button>

      {isOpen && !disabled && (
        <div
          style={{
            position: 'absolute',
            ...(direction === 'up' ? { bottom: '100%', marginBottom: '0.5rem' } : { top: '100%', marginTop: '0.5rem' }),
            left: '50%',
            transform: 'translateX(-50%)',
            width: 'min(28rem, calc(100vw - 2rem))',
            maxHeight: 'calc(100vh - 12.5rem)',
            background: '#FFFFFF',
            border: '0.0625rem solid #d1d5db',
            borderRadius: '0.5rem',
            boxShadow: '0 0.125rem 0.5rem rgba(0, 0, 0, 0.12)',
            zIndex: 1000,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(7.5rem, 1fr))',
              gap: '0.375rem',
              padding: '0.5rem',
              overflowY: 'auto',
              flex: 1,
            }}
          >
            {agentModes.map((modeOption) => {
              const ModeIcon = modeOption.icon;
              const isSelected = mode === modeOption.id;
              const isComingSoon = modeOption.badge === 'Coming Soon';

              return (
                <div
                  key={modeOption.id}
                  onClick={() => {
                    if (!isComingSoon) {
                      onModeChange(modeOption.id);
                      setIsOpen(false);
                    }
                  }}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.25rem',
                    padding: '0.5rem',
                    cursor: isComingSoon ? 'not-allowed' : 'pointer',
                    background: isSelected ? '#f0f9ff' : '#FFFFFF',
                    border: isSelected ? `0.125rem solid ${modeOption.color}` : '0.0625rem solid #e5e7eb',
                    borderRadius: '0.375rem',
                    transition: 'all 0.2s',
                    position: 'relative',
                    opacity: isComingSoon ? 0.5 : 1,
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected && !isComingSoon) {
                      e.currentTarget.style.background = '#f9fafb';
                      e.currentTarget.style.borderColor = '#9ca3af';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected && !isComingSoon) {
                      e.currentTarget.style.background = '#FFFFFF';
                      e.currentTarget.style.borderColor = '#e5e7eb';
                    }
                  }}
                >
                  {/* Header with icon and name */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                    <ModeIcon
                      size={16}
                      style={{
                        color: modeOption.color,
                        flexShrink: 0,
                      }}
                    />
                    <span
                      style={{
                        fontSize: '0.8125rem',
                        fontWeight: isSelected ? 600 : 500,
                        color: '#111827',
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {modeOption.shortName}
                    </span>
                    {isSelected && (
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke={modeOption.color}
                        strokeWidth="3"
                        style={{ flexShrink: 0 }}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>

                  {/* Badge */}
                  {modeOption.badge && (
                    <span
                      style={{
                        fontSize: '0.5625rem',
                        padding: '0.0625rem 0.25rem',
                        borderRadius: '0.1875rem',
                        background: isSelected ? modeOption.color : '#f3f4f6',
                        color: isSelected ? '#FFFFFF' : '#6b7280',
                        fontWeight: 500,
                        alignSelf: 'flex-start',
                      }}
                    >
                      {modeOption.badge}
                    </span>
                  )}

                  {/* Description */}
                  <p
                    style={{
                      fontSize: '0.625rem',
                      color: '#9ca3af',
                      margin: 0,
                      lineHeight: '1.3',
                    }}
                  >
                    {modeOption.description}
                  </p>
                </div>
              );
            })}
          </div>

          <div
            style={{
              padding: '0.5rem 0.75rem',
              fontSize: '0.625rem',
              color: '#9ca3af',
              textAlign: 'center',
            }}
          >
            Tip: Use specific modes to bypass routing and directly access specialized agents.
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentModeSelector;
