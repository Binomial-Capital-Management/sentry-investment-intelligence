import React, { useEffect, useRef, memo } from 'react';

function HotlistsWidget() {
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
        <style>{`
          .tradingview-widget-copyright {
            display: none !important;
          }
        `}</style>
      </div>
    </>
  );
}

export default memo(HotlistsWidget);
