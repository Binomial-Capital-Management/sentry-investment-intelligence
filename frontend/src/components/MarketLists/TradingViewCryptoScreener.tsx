/**
 * TradingView Crypto Screener Widget
 *
 * Embeds TradingView's crypto screener showing top gainers and market overview.
 * Free to use under TradingView's terms of service.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewCryptoScreenerProps {
  theme?: 'light' | 'dark';
  height?: string;
  locale?: string;
  defaultColumn?: string;
  defaultScreen?: string;
  showToolbar?: boolean;
}

const TradingViewCryptoScreener: React.FC<TradingViewCryptoScreenerProps> = ({
  theme = 'light',
  height = '100%',
  locale = 'en',
  defaultColumn = 'overview',
  defaultScreen = 'top_gainers',
  showToolbar = true,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing scripts
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
      showToolbar: showToolbar,
      locale: locale,
      market: 'crypto',
      colorTheme: theme,
    };

    script.innerHTML = JSON.stringify(config);
    containerRef.current.appendChild(script);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [theme, locale, defaultColumn, defaultScreen, showToolbar]);

  return (
    <div
      className="tradingview-widget-container"
      ref={containerRef}
      style={{
        height,
        width: '100%',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        className="tradingview-widget-container__widget"
        style={{ height: 'calc(100% - 32px)', width: '100%' }}
      />
      <div
        className="tradingview-widget-copyright"
        style={{
          fontSize: '11px',
          color: '#605E5C',
          textAlign: 'center',
          padding: '4px 0',
        }}
      >
        <a
          href="https://www.tradingview.com/"
          rel="noopener nofollow noreferrer"
          target="_blank"
          style={{ color: '#0066CC', textDecoration: 'none' }}
        >
          <span className="blue-text">Track all markets on TradingView</span>
        </a>
      </div>
    </div>
  );
};

export default memo(TradingViewCryptoScreener);
