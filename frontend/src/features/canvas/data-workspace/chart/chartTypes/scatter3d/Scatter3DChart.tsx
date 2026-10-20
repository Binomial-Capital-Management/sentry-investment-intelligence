/**
 * 3D Scatter Chart - Three-dimensional point visualization
 * Great for exploring relationships between 3 variables
 */

import { ChartTypeDefinition } from '../types';

export interface Scatter3DChartOptions {
  markerSize: number;
  markerOpacity: number;
  colorByField: string | null;  // Optional field to color by
  colorScale: 'Viridis' | 'Blues' | 'Reds' | 'Greens' | 'RdYlBu' | 'Spectral';
  showColorbar: boolean;
  zAxis: string;  // Third dimension
}

const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899'];

export const Scatter3DChart: ChartTypeDefinition<Scatter3DChartOptions> = {
  id: 'scatter3d',
  name: '3D Scatter',
  description: 'Three-dimensional relationships',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
      <circle cx="12" cy="8" r="1.5" fill="currentColor" />
      <circle cx="8" cy="14" r="1.5" fill="currentColor" />
      <circle cx="16" cy="12" r="1.5" fill="currentColor" />
    </svg>
  ),
  
  defaultOptions: {
    markerSize: 5,
    markerOpacity: 0.8,
    colorByField: null,
    colorScale: 'Viridis',
    showColorbar: true,
    zAxis: '',
  },
  
  buildTraces: (data, xAxis, ySeries, options) => {
    const traces: any[] = [];
    
    // For 3D scatter, we need X, Y (first ySeries), and Z (from options.zAxis or second ySeries)
    const yField = ySeries[0]?.field;
    const zField = options.zAxis || ySeries[1]?.field;
    
    if (!xAxis || !yField) {
      return traces;
    }
    
    // Parse values (handle dates for x-axis)
    const parseValue = (val: any): number | null => {
      if (typeof val === 'number') return isFinite(val) ? val : null;
      if (typeof val === 'string') {
        if (val.match(/^\d{4}-\d{2}-\d{2}/)) {
          return new Date(val).getTime();
        }
        const num = Number(val);
        return isFinite(num) ? num : null;
      }
      return null;
    };
    
    // Check for long-format mode (data has 'symbol' column for grouping)
    const hasSymbolColumn = data.length > 0 && 'symbol' in data[0];
    const uniqueSymbols = hasSymbolColumn 
      ? [...new Set(data.map(d => d.symbol).filter(Boolean))] as string[]
      : [];
    
    // Helper to strip symbol prefix from field name
    const stripSymbolPrefix = (field: string | undefined): string => {
      if (!field) return '';
      for (const sym of uniqueSymbols) {
        if (field.startsWith(`${sym}_`)) {
          return field.slice(sym.length + 1);
        }
      }
      return field;
    };
    
    const yFieldBase = stripSymbolPrefix(yField);
    const zFieldBase = stripSymbolPrefix(zField);
    
    const isLongFormat = hasSymbolColumn && uniqueSymbols.length > 1 && 
                         yFieldBase && data.some(d => d[yFieldBase] != null);
    
    // Long-format mode: create one trace per symbol
    if (isLongFormat && uniqueSymbols.length > 1) {
      const yFieldToUse = yFieldBase;
      const zFieldToUse = zFieldBase || zField;
      
      uniqueSymbols.forEach((symbol, idx) => {
        const symbolData = data.filter(d => d.symbol === symbol);
        const color = COLORS[idx % COLORS.length];
        
        const xValues: number[] = [];
        const yValues: number[] = [];
        const zValues: number[] = [];
        const hoverTexts: string[] = [];
        
        symbolData.forEach((row) => {
          const x = parseValue(row[xAxis]);
          const y = parseValue(row[yFieldToUse]);
          const z = zFieldToUse ? parseValue(row[zFieldToUse]) : 0;
          
          if (x !== null && y !== null && z !== null) {
            xValues.push(x);
            yValues.push(y);
            zValues.push(z);
            hoverTexts.push(
              `${symbol}<br>${xAxis}: ${row[xAxis]}<br>${yFieldToUse}: ${row[yFieldToUse]}<br>` +
              (zFieldToUse ? `${zFieldToUse}: ${row[zFieldToUse]}` : '')
            );
          }
        });
        
        if (xValues.length > 0) {
          traces.push({
            x: xValues,
            y: yValues,
            z: zValues,
            type: 'scatter3d',
            mode: 'markers',
            name: symbol,
            marker: { size: options.markerSize, opacity: options.markerOpacity, color },
            hovertext: hoverTexts,
            hoverinfo: 'text',
          });
        }
      });
      
      return traces;
    }
    
    // Standard mode: single trace
    const xValues: number[] = [];
    const yValues: number[] = [];
    const zValues: number[] = [];
    const colorValues: number[] = [];
    const hoverTexts: string[] = [];
    
    data.forEach((row) => {
      const x = parseValue(row[xAxis]);
      const y = parseValue(row[yField]);
      const z = zField ? parseValue(row[zField]) : 0;
      
      if (x !== null && y !== null && z !== null) {
        xValues.push(x);
        yValues.push(y);
        zValues.push(z);
        
        // Color by field if specified
        if (options.colorByField && row[options.colorByField] !== undefined) {
          const colorVal = parseValue(row[options.colorByField]);
          colorValues.push(colorVal ?? 0);
        }
        
        // Hover text
        hoverTexts.push(
          `${xAxis}: ${row[xAxis]}<br>` +
          `${yField}: ${row[yField]}<br>` +
          (zField ? `${zField}: ${row[zField]}` : '')
        );
      }
    });
    
    if (xValues.length === 0) {
      return traces;
    }
    
    // Build marker config
    const marker: any = {
      size: options.markerSize,
      opacity: options.markerOpacity,
    };
    
    if (colorValues.length > 0 && options.colorByField) {
      marker.color = colorValues;
      marker.colorscale = options.colorScale;
      marker.showscale = options.showColorbar;
      marker.colorbar = {
        title: options.colorByField,
        thickness: 15,
        len: 0.5,
      };
    } else {
      marker.color = COLORS[0];
    }
    
    traces.push({
      x: xValues,
      y: yValues,
      z: zValues,
      type: 'scatter3d',
      mode: 'markers',
      name: `${yField} vs ${xAxis}`,
      marker,
      hovertext: hoverTexts,
      hoverinfo: 'text',
    });
    
    return traces;
  },
  
  customizeLayout: (baseLayout, options) => {
    return {
      ...baseLayout,
      scene: {
        xaxis: { title: { text: String(baseLayout.xaxis?.title || 'X') } },
        yaxis: { title: { text: String(baseLayout.yaxis?.title || 'Y') } },
        zaxis: { title: { text: options.zAxis || 'Z' } },
        camera: {
          eye: { x: 1.5, y: 1.5, z: 1.5 },
        },
      },
      margin: { l: 0, r: 0, t: 30, b: 0 },
    };
  },
};

