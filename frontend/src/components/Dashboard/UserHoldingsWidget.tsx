import React, { useEffect, useRef, memo } from 'react';
import { usePortfolioStore } from '@/stores/portfolioStore';

function UserHoldingsWidget() {
  const container = useRef<HTMLDivElement>(null);
  const getTopHoldings = usePortfolioStore(state => state.getTopHoldings);

  useEffect(() => {
    if (!container.current) return;

    // Get top 5 holdings
    const topHoldings = getTopHoldings(5);

    // If no holdings, don't render widget
    if (topHoldings.length === 0) return;

    // Convert tickers to TradingView format
    const symbols = topHoldings.map(holding => ({
      name: holding.ticker.includes(':') ? holding.ticker : `NASDAQ:${holding.ticker}`,
      displayName: holding.ticker,
    }));

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
      symbolsGroups: [
        {
          name: 'Holdings',
          symbols: symbols,
        },
      ],
      colorTheme: 'light',
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, [getTopHoldings]);

  const topHoldings = getTopHoldings(5);

  // Don't render if no holdings
  if (topHoldings.length === 0) {
    return null;
  }

  return (
    <>
      <h3 className="text-sm font-semibold text-gray-800 mb-2 px-1">My Top Holdings</h3>
      <div className="tradingview-widget-container" style={{ height: '1000px' }}>
        <div className="tradingview-widget-container__widget" ref={container}></div>
        <style>{`
          .tradingview-widget-copyright {
            display: none !important;
          }
        `}</style>
      </div>
    </>
  );
}

export default memo(UserHoldingsWidget);
