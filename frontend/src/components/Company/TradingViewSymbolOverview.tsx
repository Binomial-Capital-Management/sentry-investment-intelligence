/**
 * TradingViewSymbolOverview Component
 *
 * Displays TradingView's Symbol Overview widget with detailed chart and technical indicators.
 */

import React, { useEffect, useRef, memo } from 'react';

interface TradingViewSymbolOverviewProps {
  symbol: string;
  displayName?: string;
  chartOnly?: boolean;
  width?: number | string;
  height?: number | string;
  locale?: string;
  colorTheme?: 'light' | 'dark';
  autosize?: boolean;
  showVolume?: boolean;
  showMA?: boolean;
  hideDateRanges?: boolean;
  hideMarketStatus?: boolean;
  hideSymbolLogo?: boolean;
  scalePosition?: 'left' | 'right';
  scaleMode?: 'Normal' | 'Logarithmic' | 'Percentage';
  fontFamily?: string;
  fontSize?: string;
  noTimeScale?: boolean;
  valuesTracking?: string;
  changeMode?: 'price-and-percent' | 'price-only';
  chartType?: 'area' | 'line' | 'candlesticks' | 'bars';
  maLineColor?: string;
  maLineWidth?: number;
  maLength?: number;
  lineType?: number;
  dateRanges?: string[];
  downColor?: string;
  upColor?: string;
  borderUpColor?: string;
  borderDownColor?: string;
  wickUpColor?: string;
  wickDownColor?: string;
}

const TradingViewSymbolOverview: React.FC<TradingViewSymbolOverviewProps> = ({
  symbol,
  displayName,
  chartOnly = false,
  width = '800',
  height = '600',
  locale = 'en',
  colorTheme = 'light',
  autosize = false,
  showVolume = true,
  showMA = true,
  hideDateRanges = false,
  hideMarketStatus = false,
  hideSymbolLogo = false,
  scalePosition = 'right',
  scaleMode = 'Normal',
  fontFamily = '-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif',
  fontSize = '10',
  noTimeScale = false,
  valuesTracking = '3',
  changeMode = 'price-only',
  chartType = 'candlesticks',
  maLineColor = '#2962FF',
  maLineWidth = 1,
  maLength = 9,
  lineType = 0,
  dateRanges = ['1w|60', '1m|1D', '6m|120', '12m|1D', '60m|1W'],
  downColor = '#f7525f',
  upColor = '#22ab94',
  borderUpColor = '#22ab94',
  borderDownColor = '#f7525f',
  wickUpColor = '#22ab94',
  wickDownColor = '#f7525f',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing content
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      symbols: [[displayName || symbol, `${symbol}|12M`]],
      chartOnly,
      width,
      height,
      locale,
      colorTheme,
      autosize,
      showVolume,
      showMA,
      hideDateRanges,
      hideMarketStatus,
      hideSymbolLogo,
      scalePosition,
      scaleMode,
      fontFamily,
      fontSize,
      noTimeScale,
      valuesTracking,
      changeMode,
      chartType,
      maLineColor,
      maLineWidth,
      maLength,
      lineType,
      dateRanges,
      downColor,
      upColor,
      borderUpColor,
      borderDownColor,
      wickUpColor,
      wickDownColor,
    };

    script.innerHTML = JSON.stringify(config);
    containerRef.current.appendChild(script);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [
    symbol,
    displayName,
    chartOnly,
    width,
    height,
    locale,
    colorTheme,
    autosize,
    showVolume,
    showMA,
    hideDateRanges,
    hideMarketStatus,
    hideSymbolLogo,
    scalePosition,
    scaleMode,
    fontFamily,
    fontSize,
    noTimeScale,
    valuesTracking,
    changeMode,
    chartType,
    maLineColor,
    maLineWidth,
    maLength,
    lineType,
    dateRanges,
    downColor,
    upColor,
    borderUpColor,
    borderDownColor,
    wickUpColor,
    wickDownColor,
  ]);

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <div className="tradingview-widget-container__widget" />
      <div className="tradingview-widget-copyright">
        <a href="https://www.tradingview.com/" rel="noopener nofollow noreferrer" target="_blank">
          <span className="blue-text">Track all markets on TradingView</span>
        </a>
      </div>
    </div>
  );
};

export default memo(TradingViewSymbolOverview);
