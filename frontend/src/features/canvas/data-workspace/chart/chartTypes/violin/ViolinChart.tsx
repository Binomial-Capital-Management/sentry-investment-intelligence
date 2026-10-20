/**
 * Violin Chart - Full distribution visualization
 * 
 * Use cases:
 * - Comparing return distributions across assets
 * - Visualizing bimodal/multimodal distributions
 * - Volume distribution by time of day
 * - Price movement analysis by market regime
 */

import { ChartTypeDefinition } from '../types';
import { normalizeValues, NormalizeMode } from '../../utils/normalizeValues';

export interface ViolinChartOptions {
  side: 'both' | 'positive' | 'negative';  // Which side to show
  points: 'all' | 'outliers' | 'suspectedoutliers' | false;  // Show individual points
  meanline: boolean;  // Show mean line inside violin
  box: boolean;  // Show box plot inside violin
  bandwidth: number;  // KDE bandwidth (0 = auto)
  scaleMode: 'count' | 'width';  // How to scale violins
  orientation: 'v' | 'h';  // Vertical or horizontal
  span: 'soft' | 'hard' | [number, number];  // Extent of violin
  jitter: number;  // Point spread
  normalize: 'none' | 'zscore' | 'minmax' | 'percent';  // Normalize to compare different magnitudes
}

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1',
];

export const ViolinChart: ChartTypeDefinition<ViolinChartOptions> = {
  id: 'violin',
  name: 'Violin Plot',
  description: 'Full distribution shape with density estimation',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      {/* Violin shape */}
      <path 
        d="M8 4 Q4 8 4 12 Q4 16 8 20 Q12 16 12 12 Q12 8 8 4" 
        fill="currentColor" 
        opacity="0.3"
      />
      <path d="M8 4 Q4 8 4 12 Q4 16 8 20 Q12 16 12 12 Q12 8 8 4" />
      {/* Mean line */}
      <line x1="4" y1="12" x2="12" y2="12" strokeWidth={2} />
      {/* Second violin */}
      <path 
        d="M16 5 Q13 9 13 12 Q13 15 16 19 Q19 15 19 12 Q19 9 16 5" 
        fill="currentColor" 
        opacity="0.3"
      />
      <path d="M16 5 Q13 9 13 12 Q13 15 16 19 Q19 15 19 12 Q19 9 16 5" />
      <line x1="13" y1="12" x2="19" y2="12" strokeWidth={2} />
    </svg>
  ),

  defaultOptions: {
    side: 'both',
    points: false,
    meanline: true,
    box: true,
    bandwidth: 0,  // auto
    scaleMode: 'width',
    orientation: 'v',
    span: 'soft',
    jitter: 0.3,
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
    // Each Y-series field becomes its own violin (X = field name, Y = all values)
    const useFieldMode = avgPerCategory < 3 || !xAxis;
    
    if (useFieldMode && ySeries.length < 1) {
      console.error(`[Violin] Need at least 1 Y-series field for distribution.`);
      return [];
    }
    
    if (!useFieldMode && uniqueCategories > 50) {
      console.warn(`[Violin] ${uniqueCategories} categories. Consider using fewer categories or field comparison mode.`);
    }

    return ySeries.map((series, idx) => {
      const color = series.color || COLORS[idx % COLORS.length];
      
      // Extract values based on mode
      let xValues: any[];
      let yValues: any[];
      
      if (useFieldMode) {
        // Field comparison mode: each series is one violin showing distribution of that field
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
        type: 'violin',
        name: series.label || series.field,
        side: options.side,
        points: options.points,
        meanline: { visible: options.meanline },
        box: { visible: options.box },
        scalemode: options.scaleMode,
        orientation: options.orientation,
        jitter: options.jitter,
        marker: {
          color,
          size: 4,
          opacity: 0.7,
        },
        line: {
          color,
        },
        fillcolor: color + '60', // 37% opacity
        hoverinfo: 'y+name',
      };

      // Set bandwidth if specified (0 means auto)
      if (options.bandwidth > 0) {
        trace.bandwidth = options.bandwidth;
      }

      // Set span mode
      if (Array.isArray(options.span)) {
        trace.spanmode = 'manual';
        trace.span = options.span;
      } else {
        trace.spanmode = options.span;
      }

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
      violinmode: 'group',
      violingap: 0.3,
      violingroupgap: 0.3,
    };
  },
};

