import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '@clerk/clerk-react';
import { HelpCircle } from 'lucide-react';
import { usePortfolioStore } from '@/stores/portfolioStore';
import { DashboardGuidePanel } from '@/components/Dashboard/DashboardGuidePanel';
import AggregatedPortfolioChart from '@/components/Dashboard/AggregatedPortfolioChart';
import { MarketPillSelector } from '@/components/Dashboard/MarketPillSelector';
import MarketTickerWidget from '@/components/Dashboard/MarketTickerWidget';
import EUMarketTickerWidget from '@/components/Dashboard/EUMarketTickerWidget';
import ChinaMarketTickerWidget from '@/components/Dashboard/ChinaMarketTickerWidget';
import JapanMarketTickerWidget from '@/components/Dashboard/JapanMarketTickerWidget';
import KoreaMarketTickerWidget from '@/components/Dashboard/KoreaMarketTickerWidget';
import UserHoldingsWidget from '@/components/Dashboard/UserHoldingsWidget';
import HotlistsWidget from '@/components/Dashboard/HotlistsWidget';
import MarketFactorsWidget from '@/components/Dashboard/MarketFactorsWidget';
import BondsWidget from '@/components/Dashboard/BondsWidget';
import CryptoScreenerWidget from '@/components/Dashboard/CryptoScreenerWidget';
import CryptoTickerWidget from '@/components/Dashboard/CryptoTickerWidget';
import CommoditiesWidget from '@/components/Dashboard/CommoditiesWidget';
import ForexWidget from '@/components/Dashboard/ForexWidget';
import MacroTickerWidget from '@/components/Dashboard/MacroTickerWidget';
import EconomicCalendarWidget from '@/components/Dashboard/EconomicCalendarWidget';
import MarketNewsWidget from '@/components/Dashboard/MarketNewsWidget';
import QuickInsights from '@/components/Dashboard/QuickInsights';
import { AIScreenerInterface } from '@/components/Dashboard/AIScreenerInterface';
import { EarningsCalendar } from '@/components/Dashboard/EarningsCalendar';
import { IPOCalendar } from '@/components/Dashboard/IPOCalendar';

