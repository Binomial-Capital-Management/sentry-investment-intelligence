import React, { useEffect, useRef, memo } from 'react';

function MarketFactorsWidget() {
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
      symbolsGroups: [
        {
          name: 'Factors',
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
  }, []);

  return (
    <>
      <h3 className="text-sm font-semibold text-gray-800 mb-2 px-1" style={{ marginTop: '-750px' }}>Market Factors</h3>
      <div className="tradingview-widget-container" style={{ height: '400px' }}>
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

export default memo(MarketFactorsWidget);
