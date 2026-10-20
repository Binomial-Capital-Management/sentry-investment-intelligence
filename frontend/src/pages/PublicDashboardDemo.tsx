import { useState, useMemo, useEffect, useRef, memo } from 'react';
import Plot from 'react-plotly.js';
import { Activity, Home, MessageCircle, Briefcase, TrendingUp, Calendar, Network, Zap, Settings, ChevronDown, ChevronLeft, ChevronRight, Bitcoin, Landmark, Sparkles, Rocket, RefreshCw } from 'lucide-react';

// Dummy portfolios for demo
const DEMO_PORTFOLIOS = [
  {
    id: 'demo-1',
    name: 'Tech Growth Portfolio',
    tickers: ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'TSLA'],
    value: 1250000,
    is_default: true,
  },
  {
    id: 'demo-2',
    name: 'Value Stocks',
    tickers: ['BRK.B', 'JPM', 'JNJ', 'PG'],
    value: 875000,
    is_default: false,
  },
  {
    id: 'demo-3',
    name: 'Dividend Income',
    tickers: ['KO', 'PG', 'MCD', 'VZ', 'T', 'XOM', 'CVX'],
    value: 620000,
    is_default: false,
  },
];

// Market regions for demo
const marketRegions = [
  { id: 'us', label: 'US Markets', flagImage: '/flags/usa.png' },
  { id: 'eu', label: 'EU Markets', flagImage: '/flags/europeanunion.png' },
  { id: 'china', label: 'China', flagImage: '/flags/china.png' },
  { id: 'korea', label: 'Korea', flagImage: '/flags/korea.png' },
  { id: 'japan', label: 'Japan', flagImage: '/flags/japan.png' },
];

const pills = [
  { id: 'markets', label: 'US Markets', hasDropdown: true },
  { id: 'crypto', label: 'Crypto', icon: Bitcoin },
  { id: 'macro', label: 'Macro & Alternatives', icon: Landmark },
  { id: 'earnings', label: 'Earnings', icon: TrendingUp },
  { id: 'ipos', label: 'Recent IPOs', icon: Rocket },
  { id: 'screener', label: 'AI Screener', icon: Sparkles },
];

// Generate dummy historical data for the last 30 days
const generateDummyHistory = () => {
  const days = 30;
  const startValue = 2500000;
  const history = [];

  for (let i = 0; i < days; i++) {
    const date = new Date();
    date.setDate(date.getDate() - (days - i - 1));
    const randomChange = (Math.random() - 0.48) * 0.02;
    const value = startValue * (1 + (randomChange * (i + 1) / days) + (Math.random() - 0.5) * 0.01);
    history.push({
      date: date.toISOString().split('T')[0],
      totalValue: value,
    });
  }
  return history;
};

// ==================== TradingView Widgets ====================

