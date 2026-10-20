import { useEffect, useState } from 'react';
import { useChatStore } from '@stores/chatStore';
import { useUIStore } from '@stores/uiStore';
import type { Message } from '@/types';
import MessageList from '@/components/Chat/MessageList';
import InputArea from '@/components/Chat/InputArea';
import ModelDropdown from '@/components/Chat/ModelDropdown';
import PromptLibrary from '@/components/Chat/PromptLibrary';
import { Home, MessageCircle, Briefcase, CheckSquare, Calendar, TrendingUp, Network, Boxes, Settings, Activity, Plus, Trash2, ChevronLeft, ChevronRight, Send, Paperclip, Compass, Brain, Columns } from 'lucide-react';
import clsx from 'clsx';
import toast from 'react-hot-toast';

// Demo messages - preload into chat store
const DEMO_MESSAGES: Message[] = [
  {
    id: '1',
    role: 'user',
    content: 'Run a DCF valuation on AAPL with a 10% discount rate',
    timestamp: new Date('2024-01-15T14:30:00'),
  },
  {
    id: '2',
    role: 'assistant',
    content: `I'll perform a Discounted Cash Flow (DCF) valuation for Apple Inc. (AAPL) using a 10% discount rate.

**DCF Valuation Analysis**

**Base Assumptions:**
- Current Stock Price: $195.50
- Shares Outstanding: 15.73B
- Market Cap: $3.07T
- Discount Rate (WACC): 10.0%
- Terminal Growth Rate: 3.5%
- Projection Period: 5 years

**Free Cash Flow Projections (in billions):**

| Year | Revenue | FCF Growth | Free Cash Flow | PV of FCF |
|------|---------|------------|----------------|-----------|
| 2024 | $405.2B | 8.0% | $108.4B | $98.5B |
| 2025 | $437.6B | 7.5% | $116.5B | $96.3B |
| 2026 | $469.4B | 7.0% | $124.7B | $93.7B |
| 2027 | $500.4B | 6.5% | $132.8B | $90.7B |
| 2028 | $530.4B | 6.0% | $140.8B | $87.4B |

**Terminal Value Calculation:**
- Terminal FCF (2029): $145.7B
- Terminal Value: $2,447.3B
- PV of Terminal Value: $1,519.6B

**Valuation Summary:**
- PV of Projected FCF: $466.6B
- PV of Terminal Value: $1,519.6B
- **Enterprise Value: $1,986.2B**
- Less: Net Debt: ($50.2B)
- **Equity Value: $2,036.4B**
- **Fair Value per Share: $129.50**

**Sensitivity Analysis:**

| WACC → | 8.0% | 9.0% | 10.0% | 11.0% | 12.0% |
|--------|------|------|-------|-------|-------|
| **Terminal Growth** |||||||
| 2.5% | $142.30 | $135.20 | $129.50 | $124.10 | $119.20 |
| 3.0% | $148.60 | $140.80 | $134.20 | $128.40 | $123.10 |
| 3.5% | $155.40 | $146.90 | $139.50 | $133.00 | $127.30 |
| 4.0% | $163.20 | $153.70 | $145.50 | $138.20 | $131.90 |

**Investment Recommendation:**
At the current price of $195.50, AAPL trades at a **51% premium** to our DCF fair value of $129.50. This suggests the stock is overvalued under these assumptions. However, investors may be pricing in:
- Stronger-than-expected growth in services revenue
- Successful new product launches (Vision Pro, AI features)
- Market share gains in emerging markets
- Premium multiple for brand value and ecosystem lock-in`,
    timestamp: new Date('2024-01-15T14:30:45'),
    sources: [
      { id: 's1', title: 'FMP Financial Statements', url: '#', snippet: 'Income statement and cash flow data' },
      { id: 's2', title: 'SEC 10-K Filing', url: '#', snippet: 'Apple Inc. annual report' },
      { id: 's3', title: 'DCF Model', url: '#', snippet: 'Valuation methodology' },
    ],
  },
  {
    id: '3',
    role: 'user',
    content: 'Create a Python script to calculate the efficient frontier for a 3-asset portfolio',
    timestamp: new Date('2024-01-15T14:32:00'),
  },
  {
    id: '4',
    role: 'assistant',
    content: `I'll create a Python script to calculate and visualize the efficient frontier for a 3-asset portfolio using modern portfolio theory.

\`\`\`python
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from scipy.optimize import minimize

# Download historical data for 3 assets
tickers = ['AAPL', 'MSFT', 'GOOGL']
data = yf.download(tickers, start='2020-01-01', end='2024-01-01')['Adj Close']

# Calculate daily returns
returns = data.pct_change().dropna()

# Calculate expected returns and covariance matrix
mean_returns = returns.mean() * 252  # Annualized
cov_matrix = returns.cov() * 252     # Annualized

# Portfolio statistics functions
def portfolio_stats(weights, mean_returns, cov_matrix):
    """Calculate portfolio return and volatility"""
    portfolio_return = np.dot(weights, mean_returns)
    portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    return portfolio_return, portfolio_std

def negative_sharpe(weights, mean_returns, cov_matrix, risk_free_rate=0.04):
    """Calculate negative Sharpe ratio (for minimization)"""
    p_return, p_std = portfolio_stats(weights, mean_returns, cov_matrix)
    return -(p_return - risk_free_rate) / p_std

# Constraints: weights sum to 1
constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})

# Bounds: each weight between 0 and 1 (no short selling)
bounds = tuple((0, 1) for _ in range(len(tickers)))

# Generate efficient frontier
target_returns = np.linspace(mean_returns.min(), mean_returns.max(), 50)
efficient_portfolios = []

for target in target_returns:
    # Constraint: portfolio must achieve target return
    cons = (
        {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
        {'type': 'eq', 'fun': lambda x: portfolio_stats(x, mean_returns, cov_matrix)[0] - target}
    )

    # Minimize volatility for given return
    result = minimize(
        lambda x: portfolio_stats(x, mean_returns, cov_matrix)[1],
        x0=np.array([1/len(tickers)] * len(tickers)),
        method='SLSQP',
        bounds=bounds,
        constraints=cons
    )

    if result.success:
        efficient_portfolios.append({
            'Return': target,
            'Volatility': result.fun,
            'Weights': result.x
        })

# Find maximum Sharpe ratio portfolio
init_guess = np.array([1/len(tickers)] * len(tickers))
max_sharpe = minimize(
    negative_sharpe,
    init_guess,
    args=(mean_returns, cov_matrix),
    method='SLSQP',
    bounds=bounds,
    constraints=constraints
)

# Extract results
ef_returns = [p['Return'] for p in efficient_portfolios]
ef_volatility = [p['Volatility'] for p in efficient_portfolios]
max_sharpe_return, max_sharpe_vol = portfolio_stats(max_sharpe.x, mean_returns, cov_matrix)

# Visualization
plt.figure(figsize=(12, 8))
plt.scatter(ef_volatility, ef_returns, c='blue', marker='o', s=10, label='Efficient Frontier')
plt.scatter(max_sharpe_vol, max_sharpe_return, c='red', marker='*', s=500, label='Max Sharpe Ratio')
plt.xlabel('Volatility (Risk)', fontsize=12)
plt.ylabel('Expected Return', fontsize=12)
plt.title('Efficient Frontier - 3 Asset Portfolio', fontsize=14)
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('efficient_frontier.png', dpi=300, bbox_inches='tight')
plt.show()

# Print optimal portfolio
print("\\n=== Maximum Sharpe Ratio Portfolio ===")
print(f"Expected Return: {max_sharpe_return:.2%}")
print(f"Volatility: {max_sharpe_vol:.2%}")
print(f"Sharpe Ratio: {(max_sharpe_return - 0.04) / max_sharpe_vol:.2f}")
print("\\nOptimal Weights:")
for ticker, weight in zip(tickers, max_sharpe.x):
    print(f"  {ticker}: {weight:.2%}")
\`\`\`

**Output:**
\`\`\`
=== Maximum Sharpe Ratio Portfolio ===
Expected Return: 28.45%
Volatility: 21.30%
Sharpe Ratio: 1.15

Optimal Weights:
  AAPL: 32.50%
  MSFT: 45.20%
  GOOGL: 22.30%
\`\`\`

The script generates an efficient frontier showing all optimal risk-return combinations. The red star indicates the portfolio with the maximum Sharpe ratio (best risk-adjusted returns). The chart has been saved as \`efficient_frontier.png\`.`,
    timestamp: new Date('2024-01-15T14:33:15'),
    sources: [
      { id: 's1', title: 'Yahoo Finance API', url: '#', snippet: 'Historical price data' },
      { id: 's2', title: 'SciPy Documentation', url: '#', snippet: 'Optimization methods' },
    ],
  },
  {
    id: '5',
    role: 'user',
    content: 'Show me key risk metrics for my portfolio',
    timestamp: new Date('2024-01-15T14:35:00'),
  },
  {
    id: '6',
    role: 'assistant',
    content: `I'll calculate comprehensive risk metrics for your portfolio.

**Portfolio Risk Analysis**

**Value at Risk (VaR) - 95% Confidence:**
- 1-Day VaR: **$24,580** (2.46%)
- 10-Day VaR: **$77,680** (7.77%)
- Conditional VaR (CVaR): **$32,150**

**Risk Metrics:**
- Portfolio Volatility: 18.3% annualized
- Sharpe Ratio: 1.24
- Sortino Ratio: 1.58
- Maximum Drawdown: -22.4%
- Beta (vs S&P 500): 1.08

**Correlation Matrix:**

|        | AAPL  | MSFT  | GOOGL |
|--------|-------|-------|-------|
| AAPL   | 1.00  | 0.82  | 0.75  |
| MSFT   | 0.82  | 1.00  | 0.79  |
| GOOGL  | 0.75  | 0.79  | 1.00  |

Your portfolio has strong positive correlations across all holdings, which limits diversification benefits. Consider adding assets with lower correlations to reduce overall portfolio risk.`,
    timestamp: new Date('2024-01-15T14:35:30'),
    sources: [
      { id: 's1', title: 'Risk Calculations', url: '#', snippet: 'VaR methodology' },
      { id: 's2', title: 'FMP Market Data', url: '#', snippet: 'Historical returns' },
    ],
  },
];

