/**
 * Dashboard Guide Panel - Slide-in documentation panel from the right
 * Non-blocking - allows interaction with dashboard while reading
 */

import React, { useState, useEffect } from 'react';
import {
  X, Bitcoin, Landmark, TrendingUp, Rocket, Sparkles,
  ChevronRight, ChevronDown, Activity, BarChart3, Calendar,
  Layout, PieChart, LineChart, Globe, RefreshCw, Database,
} from 'lucide-react';

interface DashboardGuidePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabId = 'overview' | 'views' | 'widgets' | 'portfolio' | 'tips';

export const DashboardGuidePanel: React.FC<DashboardGuidePanelProps> = ({
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  // Animate in
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => setVisible(true), 10);
    } else {
      setVisible(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'overview', label: 'Overview', icon: <Layout size={14} /> },
    { id: 'views', label: 'Views', icon: <Globe size={14} /> },
    { id: 'widgets', label: 'Widgets', icon: <BarChart3 size={14} /> },
    { id: 'portfolio', label: 'Portfolio', icon: <PieChart size={14} /> },
    { id: 'tips', label: 'Tips', icon: <Sparkles size={14} /> },
  ];

  const toggleSection = (id: string) => {
    setExpandedSection(prev => prev === id ? null : id);
  };

  return (
    <>
      {/* Non-blocking side panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-xl bg-white shadow-2xl flex flex-col z-40 transition-transform duration-300 ease-out ${visible ? 'translate-x-0' : 'translate-x-full'}`}
        style={{ borderLeft: '1px solid #e5e7eb' }}
      >
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Dashboard Guide</h2>
              <p className="text-sm text-gray-500 mt-0.5">Your investment command center</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Tabs */}
          <div className="border-b border-gray-200 mt-4">
            <div className="flex gap-0 overflow-x-auto no-scrollbar">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2.5 text-xs font-medium transition-all whitespace-nowrap border-b-2 ${
                    activeTab === tab.id
                      ? 'border-gray-900 text-gray-900'
                      : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="p-6 space-y-6">
              <div className="pb-4 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-900 mb-2">Dashboard Overview</h3>
                <p className="text-sm text-gray-600">
                  Unified view of global markets, portfolios, and AI insights. Layout adapts based on selected view.
                </p>
              </div>

              <div className="space-y-4">
                <div className="text-xs font-semibold text-gray-700">PAGE STRUCTURE</div>

                <div className="space-y-3">
                  <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                    <div className="text-xs font-semibold text-gray-700 mb-1.5">HEADER</div>
                    <p className="text-sm text-gray-700">
                      Personalized greeting and help access (the ? button you clicked)
                    </p>
                  </div>

                  <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                    <div className="text-xs font-semibold text-gray-700 mb-1.5">NAVIGATION BAR</div>
                    <p className="text-sm text-gray-700">
                      Six view pills with market status and sentiment indicator. Click any pill to switch views.
                    </p>
                  </div>

                  <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                    <div className="text-xs font-semibold text-gray-700 mb-1.5">MARKET TICKER</div>
                    <p className="text-sm text-gray-700">
                      Live index prices for your selected region. Updates automatically.
                    </p>
                  </div>

                  <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                    <div className="text-xs font-semibold text-gray-700 mb-1.5">MAIN CONTENT</div>
                    <p className="text-sm text-gray-700">
                      Contextual widgets based on selected view (insights, charts, calendars).
                    </p>
                  </div>

                  <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                    <div className="text-xs font-semibold text-gray-700 mb-1.5">PORTFOLIO SIDEBAR</div>
                    <p className="text-sm text-gray-700">
                      Holdings and market factors (appears when portfolios exist).
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-blue-50 border-l-4 border-[#0051cc] p-3 text-xs text-gray-700">
                <strong>Auto-saved:</strong> Your selected view and market region are automatically saved and restored when you return.
              </div>
            </div>
          )}

          {/* Views Tab */}
          {activeTab === 'views' && (
            <div className="p-6 space-y-6">
              <div className="pb-4 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-900 mb-2">Six Specialized Views</h3>
                <p className="text-sm text-gray-600">
                  Click any pill in the navigation bar to switch views. Each optimized for specific analysis.
                </p>
              </div>

              <div className="space-y-3">
                {/* Markets */}
                <button
                  onClick={() => toggleSection('markets')}
                  className="w-full text-left"
                >
                  <div className="p-3.5 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-[#0051cc] transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <img src="/flags/usa.png" alt="US" className="w-6 h-4 object-cover rounded-sm" />
                        <span className="text-sm font-medium text-gray-900">Markets</span>
                        <span className="text-xs text-gray-500">Default view</span>
                      </div>
                      {expandedSection === 'markets' ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                    </div>
                    {expandedSection === 'markets' && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <p className="text-sm text-gray-700 mb-2">
                          Global equity indices with regional selection (US, EU, China, Japan, Korea).
                        </p>
                        <p className="text-xs text-gray-600">
                          Quick Insights • Market News • Portfolio Chart • Holdings Table
                        </p>
                      </div>
                    )}
                  </div>
                </button>

                {/* Crypto */}
                <button
                  onClick={() => toggleSection('crypto')}
                  className="w-full text-left"
                >
                  <div className="p-3.5 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-[#0051cc] transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900">Crypto</span>
                      {expandedSection === 'crypto' ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                    </div>
                    {expandedSection === 'crypto' && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <p className="text-sm text-gray-700 mb-2">
                          Cryptocurrency markets including Bitcoin, Ethereum, and major altcoins.
                        </p>
                        <p className="text-xs text-gray-600">
                          Crypto Insights • Crypto Ticker • Crypto Screener Widget
                        </p>
                      </div>
                    )}
                  </div>
                </button>

                {/* Macro */}
                <button
                  onClick={() => toggleSection('macro')}
                  className="w-full text-left"
                >
                  <div className="p-3.5 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-[#0051cc] transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900">Macro & Alternatives</span>
                      {expandedSection === 'macro' ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                    </div>
                    {expandedSection === 'macro' && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <p className="text-sm text-gray-700 mb-2">
                          Commodities, currencies, and macroeconomic indicators.
                        </p>
                        <p className="text-xs text-gray-600">
                          Macro Insights • Commodities • Forex • Economic Calendar
                        </p>
                      </div>
                    )}
                  </div>
                </button>

                {/* Earnings */}
                <button
                  onClick={() => toggleSection('earnings')}
                  className="w-full text-left"
                >
                  <div className="p-3.5 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-[#0051cc] transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900">Earnings</span>
                      {expandedSection === 'earnings' ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                    </div>
                    {expandedSection === 'earnings' && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <p className="text-sm text-gray-700 mb-2">
                          Interactive calendar for tracking upcoming earnings reports.
                        </p>
                        <p className="text-xs text-gray-600">
                          EPS (actual vs estimate) • Revenue • Company Profile • TradingView Chart
                        </p>
                      </div>
                    )}
                  </div>
                </button>

                {/* IPOs */}
                <button
                  onClick={() => toggleSection('ipos')}
                  className="w-full text-left"
                >
                  <div className="p-3.5 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-[#0051cc] transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900">IPOs</span>
                      {expandedSection === 'ipos' ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                    </div>
                    {expandedSection === 'ipos' && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <p className="text-sm text-gray-700 mb-2">
                          Recent and upcoming initial public offerings with pricing and sizing.
                        </p>
                        <p className="text-xs text-gray-600">
                          Symbol • Exchange • Price Range • Shares • Market Cap
                        </p>
                      </div>
                    )}
                  </div>
                </button>

                {/* AI Screener */}
                <button
                  onClick={() => toggleSection('screener')}
                  className="w-full text-left"
                >
                  <div className="p-3.5 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-[#0051cc] transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">AI Screener</span>
                        <span className="text-xs text-[#0051cc] font-medium">Natural Language</span>
                      </div>
                      {expandedSection === 'screener' ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                    </div>
                    {expandedSection === 'screener' && (
                      <div className="mt-3 pt-3 border-t border-gray-200 space-y-3">
                        <p className="text-sm text-gray-700">
                          Find stocks, options flow, and analyst ratings using plain English. Select a mode from the dropdown in the input bar.
                        </p>

                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-gray-700">SCREENING MODES</div>
                          <div className="space-y-1.5 text-xs text-gray-600">
                            <p><span className="font-medium text-gray-700">Stocks</span> <span className="text-gray-400">(FMP)</span> — US-listed equities by fundamentals, sector, market cap</p>
                            <p><span className="font-medium text-gray-700">Flow</span> <span className="text-gray-400">(UW)</span> — Options flow metrics: IV rank, premium, put/call ratio</p>
                            <p><span className="font-medium text-gray-700">Options</span> <span className="text-gray-400">(UW)</span> — Hot contracts: volume, OI, unusual activity, 0DTE</p>
                            <p><span className="font-medium text-gray-700">Analysts</span> <span className="text-gray-400">(UW)</span> — Recent upgrades, downgrades, price target changes</p>
                          </div>
                        </div>

                        <div className="text-xs text-gray-600 space-y-1 font-mono bg-gray-50 p-2 rounded">
                          <p>"Large cap tech stocks with high volume"</p>
                          <p>"High IV rank stocks with bullish flow"</p>
                          <p>"0DTE calls with unusual volume"</p>
                          <p>"Recent upgrades in healthcare"</p>
                        </div>
                      </div>
                    )}
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* Widgets Tab */}
          {activeTab === 'widgets' && (
            <div className="p-6 space-y-6">
              <div className="pb-4 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-900 mb-2">Dashboard Widgets</h3>
                <p className="text-sm text-gray-600">
                  Interactive components displaying market data, news, and analytics.
                </p>
              </div>

              <div className="space-y-4">
                {/* Quick Insights */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">QUICK INSIGHTS</div>
                  <p className="text-sm text-gray-700 mb-2">
                    AI-generated market commentary tailored to your current view. Updates periodically and can be manually regenerated.
                  </p>
                  <div className="bg-blue-50 border-l-4 border-[#0051cc] p-2.5 text-xs text-gray-700">
                    Click "Refresh" in insights header to regenerate (5–15 seconds)
                  </div>
                </div>

                {/* Market Status */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">MARKET STATUS</div>
                  <p className="text-sm text-gray-700">
                    Current trading session for US markets (Eastern Time): Pre-Market, Open, After Hours, or Closed.
                  </p>
                </div>

                {/* Fear & Greed */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">FEAR & GREED INDEX</div>
                  <p className="text-sm text-gray-700 mb-3">
                    Market psychology indicator (0–100 scale) based on CNN's methodology.
                  </p>
                  <div className="grid grid-cols-5 gap-1.5">
                    <div className="text-center">
                      <div className="h-2.5 bg-red-500 rounded-sm mb-1" />
                      <span className="text-[10px] text-gray-600">0–24</span>
                    </div>
                    <div className="text-center">
                      <div className="h-2.5 bg-orange-500 rounded-sm mb-1" />
                      <span className="text-[10px] text-gray-600">25–44</span>
                    </div>
                    <div className="text-center">
                      <div className="h-2.5 bg-yellow-500 rounded-sm mb-1" />
                      <span className="text-[10px] text-gray-600">45–55</span>
                    </div>
                    <div className="text-center">
                      <div className="h-2.5 bg-lime-500 rounded-sm mb-1" />
                      <span className="text-[10px] text-gray-600">56–74</span>
                    </div>
                    <div className="text-center">
                      <div className="h-2.5 bg-green-500 rounded-sm mb-1" />
                      <span className="text-[10px] text-gray-600">75–100</span>
                    </div>
                  </div>
                </div>

                {/* Market Ticker */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">MARKET TICKER</div>
                  <p className="text-sm text-gray-700 mb-2">
                    Live prices for major indices based on selected region.
                  </p>
                  <div className="space-y-1.5 text-xs text-gray-600">
                    <div className="flex items-center gap-2">
                      <img src="/flags/usa.png" alt="US" className="w-5 h-3 object-cover rounded-sm" />
                      <span>S&P 500 • Dow Jones • Nasdaq • Russell 2000 • VIX</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <img src="/flags/europeanunion.png" alt="EU" className="w-5 h-3 object-cover rounded-sm" />
                      <span>Euro Stoxx 50 • DAX • FTSE 100 • CAC 40</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <img src="/flags/china.png" alt="CN" className="w-5 h-3 object-cover rounded-sm" />
                      <span>Shanghai Composite • Hang Seng • CSI 300</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <img src="/flags/japan.png" alt="JP" className="w-5 h-3 object-cover rounded-sm" />
                      <span>Nikkei 225 • TOPIX</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <img src="/flags/korea.png" alt="KR" className="w-5 h-3 object-cover rounded-sm" />
                      <span>KOSPI • KOSDAQ</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Portfolio Tab */}
          {activeTab === 'portfolio' && (
            <div className="p-6 space-y-6">
              <div className="pb-4 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-900 mb-2">Portfolio Section</h3>
                <p className="text-sm text-gray-600">
                  Dashboard displays performance charts, holdings summary, and sidebar when portfolios exist.
                </p>
              </div>

              <div className="space-y-4">
                {/* Performance Chart */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">AGGREGATED PERFORMANCE CHART</div>
                  <p className="text-sm text-gray-700 mb-2">
                    Time-weighted return chart showing combined portfolio performance. Methodology accounts for cash flows.
                  </p>
                  <p className="text-xs text-gray-600">
                    Timeframes: 1 Week • 1 Month • 3 Months • 6 Months • 1 Year • All Time
                  </p>
                </div>

                {/* Holdings Table */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">PORTFOLIO HOLDINGS TABLE</div>
                  <p className="text-sm text-gray-700 mb-2">
                    Lists top 5 portfolios with key metrics. Click any row to navigate to full portfolio page.
                  </p>
                  <div className="text-xs text-gray-600 space-y-1">
                    <p>• Portfolio Name (with DEFAULT badge if applicable)</p>
                    <p>• Value (total market value of holdings)</p>
                    <p>• Positions (number of distinct holdings)</p>
                    <p>• Holdings ("See more →" link to detail page)</p>
                  </div>
                </div>

                {/* Sidebar */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">RIGHT SIDEBAR</div>
                  <div className="text-sm text-gray-700 space-y-1.5">
                    <p>• My Top Holdings: Live quotes for 5 largest positions</p>
                    <p>• Market Factors: Key indicators relevant to holdings</p>
                    <p>• Hotlists: Trending stocks and notable movers</p>
                    <p>• Bonds: Fixed income market overview</p>
                  </div>
                </div>
              </div>

              <div className="bg-blue-50 border-l-4 border-[#0051cc] p-3 text-xs text-gray-700">
                <strong>No portfolios yet?</strong> Create one from Portfolio page or connect brokerage in Settings → Integrations.
              </div>
            </div>
          )}

          {/* Tips Tab */}
          {activeTab === 'tips' && (
            <div className="p-6 space-y-6">
              <div className="pb-4 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-900 mb-2">Tips & Navigation</h3>
                <p className="text-sm text-gray-600">
                  Shortcuts and best practices for using dashboard effectively.
                </p>
              </div>

              <div className="space-y-4">
                {/* Quick Links */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">QUICK LINKS FOOTER</div>
                  <p className="text-sm text-gray-700 mb-2">
                    Fixed at bottom, these buttons provide one-click access to major sections:
                  </p>
                  <div className="space-y-1.5 text-xs text-gray-600">
                    <p>• <span className="font-mono bg-blue-100 text-[#0051cc] px-1.5 py-0.5 rounded">/chat</span> - AI chat for investment analysis</p>
                    <p>• <span className="font-mono bg-blue-100 text-[#0051cc] px-1.5 py-0.5 rounded">/portfolio</span> - Manage portfolios and holdings</p>
                    <p>• <span className="font-mono bg-blue-100 text-[#0051cc] px-1.5 py-0.5 rounded">/analytics</span> - Charts, heatmaps, screeners</p>
                    <p>• <span className="font-mono bg-blue-100 text-[#0051cc] px-1.5 py-0.5 rounded">/events</span> - Market news and calendar</p>
                    <p>• <span className="font-mono bg-blue-100 text-[#0051cc] px-1.5 py-0.5 rounded">/workflows</span> - Automated analysis workflows</p>
                    <p>• <span className="font-mono bg-blue-100 text-[#0051cc] px-1.5 py-0.5 rounded">/settings</span> - Account and preferences</p>
                  </div>
                </div>

                {/* Keyboard Shortcuts */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">KEYBOARD SHORTCUTS</div>
                  <div className="space-y-1.5 text-sm text-gray-700">
                    <div className="flex items-center justify-between">
                      <span>Open command palette</span>
                      <span className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded">⌘ + K</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>New chat thread</span>
                      <span className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded">⌘ + N</span>
                    </div>
                  </div>
                </div>

                {/* Best Practices */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">BEST PRACTICES</div>
                  <div className="text-sm text-gray-700 space-y-1.5">
                    <p>• Start with Markets view for quick overview of global indices</p>
                    <p>• Refresh insights after significant market moves</p>
                    <p>• Use AI Screener with specific criteria for better results</p>
                    <p>• Create portfolios to unlock personalized analytics</p>
                    <p>• Check Earnings calendar for holdings before earnings dates</p>
                  </div>
                </div>

                {/* Left Sidebar */}
                <div className="border-l-4 border-[#0051cc] pl-4 py-1">
                  <div className="text-xs font-semibold text-gray-700 mb-1.5">LEFT SIDEBAR</div>
                  <p className="text-sm text-gray-700">
                    Icon rail on left provides access to all major sections. Icons labeled on hover. Settings located at bottom of rail.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default DashboardGuidePanel;

