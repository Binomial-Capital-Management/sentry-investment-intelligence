/**
 * TradingViewTimeline Component
 *
 * Displays TradingView's Timeline widget showing top market news stories.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewTimelineProps {
  displayMode?: 'regular' | 'adaptive';
  feedMode?: 'all_symbols' | 'market';
  colorTheme?: 'light' | 'dark';
  isTransparent?: boolean;
  locale?: string;
  width?: number | string;
  height?: number | string;
}

const TradingViewTimeline: React.FC<TradingViewTimelineProps> = ({
  displayMode = 'regular',
  feedMode = 'all_symbols',
  colorTheme = 'light',
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
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-timeline.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      displayMode,
      feedMode,
      colorTheme,
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
  }, [displayMode, feedMode, colorTheme, isTransparent, locale, width, height]);

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <div className="tradingview-widget-container__widget" style={{ height: 'calc(100% - 32px)', width: '100%' }} />
      <div className="tradingview-widget-copyright">
        <a href="https://www.tradingview.com/news/top-providers/tradingview/" rel="noopener nofollow noreferrer" target="_blank">
          <span className="blue-text">Top stories</span>
        </a>
        <span className="trademark"> by TradingView</span>
      </div>
    </div>
  );
};

export default memo(TradingViewTimeline);
