/**
 * Histogram Chart - distribution visualization
 * Great for analyzing return distributions, volume patterns, etc.
 */

import { ChartTypeDefinition } from '../types';

export interface HistogramChartOptions {
  bins: number;
  normalize: boolean;  // Show as density (probability) instead of count
  showKDE: boolean;    // Overlay kernel density estimate
  barColor: string;
  barOpacity: number;
  showMean: boolean;   // Show vertical line at mean
  showMedian: boolean; // Show vertical line at median
}

const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899'];

export const HistogramChart: ChartTypeDefinition<HistogramChartOptions> = {
  id: 'histogram',
  name: 'Histogram',
  description: 'Distribution of values',
  icon: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <rect x="2" y="14" width="4" height="6" />
      <rect x="7" y="8" width="4" height="12" />
      <rect x="12" y="4" width="4" height="16" />
      <rect x="17" y="10" width="4" height="10" />
    </svg>
  ),
  
  defaultOptions: {
    bins: 20,
    normalize: false,
    showKDE: false,
    barColor: '#3B82F6',
    barOpacity: 0.7,
    showMean: true,
    showMedian: false,
  },
  
  buildTraces: (data, xAxis, ySeries, options) => {
    const traces: any[] = [];
    
    // For histogram, we use ySeries fields as the data to histogram
    // xAxis is ignored (Plotly auto-generates bins)
    ySeries.forEach((series, idx) => {
      const values = data
        .map((d) => d[series.field])
        .filter((v) => v !== null && v !== undefined && !isNaN(Number(v)))
        .map((v) => Number(v));
      
      if (values.length === 0) return;
      
      const color = series.color || options.barColor || COLORS[idx % COLORS.length];
      
      // Main histogram trace
      traces.push({
        x: values,
        type: 'histogram',
        name: series.label || series.field,
        nbinsx: options.bins,
        histnorm: options.normalize ? 'probability density' : '',
        marker: {
          color,
          opacity: options.barOpacity,
          line: {
            color: 'white',
            width: 1,
          },
        },
      });
      
      // KDE overlay
      if (options.showKDE && values.length >= 2) {
        const kde = computeKDE(values, 100);
        traces.push({
          x: kde.x,
          y: options.normalize ? kde.y : kde.y.map((v) => v * values.length * (Math.max(...values) - Math.min(...values)) / options.bins),
          type: 'scatter',
          mode: 'lines',
          name: `${series.label || series.field} (KDE)`,
          line: {
            color,
            width: 2,
          },
          showlegend: false,
        });
      }
      
      // Mean line
      if (options.showMean && values.length > 0) {
        const mean = values.reduce((a, b) => a + b, 0) / values.length;
        traces.push({
          x: [mean, mean],
          y: [0, 1],
          type: 'scatter',
          mode: 'lines',
          name: `Mean: ${mean.toFixed(2)}`,
          line: {
            color: '#EF4444',
            width: 2,
            dash: 'dash',
          },
          yaxis: 'y2',
        });
      }
      
      // Median line
      if (options.showMedian && values.length > 0) {
        const sorted = [...values].sort((a, b) => a - b);
        const median = sorted.length % 2 === 0
          ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
          : sorted[Math.floor(sorted.length / 2)];
        traces.push({
          x: [median, median],
          y: [0, 1],
          type: 'scatter',
          mode: 'lines',
          name: `Median: ${median.toFixed(2)}`,
          line: {
            color: '#F59E0B',
            width: 2,
            dash: 'dot',
          },
          yaxis: 'y2',
        });
      }
    });
    
    return traces;
  },
  
  customizeLayout: (baseLayout, options) => {
    return {
      ...baseLayout,
      barmode: 'overlay',
      yaxis: {
        ...baseLayout.yaxis,
        // Only set default title if user hasn't set one
        title: baseLayout.yaxis?.title || (options.normalize ? 'Density' : 'Count'),
      },
      yaxis2: {
        overlaying: 'y',
        visible: false,
        range: [0, 1],
      },
    };
  },
};

// Simple Gaussian KDE
function computeKDE(values: number[], nPoints: number): { x: number[]; y: number[] } {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  
  // Silverman's rule of thumb for bandwidth
  const std = Math.sqrt(values.reduce((sum, v) => sum + (v - values.reduce((a, b) => a + b, 0) / values.length) ** 2, 0) / values.length);
  const bandwidth = 1.06 * std * Math.pow(values.length, -0.2);
  
  const x: number[] = [];
  const y: number[] = [];
  
  for (let i = 0; i < nPoints; i++) {
    const xi = min - range * 0.1 + (i / (nPoints - 1)) * range * 1.2;
    x.push(xi);
    
    // Gaussian kernel
    let density = 0;
    for (const v of values) {
      const u = (xi - v) / bandwidth;
      density += Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI);
    }
    y.push(density / (values.length * bandwidth));
  }
  
  return { x, y };
}

