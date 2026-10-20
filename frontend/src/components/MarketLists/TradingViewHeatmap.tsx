/**
 * TradingView Stock Heatmap Widget
 *
 * Embeds TradingView's stock market heatmap widget showing performance by market cap.
 * Free to use under TradingView's terms of service.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewHeatmapProps {
  dataMode?: 'stock' | 'crypto';
  theme?: 'light' | 'dark';
  height?: string;
  locale?: string;
  symbolsGroups?: string[];
  blockSize?: string;
  blockColor?: string;
}

const TradingViewHeatmap: React.FC<TradingViewHeatmapProps> = ({
  dataMode = 'stock',
  theme = 'light',
  height = '100%',
  locale = 'en',
  symbolsGroups = [],
  blockSize = 'market_cap_basic',
  blockColor = 'change',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing scripts
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js';
    script.type = 'text/javascript';
    script.async = true;

    const config: any = {
      dataSource: dataMode === 'crypto' ? 'Crypto' : 'SPX500',
      blockSize: blockSize,
      blockColor: blockColor,
      grouping: 'sector',
      locale: locale,
      symbolUrl: '',
      colorTheme: theme,
      exchanges: [],
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
  }, [dataMode, theme, locale, blockSize, blockColor, symbolsGroups]);

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
          href={dataMode === 'crypto'
            ? 'https://www.tradingview.com/heatmap/crypto/'
            : 'https://www.tradingview.com/heatmap/stock/'
          }
          rel="noopener nofollow noreferrer"
          target="_blank"
          style={{ color: '#0066CC', textDecoration: 'none' }}
        >
          <span className="blue-text">{dataMode === 'crypto' ? 'Crypto' : 'Stock'} Heatmap</span>
        </a>
        <span className="trademark" style={{ color: '#605E5C' }}> by TradingView</span>
      </div>
    </div>
  );
};

export default memo(TradingViewHeatmap);