// Updated DemoThreadSidebar to match production ThreadSidebar design
const DemoThreadSidebar = () => {
  const { threads = [], currentThreadId, setCurrentThread } = useChatStore();
  const { sidebarExpanded, setSidebarExpanded } = useUIStore();

  const handleAction = (action: string, e: React.MouseEvent) => {
    e.stopPropagation();
    toast(`Demo Mode: ${action} is disabled`);
  };

  return (
    <div
      className={clsx('flex flex-col h-full transition-all duration-300 ease-in-out')}
      style={{
        width: sidebarExpanded ? 'min(16rem, 40vw)' : '3.5rem',
        background: 'linear-gradient(180deg, #FAFAFA 0%, #F5F5F5 100%)',
        borderRight: '1px solid #E5E5E5',
        boxShadow: '2px 0 8px rgba(0, 0, 0, 0.03)',
      }}
    >
      {/* Header */}
      <div style={{ borderBottom: '1px solid #E5E5E5', padding: sidebarExpanded ? '16px' : '14px' }}>
        <div className="flex items-center justify-between">
          {sidebarExpanded && (
            <span style={{
              fontSize: '15px',
              fontWeight: '600',
              color: '#1A1A1A',
              letterSpacing: '-0.01em',
            }}>
              Conversations
            </span>
          )}
          <button
            onClick={() => setSidebarExpanded(!sidebarExpanded)}
            style={{
              padding: '6px',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              marginLeft: sidebarExpanded ? '0' : 'auto',
              marginRight: sidebarExpanded ? '0' : 'auto',
              borderRadius: '6px',
              transition: 'all 0.2s ease',
            }}
            title={sidebarExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            {sidebarExpanded ? <ChevronLeft size={16} style={{ color: '#666' }} /> : <ChevronRight size={16} style={{ color: '#666' }} />}
          </button>
        </div>

        {sidebarExpanded && (
          <button
            onClick={(e) => handleAction('New Chat', e)}
            style={{
              width: '100%',
              marginTop: '12px',
              padding: '8px 12px',
              background: '#0078D4',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '600',
              height: '36px',
              cursor: 'pointer', // Show pointer but act disabled
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.2s ease',
              boxShadow: '0 1px 2px rgba(0, 120, 212, 0.2)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#106EBE';
              e.currentTarget.style.transform = 'translateY(-1px)';
              e.currentTarget.style.boxShadow = '0 2px 4px rgba(0, 120, 212, 0.3)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#0078D4';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 1px 2px rgba(0, 120, 212, 0.2)';
            }}
          >
            <Plus size={16} strokeWidth={2.5} />
            New Chat
          </button>
        )}
      </div>

      {/* Thread List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: sidebarExpanded ? '12px 8px' : '8px 4px' }}>
        {threads.map((thread) => {
          const isActive = thread.id === currentThreadId;
          return (
            <div
              key={thread.id}
              onClick={() => setCurrentThread(thread.id)}
              className="group"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: sidebarExpanded ? '10px 12px' : '8px',
                background: isActive ? 'rgba(0, 120, 212, 0.08)' : 'transparent',
                border: isActive ? '1px solid rgba(0, 120, 212, 0.2)' : '1px solid transparent',
                borderRadius: '6px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                justifyContent: sidebarExpanded ? 'flex-start' : 'center',
                marginBottom: '4px',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'rgba(0, 0, 0, 0.04)';
                  e.currentTarget.style.border = '1px solid rgba(0, 0, 0, 0.08)';
                  e.currentTarget.style.transform = 'translateX(2px)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.border = '1px solid transparent';
                  e.currentTarget.style.transform = 'translateX(0)';
                }
              }}
              title={!sidebarExpanded ? thread.title : undefined}
            >
              <MessageCircle
                size={16}
                strokeWidth={isActive ? 2.5 : 2}
                style={{
                  color: isActive ? '#0078D4' : '#666',
                  flexShrink: 0,
                }}
              />
              {sidebarExpanded && (
                <>
                  <span style={{
                    flex: 1,
                    fontSize: '14px',
                    color: isActive ? '#1A1A1A' : '#4A4A4A',
                    fontWeight: isActive ? '600' : '500',
                    fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {thread.title}
                  </span>
                  <button
                    onClick={(e) => handleAction('Delete Thread', e)}
                    className="opacity-0 group-hover:opacity-100"
                    style={{
                      padding: '4px',
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      borderRadius: '4px',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <Trash2 size={14} style={{ color: '#EF4444' }} strokeWidth={2} />
                  </button>
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      {sidebarExpanded && threads.length > 0 && (
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid #E5E5E5',
          fontSize: '12px',
          color: '#999',
          fontWeight: '500',
          background: 'rgba(255, 255, 255, 0.5)',
        }}>
          {threads.length} {threads.length === 1 ? 'conversation' : 'conversations'}
        </div>
      )}
    </div>
  );
};

const PublicChatDemo = () => {
  const [isInitialized, setIsInitialized] = useState(false);

  // Get current thread messages from store (MUST be before any conditional returns)
  const { threads, currentThreadId } = useChatStore();
  const currentThread = threads.find(t => t.id === currentThreadId);
  const messages = currentThread?.messages || [];

  useEffect(() => {
    // Clear existing threads and create fresh demo thread
    const demoThreadId = crypto.randomUUID();

    // Get the current state to preserve other properties
    const currentState = useChatStore.getState();

    useChatStore.setState({
      ...currentState,
      threads: [{
        id: demoThreadId,
        title: 'Investment Analysis Demo',
        messages: [...DEMO_MESSAGES], // Spread to ensure it's a proper array
        createdAt: new Date(),
        updatedAt: new Date(),
        agentMode: 'auto' as const,
        selectedModel: 'gpt-6.1-sol' as const,
      }],
      currentThreadId: demoThreadId,
    });

    setIsInitialized(true);
  }, []);

  if (!isInitialized) {
    return <div className="flex items-center justify-center h-screen">Loading demo...</div>;
  }

  // Render standalone chat interface with NavigationRail, simplified SystemBar, and actual components
  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden">
      {/* Simplified System Bar (no user menu or links) */}
      <div
        className="flex items-center justify-between px-3"
        style={{
          width: '100%',
          height: '48px',
          background: '#FFFFFF',
          borderBottom: '1px solid #E1DFDD',
          fontSize: '12px',
        }}
      >
        {/* Left - Branding */}
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--text-primary)', fontSize: '16px', fontWeight: 'var(--fw-medium)' }}>
            Sentry
          </span>
        </div>

        {/* Center - Status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full" style={{ background: '#0078D4' }} />
            <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)' }}>DEMO</span>
          </div>
          <div className="flex items-center gap-1">
            <Activity size={10} style={{ color: '#107C10' }} />
            <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)' }}>Read-Only</span>
          </div>
        </div>

        {/* Right - Profile Placeholder */}
        <div
          className="flex items-center gap-2 cursor-not-allowed"
          title="Demo User Profile"
          style={{ opacity: 0.7 }}
        >
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              fontSize: '14px',
              fontWeight: 'var(--fw-semibold)',
            }}
          >
            DU
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Navigation Rail (Demo Version - No Navigation) */}
        <div className="w-16 flex flex-col" style={{ background: 'var(--bg-card)', borderRight: '1px solid var(--border-light)', boxShadow: '2px 0 4px rgba(0,0,0,0.04)' }}>
          {/* Logo Area */}
          <div className="flex items-center justify-center py-3" style={{ borderBottom: '1px solid var(--border-light)' }}>
            <img
              src="/binomial-icon-logo.png"
              alt="Binomial"
              style={{ width: '32px', height: '32px' }}
            />
          </div>

          {/* Main Navigation */}
          <div className="flex-1 flex flex-col items-center pt-1 pb-1">
            {[
              { icon: Home, label: 'Home', color: '#0078D4', active: false },
              { icon: MessageCircle, label: 'Chat', color: '#8764B8', active: true },
              { icon: Briefcase, label: 'Portfolios', color: '#00897B', active: false },
              { icon: CheckSquare, label: 'Tasks', color: '#10B981', active: false },
              { icon: Calendar, label: 'Calendar', color: '#DC2626', active: false },
              { icon: TrendingUp, label: 'Analytics', color: '#FF8C00', active: false },
              { icon: Network, label: 'Graph', color: '#143E7F', active: false },
              { icon: Boxes, label: 'Ontology', color: '#9333EA', active: false, disabled: true },
            ].map((item, idx) => {
              const Icon = item.icon;
              return (
                <button
                  key={idx}
                  onClick={() => !item.active && toast('Navigation disabled in demo mode', { icon: '🔒' })}
                  className="relative flex flex-col items-center justify-center w-full h-14"
                  style={{ background: 'transparent', cursor: item.active ? 'default' : 'pointer', opacity: item.active ? 1 : 0.6, border: 'none' }}
                  title={item.active ? item.label : `${item.label} (Demo Only)`}
                >
                  <Icon
                    size={24}
                    strokeWidth={item.active ? 3 : 2}
                    className="transition-all duration-200"
                    style={{
                      color: item.active ? item.color : 'var(--text-secondary)',
                      opacity: item.active ? 1 : 0.6,
                    }}
                  />
                  <span style={{
                    fontSize: '11px',
                    marginTop: '4px',
                    fontWeight: item.active ? 'var(--fw-semibold)' : 'var(--fw-regular)',
                    color: item.active ? item.color : 'var(--text-secondary)',
                  }}>
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Settings at bottom */}
          <div className="flex flex-col items-center pb-3 pt-1" style={{ borderTop: '1px solid var(--border-light)' }}>
            <button
              onClick={() => toast('Settings disabled in demo mode', { icon: '🔒' })}
              className="flex flex-col items-center justify-center w-full h-14"
              style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
              title="Setup (Demo Only)"
            >
              <Settings
                size={24}
                strokeWidth={2}
                className="transition-all duration-200"
                style={{
                  color: 'var(--text-secondary)',
                  opacity: 0.6,
                }}
              />
              <span style={{
                fontSize: '11px',
                marginTop: '4px',
                fontWeight: 'var(--fw-regular)',
                color: 'var(--text-secondary)',
              }}>
                Setup
              </span>
            </button>
          </div>
        </div>

        {/* Demo Thread Sidebar (updated to match production) */}
        <DemoThreadSidebar />

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Top bar with model selector and prompt library */}
          <div className="h-14 border-b border-border bg-card px-4 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              {/* Model Dropdown */}
              <ModelDropdown />

              {/* Prompt Library */}
              <PromptLibrary onPromptSelect={(prompt) => console.log('Prompt selected:', prompt)} />
            </div>

          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto">
            <MessageList messages={messages} />
          </div>

          {/* Input Area with Overlay */}
          <div className="flex-shrink-0 relative">
            <InputArea />
            {/* Invisible Overlay to intercept interactions */}
            <div
              className="absolute inset-0 z-50 cursor-not-allowed"
              onClick={(e) => {
                e.stopPropagation();
                toast('Chat is disabled in demo mode', { icon: '🔒' });
              }}
              style={{ background: 'transparent' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default PublicChatDemo;
