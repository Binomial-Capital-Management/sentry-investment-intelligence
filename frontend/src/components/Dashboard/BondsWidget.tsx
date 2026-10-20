import React, { useEffect, useRef, memo } from 'react';

function BondsWidget() {
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
      symbolsGroups: [
        {
          name: 'Bonds',
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
      <h3 className="text-sm font-semibold text-gray-800 mb-2 px-1" style={{ marginTop: '-75px' }}>Fixed Income</h3>
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

export default memo(BondsWidget);
