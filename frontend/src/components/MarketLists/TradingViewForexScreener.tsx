/**
 * TradingViewForexScreener Component
 *
 * Displays TradingView's Forex Screener widget for currency pair analysis.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewForexScreenerProps {
  theme?: 'light' | 'dark';
  height?: string;
  locale?: string;
  defaultColumn?: string;
  defaultScreen?: string;
  market?: string;
  showToolbar?: boolean;
}

const TradingViewForexScreener: React.FC<TradingViewForexScreenerProps> = ({
  theme = 'light',
  height = '100%',
  locale = 'en',
  defaultColumn = 'overview',
  defaultScreen = 'general',
  market = 'forex',
  showToolbar = true,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing content
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-screener.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      width: '100%',
      height: '100%',
      defaultColumn: defaultColumn,
      defaultScreen: defaultScreen,
      market: market,
      showToolbar: showToolbar,
      colorTheme: theme,
      locale: locale,
    };

    script.innerHTML = JSON.stringify(config);
    containerRef.current.appendChild(script);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [theme, locale, defaultColumn, defaultScreen, market, showToolbar]);

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ height, width: '100%' }}>
      <div className="tradingview-widget-container__widget" style={{ height: 'calc(100% - 32px)', width: '100%' }} />
      <div className="tradingview-widget-copyright">
        <a href="https://www.tradingview.com/" rel="noopener nofollow noreferrer" target="_blank">
          <span className="blue-text">Forex Screener</span>
        </a>
        <span className="trademark"> by TradingView</span>
      </div>
    </div>
  );
};

export default memo(TradingViewForexScreener);
