/**
 * Bar Chart - Vertical bar chart for categorical comparisons
 * 
 * Use cases:
 * - Comparing values across categories
 * - Revenue by product
 * - Performance by region
 */

import { ChartTypeDefinition } from '../types';

export interface BarChartOptions {
  orientation: 'v' | 'h';  // vertical or horizontal
  barMode: 'group' | 'stack' | 'overlay';  // how to display multiple series
  showValues: boolean;  // show value labels on bars
  barWidth?: number;  // custom bar width (0-1)
  gap: number;  // gap between bars (0-1)
}

export const BarChart: ChartTypeDefinition<BarChartOptions> = {
  id: 'bar',
  name: 'Bar Chart',
  description: 'Vertical or horizontal bars for categorical data',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <rect x="4" y="14" width="3" height="6" fill="currentColor" />
      <rect x="9" y="10" width="3" height="10" fill="currentColor" />
      <rect x="14" y="6" width="3" height="14" fill="currentColor" />
      <rect x="19" y="8" width="3" height="12" fill="currentColor" />
    </svg>
  ),

  defaultOptions: {
    orientation: 'v',
    barMode: 'group',
    showValues: false,
    gap: 0.2,
  },

  buildTraces: (data, xAxis, ySeries, options) => {
    if (!xAxis || ySeries.length === 0) {
      return [];
    }
    
    const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6', '#F97316', '#EF4444'];
    
    // Check for long-format mode (data has 'symbol' column for grouping)
    const hasSymbolColumn = data.length > 0 && 'symbol' in data[0];
    const has_source_symbol = data.length > 0 && '_source_symbol' in data[0];
    const uniqueSymbols = hasSymbolColumn 
      ? [...new Set(data.map(d => d.symbol).filter(Boolean))] as string[]
      : [];

    // Helper to strip symbol prefix from field name
    const stripSymbolPrefix = (field: string): string => {
      for (const sym of uniqueSymbols) {
        if (field.startsWith(`${sym}_`)) {
          return field.slice(sym.length + 1);
        }
      }
      return field;
    };
    
    const firstYFieldRaw = ySeries[0]?.field;
    const firstYFieldBase = firstYFieldRaw ? stripSymbolPrefix(firstYFieldRaw) : '';
    
    // Use long-format if: data has symbol column AND we can find the base Y field (unprefixed)
    const isLongFormat = hasSymbolColumn && uniqueSymbols.length > 1 && 
                         firstYFieldBase && data.some(d => d[firstYFieldBase] != null);
    
    // Long-format mode: create one trace per symbol
    if (isLongFormat && uniqueSymbols.length > 1) {
      const yFieldToUse = firstYFieldBase;
      
      return uniqueSymbols.map((symbol, idx) => {
        const symbolData = data.filter(d => d.symbol === symbol);
        const color = COLORS[idx % COLORS.length];
        
        // For bar charts comparing symbols: X = symbol name or period, Y = metric value
        // If X-axis is 'symbol', use the symbol as label
        // Otherwise, use the actual X-axis values (like date/period)
        const xData = xAxis === 'symbol' 
          ? symbolData.map(() => symbol)
          : symbolData.map(row => row[xAxis]);
        const yData = symbolData.map(row => row[yFieldToUse]);
        
        const trace: any = {
          type: 'bar',
          name: symbol,
          x: options.orientation === 'v' ? xData : yData,
          y: options.orientation === 'v' ? yData : xData,
          orientation: options.orientation,
          marker: {
            color,
            line: { width: 0.5, color: '#fff' },
          },
          hovertemplate: options.orientation === 'v'
            ? `${symbol}<br>${yFieldToUse}: %{y}<extra></extra>`
            : `${symbol}<br>${yFieldToUse}: %{x}<extra></extra>`,
        };
        
        if (options.showValues) {
          trace.text = yData.map((v: any) => 
            typeof v === 'number' ? v.toFixed(2) : String(v)
          );
          trace.textposition = 'outside';
          trace.textfont = { size: 10 };
        }
        
        if (options.barWidth !== undefined) {
          trace.width = options.barWidth;
        }
        
        return trace;
      });
    }
    
    // Standard mode: one trace per Y-series
    const traces = ySeries.map((series) => {
      const xData = data.map(row => row[xAxis]);
      const yData = data.map(row => row[series.field]);

      const trace: any = {
        type: 'bar',
        name: series.label || series.field,
        x: options.orientation === 'v' ? xData : yData,
        y: options.orientation === 'v' ? yData : xData,
        orientation: options.orientation,
        marker: {
          color: series.color || undefined,
          line: {
            width: 0.5,
            color: '#fff',
          },
        },
        hovertemplate: options.orientation === 'v'
          ? `${xAxis}: %{x}<br>${series.field}: %{y}<extra></extra>`
          : `${series.field}: %{x}<br>${xAxis}: %{y}<extra></extra>`,
      };

      // Add value labels if enabled
      if (options.showValues) {
        trace.text = yData.map((v: any) => 
          typeof v === 'number' ? v.toFixed(2) : String(v)
        );
        trace.textposition = 'outside';
        trace.textfont = { size: 10 };
      }

      // Custom bar width
      if (options.barWidth !== undefined) {
        trace.width = options.barWidth;
      }

      return trace;
    });

    return traces;
  },

  customizeLayout: (baseLayout, options) => {
    return {
      ...baseLayout,
      barmode: options.barMode,
      bargap: options.gap,
      bargroupgap: 0.1,
    };
  },
};
