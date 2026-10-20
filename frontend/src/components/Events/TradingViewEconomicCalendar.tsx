/**
 * TradingViewEconomicCalendar Component
 *
 * Displays TradingView's Economic Calendar widget showing upcoming economic events.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewEconomicCalendarProps {
  colorTheme?: 'light' | 'dark';
  isTransparent?: boolean;
  locale?: string;
  countryFilter?: string;
  importanceFilter?: string;
  width?: number | string;
  height?: number | string;
}

const TradingViewEconomicCalendar: React.FC<TradingViewEconomicCalendarProps> = ({
  colorTheme = 'light',
  isTransparent = false,
  locale = 'en',
  countryFilter = 'ar,au,br,ca,cn,fr,de,in,id,it,jp,kr,mx,ru,sa,za,tr,gb,us,eu',
  importanceFilter = '-1,0,1',
  width = 400,
  height = 550,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing content
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-events.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      colorTheme,
      isTransparent,
      locale,
      countryFilter,
      importanceFilter,
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
  }, [colorTheme, isTransparent, locale, countryFilter, importanceFilter, width, height]);

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <div className="tradingview-widget-container__widget" style={{ height: 'calc(100% - 32px)', width: '100%' }} />
      <div className="tradingview-widget-copyright">
        <a href="https://www.tradingview.com/economic-calendar/" rel="noopener nofollow noreferrer" target="_blank">
          <span className="blue-text">Economic Calendar</span>
        </a>
        <span className="trademark"> by TradingView</span>
      </div>
    </div>
  );
};

export default memo(TradingViewEconomicCalendar);
