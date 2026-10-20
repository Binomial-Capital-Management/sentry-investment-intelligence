/**
 * Pie/Donut Chart - for showing proportions and distributions
 */

import { ChartTypeDefinition } from '../types';

export interface PieChartOptions {
  donutHole: number;      // 0 = pie, 0.3-0.7 = donut
  showLabels: boolean;
  labelPosition: 'inside' | 'outside' | 'none';
  showPercent: boolean;
  showValues: boolean;
  sortByValue: boolean;
  startAngle: number;
  rotation: number;
  pull: number;           // Explode slices
}

const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6', '#F97316', '#EF4444', '#6366F1', '#84CC16'];

export const PieChart: ChartTypeDefinition<PieChartOptions> = {
  id: 'pie',
  name: 'Pie/Donut',
  description: 'Show proportions and distributions',
  icon: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8v8l5.66 5.66C14.54 19.08 13.32 20 12 20z" />
    </svg>
  ),
  
  defaultOptions: {
    donutHole: 0,
    showLabels: true,
    labelPosition: 'outside',
    showPercent: true,
    showValues: false,
    sortByValue: true,
    startAngle: 0,
    rotation: 0,
    pull: 0,
  },
  
  buildTraces: (data, xAxis, ySeries, options) => {
    if (ySeries.length === 0 || data.length === 0) return [];
    
    // For pie charts, xAxis contains labels and first ySeries contains values
    const labels = data.map((d) => String(d[xAxis] || 'Unknown'));
    const values = data.map((d) => {
      const val = d[ySeries[0].field];
      return typeof val === 'number' ? val : parseFloat(val) || 0;
    });
    
    // Sort by value if enabled
    let sortedData = labels.map((label, i) => ({ label, value: values[i] }));
    if (options.sortByValue) {
      sortedData.sort((a, b) => b.value - a.value);
    }
    
    // Build text info string
    const textinfo: string[] = [];
    if (options.showLabels && options.labelPosition !== 'none') textinfo.push('label');
    if (options.showPercent) textinfo.push('percent');
    if (options.showValues) textinfo.push('value');
    
    const trace: Record<string, any> = {
      labels: sortedData.map(d => d.label),
      values: sortedData.map(d => d.value),
      type: 'pie',
      hole: options.donutHole,
      textposition: options.labelPosition === 'none' ? 'none' : options.labelPosition,
      textinfo: textinfo.length > 0 ? textinfo.join('+') : 'none',
      marker: {
        colors: COLORS,
      },
      rotation: options.rotation + options.startAngle,
      pull: options.pull > 0 ? Array(sortedData.length).fill(options.pull) : 0,
      hoverinfo: 'label+percent+value',
      hoverlabel: {
        bgcolor: '#1E293B',
        font: { color: 'white', size: 12 },
      },
    };
    
    return [trace];
  },
  
  customizeLayout: (baseLayout, options) => {
    return {
      ...baseLayout,
      showlegend: true,
      legend: {
        orientation: 'v',
        x: 1.02,
        y: 0.5,
        xanchor: 'left',
        yanchor: 'middle',
      },
      // Remove axis settings for pie charts
      xaxis: { visible: false },
      yaxis: { visible: false },
    };
  },
};

