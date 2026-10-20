/**
 * Line Chart - time series and continuous data visualization
 * 
 * Note: Config panel is in separate file for Fast Refresh compatibility
 */

import { ChartTypeDefinition } from '../types';

// Line-specific options
export interface LineChartOptions {
  smoothing: boolean;       // Spline interpolation
  lineStyle: 'solid' | 'dash' | 'dot' | 'dashdot';
  lineWidth: number;
  fillArea: boolean;        // Fill area under line
  connectGaps: boolean;     // Connect across null values
  showMarkers: boolean;     // Show points on line
  markerSize: number;
}

// Default color palette
const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6', '#F97316', '#EF4444'];

export const LineChart: ChartTypeDefinition<LineChartOptions> = {
  id: 'line',
  name: 'Line',
  description: 'Best for time series and trends',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 12l3-3 3 3 4-4" />
    </svg>
  ),
  
  defaultOptions: {
    smoothing: false,
    lineStyle: 'solid',
    lineWidth: 2,
    fillArea: false,
    connectGaps: true,
    showMarkers: false,
    markerSize: 6,
  },
  
  buildTraces: (data, xAxis, ySeries, options) => {
    const xValues = data.map((d) => d[xAxis]);
    
    // Debug logging
    console.log('[LineChart] Building traces:', {
      dataLength: data.length,
      xAxis,
      xValuesLength: xValues.length,
      xValuesSample: xValues.slice(0, 3),
      ySeries: ySeries.map(s => s.field),
    });
    
    return ySeries.map((series, idx) => {
      const color = series.color || COLORS[idx % COLORS.length];
      const yValues = data.map((d) => d[series.field]);
      
      // Build trace object - only include defined properties
      const trace: any = {
        x: xValues,
        y: yValues,
        type: 'scatter' as const,
        mode: options.showMarkers ? 'lines+markers' : 'lines',
        name: series.label || series.field,
        line: {
          color,
          width: options.lineWidth,
          shape: options.smoothing ? 'spline' : 'linear',
          dash: options.lineStyle,
        },
        fill: options.fillArea ? 'tozeroy' : 'none',
        connectgaps: options.connectGaps,
      };
      
      // Only add marker if showMarkers is enabled
      if (options.showMarkers) {
        trace.marker = {
          color,
          size: options.markerSize,
        };
      }
      
      return trace;
    });
  },
};
