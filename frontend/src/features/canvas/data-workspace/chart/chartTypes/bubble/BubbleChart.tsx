/**
 * Bubble Chart - scatter plot with size dimension
 * 
 * X = position, Y = position, Size = third variable, Color = optional fourth
 */

import { ChartTypeDefinition } from '../types';

export interface BubbleChartOptions {
  sizeField: string;          // Field for bubble size
  colorField: string | null;  // Optional field for color
  minSize: number;            // Min bubble diameter
  maxSize: number;            // Max bubble diameter  
  opacity: number;
  colorScale: string;
  showColorbar: boolean;
}

const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6', '#F97316', '#EF4444'];

export const BubbleChart: ChartTypeDefinition<BubbleChartOptions> = {
  id: 'bubble',
  name: 'Bubble',
  description: 'Scatter with size dimension',
  icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
      <circle cx="7" cy="17" r="3" fill="currentColor" opacity="0.7" />
      <circle cx="12" cy="9" r="5" fill="currentColor" opacity="0.7" />
      <circle cx="18" cy="15" r="2" fill="currentColor" opacity="0.7" />
    </svg>
  ),
  
  defaultOptions: {
    sizeField: '',
    colorField: null,
    minSize: 8,
    maxSize: 50,
    opacity: 0.7,
    colorScale: 'Viridis',
    showColorbar: true,
  },
  
  buildTraces: (data, xAxis, ySeries, options) => {
    const traces: any[] = [];
    
    // Check for long-format mode (data has 'symbol' column for grouping)
    const hasSymbolColumn = data.length > 0 && 'symbol' in data[0];
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
    const isLongFormat = hasSymbolColumn && uniqueSymbols.length > 1 && 
                         firstYFieldBase && data.some(d => d[firstYFieldBase] != null);
    
    // Get size values and compute scale (global across all data)
    let globalSizeValues: number[] = [];
    let sizeMin = 0;
    let sizeMax = 1;
    
    if (options.sizeField) {
      globalSizeValues = data.map((d) => {
        const v = d[options.sizeField];
        return typeof v === 'number' ? v : parseFloat(String(v)) || 0;
      });
      sizeMin = Math.min(...globalSizeValues.filter(v => !isNaN(v)));
      sizeMax = Math.max(...globalSizeValues.filter(v => !isNaN(v)));
    }
    
    const scaleSize = (v: number) => {
      if (isNaN(v) || sizeMax === sizeMin) return (options.minSize + options.maxSize) / 2;
      return options.minSize + ((v - sizeMin) / (sizeMax - sizeMin)) * (options.maxSize - options.minSize);
    };
    
    // Long-format mode: group by symbol
    if (isLongFormat && uniqueSymbols.length > 1) {
      const yFieldToUse = firstYFieldBase;
      
      uniqueSymbols.forEach((symbol, idx) => {
        const symbolData = data.filter(d => d.symbol === symbol);
        const color = COLORS[idx % COLORS.length];
        
        const xValues = symbolData.map(d => d[xAxis]);
        const yValues = symbolData.map(d => d[yFieldToUse]);
        
        const sizeValues = options.sizeField 
          ? symbolData.map(d => scaleSize(typeof d[options.sizeField] === 'number' ? d[options.sizeField] : parseFloat(String(d[options.sizeField])) || 0))
          : symbolData.map(() => (options.minSize + options.maxSize) / 2);
        
        const hoverText = symbolData.map((d) => {
          let text = `${symbol}<br>${xAxis}: ${d[xAxis]}<br>${yFieldToUse}: ${d[yFieldToUse]}`;
          if (options.sizeField) text += `<br>${options.sizeField}: ${d[options.sizeField]}`;
          return text;
        });
        
        traces.push({
          x: xValues,
          y: yValues,
          type: 'scatter' as const,
          mode: 'markers',
          name: symbol,
          marker: {
            color,
            size: sizeValues,
            opacity: options.opacity,
            sizemode: 'diameter',
            line: { color: 'white', width: 1 },
          },
          text: hoverText,
          hovertemplate: '%{text}<extra></extra>',
        });
      });
      
      return traces;
    }
    
    // Standard mode
    const xValues = data.map((d) => d[xAxis]);
    
    // Scale size values to pixel range
    const scaledSizes = globalSizeValues.length > 0
      ? globalSizeValues.map(scaleSize)
      : data.map(() => (options.minSize + options.maxSize) / 2);
    
    // Get color values if specified
    let colorValues: number[] | undefined;
    if (options.colorField) {
      colorValues = data.map((d) => {
        const v = d[options.colorField!];
        return typeof v === 'number' ? v : parseFloat(String(v)) || 0;
      });
    }
    
    ySeries.forEach((series, idx) => {
      const yValues = data.map((d) => d[series.field]);
      const baseColor = series.color || COLORS[idx % COLORS.length];
      
      // Build hover text
      const hoverText = data.map((d, i) => {
        let text = `${xAxis}: ${d[xAxis]}<br>${series.field}: ${d[series.field]}`;
        if (options.sizeField) {
          text += `<br>${options.sizeField}: ${d[options.sizeField]}`;
        }
        if (options.colorField) {
          text += `<br>${options.colorField}: ${d[options.colorField]}`;
        }
        return text;
      });
      
      const marker: any = {
        size: scaledSizes,
        opacity: options.opacity,
        sizemode: 'diameter',
        line: {
          color: 'white',
          width: 1,
        },
      };
      
      // Apply color based on colorField or use series color
      if (colorValues && options.colorField) {
        marker.color = colorValues;
        marker.colorscale = options.colorScale;
        marker.showscale = options.showColorbar && idx === 0; // Only first series shows colorbar
        marker.colorbar = {
          title: options.colorField,
          thickness: 15,
          len: 0.5,
        };
      } else {
        marker.color = baseColor;
      }
      
      traces.push({
        x: xValues,
        y: yValues,
        type: 'scatter' as const,
        mode: 'markers',
        name: series.label || series.field,
        marker,
        text: hoverText,
        hovertemplate: '%{text}<extra></extra>',
      });
    });
    
    return traces;
  },
};