// Market Ticker Widget (US)
const DemoMarketTickerWidget = memo(function DemoMarketTickerWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-tickers.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: 'AMEX:SPY', title: 'S&P 500' },
        { proName: 'NASDAQ:QQQ', title: 'Nasdaq 100' },
        { proName: 'BATS:VIXY', title: 'VIX Short-Term' },
      ],
      colorTheme: 'light',
      isTransparent: false,
      showSymbolLogo: true,
      locale: 'en',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container market-ticker-clean rounded-lg overflow-hidden" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <style>{`
        .market-ticker-clean .tradingview-widget-copyright { display: none !important; }
        .market-ticker-clean { border-radius: 0.75rem; overflow: hidden; }
      `}</style>
    </div>
  );
});

// EU Market Ticker Widget
const DemoEUMarketTickerWidget = memo(function DemoEUMarketTickerWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-tickers.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: 'AMEX:FEZ', title: 'Euro STOXX 50' },
        { proName: 'AMEX:EWG', title: 'Germany DAX' },
        { proName: 'AMEX:EWU', title: 'UK FTSE' },
      ],
      colorTheme: 'light',
      isTransparent: false,
      showSymbolLogo: true,
      locale: 'en',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container market-ticker-clean rounded-lg overflow-hidden" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <style>{'.market-ticker-clean .tradingview-widget-copyright { display: none !important; }'}</style>
    </div>
  );
});

// Crypto Ticker Widget
const DemoCryptoTickerWidget = memo(function DemoCryptoTickerWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-tickers.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: 'BITSTAMP:BTCUSD', title: 'Bitcoin' },
        { proName: 'BITSTAMP:ETHUSD', title: 'Ethereum' },
        { proName: 'BINANCE:SOLUSD', title: 'Solana' },
      ],
      colorTheme: 'light',
      isTransparent: false,
      showSymbolLogo: true,
      locale: 'en',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container market-ticker-clean rounded-lg overflow-hidden" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <style>{'.market-ticker-clean .tradingview-widget-copyright { display: none !important; }'}</style>
    </div>
  );
});

// Macro Ticker Widget
const DemoMacroTickerWidget = memo(function DemoMacroTickerWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-tickers.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: 'TVC:DXY', title: 'US Dollar Index' },
        { proName: 'TVC:GOLD', title: 'Gold' },
        { proName: 'NYMEX:CL1!', title: 'Crude Oil' },
      ],
      colorTheme: 'light',
      isTransparent: false,
      showSymbolLogo: true,
      locale: 'en',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container market-ticker-clean rounded-lg overflow-hidden" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <style>{'.market-ticker-clean .tradingview-widget-copyright { display: none !important; }'}</style>
    </div>
  );
});

// User Holdings Widget (TradingView Market Quotes)
const DemoUserHoldingsWidget = memo(function DemoUserHoldingsWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const symbols = [
      { name: 'NASDAQ:AAPL', displayName: 'AAPL' },
      { name: 'NASDAQ:MSFT', displayName: 'MSFT' },
      { name: 'NASDAQ:NVDA', displayName: 'NVDA' },
      { name: 'NASDAQ:GOOGL', displayName: 'GOOGL' },
      { name: 'NASDAQ:META', displayName: 'META' },
    ];

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      title: 'My Top Holdings',
      width: '100%',
      height: 235,
      locale: 'en',
      showSymbolLogo: true,
      symbolsGroups: [{ name: 'Holdings', symbols: symbols }],
      colorTheme: 'light',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <>
      <h3 className="text-sm font-semibold text-gray-800 mb-2 px-1">My Top Holdings</h3>
      <div className="tradingview-widget-container" style={{ height: '1000px' }}>
        <div className="tradingview-widget-container__widget" ref={container}></div>
        <style>{'.tradingview-widget-copyright { display: none !important; }'}</style>
      </div>
    </>
  );
});

// Market Factors Widget
const DemoMarketFactorsWidget = memo(function DemoMarketFactorsWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const symbols = [
      { name: 'AMEX:XLK', displayName: 'Technology' },
      { name: 'AMEX:XLF', displayName: 'Financials' },
      { name: 'AMEX:XLE', displayName: 'Energy' },
      { name: 'AMEX:XLV', displayName: 'Healthcare' },
      { name: 'AMEX:XLP', displayName: 'Consumer Staples' },
      { name: 'AMEX:XLY', displayName: 'Consumer Discretionary' },
      { name: 'AMEX:GLD', displayName: 'Gold' },
      { name: 'AMEX:UCO', displayName: 'Oil' },
      { name: 'AMEX:MTUM', displayName: 'Momentum' },
      { name: 'AMEX:VTV', displayName: 'Value' },
      { name: 'AMEX:UUP', displayName: 'US Dollar' },
    ];

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      title: 'Market Factors',
      width: '100%',
      height: 300,
      locale: 'en',
      showSymbolLogo: true,
      symbolsGroups: [{ name: 'Factors', symbols: symbols }],
      colorTheme: 'light',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <>
      <h3 className="text-sm font-semibold text-gray-800 mb-2 px-1" style={{ marginTop: '-750px' }}>Market Factors</h3>
      <div className="tradingview-widget-container" style={{ height: '400px' }}>
        <div className="tradingview-widget-container__widget" ref={container}></div>
        <style>{'.tradingview-widget-copyright { display: none !important; }'}</style>
      </div>
    </>
  );
});

// Hotlists Widget
const DemoHotlistsWidget = memo(function DemoHotlistsWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-hotlists.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      colorTheme: 'light',
      dateRange: '3M',
      exchange: 'NASDAQ',
      showChart: false,
      locale: 'en',
      largeChartUrl: '',
      isTransparent: false,
      showSymbolLogo: false,
      showFloatingTooltip: false,
      width: '100%',
      height: 300,
      plotLineColorGrowing: 'rgba(56, 118, 29, 1)',
      plotLineColorFalling: 'rgba(255, 0, 0, 1)',
      gridLineColor: 'rgba(240, 243, 250, 0)',
      scaleFontColor: 'rgba(19, 23, 34, 1)',
      belowLineFillColorGrowing: 'rgba(39, 78, 19, 0.12)',
      belowLineFillColorFalling: 'rgba(153, 0, 0, 0.12)',
      belowLineFillColorGrowingBottom: 'rgba(41, 98, 255, 0)',
      belowLineFillColorFallingBottom: 'rgba(41, 98, 255, 0)',
      symbolActiveColor: 'rgba(249, 203, 156, 0.12)',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <>
      <h3 className="text-sm font-semibold text-gray-800 mb-2 px-1" style={{ marginTop: '-75px' }}>Market Movers</h3>
      <div className="tradingview-widget-container" style={{ height: '400px' }}>
        <div className="tradingview-widget-container__widget" ref={container}></div>
        <style>{'.tradingview-widget-copyright { display: none !important; }'}</style>
      </div>
    </>
  );
});

// Bonds Widget
const DemoBondsWidget = memo(function DemoBondsWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const symbols = [
      { name: 'NASDAQ:TLT', displayName: 'Long-term Treasuries' },
      { name: 'AMEX:HYG', displayName: 'High Yield Corporate Bonds' },
      { name: 'AMEX:SGOV', displayName: 'Short-term Treasuries' },
      { name: 'AMEX:AGG', displayName: 'Aggregate Bonds' },
      { name: 'NASDAQ:IEF', displayName: 'Mid-term Treasuries' },
      { name: 'AMEX:JNK', displayName: 'Junk Bonds' },
    ];

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      title: 'Fixed Income',
      width: '100%',
      height: 270,
      locale: 'en',
      showSymbolLogo: true,
      symbolsGroups: [{ name: 'Bonds', symbols: symbols }],
      colorTheme: 'light',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <>
      <h3 className="text-sm font-semibold text-gray-800 mb-2 px-1" style={{ marginTop: '-75px' }}>Fixed Income</h3>
      <div className="tradingview-widget-container" style={{ height: '400px' }}>
        <div className="tradingview-widget-container__widget" ref={container}></div>
        <style>{'.tradingview-widget-copyright { display: none !important; }'}</style>
      </div>
    </>
  );
});

// Crypto Screener Widget
const DemoCryptoScreenerWidget = memo(function DemoCryptoScreenerWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-screener.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      defaultColumn: 'overview',
      screener_type: 'crypto_mkt',
      displayCurrency: 'USD',
      colorTheme: 'light',
      isTransparent: false,
      locale: 'en',
      width: '100%',
      height: 550,
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <style>{'.tradingview-widget-copyright { display: none !important; }'}</style>
    </div>
  );
});

// Commodities Widget
const DemoCommoditiesWidget = memo(function DemoCommoditiesWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      title: 'Commodities',
      width: '100%',
      height: 300,
      locale: 'en',
      showSymbolLogo: true,
      symbolsGroups: [{
        name: 'Commodities',
        symbols: [
          { name: 'TVC:GOLD', displayName: 'Gold' },
          { name: 'TVC:SILVER', displayName: 'Silver' },
          { name: 'NYMEX:CL1!', displayName: 'Crude Oil' },
          { name: 'NYMEX:NG1!', displayName: 'Natural Gas' },
        ],
      }],
      colorTheme: 'light',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <style>{'.tradingview-widget-copyright { display: none !important; }'}</style>
    </div>
  );
});

// Forex Widget
const DemoForexWidget = memo(function DemoForexWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      title: 'Currencies',
      width: '100%',
      height: 300,
      locale: 'en',
      showSymbolLogo: true,
      symbolsGroups: [{
        name: 'Forex',
        symbols: [
          { name: 'FX:EURUSD', displayName: 'EUR/USD' },
          { name: 'FX:GBPUSD', displayName: 'GBP/USD' },
          { name: 'FX:USDJPY', displayName: 'USD/JPY' },
          { name: 'TVC:DXY', displayName: 'US Dollar Index' },
        ],
      }],
      colorTheme: 'light',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <style>{'.tradingview-widget-copyright { display: none !important; }'}</style>
    </div>
  );
});

// Economic Calendar Widget
const DemoEconomicCalendarWidget = memo(function DemoEconomicCalendarWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-events.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      colorTheme: 'light',
      isTransparent: false,
      width: '100%',
      height: 400,
      locale: 'en',
      importanceFilter: '-1,0,1',
      countryFilter: 'us,eu,gb,jp,cn',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <style>{'.tradingview-widget-copyright { display: none !important; }'}</style>
    </div>
  );
});

// ==================== Demo Components ====================

// Demo Market Pill Selector Component
const DemoMarketPillSelector = ({ selectedMarket, selectedPill, onMarketSelect, onPillSelect }: {
  selectedMarket: typeof marketRegions[0];
  selectedPill: string;
  onMarketSelect: (market: typeof marketRegions[0]) => void;
  onPillSelect: (pillId: string) => void;
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const formatDate = () => {
    const now = new Date();
    return now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="flex flex-col md:flex-row items-start md:items-center justify-between px-4 md:px-6 py-3 bg-white gap-3">
      {/* Left side - Pills */}
      <div className="flex items-center gap-2 flex-wrap">
        {pills.map((pill) => (
          <div key={pill.id} className="relative">
            <button
              onClick={() => {
                onPillSelect(pill.id);
                if (pill.id === 'markets') {
                  setIsDropdownOpen(!isDropdownOpen);
                }
              }}
              className={`
                flex items-center justify-center gap-2 px-4 py-2 rounded-full text-sm font-medium
                transition-all duration-200 min-w-[88px] sm:min-w-[110px] border
                ${selectedPill === pill.id
                  ? 'border-blue-500 text-blue-600 bg-blue-50'
                  : 'border-gray-300 text-gray-700 bg-transparent hover:border-gray-400 hover:bg-gray-50'
                }
              `}
            >
              {pill.id === 'markets' && (
                <img src={selectedMarket.flagImage} alt="" className="w-4 h-3 object-cover rounded-sm" />
              )}
              {pill.icon && pill.id !== 'markets' && (
                <pill.icon
                  size={16}
                  className={`flex-shrink-0 ${
                    pill.id === 'earnings' ? 'text-blue-600' :
                    pill.id === 'ipos' ? 'text-indigo-600' :
                    pill.id === 'crypto' ? 'text-orange-500' :
                    pill.id === 'macro' ? 'text-emerald-600' :
                    pill.id === 'screener' ? 'text-purple-600' : ''
                  }`}
                />
              )}
              <span>{pill.id === 'markets' ? selectedMarket.label : pill.label}</span>
              {pill.id === 'screener' && (
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 rounded">Beta</span>
              )}
              {pill.hasDropdown && (
                <ChevronDown size={14} className={`transition-transform ${isDropdownOpen && selectedPill === 'markets' ? 'rotate-180' : ''}`} />
              )}
            </button>

            {/* Dropdown menu */}
            {pill.id === 'markets' && isDropdownOpen && selectedPill === 'markets' && (
              <div className="absolute top-full left-0 mt-1 w-40 bg-white border border-gray-200 rounded shadow-lg overflow-hidden z-50">
                {marketRegions.map((market) => (
                  <button
                    key={market.id}
                    onClick={() => {
                      onMarketSelect(market);
                      setIsDropdownOpen(false);
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors
                      ${selectedMarket.id === market.id ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-50'}`}
                  >
                    <img src={market.flagImage} alt="" className="w-4 h-3 object-cover rounded-sm" />
                    <span className="font-medium">{market.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Right side - Market status and sentiment */}
      <div className="flex items-center gap-3 md:gap-4 text-xs">
        <div className="flex items-center gap-2 text-gray-500">
          <span className="font-medium hidden sm:inline">{formatDate()}, EST</span>
          <span className="text-gray-300 hidden sm:inline">·</span>
          <span className="font-medium text-gray-600">Market Closed</span>
        </div>

        <div className="hidden md:flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5">
              {[...Array(8)].map((_, i) => (
                <div key={i} className={`w-0.5 h-3 rounded-sm ${i < 5 ? 'bg-yellow-500' : 'bg-gray-300'}`} />
              ))}
            </div>
            <span className="text-gray-600 font-medium">Neutral</span>
          </div>

          <div className="flex items-center gap-2 text-gray-400 text-xs">
            <span className="text-gray-300">·</span>
            <span>Updated 4:00 PM</span>
            <div className="p-1 opacity-50 cursor-default" title="Demo Mode">
              <RefreshCw size={12} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Demo Quick Insights Widget
