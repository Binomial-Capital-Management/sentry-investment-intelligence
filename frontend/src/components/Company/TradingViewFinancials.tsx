/**
 * TradingViewFinancials Component
 *
 * Displays TradingView's Financials widget showing fundamental financial data.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewFinancialsProps {
  symbol: string;
  colorTheme?: 'light' | 'dark';
  displayMode?: 'regular' | 'compact';
  isTransparent?: boolean;
  locale?: string;
  width?: number | string;
  height?: number | string;
}

const TradingViewFinancials: React.FC<TradingViewFinancialsProps> = ({
  symbol,
  colorTheme = 'light',
  displayMode = 'regular',
  isTransparent = false,
  locale = 'en',
  width = 400,
  height = 550,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing content
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-financials.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      symbol,
      colorTheme,
      displayMode,
      isTransparent,
      locale,
      width,
      height,
    };

    script.innerHTML = JSON.stringify(config);
    containerRef.current.appendChild(script);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [symbol, colorTheme, displayMode, isTransparent, locale, width, height]);

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <div className="tradingview-widget-container__widget" />
      <div className="tradingview-widget-copyright">
        <a href={`https://www.tradingview.com/symbols/${symbol.replace(':', '-')}/financials-overview/`} rel="noopener nofollow noreferrer" target="_blank">
          <span className="blue-text">{symbol} fundamentals</span>
        </a>
        <span className="trademark"> by TradingView</span>
      </div>
    </div>
  );
};

export default memo(TradingViewFinancials);
