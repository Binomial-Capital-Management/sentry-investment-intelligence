/**
 * Chart Type Registry - exports all available chart types
 */

import React from 'react';

export * from './types';

// Chart type definitions (non-component exports)
export { LineChart } from './line/LineChart';
export type { LineChartOptions } from './line/LineChart';

export { ScatterChart } from './scatter/ScatterChart';
export type { ScatterChartOptions, RegressionType, RegressionConfig } from './scatter/ScatterChart';

export { HistogramChart } from './histogram/HistogramChart';
export type { HistogramChartOptions } from './histogram/HistogramChart';

export { Scatter3DChart } from './scatter3d/Scatter3DChart';
export type { Scatter3DChartOptions } from './scatter3d/Scatter3DChart';

export { CandlestickChart, detectOHLCFields, hasOHLCFields } from './candlestick/CandlestickChart';
export type { CandlestickChartOptions } from './candlestick/CandlestickChart';

export { HeatmapChart, COLOR_SCALES } from './heatmap/HeatmapChart';
export type { HeatmapChartOptions, ColorScale } from './heatmap/HeatmapChart';

export { Surface3DChart } from './surface3d/Surface3DChart';
export type { Surface3DChartOptions } from './surface3d/Surface3DChart';

export { BarChart } from './bar/BarChart';
export type { BarChartOptions } from './bar/BarChart';

export { AreaChart } from './area/AreaChart';
export type { AreaChartOptions } from './area/AreaChart';

export { BubbleChart } from './bubble/BubbleChart';
export type { BubbleChartOptions } from './bubble/BubbleChart';

export { PieChart } from './pie/PieChart';
export type { PieChartOptions } from './pie/PieChart';

export { BoxPlotChart } from './box/BoxPlotChart';
export type { BoxPlotChartOptions } from './box/BoxPlotChart';

export { ViolinChart } from './violin/ViolinChart';
export type { ViolinChartOptions } from './violin/ViolinChart';

export { RadarChart } from './radar/RadarChart';
export type { RadarChartOptions } from './radar/RadarChart';

export { ScatterMatrixChart } from './scatterMatrix/ScatterMatrixChart';
export type { ScatterMatrixChartOptions } from './scatterMatrix/ScatterMatrixChart';

export { DotPlotChart, getDotPlotAxisConfig } from './dotPlot/DotPlotChart';
export type { DotPlotChartOptions } from './dotPlot/DotPlotChart';

// Config panel imports for registry
import { LineChartConfigPanel } from './line/ConfigPanel';
import { ScatterChartConfigPanel } from './scatter/ConfigPanel';
import { HistogramChartConfigPanel } from './histogram/ConfigPanel';
import { Scatter3DChartConfigPanel } from './scatter3d/ConfigPanel';
import { CandlestickChartConfigPanel } from './candlestick/ConfigPanel';
import { HeatmapChartConfigPanel } from './heatmap/ConfigPanel';
import { Surface3DChartConfigPanel } from './surface3d/ConfigPanel';
import { BarChartConfigPanel } from './bar/ConfigPanel';
import { AreaChartConfigPanel } from './area/ConfigPanel';
import { BubbleChartConfigPanel } from './bubble/ConfigPanel';
import { PieChartConfigPanel } from './pie/ConfigPanel';
import { BoxPlotChartConfigPanel } from './box/ConfigPanel';
import { ViolinChartConfigPanel } from './violin/ConfigPanel';
import { RadarChartConfigPanel } from './radar/ConfigPanel';
import { ScatterMatrixChartConfigPanel } from './scatterMatrix/ConfigPanel';
import { DotPlotChartConfigPanel } from './dotPlot/ConfigPanel';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const CONFIG_PANEL_REGISTRY: Record<string, React.ComponentType<{ options: any; onChange: (opts: any) => void }>> = {
  line: LineChartConfigPanel,
  area: AreaChartConfigPanel,
  bar: BarChartConfigPanel,
  pie: PieChartConfigPanel,
  scatter: ScatterChartConfigPanel,
  bubble: BubbleChartConfigPanel,
  box: BoxPlotChartConfigPanel,
  violin: ViolinChartConfigPanel,
  histogram: HistogramChartConfigPanel,
  scatter3d: Scatter3DChartConfigPanel,
  surface3d: Surface3DChartConfigPanel,
  candlestick: CandlestickChartConfigPanel,
  heatmap: HeatmapChartConfigPanel,
  radar: RadarChartConfigPanel,
  scatterMatrix: ScatterMatrixChartConfigPanel,
  dotPlot: DotPlotChartConfigPanel,
};

// Registry of all chart types
import { LineChart } from './line/LineChart';
import { ScatterChart } from './scatter/ScatterChart';
import { HistogramChart } from './histogram/HistogramChart';
import { Scatter3DChart } from './scatter3d/Scatter3DChart';
import { CandlestickChart } from './candlestick/CandlestickChart';
import { HeatmapChart } from './heatmap/HeatmapChart';
import { Surface3DChart } from './surface3d/Surface3DChart';
import { BarChart } from './bar/BarChart';
import { AreaChart } from './area/AreaChart';
import { BubbleChart } from './bubble/BubbleChart';
import { PieChart } from './pie/PieChart';
import { BoxPlotChart } from './box/BoxPlotChart';
import { ViolinChart } from './violin/ViolinChart';
import { RadarChart } from './radar/RadarChart';
import { ScatterMatrixChart } from './scatterMatrix/ScatterMatrixChart';
import { DotPlotChart } from './dotPlot/DotPlotChart';
import { ChartTypeDefinition } from './types';

export const CHART_TYPES: Record<string, ChartTypeDefinition> = {
  line: LineChart,
  area: AreaChart,
  bar: BarChart,
  pie: PieChart,
  scatter: ScatterChart,
  bubble: BubbleChart,
  box: BoxPlotChart,
  violin: ViolinChart,
  histogram: HistogramChart,
  scatter3d: Scatter3DChart,
  surface3d: Surface3DChart,
  candlestick: CandlestickChart,
  heatmap: HeatmapChart,
  radar: RadarChart,
  scatterMatrix: ScatterMatrixChart,
  dotPlot: DotPlotChart,
};

// Get chart type by ID
export function getChartType(id: string): ChartTypeDefinition | undefined {
  return CHART_TYPES[id];
}

// List all chart types
export function listChartTypes(): ChartTypeDefinition[] {
  return Object.values(CHART_TYPES);
}