const DemoQuickInsights = ({ pageType }: { pageType: string }) => {
  const insights = {
    markets: [
      'S&P 500 approaching all-time highs with tech sector leading gains',
      'Fed minutes suggest potential rate pause in upcoming meeting',
      'Earnings season showing better-than-expected results for mega-caps',
    ],
    crypto: [
      'Bitcoin ETF inflows continue strong momentum',
      'Ethereum staking yields remain attractive at 4.2%',
      'Layer 2 solutions seeing increased adoption',
    ],
    macro: [
      '10Y Treasury yield stabilizing around 4.5%',
      'Oil prices consolidating amid OPEC+ uncertainty',
      'Dollar index showing strength against major currencies',
    ],
  };

  const data = insights[pageType as keyof typeof insights] || insights.markets;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={16} className="text-purple-600" />
        <span className="text-xs font-medium text-purple-600 uppercase tracking-wider">AI-Generated Insights</span>
        <span className="text-xs text-gray-400 ml-auto">Demo Mode 🔒</span>
      </div>
      <ul className="space-y-2">
        {data.map((insight, idx) => (
          <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
            <span className="text-gray-400 mt-0.5">•</span>
            <span>{insight}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

// Demo Earnings Calendar
const DemoEarningsCalendar = () => {
  const demoEarnings = [
    { symbol: 'AAPL', date: 'Dec 2', time: '4:00 PM' },
    { symbol: 'MSFT', date: 'Dec 2', time: '4:00 PM' },
    { symbol: 'GOOGL', date: 'Dec 3', time: '4:00 PM' },
    { symbol: 'NVDA', date: 'Dec 3', time: '4:00 PM' },
    { symbol: 'META', date: 'Dec 4', time: '4:00 PM' },
    { symbol: 'AMZN', date: 'Dec 4', time: '4:00 PM' },
    { symbol: 'TSLA', date: 'Dec 5', time: '4:00 PM' },
  ];

  const weekDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const dates = ['Dec 2', 'Dec 3', 'Dec 4', 'Dec 5', 'Dec 6'];

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b">
        <h2 className="text-xl font-semibold text-gray-800">Earnings Calendar</h2>
        <div className="flex items-center gap-1">
          <div className="p-1.5 text-gray-400 cursor-default opacity-50"><Calendar size={14} /></div>
          <div className="p-1.5 text-gray-400 cursor-default opacity-50"><RefreshCw size={12} /></div>
          <div className="p-1.5 text-gray-400 cursor-default opacity-50"><ChevronLeft size={14} /></div>
          <div className="px-2.5 py-1 text-xs font-medium text-gray-400 cursor-default">Today</div>
          <div className="p-1.5 text-gray-400 cursor-default opacity-50"><ChevronRight size={14} /></div>
        </div>
      </div>

      {/* Week selector */}
      <div className="grid grid-cols-5 gap-1 px-6 py-2">
        {weekDays.map((day, idx) => {
          const dayEarnings = demoEarnings.filter(e => e.date === dates[idx]);
          const isSelected = idx === 0;
          return (
            <div
              key={day}
              className={`flex flex-col overflow-hidden rounded-md border ${isSelected ? 'border-blue-500' : 'border-gray-300'}`}
            >
              <div className="bg-gray-100 w-full py-1 text-center">
                <span className="text-[10px] font-medium text-gray-600">{day}</span>
              </div>
              <div className="bg-white flex flex-col items-center px-1.5 py-1.5">
                <span className={`text-xs font-bold mb-0.5 ${isSelected ? 'text-blue-600' : 'text-gray-900'}`}>{dates[idx]}</span>
                {dayEarnings.length > 0 ? (
                  <span className={`text-[9px] font-medium ${isSelected ? 'text-blue-600' : 'text-gray-700'}`}>
                    {dayEarnings.length} Calls
                  </span>
                ) : (
                  <span className="text-[9px] text-gray-400">No Calls</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Earnings list */}
      <div className="divide-y divide-gray-100 max-h-80 overflow-y-auto">
        {demoEarnings.filter(e => e.date === 'Dec 2').map((event, idx) => (
          <div key={idx} className="flex items-center gap-3 px-6 py-2.5 hover:bg-gray-50 transition-colors cursor-default opacity-70">
            <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-xs font-bold text-gray-600">
              {event.symbol.slice(0, 2)}
            </div>
            <div className="flex-1">
              <div className="font-medium text-sm text-gray-900">{event.symbol}</div>
              <div className="text-xs text-gray-500">{event.symbol}</div>
            </div>
            <div className="text-xs font-medium text-gray-600">Q4 '24 {event.time}</div>
          </div>
        ))}
      </div>
      <div className="px-6 py-3 border-t bg-gray-50 text-center">
        <span className="text-xs text-gray-400">Demo Mode - Sign up to view full calendar 🔒</span>
      </div>
    </div>
  );
};

// Demo Aggregated Portfolio Chart
const DemoAggregatedPortfolioChart = () => {
  const [viewMode, setViewMode] = useState<'twr' | 'value'>('twr');
  const aggregatedHistory = useMemo(() => generateDummyHistory(), []);

  const timeRanges = [
    { label: '1W', days: 7 },
    { label: '1M', days: 30 },
    { label: '3M', days: 90 },
    { label: '6M', days: 180 },
    { label: '1Y', days: 365 },
  ];

  const metrics = useMemo(() => {
    if (aggregatedHistory.length === 0) return null;
    const firstValue = aggregatedHistory[0].totalValue;
    const lastValue = aggregatedHistory[aggregatedHistory.length - 1].totalValue;
    const valueChange = lastValue - firstValue;
    const valueChangePercent = (valueChange / firstValue) * 100;
    return {
      currentValue: lastValue,
      startValue: firstValue,
      valueChange,
      valueChangePercent,
      twr: valueChangePercent,
      isPositive: valueChange >= 0,
    };
  }, [aggregatedHistory]);

  const chartData = useMemo(() => {
    if (aggregatedHistory.length === 0 || !metrics) return [];
    const dates = aggregatedHistory.map(h => h.date);

    if (viewMode === 'value') {
      const values = aggregatedHistory.map(h => h.totalValue);
      return [{
        x: dates, y: values, type: 'scatter' as const, mode: 'lines+markers' as const,
        name: 'Total Portfolio Value',
        marker: { size: 8, color: metrics.isPositive ? '#10b981' : '#ef4444' },
        line: { color: metrics.isPositive ? '#10b981' : '#ef4444', width: 2 },
        fill: 'tonexty' as const,
        fillcolor: metrics.isPositive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
        hovertemplate: '<b>%{x|%b %d, %Y}</b><br>Total Value: $%{y:,.0f}<br><extra></extra>',
      }];
    } else {
      const startValue = aggregatedHistory[0].totalValue;
      const twrValues = aggregatedHistory.map(h => ((h.totalValue - startValue) / startValue) * 100);
      return [{
        x: dates, y: twrValues, type: 'scatter' as const, mode: 'lines+markers' as const,
        name: 'Time-Weighted Return',
        marker: { size: 8, color: metrics.isPositive ? '#10b981' : '#ef4444' },
        line: { color: metrics.isPositive ? '#10b981' : '#ef4444', width: 2 },
        fill: 'tonexty' as const,
        fillcolor: metrics.isPositive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
        hovertemplate: '<b>%{x|%b %d, %Y}</b><br>TWR: %{y:.2f}%<br><extra></extra>',
      }];
    }
  }, [aggregatedHistory, metrics, viewMode]);

  const layout = {
    autosize: true, height: 280, margin: { l: 70, r: 20, t: 10, b: 60 },
    paper_bgcolor: '#FFFFFF', plot_bgcolor: '#fafafa',
    xaxis: { showgrid: true, gridcolor: '#e5e7eb', zeroline: false, showline: false, type: 'date' as const, tickfont: { size: 10, color: '#6b7280' }, tickangle: -45, tickformat: '%d %b', nticks: 8 },
    yaxis: { showgrid: true, gridcolor: '#e5e7eb', zeroline: false, showline: false, tickformat: viewMode === 'value' ? '$,.0f' : '.2f', ticksuffix: viewMode === 'value' ? '' : '%', tickfont: { size: 10, color: '#6b7280' }, nticks: 6 },
    hovermode: 'x unified' as const,
    font: { family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', size: 10, color: '#6b7280' },
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Aggregate Performance</h3>
          {metrics && (
            <div className="flex items-baseline gap-3 mt-1">
              {viewMode === 'value' ? (
                <>
                  <span className="text-2xl font-semibold text-gray-900">
                    ${metrics.currentValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                  </span>
                  <span className={`text-sm font-semibold ${metrics.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                    {metrics.isPositive ? '+' : ''}${Math.abs(metrics.valueChange).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    {' '}({metrics.isPositive ? '+' : ''}{metrics.valueChangePercent.toFixed(2)}%)
                  </span>
                </>
              ) : (
                <>
                  <span className="text-2xl font-semibold text-gray-900">{metrics.isPositive ? '+' : ''}{metrics.twr.toFixed(2)}%</span>
                  <span className="text-sm text-gray-500">Time-Weighted Return</span>
                </>
              )}
              <span className="text-xs text-gray-500">{DEMO_PORTFOLIOS.length} portfolios</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-4">
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            <button onClick={() => setViewMode('twr')} className={`px-3 py-1 text-xs font-medium rounded transition-colors ${viewMode === 'twr' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}>TWR</button>
            <button onClick={() => setViewMode('value')} className={`px-3 py-1 text-xs font-medium rounded transition-colors ${viewMode === 'value' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}>Total Value</button>
          </div>
          <div className="flex space-x-2">
            {timeRanges.map((range, idx) => (
              <div key={range.days} className={`px-3 py-1 text-sm rounded-lg cursor-default select-none ${idx === 1 ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-400 opacity-60'}`}>{range.label}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 flex justify-start items-start">
        <Plot data={chartData} layout={layout} config={{ displayModeBar: false, responsive: true }} style={{ width: '100%' }} useResizeHandler={true} />
      </div>
    </div>
  );
};

// ==================== Main Component ====================

const PublicDashboardDemo = () => {
  const [selectedMarket, setSelectedMarket] = useState(marketRegions[0]);
  const [selectedPill, setSelectedPill] = useState('markets');

  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden">
      {/* Simplified System Bar */}
      <div className="flex items-center justify-between px-3 w-full h-12 bg-white border-b border-gray-200 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-gray-900 text-base font-medium">Sentry</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-blue-500" />
            <span className="text-gray-500 text-xs">DEMO</span>
          </div>
          <div className="flex items-center gap-1">
            <Activity size={10} className="text-green-600" />
            <span className="text-gray-500 text-xs">Read-Only</span>
          </div>
        </div>
        <div className="flex items-center gap-2 cursor-default opacity-70" title="Demo User Profile">
          <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-semibold" style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>DU</div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Navigation Rail */}
        <div className="w-16 flex flex-col bg-white border-r border-gray-200 shadow-sm">
          <div className="flex items-center justify-center py-3 border-b border-gray-200">
            <img src="/binomial-icon-logo.png" alt="Binomial" className="w-8 h-8" />
          </div>
          <div className="flex-1 flex flex-col items-center pt-1 pb-1">
            {[
              { icon: Home, label: 'Home', color: '#0078D4', active: true },
              { icon: MessageCircle, label: 'Chat', color: '#8764B8', active: false },
              { icon: Briefcase, label: 'Portfolios', color: '#00897B', active: false },
              { icon: TrendingUp, label: 'Analytics', color: '#FF8C00', active: false },
              { icon: Calendar, label: 'Events', color: '#E3008C', active: false },
              { icon: Network, label: 'Graph', color: '#143E7F', active: false },
              { icon: Zap, label: 'Flow', color: '#00BCF2', active: false },
            ].map((item, idx) => {
              const Icon = item.icon;
              return (
                <div key={idx} className="relative flex flex-col items-center justify-center w-full h-14" style={{ cursor: item.active ? 'default' : 'not-allowed', opacity: item.active ? 1 : 0.5 }} title={item.active ? item.label : `${item.label} (Demo Only)`}>
                  <Icon size={24} strokeWidth={item.active ? 3 : 2} className="transition-all duration-200" style={{ color: item.active ? item.color : '#6b7280', opacity: item.active ? 1 : 0.6 }} />
                  <span className="text-xs mt-1" style={{ fontWeight: item.active ? 600 : 400, color: item.active ? item.color : '#6b7280' }}>{item.label}</span>
                </div>
              );
            })}
          </div>
          <div className="flex flex-col items-center pb-3 pt-1 border-t border-gray-200">
            <div className="flex flex-col items-center justify-center w-full h-14 cursor-not-allowed opacity-50" title="Setup (Demo Only)">
              <Settings size={24} strokeWidth={2} className="text-gray-500 opacity-60" />
              <span className="text-xs mt-1 text-gray-500">Setup</span>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 h-full overflow-hidden" style={{ background: 'var(--bg-base)' }}>
          <div className="h-full p-0 max-w-[1600px] mx-auto w-full overflow-y-auto pt-3 pb-20">
            {/* Header Section */}
            <div className="px-4 md:px-6 py-2 border-b border-gray-300 bg-white">
              <h1 className="text-xl md:text-2xl font-semibold mb-0.5 text-gray-800">Welcome, Demo User</h1>
              <p className="text-xs md:text-sm text-gray-600">Sentry Investment Intelligence — Empowering Smarter Investments</p>
            </div>

            {/* Market Pill Selector */}
            <div className="bg-white mb-4">
              <DemoMarketPillSelector selectedMarket={selectedMarket} selectedPill={selectedPill} onMarketSelect={setSelectedMarket} onPillSelect={setSelectedPill} />
            </div>

            {/* Market Indexes Row */}
            <div className="px-4 md:px-6 mb-2">
              <div className="max-w-2xl">
                {selectedPill === 'crypto' ? (
                  <DemoCryptoTickerWidget />
                ) : selectedPill === 'macro' ? (
                  <DemoMacroTickerWidget />
                ) : selectedPill === 'screener' || selectedPill === 'earnings' || selectedPill === 'ipos' ? (
                  <DemoMarketTickerWidget />
                ) : (
                  <>
                    {selectedMarket.id === 'us' && <DemoMarketTickerWidget />}
                    {selectedMarket.id === 'eu' && <DemoEUMarketTickerWidget />}
                    {(selectedMarket.id === 'china' || selectedMarket.id === 'japan' || selectedMarket.id === 'korea') && <DemoMarketTickerWidget />}
                  </>
                )}
              </div>
            </div>

            {/* Two Column Layout */}
            <div className="px-4 md:px-6 -mt-1">
              <div className="grid grid-cols-1 lg:grid-cols-[1fr_450px] gap-5 items-start">
                {/* Left Column */}
                <div className="flex flex-col">
                  {selectedPill === 'screener' ? (
                    <div className="bg-white border border-gray-200 rounded-lg p-6 text-center">
                      <Sparkles size={48} className="text-purple-400 mx-auto mb-4" />
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">AI Screener</h3>
                      <p className="text-sm text-gray-500 mb-4">Advanced AI-powered stock screening with natural language queries</p>
                      <span className="text-xs text-gray-400">Demo Mode - Sign up to access 🔒</span>
                    </div>
                  ) : selectedPill === 'earnings' ? (
                    <div className="mb-6">
                      <DemoEarningsCalendar />
                    </div>
                  ) : selectedPill === 'ipos' ? (
                    <div className="bg-white border border-gray-200 rounded-lg p-6 text-center">
                      <Rocket size={48} className="text-indigo-400 mx-auto mb-4" />
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">Recent IPOs</h3>
                      <p className="text-sm text-gray-500 mb-4">Track recent and upcoming IPOs with detailed analysis</p>
                      <span className="text-xs text-gray-400">Demo Mode - Sign up to access 🔒</span>
                    </div>
                  ) : (
                    <>
                      {/* Quick Insights */}
                      <div className="mb-6">
                        <h2 className="text-xl font-semibold text-gray-900 mb-3">Quick Insights</h2>
                        <DemoQuickInsights pageType={selectedPill === 'markets' ? 'markets' : selectedPill === 'crypto' ? 'crypto' : 'macro'} />
                      </div>

                      {/* Crypto Screener - Only show on crypto pill */}
                      {selectedPill === 'crypto' && (
                        <div className="mb-6 mt-2">
                          <DemoCryptoScreenerWidget />
                        </div>
                      )}

                      {/* Macro Widgets - Only show on macro pill */}
                      {selectedPill === 'macro' && (
                        <>
                          <div className="mb-6 mt-2 grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <h2 className="text-lg font-semibold text-gray-900 mb-2">Commodities</h2>
                              <DemoCommoditiesWidget />
                            </div>
                            <div>
                              <h2 className="text-lg font-semibold text-gray-900 mb-2">Currencies</h2>
                              <DemoForexWidget />
                            </div>
                          </div>
                          <div className="mb-6">
                            <h2 className="text-lg font-semibold text-gray-900 mb-2">Economic Calendar</h2>
                            <DemoEconomicCalendarWidget />
                          </div>
                        </>
                      )}

                      {/* Aggregated Portfolio Performance Chart */}
                      <div className="mb-6 mt-0">
                        <DemoAggregatedPortfolioChart />
                      </div>

                      {/* Portfolio Table */}
                      <div className="mb-5">
                        <div className="bg-white border border-gray-300 rounded overflow-hidden">
                          <div className="px-4 py-3 bg-gray-50 border-b border-gray-300 flex justify-between items-center">
                            <h3 className="text-sm font-semibold text-gray-800">Portfolio Holdings</h3>
                            <span className="text-sm text-gray-400 cursor-default">View All 🔒</span>
                          </div>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="bg-gray-50 border-b border-gray-300">
                                  <th className="px-4 py-2 text-left font-semibold text-gray-600">Portfolio Name</th>
                                  <th className="px-4 py-2 text-right font-semibold text-gray-600">Value</th>
                                  <th className="px-4 py-2 text-right font-semibold text-gray-600">Positions</th>
                                  <th className="px-4 py-2 text-left font-semibold text-gray-600">Holdings</th>
                                  <th className="px-4 py-2 text-center font-semibold text-gray-600">Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {DEMO_PORTFOLIOS.map((portfolio) => (
                                  <tr key={portfolio.id} className="border-b border-gray-100 cursor-default transition-colors hover:bg-gray-50 opacity-70">
                                    <td className="px-4 py-3 font-medium text-gray-800">
                                      {portfolio.name} 🔒
                                      {portfolio.is_default && <span className="ml-2 text-xs px-1.5 py-0.5 bg-gray-200 text-gray-600 rounded">DEFAULT</span>}
                                    </td>
                                    <td className="px-4 py-3 text-right text-gray-800">${portfolio.value.toLocaleString()}</td>
                                    <td className="px-4 py-3 text-right text-gray-800">{portfolio.tickers.length}</td>
                                    <td className="px-4 py-3">
                                      <span className="text-gray-400 text-sm">Premium Feature 🔒</span>
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                      <span className="text-xs px-2 py-1 bg-green-600 text-white rounded">ACTIVE</span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>

                {/* Right Column: TradingView Widgets */}
                {(selectedPill === 'markets' || selectedPill === 'crypto' || selectedPill === 'macro') && (
                  <div className="w-full self-start -mt-20 flex flex-col gap-0">
                    <DemoUserHoldingsWidget />
                    <DemoMarketFactorsWidget />
                    <DemoHotlistsWidget />
                    <DemoBondsWidget />
                  </div>
                )}
              </div>
            </div>

            {/* Quick Links Footer */}
            <div className="fixed bottom-0 left-0 right-0 md:left-[72px] z-[5] flex justify-start items-center gap-2 px-6 py-4 border-t border-gray-300 text-sm" style={{ background: 'var(--bg-base)' }}>
              {[
                { label: '/ chat', color: 'bg-blue-800' },
                { label: '/ portfolio', color: 'bg-blue-600' },
                { label: '/ analytics', color: 'bg-blue-500' },
                { label: '/ events', color: 'bg-blue-400' },
                { label: '/ workflows', color: 'bg-cyan-600' },
                { label: '/ settings', color: 'bg-gray-500' },
              ].map((item, idx) => (
                <div key={idx} className={`text-white ${item.color} border-none rounded cursor-default px-3 py-1.5 text-xs font-medium shadow-sm opacity-60 select-none pointer-events-none`}>
                  {item.label} 🔒
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PublicDashboardDemo;
