import React, { useEffect, useRef, memo } from 'react';

function MarketNewsWidget() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-timeline.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      displayMode: 'regular',
      feedMode: 'all_symbols',
      colorTheme: 'light',
      isTransparent: false,
      locale: 'en',
      width: '100%',
      height: 500,
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="tradingview-widget-container" style={{ height: '500px' }}>
      <div className="tradingview-widget-container__widget" ref={container}></div>
      <style>{`
        .tradingview-widget-copyright {
          display: none !important;
        }
      `}</style>
    </div>
  );
}

export default memo(MarketNewsWidget);
