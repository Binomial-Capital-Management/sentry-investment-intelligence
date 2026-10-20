/**
 * Heatmap Chart - 2D matrix visualization with color encoding
 * 
 * Use cases:
 * - Correlation matrices
 * - Calendar returns
 * - Sector/factor grids
 * 
 * Data format: Long-form with X, Y, Z columns (pivoted internally)
 */

import { ChartTypeDefinition } from '../types';
import { pivotToMatrix } from '../../utils/pivotToMatrix';

export type ColorScale = 
  | 'Viridis' 
  | 'Plasma' 
  | 'Inferno' 
  | 'Blues' 
  | 'Reds' 
  | 'Greens' 
  | 'RdBu' 
  | 'RdYlGn' 
  | 'Spectral'
  | 'Portland'
  | 'Picnic';

export interface HeatmapChartOptions {
  // Mode toggle
  correlationMode: boolean;  // If true, compute correlation matrix from Y-series
  // Field mappings for matrix (used when correlationMode=false)
  xField: string;
  yField: string;
  zField: string;
  // Color settings
  colorScale: ColorScale;
  reverseScale: boolean;
  zMin?: number;  // Custom min for color scale
  zMax?: number;  // Custom max for color scale
  // Display options
  showValues: boolean;
  valueFormat: string;  // d3-format string
  showColorbar: boolean;
  // Gap between cells
  xGap: number;
  yGap: number;
}

// Color scale options for the config panel
export const COLOR_SCALES: { id: ColorScale; name: string; type: 'sequential' | 'diverging' }[] = [
  { id: 'Viridis', name: 'Viridis', type: 'sequential' },
  { id: 'Plasma', name: 'Plasma', type: 'sequential' },
  { id: 'Inferno', name: 'Inferno', type: 'sequential' },
  { id: 'Blues', name: 'Blues', type: 'sequential' },
  { id: 'Reds', name: 'Reds', type: 'sequential' },
  { id: 'Greens', name: 'Greens', type: 'sequential' },
  { id: 'RdBu', name: 'Red-Blue', type: 'diverging' },
  { id: 'RdYlGn', name: 'Red-Yellow-Green', type: 'diverging' },
  { id: 'Spectral', name: 'Spectral', type: 'diverging' },
  { id: 'Portland', name: 'Portland', type: 'diverging' },
  { id: 'Picnic', name: 'Picnic', type: 'diverging' },
];

export const HeatmapChart: ChartTypeDefinition<HeatmapChartOptions> = {
  id: 'heatmap',
  name: 'Heatmap',
  description: 'Matrix visualization with colors',
  icon: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <rect x="2" y="2" width="6" height="6" opacity="0.3" />
      <rect x="9" y="2" width="6" height="6" opacity="0.6" />
      <rect x="16" y="2" width="6" height="6" opacity="0.9" />
      <rect x="2" y="9" width="6" height="6" opacity="0.5" />
      <rect x="9" y="9" width="6" height="6" opacity="0.8" />
      <rect x="16" y="9" width="6" height="6" opacity="0.4" />
      <rect x="2" y="16" width="6" height="6" opacity="0.7" />
      <rect x="9" y="16" width="6" height="6" opacity="0.2" />
      <rect x="16" y="16" width="6" height="6" opacity="1" />
    </svg>
  ),
  
  defaultOptions: {
    correlationMode: true,  // Default to correlation matrix mode
    xField: '',
    yField: '',
    zField: '',
    colorScale: 'RdBu',
    reverseScale: false,
    showValues: true,
    valueFormat: '.2f',
    showColorbar: true,
    xGap: 1,
    yGap: 1,
  },
  
  buildTraces: (data, _xAxis, _ySeries, options) => {
    let matrix;

    if (options.correlationMode) {
      // Correlation mode: compute correlation matrix from Y-series
      // Data format: [{date: "2024-01", AAPL: 150, MSFT: 380, ...}, ...]
      // We need to compute correlations between columns (AAPL, MSFT, etc.)
      
      if (_ySeries.length < 2) {
        console.error('[Heatmap] Correlation mode requires at least 2 Y-series', {
          currentCount: _ySeries.length,
          currentFields: _ySeries.map(s => s.field),
          hint: 'Add more Y-series columns (e.g., open, high, low, close) to compute correlations between them. Or switch to "Custom Matrix" mode if you have pre-computed data.'
        });
        return [];
      }

      // Extract field names (excluding X axis)
      const fields = _ySeries.map(s => s.field);
      
      // Compute correlation matrix
      const corrMatrix = computeCorrelationMatrix(data, fields);
      
      matrix = {
        x: corrMatrix.labels,
        y: corrMatrix.labels,
        z: corrMatrix.matrix,
        xLabel: 'Asset',
        yLabel: 'Asset',
        zLabel: 'Correlation',
      };
    } else {
      // Standard mode: pivot long-form data to matrix
      matrix = pivotToMatrix(
        data,
        options.xField || _xAxis,
        options.yField || (data[0] && Object.keys(data[0]).find(k => k !== options.xField && k !== options.zField)) || '',
        options.zField || (_ySeries[0]?.field) || '',
        { aggregation: 'mean', sortX: true, sortY: true, fillValue: null }
      );

      if (matrix.x.length === 0 || matrix.y.length === 0) {
        return [];
      }

      // Detect sparse diagonal pattern (common mistake: using time-series data)
      const totalCells = matrix.x.length * matrix.y.length;
      const filledCells = matrix.z.flat().filter(v => v !== null).length;
      const sparsity = 1 - (filledCells / totalCells);
      
      if (sparsity > 0.8 && filledCells > 0) {
        console.warn(
          'Heatmap is very sparse (' + Math.round(sparsity * 100) + '% empty cells). ' +
          'This usually means your Y-field has mostly unique values (like prices). ' +
          'Try enabling "Correlation Mode" to compute a correlation matrix instead.'
        );
      }
    }

    // Build heatmap trace
    const trace: any = {
      type: 'heatmap',
      x: matrix.x,
      y: matrix.y,
      z: matrix.z,
      colorscale: options.colorScale,
      reversescale: options.reverseScale,
      showscale: options.showColorbar,
      xgap: options.xGap,
      ygap: options.yGap,
      hoverongaps: false,
      hovertemplate: `${matrix.xLabel}: %{x}<br>${matrix.yLabel}: %{y}<br>${matrix.zLabel}: %{z:.3f}<extra></extra>`,
    };

    // Custom z range
    if (options.zMin !== undefined) {
      trace.zmin = options.zMin;
    }
    if (options.zMax !== undefined) {
      trace.zmax = options.zMax;
    }

    // Add text annotations if showValues is enabled
    if (options.showValues) {
      trace.text = matrix.z.map(row => 
        row.map(val => val !== null ? formatValue(val, options.valueFormat) : '')
      );
      trace.texttemplate = '%{text}';
      trace.textfont = { size: 10 };
    }

    return [trace];
  },
  
  customizeLayout: (baseLayout, options) => {
    // Helper to normalize title to object form
    const toTitleObj = (val: unknown): { text: string } | undefined => {
      if (!val) return undefined;
      if (typeof val === 'string') return { text: val };
      if (typeof val === 'object' && 'text' in (val as object)) return val as { text: string };
      return undefined;
    };
    
    return {
      ...baseLayout,
      xaxis: {
        ...baseLayout.xaxis,
        side: 'bottom' as const,
        tickangle: -45,
        title: toTitleObj(options.xField) || toTitleObj(baseLayout.xaxis?.title),
      },
      yaxis: {
        ...baseLayout.yaxis,
        autorange: 'reversed' as const,  // Top-to-bottom like a table
        title: toTitleObj(options.yField) || toTitleObj(baseLayout.yaxis?.title),
      },
      // Adjust margins for rotated labels
      margin: { l: 80, r: 80, t: 40, b: 100 },
    };
  },
};

