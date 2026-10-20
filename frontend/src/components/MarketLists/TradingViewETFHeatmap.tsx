/**
 * TradingViewETFHeatmap Component
 *
 * Displays TradingView's ETF Heatmap widget showing all US ETFs.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewETFHeatmapProps {
  theme?: 'light' | 'dark';
  height?: string;
  locale?: string;
  blockSize?: string;
  blockColor?: string;
  grouping?: string;
}

const TradingViewETFHeatmap: React.FC<TradingViewETFHeatmapProps> = ({
  theme = 'light',
  height = '100%',
  locale = 'en',
  blockSize = 'volume',
  blockColor = 'change',
  grouping = 'asset_class',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing content
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-etf-heatmap.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      dataSource: 'AllUSEtf',
      blockSize: blockSize,
      blockColor: blockColor,
      grouping: grouping,
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
  }, [theme, locale, blockSize, blockColor, grouping]);

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ height, width: '100%' }}>
      <div className="tradingview-widget-container__widget" style={{ height: 'calc(100% - 32px)', width: '100%' }} />
      <div className="tradingview-widget-copyright">
        <a href="https://www.tradingview.com/heatmap/etf/" rel="noopener nofollow noreferrer" target="_blank">
          <span className="blue-text">ETF Heatmap</span>
        </a>
        <span className="trademark"> by TradingView</span>
      </div>
    </div>
  );
};

export default memo(TradingViewETFHeatmap);
