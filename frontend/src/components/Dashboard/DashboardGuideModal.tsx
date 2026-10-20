/**
 * Dashboard Guide Modal - Professional user guide for the Dashboard
 */

import React, { useState } from 'react';
import { X, ChevronLeft, ChevronRight, Bitcoin, Landmark, TrendingUp, Rocket, Sparkles } from 'lucide-react';

interface DashboardGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DashboardGuideModal: React.FC<DashboardGuideModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [currentPage, setCurrentPage] = useState(0);

  if (!isOpen) return null;

  const pages = [
    // Page 1: Overview
    {
      title: 'Dashboard Overview',
      subtitle: 'Your investment command center',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            The Dashboard provides a unified view of global markets, your portfolios, and AI-powered
            insights. It adapts dynamically based on your selected view — showing relevant data for
            equities, crypto, macro indicators, or corporate events.
          </p>

          <div className="space-y-1">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Page Structure</p>

            <div className="border-l-2 border-gray-200 pl-4 space-y-4">
              <div>
                <p className="text-sm font-medium text-gray-900">Header</p>
                <p className="text-sm text-gray-500">Personalized greeting and help access</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Navigation Bar</p>
                <p className="text-sm text-gray-500">Six view pills + market status + sentiment indicator</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Market Ticker</p>
                <p className="text-sm text-gray-500">Live index prices for your selected region</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Main Content</p>
                <p className="text-sm text-gray-500">Contextual widgets based on selected view</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Portfolio Sidebar</p>
                <p className="text-sm text-gray-500">Your holdings and market factors (when portfolios exist)</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Quick Links</p>
                <p className="text-sm text-gray-500">Fixed footer with navigation shortcuts</p>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-500">
              Your view preferences (selected pill and market region) are automatically saved and
              restored when you return to the Dashboard.
            </p>
          </div>
        </div>
      ),
    },

    // Page 2: Navigation Pills
    {
      title: 'View Selection',
      subtitle: 'Six specialized views',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            The navigation bar contains six pills that transform the Dashboard content. Each view
            is optimized for a specific type of market analysis.
          </p>

          <div className="space-y-3">
            {/* Markets */}
            <div className="p-4 border border-gray-200 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <img src="/flags/usa.png" alt="US" className="w-5 h-3.5 object-cover rounded-sm" />
                  <span className="text-sm font-semibold text-gray-900">Markets</span>
                </div>
                <span className="text-xs text-gray-400">Default view</span>
              </div>
              <p className="text-sm text-gray-600 mb-3">
                Global equity indices with regional selection. Click the pill to open a dropdown
                with five regions: US, EU, China, Japan, and Korea.
              </p>
              <p className="text-xs text-gray-500">
                <strong>Shows:</strong> Quick Insights • Market News • Portfolio Chart • Holdings Table
              </p>
            </div>

            {/* Crypto */}
            <div className="p-4 border border-gray-200 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Bitcoin size={16} className="text-orange-500" />
                <span className="text-sm font-semibold text-gray-900">Crypto</span>
              </div>
              <p className="text-sm text-gray-600 mb-2">
                Cryptocurrency markets including Bitcoin, Ethereum, and major altcoins.
              </p>
              <p className="text-xs text-gray-500">
                <strong>Shows:</strong> Crypto Insights • Crypto Ticker • Crypto Screener Widget
              </p>
            </div>

            {/* Macro */}
            <div className="p-4 border border-gray-200 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Landmark size={16} className="text-emerald-600" />
                <span className="text-sm font-semibold text-gray-900">Macro & Alternatives</span>
              </div>
              <p className="text-sm text-gray-600 mb-2">
                Commodities, currencies, and macroeconomic indicators.
              </p>
              <p className="text-xs text-gray-500">
                <strong>Shows:</strong> Macro Insights • Commodities • Forex • Economic Calendar
              </p>
            </div>

            {/* Row of 3 smaller items */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-1.5 mb-1">
                  <TrendingUp size={14} className="text-blue-600" />
                  <span className="text-xs font-semibold text-gray-900">Earnings</span>
                </div>
                <p className="text-xs text-gray-500">Upcoming earnings reports calendar</p>
              </div>
              <div className="p-3 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-1.5 mb-1">
                  <Rocket size={14} className="text-indigo-600" />
                  <span className="text-xs font-semibold text-gray-900">IPOs</span>
                </div>
                <p className="text-xs text-gray-500">Recent and upcoming public offerings</p>
              </div>
              <div className="p-3 border border-purple-200 bg-purple-50/50 rounded-lg">
                <div className="flex items-center gap-1.5 mb-1">
                  <Sparkles size={14} className="text-purple-600" />
                  <span className="text-xs font-semibold text-gray-900">AI Screener</span>
                </div>
                <p className="text-xs text-gray-500">Natural language stock search</p>
              </div>
            </div>
          </div>
        </div>
      ),
    },

    // Page 3: Market Status & Refresh
    {
      title: 'Market Status & Refresh',
      subtitle: 'Real-time data controls',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            The navigation bar displays current market status and the Fear & Greed sentiment
            indicator. Both can be refreshed to fetch the latest data.
          </p>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Refreshing Sentiment Data</p>
            <div className="p-4 border border-gray-200 rounded-lg space-y-3">
              <p className="text-sm text-gray-600">
                The Fear & Greed Index (based on CNN's methodology) shows market psychology on a
                0–100 scale. The colored bars visualize the current reading.
              </p>
              <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg border border-blue-100">
                <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center">
                  <svg className="w-4 h-4 text-gray-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">Click the refresh icon</p>
                  <p className="text-xs text-gray-500">Located next to the sentiment label in the navigation bar</p>
                </div>
              </div>
              <div className="grid grid-cols-5 gap-1 pt-2">
                <div className="text-center">
                  <div className="h-2 bg-red-500 rounded-sm mb-1" />
                  <span className="text-[10px] text-gray-500">0–24</span>
                </div>
                <div className="text-center">
                  <div className="h-2 bg-orange-500 rounded-sm mb-1" />
                  <span className="text-[10px] text-gray-500">25–44</span>
                </div>
                <div className="text-center">
                  <div className="h-2 bg-yellow-500 rounded-sm mb-1" />
                  <span className="text-[10px] text-gray-500">45–55</span>
                </div>
                <div className="text-center">
                  <div className="h-2 bg-lime-500 rounded-sm mb-1" />
                  <span className="text-[10px] text-gray-500">56–74</span>
                </div>
                <div className="text-center">
                  <div className="h-2 bg-green-500 rounded-sm mb-1" />
                  <span className="text-[10px] text-gray-500">75–100</span>
                </div>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Market Status</p>
            <p className="text-sm text-gray-600 mb-3">
              Shows current trading session for US markets (Eastern Time): Pre-Market, Open,
              After Hours, or Closed.
            </p>
          </div>

          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-600">
              <strong>When to refresh:</strong> Sentiment data is cached. Click refresh if you
              want the absolute latest reading, especially during volatile market conditions.
            </p>
          </div>
        </div>
      ),
    },

    // Page 4: Market Ticker
    {
      title: 'Market Ticker',
      subtitle: 'Live index prices',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            Below the navigation bar, a ticker widget displays live prices for major indices.
            The indices shown depend on your selected view and region.
          </p>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Indices by Region</p>
            <div className="space-y-3">
              <div className="p-3 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <img src="/flags/usa.png" alt="US" className="w-5 h-3.5 object-cover rounded-sm" />
                  <span className="text-sm font-medium text-gray-900">United States</span>
                </div>
                <p className="text-xs text-gray-500 font-mono">S&P 500 • Dow Jones • Nasdaq • Russell 2000 • VIX</p>
              </div>
              <div className="p-3 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <img src="/flags/europeanunion.png" alt="EU" className="w-5 h-3.5 object-cover rounded-sm" />
                  <span className="text-sm font-medium text-gray-900">Europe</span>
                </div>
                <p className="text-xs text-gray-500 font-mono">Euro Stoxx 50 • DAX • FTSE 100 • CAC 40</p>
              </div>
              <div className="p-3 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <img src="/flags/china.png" alt="China" className="w-5 h-3.5 object-cover rounded-sm" />
                  <span className="text-sm font-medium text-gray-900">China</span>
                </div>
                <p className="text-xs text-gray-500 font-mono">Shanghai Composite • Shenzhen • Hang Seng • CSI 300</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 border border-gray-200 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <img src="/flags/japan.png" alt="Japan" className="w-5 h-3.5 object-cover rounded-sm" />
                    <span className="text-sm font-medium text-gray-900">Japan</span>
                  </div>
                  <p className="text-xs text-gray-500 font-mono">Nikkei 225 • TOPIX</p>
                </div>
                <div className="p-3 border border-gray-200 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <img src="/flags/korea.png" alt="Korea" className="w-5 h-3.5 object-cover rounded-sm" />
                    <span className="text-sm font-medium text-gray-900">Korea</span>
                  </div>
                  <p className="text-xs text-gray-500 font-mono">KOSPI</p>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Special Views</p>
            <div className="space-y-2 text-sm text-gray-600">
              <p><strong>Crypto:</strong> Bitcoin, Ethereum, and top cryptocurrencies by market cap</p>
              <p><strong>Macro:</strong> Treasury yields, commodities, and currency pairs</p>
              <p><strong>Earnings/IPOs/Screener:</strong> US market indices (default ticker)</p>
            </div>
          </div>
        </div>
      ),
    },

    // Page 5: Quick Insights
    {
      title: 'Quick Insights',
      subtitle: 'AI-generated market analysis',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            Quick Insights provides AI-generated market commentary tailored to your current view.
            Insights update periodically and can be manually regenerated on demand.
          </p>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Regenerating Insights</p>
            <div className="p-4 border border-blue-200 bg-blue-50/50 rounded-lg space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center">
                  <svg className="w-5 h-5 text-gray-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">Click "Refresh" in the insights header</p>
                  <p className="text-xs text-gray-600">Generates fresh analysis using the latest market data (5–15 seconds)</p>
                </div>
              </div>
              <p className="text-xs text-gray-600">
                The timestamp shows when insights were last generated (e.g., "Updated Nov 29, 2:30 PM").
                Refresh if the data feels stale or after significant market moves.
              </p>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Insight Types by View</p>
            <div className="overflow-hidden rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-gray-100">
                    <td className="px-4 py-3 font-medium text-gray-900 w-24">Markets</td>
                    <td className="px-4 py-3 text-gray-600">Index performance, sector rotation, notable movers. Adapts to selected region.</td>
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="px-4 py-3 font-medium text-gray-900">Crypto</td>
                    <td className="px-4 py-3 text-gray-600">Bitcoin/Ethereum trends, altcoin performance, market cap changes.</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 font-medium text-gray-900">Macro</td>
                    <td className="px-4 py-3 text-gray-600">Commodities, currencies, yields, upcoming economic releases.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-600">
              <strong>Note:</strong> Insights are AI-generated and should be used as a starting
              point for research. Always verify data from primary sources.
            </p>
          </div>
        </div>
      ),
    },

    // Page 6: Portfolio Section
    {
      title: 'Portfolio Section',
      subtitle: 'Your holdings at a glance',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            When you have portfolios configured, the Dashboard displays performance charts,
            a holdings summary, and a sidebar with your top positions. This section only
            appears after you create or connect at least one portfolio.
          </p>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Main Content Area</p>
            <div className="space-y-3">
              <div className="p-4 border border-gray-200 rounded-lg">
                <p className="text-sm font-medium text-gray-900 mb-2">Aggregated Performance Chart</p>
                <p className="text-sm text-gray-600 mb-3">
                  A time-weighted return chart showing your combined portfolio performance.
                  This methodology accounts for cash flows, giving an accurate picture of
                  investment returns.
                </p>
                <p className="text-xs text-gray-500">
                  <strong>Timeframes:</strong> 1 Week • 1 Month • 3 Months • 6 Months • 1 Year • All Time
                </p>
              </div>
              <div className="p-4 border border-gray-200 rounded-lg">
                <p className="text-sm font-medium text-gray-900 mb-2">Portfolio Holdings Table</p>
                <p className="text-sm text-gray-600 mb-3">
                  Lists your top 5 portfolios with key metrics. Click any row to navigate
                  to the full portfolio page.
                </p>
                <div className="overflow-hidden rounded border border-gray-100">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-gray-50 text-gray-500">
                        <th className="px-3 py-2 text-left font-medium">Column</th>
                        <th className="px-3 py-2 text-left font-medium">Description</th>
                      </tr>
                    </thead>
                    <tbody className="text-gray-600">
                      <tr className="border-t border-gray-100">
                        <td className="px-3 py-2">Portfolio Name</td>
                        <td className="px-3 py-2">Name with DEFAULT badge if applicable</td>
                      </tr>
                      <tr className="border-t border-gray-100">
                        <td className="px-3 py-2">Value</td>
                        <td className="px-3 py-2">Total market value of holdings</td>
                      </tr>
                      <tr className="border-t border-gray-100">
                        <td className="px-3 py-2">Positions</td>
                        <td className="px-3 py-2">Number of distinct holdings</td>
                      </tr>
                      <tr className="border-t border-gray-100">
                        <td className="px-3 py-2">Holdings</td>
                        <td className="px-3 py-2">"See more →" link to detail page</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Right Sidebar (450px)</p>
            <div className="space-y-2 text-sm text-gray-600">
              <p><strong>My Top Holdings:</strong> Live quotes for your 5 largest positions</p>
              <p><strong>Market Factors:</strong> Key indicators relevant to your holdings</p>
              <p><strong>Hotlists:</strong> Trending stocks and notable movers</p>
              <p><strong>Bonds:</strong> Fixed income market overview</p>
            </div>
          </div>
        </div>
      ),
    },

    // Page 7: Earnings & IPO Calendars
    {
      title: 'Event Calendars',
      subtitle: 'Earnings and IPO tracking',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            The Earnings and IPO views provide interactive calendars for tracking corporate events.
            Click on any company to view detailed information, financials, and charts.
          </p>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Earnings Calendar</p>
            <div className="p-4 border border-gray-200 rounded-lg space-y-3">
              <p className="text-sm text-gray-600">
                Displays companies reporting earnings for the current week. Each entry shows
                the company logo, ticker, and reporting date.
              </p>
              <div className="overflow-hidden rounded border border-gray-100">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500">
                      <th className="px-3 py-2 text-left font-medium">Detail View</th>
                      <th className="px-3 py-2 text-left font-medium">Information</th>
                    </tr>
                  </thead>
                  <tbody className="text-gray-600">
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">EPS</td>
                      <td className="px-3 py-2">Actual vs. Estimated earnings per share</td>
                    </tr>
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">Revenue</td>
                      <td className="px-3 py-2">Actual vs. Estimated revenue</td>
                    </tr>
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">Profile</td>
                      <td className="px-3 py-2">Company description and key stats</td>
                    </tr>
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">Chart</td>
                      <td className="px-3 py-2">TradingView technical chart</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">IPO Calendar</p>
            <div className="p-4 border border-gray-200 rounded-lg space-y-3">
              <p className="text-sm text-gray-600">
                Tracks recent and upcoming initial public offerings with pricing and sizing details.
              </p>
              <div className="overflow-hidden rounded border border-gray-100">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500">
                      <th className="px-3 py-2 text-left font-medium">Field</th>
                      <th className="px-3 py-2 text-left font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody className="text-gray-600">
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">Symbol</td>
                      <td className="px-3 py-2">Ticker and company name</td>
                    </tr>
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">Exchange</td>
                      <td className="px-3 py-2">NYSE, NASDAQ, etc.</td>
                    </tr>
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">Price Range</td>
                      <td className="px-3 py-2">Expected offering price</td>
                    </tr>
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">Shares</td>
                      <td className="px-3 py-2">Number of shares offered</td>
                    </tr>
                    <tr className="border-t border-gray-100">
                      <td className="px-3 py-2">Market Cap</td>
                      <td className="px-3 py-2">Expected valuation</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Navigation</p>
            <p className="text-sm text-gray-600">
              Use ◀ ▶ arrows to move between weeks. Click any date to filter events.
              Click ↻ to refresh data from the source.
            </p>
          </div>
        </div>
      ),
    },

    // Page 8: AI Screener
    {
      title: 'AI Screener',
      subtitle: 'Natural language stock search',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            The AI Screener finds US-listed stocks using plain English queries. Describe your
            criteria and receive a table of matching stocks with key metrics.
          </p>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Available Data Fields</p>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">
                <span className="font-medium text-gray-900">Returns:</span> Ticker, Company Name, Price, Market Cap, Beta, Dividend Yield, Volume, Sector, Industry
              </p>
              <p className="text-xs text-gray-500 mt-2">
                Note: Advanced metrics like P/E ratios, profit margins, and growth rates are not available through the screener.
              </p>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Example Queries</p>
            <div className="space-y-2">
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm font-mono text-gray-700">"Large cap tech stocks with high trading volume"</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm font-mono text-gray-700">"Healthcare companies with market cap over $10 billion"</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm font-mono text-gray-700">"Dividend paying stocks in the utilities sector"</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm font-mono text-gray-700">"Low beta financial stocks"</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm font-mono text-gray-700">"Small cap industrials with dividends"</p>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Workflow</p>
            <div className="border-l-2 border-gray-200 pl-4 space-y-3">
              <div>
                <p className="text-sm font-medium text-gray-900">1. Enter your query</p>
                <p className="text-sm text-gray-500">Use natural language with sector, market cap, or dividend criteria</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">2. Press Enter or click Send</p>
                <p className="text-sm text-gray-500">Processing takes 10–30 seconds</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">3. Export results</p>
                <p className="text-sm text-gray-500">Download as CSV or Excel for further analysis</p>
              </div>
            </div>
          </div>

          <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
            <p className="text-xs text-purple-900">
              <strong>Beta Feature:</strong> Results are saved to your session. You can navigate
              away and return without losing them.
            </p>
          </div>
        </div>
      ),
    },

    // Page 9: Navigation
    {
      title: 'Navigation',
      subtitle: 'Getting around the platform',
      content: (
        <div className="space-y-6">
          <p className="text-[15px] text-gray-600 leading-relaxed">
            The Dashboard provides multiple ways to navigate the platform. Use the fixed footer
            for quick access, the left sidebar for full navigation, or keyboard shortcuts.
          </p>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Quick Links Footer</p>
            <p className="text-sm text-gray-600 mb-3">
              Fixed at the bottom of the Dashboard, these buttons provide one-click access to major sections:
            </p>
            <div className="overflow-hidden rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-gray-100">
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs bg-blue-800 text-white px-2 py-0.5 rounded">/ chat</span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">AI chat for investment analysis and research</td>
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs bg-blue-600 text-white px-2 py-0.5 rounded">/ portfolio</span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">Manage portfolios, holdings, and transactions</td>
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs bg-blue-500 text-white px-2 py-0.5 rounded">/ analytics</span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">Advanced charts, heatmaps, and screeners</td>
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs bg-blue-400 text-white px-2 py-0.5 rounded">/ events</span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">Market news and economic calendar</td>
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs bg-cyan-600 text-white px-2 py-0.5 rounded">/ workflows</span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">Automated analysis and reporting workflows</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs bg-gray-500 text-white px-2 py-0.5 rounded">/ settings</span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">Account, preferences, and integrations</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Keyboard Shortcuts</p>
            <div className="overflow-hidden rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-gray-100">
                    <td className="px-4 py-2.5 text-gray-600">Open command palette</td>
                    <td className="px-4 py-2.5 text-right">
                      <kbd className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">⌘</kbd>
                      <span className="mx-1 text-gray-400">+</span>
                      <kbd className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">K</kbd>
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2.5 text-gray-600">New chat thread</td>
                    <td className="px-4 py-2.5 text-right">
                      <kbd className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">⌘</kbd>
                      <span className="mx-1 text-gray-400">+</span>
                      <kbd className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">N</kbd>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-500">
              <strong>Left Sidebar:</strong> The icon rail on the left provides access to all major
              sections. Icons are labeled on hover. Settings is located at the bottom of the rail.
            </p>
          </div>
        </div>
      ),
    },
  ];

  const handleNext = () => {
    if (currentPage < pages.length - 1) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handlePrev = () => {
    if (currentPage > 0) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleClose = () => {
    setCurrentPage(0);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-start px-6 pt-6 pb-4 border-b border-gray-100">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
              Dashboard Guide
            </p>
            <h2 className="text-xl font-semibold text-gray-900">
              {pages[currentPage].title}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {pages[currentPage].subtitle}
            </p>
          </div>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 p-1.5 hover:bg-gray-100 rounded-lg transition-colors -mr-1.5 -mt-1.5"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {pages[currentPage].content}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50/50">
          <div className="flex justify-between items-center">
            {/* Page indicator */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400 font-medium">
                {currentPage + 1} / {pages.length}
              </span>
              <div className="flex gap-1">
                {pages.map((_, index) => (
                  <button
                    key={index}
                    onClick={() => setCurrentPage(index)}
                    className={`h-1.5 rounded-full transition-all ${
                      index === currentPage
                        ? 'w-4'
                        : 'bg-gray-300 w-1.5 hover:bg-gray-400'
                    }`}
                    style={index === currentPage ? { backgroundColor: '#0051cc' } : undefined}
                  />
                ))}
              </div>
            </div>

            {/* Navigation buttons */}
            <div className="flex gap-2">
              {currentPage > 0 && (
                <button
                  onClick={handlePrev}
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg flex items-center gap-1 transition-colors"
                >
                  <ChevronLeft size={16} />
                  Back
                </button>
              )}
              <button
                onClick={currentPage === pages.length - 1 ? handleClose : handleNext}
                className="px-4 py-1.5 text-white text-sm font-medium rounded-lg flex items-center gap-1 transition-colors"
                style={{ backgroundColor: '#0051cc' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#0047b3'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#0051cc'}
              >
                {currentPage === pages.length - 1 ? (
                  'Close'
                ) : (
                  <>
                    Continue
                    <ChevronRight size={16} />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
