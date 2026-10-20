/**
 * TradingView Crypto Heatmap Widget
 *
 * Embeds TradingView's cryptocurrency heatmap widget.
 * Free to use under TradingView's terms of service.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewCryptoHeatmapProps {
  theme?: 'light' | 'dark';
  height?: string;
  locale?: string;
}

const TradingViewCryptoHeatmap: React.FC<TradingViewCryptoHeatmapProps> = ({
  theme = 'light',
  height = '100%',
  locale = 'en',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing scripts
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-crypto-coins-heatmap.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      dataSource: 'Crypto',
      blockSize: 'market_cap_calc',
      blockColor: '24h_close_change|5',
      locale: locale,
      symbolUrl: '',
      colorTheme: theme,
      hasTopBar: false,
      isDataSetEnabled: false,
      isZoomEnabled: true,
      hasSymbolTooltip: true,
      isMonoSize: false,
      width: '100%',
      height: '100%',
    };

    script.innerHTML = JSON.stringify(config);
    containerRef.current.appendChild(script);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [theme, locale]);

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
          href="https://www.tradingview.com/heatmap/crypto/"
          rel="noopener nofollow noreferrer"
          target="_blank"
          style={{ color: '#0066CC', textDecoration: 'none' }}
        >
          <span className="blue-text">Crypto Heatmap</span>
        </a>
        <span className="trademark" style={{ color: '#605E5C' }}> by TradingView</span>
      </div>
    </div>
  );
};

export default memo(TradingViewCryptoHeatmap);
