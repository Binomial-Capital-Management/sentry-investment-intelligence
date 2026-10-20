/**
 * Box Plot Chart - Statistical distribution visualization
 * 
 * Use cases:
 * - Daily return distribution per ticker
 * - Volume distribution by exchange
 * - Price range analysis by sector
 * - Comparing distributions across categories
 */

import { ChartTypeDefinition } from '../types';
import { normalizeValues, NormalizeMode } from '../../utils/normalizeValues';

export interface BoxPlotChartOptions {
  boxPoints: 'all' | 'outliers' | 'suspectedoutliers' | false;  // Show individual points
  boxMean: boolean | 'sd';  // Show mean line (true = line, 'sd' = mean ± std dev)
  notched: boolean;  // Show confidence interval notches
  jitter: number;  // Spread of individual points (0 to 1)
  pointPos: number;  // Position of points relative to box (-2 to 2)
  orientation: 'v' | 'h';  // Vertical or horizontal boxes
  quartileMethod: 'linear' | 'exclusive' | 'inclusive';  // Quartile calculation method
  normalize: 'none' | 'zscore' | 'minmax' | 'percent';  // Normalize to compare different magnitudes
}

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1',
];

export const BoxPlotChart: ChartTypeDefinition<BoxPlotChartOptions> = {
  id: 'box',
  name: 'Box Plot',
  description: 'Statistical distribution with quartiles and outliers',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      {/* Box */}
      <rect x="6" y="8" width="4" height="8" fill="currentColor" opacity="0.3" />
      <rect x="6" y="8" width="4" height="8" />
      {/* Whiskers */}
      <line x1="8" y1="4" x2="8" y2="8" />
      <line x1="8" y1="16" x2="8" y2="20" />
      <line x1="6" y1="4" x2="10" y2="4" />
      <line x1="6" y1="20" x2="10" y2="20" />
      {/* Median */}
      <line x1="6" y1="12" x2="10" y2="12" strokeWidth={2} />
      {/* Second box */}
      <rect x="14" y="6" width="4" height="10" fill="currentColor" opacity="0.3" />
      <rect x="14" y="6" width="4" height="10" />
      <line x1="16" y1="3" x2="16" y2="6" />
      <line x1="16" y1="16" x2="16" y2="19" />
      <line x1="14" y1="3" x2="18" y2="3" />
      <line x1="14" y1="19" x2="18" y2="19" />
      <line x1="14" y1="10" x2="18" y2="10" strokeWidth={2} />
    </svg>
  ),

  defaultOptions: {
    boxPoints: 'outliers',
    boxMean: true,
    notched: false,
    jitter: 0.3,
    pointPos: 0,
    orientation: 'v',
    quartileMethod: 'linear',
    normalize: 'none',
  },

  buildTraces: (data, xAxis, ySeries, options) => {
    if (ySeries.length === 0 || data.length === 0) {
      return [];
    }

    // Check if X-axis grouping has enough values per category
    const categoryCount = new Map<string, number>();
    data.forEach(row => {
      const cat = String(row[xAxis] ?? '_none_');
      categoryCount.set(cat, (categoryCount.get(cat) || 0) + 1);
    });
    
    const uniqueCategories = categoryCount.size;
    const avgPerCategory = data.length / uniqueCategories;
    
    // If not enough values per X category, use "field comparison" mode:
    // Each Y-series field becomes its own box (X = field name, Y = all values)
    const useFieldMode = avgPerCategory < 3 || !xAxis;
    
    if (useFieldMode && ySeries.length < 1) {
      console.error(`[BoxPlot] Need at least 1 Y-series field for distribution.`);
      return [];
    }
    
    if (!useFieldMode && uniqueCategories > 50) {
      console.warn(`[BoxPlot] ${uniqueCategories} categories. Consider using fewer categories or field comparison mode.`);
    }

    // For box plots, each Y-series becomes a separate box trace
    return ySeries.map((series, idx) => {
      const color = series.color || COLORS[idx % COLORS.length];
      
      // Extract values based on mode
      let xValues: any[];
      let yValues: any[];
      
      if (useFieldMode) {
        // Field comparison mode: each series is one box showing distribution of that field
        xValues = data.map(() => series.label || series.field);
        yValues = data.map(row => row[series.field]);
      } else {
        // Category mode: group by X-axis field
        xValues = data.map(row => row[xAxis]);
        yValues = data.map(row => row[series.field]);
      }
      
      // Apply normalization to eliminate magnitude differences
      yValues = normalizeValues(yValues, options.normalize as NormalizeMode);

      const trace: any = {
        type: 'box',
        name: series.label || series.field,
        boxpoints: options.boxPoints,
        boxmean: options.boxMean,
        notched: options.notched,
        jitter: options.jitter,
        pointpos: options.pointPos,
        orientation: options.orientation,
        quartilemethod: options.quartileMethod,
        marker: {
          color,
          outliercolor: color,
          size: 4,
        },
        line: {
          color,
        },
        fillcolor: color + '40', // 25% opacity
        hoverinfo: 'y+name',
      };

      if (options.orientation === 'v') {
        trace.x = xValues;
        trace.y = yValues;
      } else {
        trace.x = yValues;
        trace.y = xValues;
      }

      return trace;
    });
  },

  customizeLayout: (baseLayout, options) => {
    return {
      ...baseLayout,
      boxmode: 'group', // Group multiple box plots together
      boxgap: 0.3,
      boxgroupgap: 0.3,
    };
  },
};

