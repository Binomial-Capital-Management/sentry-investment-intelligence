/**
 * Scatter Matrix (SPLOM) - Pairwise variable relationships
 * 
 * Use cases:
 * - Exploratory data analysis across multiple variables
 * - Identifying correlations and clusters
 * - Comparing distributions and relationships
 */

import { ChartTypeDefinition } from '../types';

export interface ScatterMatrixChartOptions {
  diagonalType: 'histogram' | 'box' | 'none';  // What to show on diagonal
  markerSize: number;
  markerOpacity: number;
  showUpperHalf: boolean;  // Show upper triangle (redundant but sometimes useful)
  colorByField: string | null;  // Color points by a categorical field
}

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1',
];

export const ScatterMatrixChart: ChartTypeDefinition<ScatterMatrixChartOptions> = {
  id: 'scatterMatrix',
  name: 'Scatter Matrix',
  description: 'Pairwise scatter plots for exploring variable relationships',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      {/* 3x3 grid of scatter plots */}
      <rect x="2" y="2" width="6" height="6" rx="0.5" opacity="0.3" fill="currentColor" />
      <rect x="9" y="2" width="6" height="6" rx="0.5" />
      <rect x="16" y="2" width="6" height="6" rx="0.5" />
      <rect x="2" y="9" width="6" height="6" rx="0.5" />
      <rect x="9" y="9" width="6" height="6" rx="0.5" opacity="0.3" fill="currentColor" />
      <rect x="16" y="9" width="6" height="6" rx="0.5" />
      <rect x="2" y="16" width="6" height="6" rx="0.5" />
      <rect x="9" y="16" width="6" height="6" rx="0.5" />
      <rect x="16" y="16" width="6" height="6" rx="0.5" opacity="0.3" fill="currentColor" />
      {/* Dots in cells */}
      <circle cx="10.5" cy="4" r="0.7" fill="currentColor" />
      <circle cx="12" cy="5" r="0.7" fill="currentColor" />
      <circle cx="13.5" cy="3.5" r="0.7" fill="currentColor" />
    </svg>
  ),

  defaultOptions: {
    diagonalType: 'histogram',
    markerSize: 4,
    markerOpacity: 0.6,
    showUpperHalf: true,
    colorByField: null,
  },

  buildTraces: (data, xAxis, ySeries, options) => {
    if (ySeries.length < 2) {
      console.warn('[ScatterMatrix] Need at least 2 numeric fields for scatter matrix');
      return [];
    }

    if (data.length === 0) {
      return [];
    }

    // Extract dimensions from ySeries
    const dimensions = ySeries.map(s => {
      const values = data.map(row => {
        const val = row[s.field];
        return typeof val === 'number' ? val : NaN;
      });
      
      return {
        label: s.label || s.field,
        values,
      };
    });

    // Determine colors based on colorByField or use single color
    let markerConfig: any = {
      size: options.markerSize,
      opacity: options.markerOpacity,
      color: COLORS[0],
    };

    if (options.colorByField && data.length > 0) {
      const colorValues = data.map(row => row[options.colorByField!]);
      const uniqueColors = [...new Set(colorValues.filter(v => v !== undefined && v !== null))];
      
      if (uniqueColors.length <= 10) {
        // Categorical coloring
        const colorMap = new Map(uniqueColors.map((v, i) => [v, COLORS[i % COLORS.length]]));
        markerConfig.color = colorValues.map(v => colorMap.get(v) || COLORS[0]);
      } else if (uniqueColors.every(v => typeof v === 'number')) {
        // Continuous coloring
        markerConfig.color = colorValues;
        markerConfig.colorscale = 'Viridis';
        markerConfig.showscale = true;
        markerConfig.colorbar = { title: options.colorByField };
      }
    }

    const trace: any = {
      type: 'splom',
      dimensions,
      marker: markerConfig,
      showupperhalf: options.showUpperHalf,
      showlowerhalf: true,
      diagonal: { visible: options.diagonalType !== 'none' },
      hovertemplate: dimensions.map(d => `${d.label}: %{${d.label}}`).join('<br>') + '<extra></extra>',
    };

    // Configure diagonal
    if (options.diagonalType === 'histogram') {
      trace.diagonal = { visible: true };
    } else if (options.diagonalType === 'box') {
      trace.diagonal = { visible: true };
    }

    return [trace];
  },

  customizeLayout: (baseLayout, options) => {
    return {
      ...baseLayout,
      // SPLOM auto-generates axes, but we can customize
      hovermode: 'closest',
      dragmode: 'select',
    };
  },
};

