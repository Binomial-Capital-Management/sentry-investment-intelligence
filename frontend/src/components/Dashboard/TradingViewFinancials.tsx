import React, { useEffect, useRef, memo } from 'react';

interface TradingViewFinancialsProps {
  symbol: string;
}

function TradingViewFinancials({ symbol }: TradingViewFinancialsProps) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    // Clear previous widget
    container.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-financials.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbol: symbol,
      colorTheme: 'light',
      displayMode: 'regular',
      isTransparent: false,
      locale: 'en',
      width: '100%',
      height: 450,
    });

    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'tradingview-widget-container__widget';
    container.current.appendChild(widgetContainer);
    container.current.appendChild(script);
  }, [symbol]);

  return (
    <div className="tradingview-widget-container" ref={container} style={{ height: '450px' }}>
    </div>
  );
}

export default memo(TradingViewFinancials);
