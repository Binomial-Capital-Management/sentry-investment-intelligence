/**
 * ChartCreator types - shared across all chart creator components
 */

export interface ChartField {
  name: string;
  type: 'numeric' | 'datetime' | 'categorical';
  source?: string;
}

export interface ChartSource {
  tabId: string;
  sheetId: string;
  sheet: any;
  sourceType: 'sheet' | 'pivot';  // Whether source is a data sheet or pivot table
}

// OHLC field mappings for candlestick charts
export interface OHLCConfig {
  dateField: string;
  openField: string;
  highField: string;
  lowField: string;
  closeField: string;
  volumeField?: string;
}

// Matrix field mapping for heatmap and surface3d charts
export interface MatrixConfig {
  xField: string;
  yField: string;
  zField: string;
}

export interface ChartConfigState {
  chartType: 'line' | 'area' | 'bar' | 'pie' | 'scatter' | 'bubble' | 'box' | 'violin' | 'radar' | 'histogram' | 'scatter3d' | 'surface3d' | 'candlestick' | 'heatmap' | 'scatterMatrix' | 'dotPlot';
  xAxis: string;
  ySeries: { field: string; color?: string; label?: string }[];
  zAxis?: string;  // For 3D scatter (legacy)
  ohlc?: OHLCConfig;  // For candlestick
  matrix?: MatrixConfig;  // For heatmap and surface3d
}



