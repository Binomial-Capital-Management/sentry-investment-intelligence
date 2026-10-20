/**
 * Radar Chart (Spider Chart) - Multi-dimensional comparison
 * 
 * Use cases:
 * - Compare fundamentals across tickers (PE, PB, ROE, etc.)
 * - Factor analysis and screening
 * - Multi-metric performance comparison
 */

import { ChartTypeDefinition } from '../types';

export interface RadarChartOptions {
  fill: 'toself' | 'none';  // Fill polygon or just lines
  opacity: number;  // Fill opacity (0-1)
  normalize: 'none' | 'zscore' | 'minmax' | 'rank';  // Normalize across different scales
  showValues: boolean;  // Show values on hover
  connectEnd: boolean;  // Close the polygon (connect last point to first)
}

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1',
];

export const RadarChart: ChartTypeDefinition<RadarChartOptions> = {
  id: 'radar',
  name: 'Radar Chart',
  description: 'Compare multiple metrics across categories',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      {/* Hexagon shape */}
      <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" fill="currentColor" opacity="0.2" />
      <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" />
      {/* Inner shape */}
      <polygon points="12,6 18,9.5 18,14.5 12,18 6,14.5 6,9.5" fill="currentColor" opacity="0.3" />
      {/* Axes */}
      <line x1="12" y1="2" x2="12" y2="22" opacity="0.3" />
      <line x1="2" y1="8.5" x2="22" y2="15.5" opacity="0.3" />
      <line x1="2" y1="15.5" x2="22" y2="8.5" opacity="0.3" />
    </svg>
  ),

  defaultOptions: {
    fill: 'toself',
    opacity: 0.3,
    normalize: 'minmax',  // Default to minmax since metrics have different scales
    showValues: true,
    connectEnd: true,
  },

  buildTraces: (data, xAxis, ySeries, options) => {
    if (ySeries.length < 3 || data.length === 0) {
      console.error('[Radar] Need at least 3 Y-series fields for a meaningful radar chart.');
      return [];
    }

    // Group data by X-axis (e.g., by symbol)
    // Each unique X value becomes one polygon
    const groups = new Map<string, Record<string, number[]>>();
    
    data.forEach(row => {
      const groupKey = String(row[xAxis] ?? 'All');
      if (!groups.has(groupKey)) {
        groups.set(groupKey, {});
        ySeries.forEach(s => groups.get(groupKey)![s.field] = []);
      }
      ySeries.forEach(s => {
        const val = row[s.field];
        if (typeof val === 'number' && !isNaN(val)) {
          groups.get(groupKey)![s.field].push(val);
        }
      });
    });

    // Compute aggregated value per group per field (mean)
    const aggregated = new Map<string, Map<string, number>>();
    groups.forEach((fields, groupKey) => {
      aggregated.set(groupKey, new Map());
      Object.entries(fields).forEach(([field, values]) => {
        const mean = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;
        aggregated.get(groupKey)!.set(field, mean);
      });
    });

    // Compute normalization stats per field (across all groups)
    const fieldStats = new Map<string, { min: number; max: number; mean: number; std: number; values: number[] }>();
    ySeries.forEach(s => {
      const allValues: number[] = [];
      aggregated.forEach(fields => {
        const val = fields.get(s.field);
        if (val !== undefined) allValues.push(val);
      });
      
      const min = Math.min(...allValues);
      const max = Math.max(...allValues);
      const mean = allValues.reduce((a, b) => a + b, 0) / allValues.length;
      const std = Math.sqrt(allValues.reduce((sum, v) => sum + (v - mean) ** 2, 0) / allValues.length);
      
      fieldStats.set(s.field, { min, max, mean, std, values: allValues.sort((a, b) => a - b) });
    });

    // Normalize function
    const normalize = (value: number, field: string): number => {
      const stats = fieldStats.get(field);
      if (!stats) return value;
      
      switch (options.normalize) {
        case 'zscore':
          return stats.std > 0 ? (value - stats.mean) / stats.std : 0;
        case 'minmax':
          return stats.max > stats.min ? (value - stats.min) / (stats.max - stats.min) : 0.5;
        case 'rank':
          // Percentile rank
          const rank = stats.values.filter(v => v <= value).length;
          return rank / stats.values.length;
        default:
          return value;
      }
    };

    // Build traces - one per group (entity)
    const traces: any[] = [];
    let idx = 0;
    
    aggregated.forEach((fields, groupKey) => {
      const theta: string[] = [];
      const r: number[] = [];
      
      ySeries.forEach(s => {
        const rawValue = fields.get(s.field) ?? 0;
        const normValue = normalize(rawValue, s.field);
        
        theta.push(s.label || s.field);
        r.push(normValue);
      });
      
      // Close the polygon by repeating first point
      if (options.connectEnd && theta.length > 0) {
        theta.push(theta[0]);
        r.push(r[0]);
      }
      
      const color = COLORS[idx % COLORS.length];
      
      traces.push({
        type: 'scatterpolar',
        name: groupKey,
        theta,
        r,
        fill: options.fill,
        fillcolor: options.fill === 'toself' ? color + Math.round(options.opacity * 255).toString(16).padStart(2, '0') : undefined,
        line: { color },
        marker: { color, size: 6 },
        hovertemplate: options.showValues 
          ? `%{theta}: %{r:.2f}<extra>${groupKey}</extra>`
          : `%{theta}<extra>${groupKey}</extra>`,
      });
      
      idx++;
    });

    return traces;
  },

  customizeLayout: (baseLayout, options) => {
    // Determine radial axis label based on normalization
    let radialTitle = '';
    if (options.normalize === 'zscore') radialTitle = 'Z-Score';
    else if (options.normalize === 'minmax') radialTitle = '0-1 Normalized';
    else if (options.normalize === 'rank') radialTitle = 'Percentile';
    
    return {
      ...baseLayout,
      polar: {
        radialaxis: {
          visible: true,
          title: { text: radialTitle },
          tickfont: { size: 10 },
        },
        angularaxis: {
          tickfont: { size: 11 },
          rotation: 90,  // Start from top
          direction: 'clockwise' as const,
        },
      },
      // Hide regular axes for polar chart
      xaxis: { visible: false },
      yaxis: { visible: false },
    };
  },
};