/**
 * Compute correlation matrix from time-series data
 */
function computeCorrelationMatrix(
  data: Record<string, any>[],
  fields: string[]
): { labels: string[]; matrix: number[][] } {
  // Extract numeric values for each field, keeping nulls in place for alignment
  const series: Record<string, (number | null)[]> = {};
  
  for (const field of fields) {
    series[field] = data.map(row => {
      const val = row[field];
      return typeof val === 'number' && !isNaN(val) ? val : null;
    });
  }

  // Remove fields with insufficient valid data points
  const validFields = fields.filter(f => 
    series[f].filter(v => v !== null).length >= 2
  );
  
  if (validFields.length < 2) {
    return { labels: [], matrix: [] };
  }

  // Compute pairwise correlations
  const n = validFields.length;
  const matrix: number[][] = [];

  for (let i = 0; i < n; i++) {
    const row: number[] = [];
    for (let j = 0; j < n; j++) {
      if (i === j) {
        row.push(1.0); // Correlation with self is 1
      } else {
        const corr = pearsonCorrelation(series[validFields[i]], series[validFields[j]]);
        row.push(corr);
      }
    }
    matrix.push(row);
  }

  return { labels: validFields, matrix };
}

/**
 * Compute Pearson correlation coefficient
 * Arrays must be aligned by index - only uses pairs where both values are valid
 */
function pearsonCorrelation(x: (number | null)[], y: (number | null)[]): number {
  // Build aligned pairs where both values exist
  const xAligned: number[] = [];
  const yAligned: number[] = [];
  
  const len = Math.min(x.length, y.length);
  for (let i = 0; i < len; i++) {
    const xi = x[i];
    const yi = y[i];
    if (xi !== null && yi !== null) {
      xAligned.push(xi);
      yAligned.push(yi);
    }
  }
  
  const n = xAligned.length;
  if (n < 2) return 0;

  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;

  for (let i = 0; i < n; i++) {
    sumX += xAligned[i];
    sumY += yAligned[i];
    sumXY += xAligned[i] * yAligned[i];
    sumX2 += xAligned[i] * xAligned[i];
    sumY2 += yAligned[i] * yAligned[i];
  }

  const numerator = n * sumXY - sumX * sumY;
  const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));

  if (denominator === 0) return 0;
  return numerator / denominator;
}

/**
 * Format a number using simple format patterns
 */
function formatValue(value: number, format: string): string {
  // Simple format parsing: .Nf for N decimal places
  const match = format.match(/\.(\d+)f/);
  if (match) {
    const decimals = parseInt(match[1], 10);
    return value.toFixed(decimals);
  }
  // Percentage
  if (format.includes('%')) {
    const match2 = format.match(/\.(\d+)%/);
    const decimals = match2 ? parseInt(match2[1], 10) : 0;
    return (value * 100).toFixed(decimals) + '%';
  }
  // Default
  return value.toFixed(2);
}

