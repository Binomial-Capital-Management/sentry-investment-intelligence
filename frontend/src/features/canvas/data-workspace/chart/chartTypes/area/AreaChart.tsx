/**
 * Area Chart - filled line chart for cumulative/stacked visualization
 */

import { ChartTypeDefinition } from '../types';
import { normalizeValues, NormalizeMode } from '../../utils/normalizeValues';

export interface AreaChartOptions {
  smoothing: boolean;
  stackMode: 'none' | 'stack' | 'percent';  // How to handle multiple series
  fillOpacity: number;
  lineWidth: number;
  showMarkers: boolean;
  markerSize: number;
  normalize: 'none' | 'zscore' | 'minmax' | 'percent';  // Normalize to compare different magnitudes (e.g., currencies)
}

const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6', '#F97316', '#EF4444'];

export const AreaChart: ChartTypeDefinition<AreaChartOptions> = {
  id: 'area',
  name: 'Area',
  description: 'Filled line chart for cumulative data',
  icon: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M3 19V5l4 8 5-6 5 4 4-6v14H3z" opacity="0.3" />
      <path d="M3 19V5l4 8 5-6 5 4 4-6" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  ),
  
  defaultOptions: {
    smoothing: true,
    stackMode: 'none',
    fillOpacity: 0.4,
    lineWidth: 2,
    showMarkers: false,
    markerSize: 5,
    normalize: 'none',
  },
  
  buildTraces: (data, xAxis, ySeries, options) => {
    const xValues = data.map((d) => d[xAxis]);
    
    // Helper to convert hex to rgba
    const hexToRgba = (hex: string, alpha: number) => {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    };
    
    return ySeries.map((series, idx) => {
      const color = series.color || COLORS[idx % COLORS.length];
      
      // Extract Y values and apply normalization if needed
      let yValues = data.map((d) => d[series.field]);
      if (options.normalize && options.normalize !== 'none') {
        yValues = normalizeValues(yValues, options.normalize as NormalizeMode);
      }
      
      // Build trace without undefined properties or as const
      const trace: Record<string, any> = {
        x: xValues,
        y: yValues,
        type: 'scatter',
        mode: options.showMarkers ? 'lines+markers' : 'lines',
        name: series.label || series.field,
        line: {
          color,
          width: options.lineWidth,
          shape: options.smoothing ? 'spline' : 'linear',
        },
        fill: 'tozeroy',
        fillcolor: hexToRgba(color, options.fillOpacity),
        connectgaps: true,
      };
      
      // Only add marker if showing markers (avoid undefined)
      if (options.showMarkers) {
        trace.marker = { color, size: options.markerSize };
      }
      
      // Handle stacking modes
      if (options.stackMode !== 'none') {
        trace.stackgroup = 'one';
        delete trace.fill; // stackgroup handles fill automatically
        if (options.stackMode === 'percent') {
          trace.groupnorm = 'percent';
        }
      }
      
      return trace;
    });
  },
};