const Dashboard = () => {
  const navigate = useNavigate();
  const { user } = useUser();
  const { savedPortfolios, loadPortfolios } = usePortfolioStore();

  // Load from localStorage or default to 'us' and 'markets'
  const [selectedMarket, setSelectedMarket] = useState(() => {
    return localStorage.getItem('dashboard_selected_market') || 'us';
  });
  const [selectedPill, setSelectedPill] = useState(() => {
    return localStorage.getItem('dashboard_selected_pill') || 'markets';
  });
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    loadPortfolios();
  }, []);

  // Persist selectedMarket to localStorage
  useEffect(() => {
    localStorage.setItem('dashboard_selected_market', selectedMarket);
  }, [selectedMarket]);

  // Persist selectedPill to localStorage
  useEffect(() => {
    localStorage.setItem('dashboard_selected_pill', selectedPill);
  }, [selectedPill]);

  return (
    <div className="h-full w-full overflow-hidden flex justify-center" style={{ background: 'var(--bg-base)' }}>
      <div
        className="h-full w-full max-w-[2200px] px-20 overflow-y-auto pt-3 pb-20 transition-all duration-300"
        style={{ marginRight: showGuide ? '576px' : '0' }}
      >
        {/* Header Section */}
        <div className="py-2 border-b border-gray-300 bg-white">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl md:text-2xl font-semibold mb-0.5 text-gray-800">
                Welcome, {user?.firstName || user?.fullName || 'User'}
              </h1>
              <p className="text-xs md:text-sm text-gray-600">
                Sentry Investment Intelligence — Empowering Smarter Investments
              </p>
            </div>
            <button
              onClick={() => setShowGuide(true)}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              title="Dashboard Guide"
            >
              <HelpCircle size={20} />
            </button>
          </div>
        </div>

        {/* Market Pill Selector - scrolls with content */}
        <div className="bg-white mb-4">
          <MarketPillSelector
            initialMarket={selectedMarket}
            initialPill={selectedPill}
            onMarketChange={setSelectedMarket}
            onPillChange={setSelectedPill}
          />
        </div>

        {/* Market Indexes Row */}
        <div className="mb-2">
          {selectedPill === 'crypto' ? (
            <div className="max-w-2xl">
              <CryptoTickerWidget />
            </div>
          ) : selectedPill === 'macro' ? (
            <div className="max-w-2xl">
              <MacroTickerWidget />
            </div>
          ) : selectedPill === 'screener' || selectedPill === 'earnings' || selectedPill === 'ipos' ? (
            <div className="max-w-2xl">
              <MarketTickerWidget />
            </div>
          ) : (
            <>
              {selectedMarket === 'us' && (
                <div className="max-w-2xl">
                  <MarketTickerWidget />
                </div>
              )}
              {selectedMarket === 'eu' && (
                <div className="max-w-2xl">
                  <EUMarketTickerWidget />
                </div>
              )}
              {selectedMarket === 'china' && (
                <div className="max-w-2xl">
                  <ChinaMarketTickerWidget />
                </div>
              )}
              {selectedMarket === 'japan' && (
                <div className="max-w-xl">
                  <JapanMarketTickerWidget />
                </div>
              )}
              {selectedMarket === 'korea' && (
                <div className="max-w-sm">
                  <KoreaMarketTickerWidget />
                </div>
              )}
            </>
          )}
        </div>

        {/* Two Column Layout: Portfolio Content + Holdings Widget */}
        <div className="-mt-1">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6 items-start">
            {/* Left Column: Chart and Table OR AI Screener OR Earnings Calendar OR IPO Calendar */}
            <div className="flex flex-col">
              {selectedPill === 'screener' ? (
                <AIScreenerInterface />
              ) : selectedPill === 'earnings' ? (
                <div className="mb-6">
                  <EarningsCalendar />
                </div>
              ) : selectedPill === 'ipos' ? (
                <div className="mb-6">
                  <IPOCalendar />
                </div>
              ) : (
                <>
                  {/* Quick Insights Section - AI-generated insights per page type */}
                  <div className="mb-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-3">Quick Insights</h2>
                    <QuickInsights
                      pageType={selectedPill as 'markets' | 'crypto' | 'macro'}
                      region={selectedPill === 'markets' ? selectedMarket : undefined}
                    />
                  </div>

              {/* Market News Section - Only show on markets pill */}
              {selectedPill === 'markets' && (
                <div className="mb-6">
                  <h2 className="text-xl font-semibold text-gray-900 mb-3">Market News</h2>
                  <MarketNewsWidget />
                </div>
              )}

              {/* Crypto Screener Widget - Only show on crypto pill */}
              {selectedPill === 'crypto' && (
                <div className="mb-6 mt-2">
                  <CryptoScreenerWidget />
                </div>
              )}

              {/* Macro Widgets - Only show on macro pill */}
              {selectedPill === 'macro' && (
                <>
                  <div className="mb-6 mt-2 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900 mb-2">Commodities</h2>
                      <CommoditiesWidget />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900 mb-2">Currencies</h2>
                      <ForexWidget />
                    </div>
                  </div>

                  <div className="mb-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-2">Economic Calendar</h2>
                    <EconomicCalendarWidget />
                  </div>
                </>
              )}

              {/* Aggregated Portfolio Performance Chart */}
              {savedPortfolios.length > 0 && (
                <div className="mb-6 mt-0">
                  <AggregatedPortfolioChart />
                </div>
              )}

              {/* Portfolio Table */}
              {savedPortfolios.length > 0 && (
                <div className="mb-5 relative z-10">
                  <div className="bg-white border border-gray-300 rounded overflow-hidden shadow-sm">
                    <div className="px-4 py-3 bg-gray-50 border-b border-gray-300 flex justify-between items-center">
                      <h3 className="text-sm font-semibold text-gray-800">
                        Portfolio Holdings
                      </h3>
                      <button
                        onClick={() => navigate('/portfolio')}
                        className="text-sm text-blue-600 bg-transparent border-none cursor-pointer px-2 py-1 hover:text-blue-700"
                      >
                        View All
                      </button>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50 border-b border-gray-300">
                            <th className="px-4 py-2 text-left font-semibold text-gray-600">
                              Portfolio Name
                            </th>
                            <th className="px-4 py-2 text-right font-semibold text-gray-600">
                              Value
                            </th>
                            <th className="px-4 py-2 text-right font-semibold text-gray-600">
                              Positions
                            </th>
                            <th className="px-4 py-2 text-left font-semibold text-gray-600">
                              Holdings
                            </th>
                            <th className="px-4 py-2 text-center font-semibold text-gray-600">
                              Status
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {savedPortfolios.slice(0, 5).map((portfolio) => (
                            <tr
                              key={portfolio.id}
                              className="border-b border-gray-100 cursor-pointer transition-colors hover:bg-gray-50"
                              onClick={() => navigate('/portfolio')}
                            >
                              <td className="px-4 py-3 font-medium text-gray-800">
                                {portfolio.name}
                                {portfolio.is_default && (
                                  <span className="ml-2 text-xs px-1.5 py-0.5 bg-gray-200 text-gray-600 rounded">
                                    DEFAULT
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-3 text-right text-gray-800">
                                ${(portfolio.value || 0).toLocaleString()}
                              </td>
                              <td className="px-4 py-3 text-right text-gray-800">
                                {portfolio.tickers.length}
                              </td>
                              <td className="px-4 py-3">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    navigate(`/portfolio/${portfolio.id}`);
                                  }}
                                  className="text-blue-600 bg-transparent border-none cursor-pointer p-0 text-sm font-medium underline hover:text-blue-800"
                                >
                                  See more →
                                </button>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span className="text-xs px-2 py-1 bg-green-600 text-white rounded">
                                  ACTIVE
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
                </>
              )}
            </div>

            {/* Right Column: User Holdings Widget + Market Factors + Hotlists + Bonds */}
            {savedPortfolios.length > 0 && (
              <div className="w-full self-start flex flex-col gap-0">
                <UserHoldingsWidget />
                <MarketFactorsWidget />
                <HotlistsWidget />
                <BondsWidget />
              </div>
            )}
          </div>
        </div>

        {/* Quick Links Footer - Full Width */}
        <div className="fixed bottom-0 left-0 right-0 md:left-[72px] z-[5] flex justify-start items-center gap-2 px-6 md:px-12 py-4 border-t border-gray-300 text-sm" style={{ background: 'var(--bg-base)' }}>
          <button
            onClick={() => navigate('/chat')}
            className="text-white bg-blue-800 border-none rounded cursor-pointer px-3 py-1.5 text-xs font-medium transition-all shadow-sm hover:bg-blue-900 hover:shadow-md"
          >
            / chat
          </button>
          <button
            onClick={() => navigate('/portfolio')}
            className="text-white bg-blue-600 border-none rounded cursor-pointer px-3 py-1.5 text-xs font-medium transition-all shadow-sm hover:bg-blue-700 hover:shadow-md"
          >
            / portfolio
          </button>
          <button
            onClick={() => navigate('/market-lists')}
            className="text-white bg-blue-500 border-none rounded cursor-pointer px-3 py-1.5 text-xs font-medium transition-all shadow-sm hover:bg-blue-600 hover:shadow-md"
          >
            / analytics
          </button>
          <button
            onClick={() => navigate('/events')}
            className="text-white bg-blue-400 border-none rounded cursor-pointer px-3 py-1.5 text-xs font-medium transition-all shadow-sm hover:bg-blue-500 hover:shadow-md"
          >
            / events
          </button>
          <button
            onClick={() => navigate('/workflows')}
            className="text-white bg-cyan-600 border-none rounded cursor-pointer px-3 py-1.5 text-xs font-medium transition-all shadow-sm hover:bg-cyan-700 hover:shadow-md"
          >
            / workflows
          </button>
          <button
            onClick={() => navigate('/settings')}
            className="text-white bg-gray-500 border-none rounded cursor-pointer px-3 py-1.5 text-xs font-medium transition-all shadow-sm hover:bg-gray-600 hover:shadow-md"
          >
            / settings
          </button>
        </div>
      </div>

      {/* Dashboard Guide Panel (slides in from right) */}
      <DashboardGuidePanel isOpen={showGuide} onClose={() => setShowGuide(false)} />
    </div>
  );
};

export default Dashboard;
