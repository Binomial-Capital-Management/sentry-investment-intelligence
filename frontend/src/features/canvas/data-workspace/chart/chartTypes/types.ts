/**
 * Common types for chart type implementations
 */

import { PlotData, Layout } from 'plotly.js';

// Base series config shared across chart types
export interface BaseSeriesConfig {
  field: string;
  color?: string;
  label?: string;
}

// OHLC field mapping for candlestick charts
export interface OHLCFieldMapping {
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume?: string;
}

// Each chart type exports its own options interface
export interface ChartTypeDefinition<TOptions = any> {
  id: string;
  name: string;
  icon: React.ReactNode;
  description: string;
  
  // Default options for this chart type
  defaultOptions: TOptions;
  
  // Build Plotly traces from data
  // ohlcFields is optional, only used for candlestick charts
  buildTraces: (
    data: any[],
    xAxis: string,
    ySeries: BaseSeriesConfig[],
    options: TOptions,
    ohlcFields?: OHLCFieldMapping
  ) => Partial<PlotData>[];
  
  // Optional: customize layout for this chart type
  customizeLayout?: (baseLayout: Partial<Layout>, options: TOptions) => Partial<Layout>;
}

// Registry type
export type ChartTypeRegistry = Record<string, ChartTypeDefinition>;

