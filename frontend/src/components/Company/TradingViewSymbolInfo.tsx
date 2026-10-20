/**
 * TradingViewSymbolInfo Component
 *
 * Displays TradingView's Symbol Info widget showing performance metrics.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewSymbolInfoProps {
  symbol: string;
  colorTheme?: 'light' | 'dark';
  isTransparent?: boolean;
  locale?: string;
  width?: number | string;
}

const TradingViewSymbolInfo: React.FC<TradingViewSymbolInfoProps> = ({
  symbol,
  colorTheme = 'light',
  isTransparent = false,
  locale = 'en',
  width = '550',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing content
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-info.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      symbol,
      colorTheme,
      isTransparent,
      locale,
      width: String(width),
    };

    script.innerHTML = JSON.stringify(config);
    containerRef.current.appendChild(script);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [symbol, colorTheme, isTransparent, locale, width]);

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ width: '100%' }}>
      <div className="tradingview-widget-container__widget" />
      <div className="tradingview-widget-copyright">
        <a href={`https://www.tradingview.com/symbols/${symbol.replace(':', '-')}/`} rel="noopener nofollow noreferrer" target="_blank">
          <span className="blue-text">{symbol} performance</span>
        </a>
        <span className="trademark"> by TradingView</span>
      </div>
    </div>
  );
};

export default memo(TradingViewSymbolInfo);
