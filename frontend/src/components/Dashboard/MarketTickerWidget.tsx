import React, { useEffect, useRef, memo } from 'react';

function MarketTickerWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-tickers.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbols: [
        {
          proName: 'AMEX:SPY',
          title: 'S&P 500',
        },
        {
          proName: 'NASDAQ:QQQ',
          title: 'Nasdaq 100',
        },
        {
          proName: 'BATS:VIXY',
          title: 'VIX Short-Term',
        },
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
        .market-ticker-clean .tradingview-widget-copyright {
          display: none !important;
        }
        .market-ticker-clean {
          border-radius: 0.75rem;
          overflow: hidden;
        }
      `}</style>
    </div>
  );
}

export default memo(MarketTickerWidget);
