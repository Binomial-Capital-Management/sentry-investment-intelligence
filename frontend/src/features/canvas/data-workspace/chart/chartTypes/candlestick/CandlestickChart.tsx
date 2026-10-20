/**
 * Candlestick Chart - OHLC price visualization
 * 
 * Requires: Date, Open, High, Low, Close fields
 * Optional: Volume (shown as bars below)
 */

import { ChartTypeDefinition } from '../types';

export interface CandlestickChartOptions {
  // Candle colors
  upColor: string;      // Color for bullish candles (close > open)
  downColor: string;    // Color for bearish candles (close < open)
  // Appearance
  lineWidth: number;    // Wick line width
  increasing: {
    line: { color: string };
    fillcolor: string;
  };
  decreasing: {
    line: { color: string };
    fillcolor: string;
  };
  // Volume
  showVolume: boolean;
  volumeColor: string;
  volumeOpacity: number;
}

// Standard OHLC field names to auto-detect
const OHLC_FIELD_PATTERNS = {
  date: ['date', 'time', 'timestamp', 'datetime', 'period'],
  open: ['open', 'o', 'openprice', 'open_price', 'openingprice'],
  high: ['high', 'h', 'highprice', 'high_price', 'highest'],
  low: ['low', 'l', 'lowprice', 'low_price', 'lowest'],
  close: ['close', 'c', 'closeprice', 'close_price', 'closingprice', 'adjclose', 'adj_close'],
  volume: ['volume', 'vol', 'v', 'tradingvolume'],
};

/**
 * Auto-detect OHLC fields from data
 */
export function detectOHLCFields(data: Record<string, any>[]): {
  date?: string;
  open?: string;
  high?: string;
  low?: string;
  close?: string;
  volume?: string;
} {
  if (!data || data.length === 0) return {};
  
  const fields = Object.keys(data[0]);
  const result: Record<string, string | undefined> = {};
  
  for (const [ohlcKey, patterns] of Object.entries(OHLC_FIELD_PATTERNS)) {
    const match = fields.find(f => 
      patterns.some(p => f.toLowerCase() === p || f.toLowerCase().includes(p))
    );
    if (match) {
      result[ohlcKey] = match;
    }
  }
  
  return result;
}

/**
 * Check if data has all required OHLC fields
 */
export function hasOHLCFields(data: Record<string, any>[]): boolean {
  const detected = detectOHLCFields(data);
  return !!(detected.date && detected.open && detected.high && detected.low && detected.close);
}

export const CandlestickChart: ChartTypeDefinition<CandlestickChartOptions> = {
  id: 'candlestick',
  name: 'Candlestick',
  description: 'OHLC price visualization',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13h2v6H3zM7 4h2v16H7zM11 8h2v8h-2zM15 6h2v12h-2zM19 10h2v4h-2z" />
      <path strokeLinecap="round" d="M4 10v3M8 2v2M8 20v2M12 5v3M12 16v3M16 3v3M16 18v3M20 8v2M20 14v2" />
    </svg>
  ),
  
  defaultOptions: {
    upColor: '#22C55E',      // Green
    downColor: '#EF4444',    // Red
    lineWidth: 1,
    increasing: {
      line: { color: '#22C55E' },
      fillcolor: '#22C55E',
    },
    decreasing: {
      line: { color: '#EF4444' },
      fillcolor: '#EF4444',
    },
    showVolume: true,
    volumeColor: '#94A3B8',  // Slate
    volumeOpacity: 0.5,
  },
  
  buildTraces: (data, xAxis, ySeries, options, ohlcFields) => {
    const traces: any[] = [];
    
    // Get field mappings (from config or auto-detect)
    // Only use ohlcFields if ALL required fields exist in the actual data
    const dataFields = data?.[0] ? new Set(Object.keys(data[0])) : new Set();
    const configFieldsExistInData = ohlcFields && 
      ohlcFields.date && dataFields.has(ohlcFields.date) &&
      ohlcFields.open && dataFields.has(ohlcFields.open) &&
      ohlcFields.high && dataFields.has(ohlcFields.high) &&
      ohlcFields.low && dataFields.has(ohlcFields.low) &&
      ohlcFields.close && dataFields.has(ohlcFields.close);
    const fields = configFieldsExistInData ? ohlcFields : detectOHLCFields(data);
    
    if (!fields.date || !fields.open || !fields.high || !fields.low || !fields.close) {
      console.warn('Candlestick chart: Missing required OHLC fields. Got:', fields, 'from data fields:', data.length > 0 ? Object.keys(data[0]) : []);
      return traces;
    }
    
    // Extract data arrays
    const dates = data.map(d => d[fields.date!]);
    const opens = data.map(d => Number(d[fields.open!]));
    const highs = data.map(d => Number(d[fields.high!]));
    const lows = data.map(d => Number(d[fields.low!]));
    const closes = data.map(d => Number(d[fields.close!]));
    
    // Main candlestick trace
    traces.push({
      type: 'candlestick',
      x: dates,
      open: opens,
      high: highs,
      low: lows,
      close: closes,
      name: 'OHLC',
      increasing: {
        line: { color: options.upColor, width: options.lineWidth },
        fillcolor: options.upColor,
      },
      decreasing: {
        line: { color: options.downColor, width: options.lineWidth },
        fillcolor: options.downColor,
      },
    });
    
    // Volume bars (if enabled and volume field exists)
    if (options.showVolume && fields.volume) {
      const volumes = data.map(d => Number(d[fields.volume!]) || 0);
      const colors = data.map((d, i) => 
        closes[i] >= opens[i] ? options.upColor : options.downColor
      );
      
      traces.push({
        type: 'bar',
        x: dates,
        y: volumes,
        name: 'Volume',
        marker: {
          color: colors,
          opacity: options.volumeOpacity,
        },
        yaxis: 'y2',
        showlegend: false,
      });
    }
    
    return traces;
  },
  
  customizeLayout: (baseLayout, options) => {
    const layout: any = {
      ...baseLayout,
      xaxis: {
        ...baseLayout.xaxis,
        rangeslider: { visible: false }, // Hide range slider for cleaner look
        type: 'date',
      },
      yaxis: {
        ...baseLayout.yaxis,
        title: 'Price',
        side: 'right',
        domain: options.showVolume ? [0.3, 1] : [0, 1],
      },
    };
    
    // Add volume y-axis if enabled
    if (options.showVolume) {
      layout.yaxis2 = {
        title: 'Volume',
        side: 'right',
        domain: [0, 0.25],
        showgrid: false,
      };
    }
    
    return layout;
  },
};
