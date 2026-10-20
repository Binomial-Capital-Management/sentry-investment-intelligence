/**
 * Dot Plot (Strip Plot) - Individual data points per category
 * 
 * Use cases:
 * - Visualize individual observations within categories
 * - See distribution shape and outliers
 * - Small-medium datasets where individual points matter
 */

import { ChartTypeDefinition } from '../types';

export interface DotPlotChartOptions {
  jitter: number;  // Amount of horizontal spread (0-0.5)
  markerSize: number;
  markerOpacity: number;
  orientation: 'vertical' | 'horizontal';  // Points along y or x axis
  showMean: boolean;  // Show mean line per category
  showMedian: boolean;  // Show median line per category
  colorMode: 'series' | 'gradient';  // Color by series or by value
}

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1',
];

// Seeded random for consistent jitter
function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

export const DotPlotChart: ChartTypeDefinition<DotPlotChartOptions> = {
  id: 'dotPlot',
  name: 'Dot Plot',
  description: 'Show individual data points per category',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      {/* Vertical axis */}
      <line x1="6" y1="4" x2="6" y2="20" />
      {/* Horizontal axis */}
      <line x1="6" y1="20" x2="20" y2="20" />
      {/* Category 1 dots */}
      <circle cx="10" cy="8" r="1.5" fill="currentColor" />
      <circle cx="9" cy="12" r="1.5" fill="currentColor" />
      <circle cx="11" cy="10" r="1.5" fill="currentColor" />
      <circle cx="10" cy="15" r="1.5" fill="currentColor" />
      {/* Category 2 dots */}
      <circle cx="17" cy="6" r="1.5" fill="currentColor" />
      <circle cx="16" cy="9" r="1.5" fill="currentColor" />
      <circle cx="18" cy="11" r="1.5" fill="currentColor" />
      <circle cx="17" cy="14" r="1.5" fill="currentColor" />
    </svg>
  ),

  defaultOptions: {
    jitter: 0.15,
    markerSize: 8,
    markerOpacity: 0.7,
    orientation: 'vertical',
    showMean: false,
    showMedian: false,
    colorMode: 'series',
  },

  buildTraces: (data, xAxis, ySeries, options) => {
    if (ySeries.length === 0 || data.length === 0) {
      return [];
    }

    const traces: any[] = [];

    // Group data by X-axis category
    const categories = [...new Set(data.map(row => String(row[xAxis] ?? 'Unknown')))];

    ySeries.forEach((series, seriesIdx) => {
      const color = series.color || COLORS[seriesIdx % COLORS.length];
      
      // Collect all points with jitter
      const xValues: (string | number)[] = [];
      const yValues: number[] = [];
      const hoverTexts: string[] = [];

      categories.forEach((category, catIdx) => {
        const categoryData = data.filter(row => String(row[xAxis]) === category);
        
        categoryData.forEach((row, pointIdx) => {
          const value = row[series.field];
          if (typeof value !== 'number' || isNaN(value)) return;
          
          // Apply jitter: random offset within jitter range
          const jitterOffset = (seededRandom(catIdx * 1000 + pointIdx + seriesIdx * 100) - 0.5) * 2 * options.jitter;
          
          if (options.orientation === 'vertical') {
            xValues.push(catIdx + jitterOffset);
            yValues.push(value);
          } else {
            xValues.push(value);
            yValues.push(catIdx + jitterOffset);
          }
          
          hoverTexts.push(`${category}<br>${series.label || series.field}: ${value.toFixed(2)}`);
        });
      });

      // Main scatter trace
      traces.push({
        type: 'scatter',
        mode: 'markers',
        name: series.label || series.field,
        x: xValues,
        y: yValues,
        text: hoverTexts,
        hovertemplate: '%{text}<extra></extra>',
        marker: {
          size: options.markerSize,
          opacity: options.markerOpacity,
          color: options.colorMode === 'gradient' 
            ? (options.orientation === 'vertical' ? yValues : xValues)
            : color,
          colorscale: options.colorMode === 'gradient' ? 'Viridis' : undefined,
          showscale: options.colorMode === 'gradient' && seriesIdx === 0,
        },
      });

      // Add mean/median lines if requested
      if (options.showMean || options.showMedian) {
        categories.forEach((category, catIdx) => {
          const categoryData = data
            .filter(row => String(row[xAxis]) === category)
            .map(row => row[series.field])
            .filter((v): v is number => typeof v === 'number' && !isNaN(v));

          if (categoryData.length === 0) return;

          if (options.showMean) {
            const mean = categoryData.reduce((a, b) => a + b, 0) / categoryData.length;
            const lineWidth = 0.3;
            
            if (options.orientation === 'vertical') {
              traces.push({
                type: 'scatter',
                mode: 'lines',
                name: seriesIdx === 0 && catIdx === 0 ? 'Mean' : undefined,
                showlegend: seriesIdx === 0 && catIdx === 0,
                x: [catIdx - lineWidth, catIdx + lineWidth],
                y: [mean, mean],
                line: { color: '#1e293b', width: 2, dash: 'solid' },
                hoverinfo: 'skip',
              });
            } else {
              traces.push({
                type: 'scatter',
                mode: 'lines',
                name: seriesIdx === 0 && catIdx === 0 ? 'Mean' : undefined,
                showlegend: seriesIdx === 0 && catIdx === 0,
                x: [mean, mean],
                y: [catIdx - lineWidth, catIdx + lineWidth],
                line: { color: '#1e293b', width: 2, dash: 'solid' },
                hoverinfo: 'skip',
              });
            }
          }

          if (options.showMedian) {
            const sorted = [...categoryData].sort((a, b) => a - b);
            const median = sorted.length % 2 === 0
              ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
              : sorted[Math.floor(sorted.length / 2)];
            const lineWidth = 0.3;
            
            if (options.orientation === 'vertical') {
              traces.push({
                type: 'scatter',
                mode: 'lines',
                name: seriesIdx === 0 && catIdx === 0 ? 'Median' : undefined,
                showlegend: seriesIdx === 0 && catIdx === 0,
                x: [catIdx - lineWidth, catIdx + lineWidth],
                y: [median, median],
                line: { color: '#dc2626', width: 2, dash: 'dash' },
                hoverinfo: 'skip',
              });
            } else {
              traces.push({
                type: 'scatter',
                mode: 'lines',
                name: seriesIdx === 0 && catIdx === 0 ? 'Median' : undefined,
                showlegend: seriesIdx === 0 && catIdx === 0,
                x: [median, median],
                y: [catIdx - lineWidth, catIdx + lineWidth],
                line: { color: '#dc2626', width: 2, dash: 'dash' },
                hoverinfo: 'skip',
              });
            }
          }
        });
      }
    });

    return traces;
  },

  customizeLayout: (baseLayout, options) => {
    // We need to set up category axis with proper tick labels
    // This will be done dynamically based on data in the main component
    return {
      ...baseLayout,
      hovermode: 'closest',
    };
  },
};

// Helper to generate tick values/text for categorical axis
export function getDotPlotAxisConfig(data: any[], xAxis: string, orientation: 'vertical' | 'horizontal') {
  const categories = [...new Set(data.map(row => String(row[xAxis] ?? 'Unknown')))];
  
  const tickvals = categories.map((_, i) => i);
  const ticktext = categories;
  
  if (orientation === 'vertical') {
    return {
      xaxis: {
        tickvals,
        ticktext,
        tickangle: categories.length > 5 ? -45 : 0,
      },
    };
  } else {
    return {
      yaxis: {
        tickvals,
        ticktext,
      },
    };
  }
}

