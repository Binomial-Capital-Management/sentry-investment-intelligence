import { Layout } from 'plotly.js';

export function getLightLayoutOverrides(): Partial<Layout> {
  return {
    paper_bgcolor: '#FFFFFF',
    plot_bgcolor: '#FAFBFC',
    font: {
      family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#0F172A',
    },
    xaxis: {
      gridcolor: '#E2E8F0',
      zeroline: false,
      ticks: 'outside',
      tickcolor: '#CBD5E1',
      tickfont: { color: '#475569' },
      linecolor: '#CBD5E1',
    },
    yaxis: {
      gridcolor: '#E2E8F0',
      zeroline: false,
      ticks: 'outside',
      tickcolor: '#CBD5E1',
      tickfont: { color: '#475569' },
      linecolor: '#CBD5E1',
    },
    legend: {
      font: { color: '#475569' },
      bgcolor: 'rgba(255, 255, 255, 0.9)',
      bordercolor: '#E2E8F0',
      borderwidth: 1,
    },
    hoverlabel: {
      bgcolor: 'rgba(255, 255, 255, 0.95)',
      bordercolor: '#CBD5E1',
      font: {
        family: 'Inter, sans-serif',
        size: 12,
        color: '#0F172A',
      },
    },
    margin: { l: 50, r: 50, t: 50, b: 50 },
    colorway: [
      '#3B82F6',  // Blue
      '#10B981',  // Emerald
      '#8B5CF6',  // Violet
      '#F59E0B',  // Amber
      '#EC4899',  // Pink
      '#14B8A6',  // Teal
      '#F97316',  // Orange
      '#EF4444',  // Red
    ],
  } as Partial<Layout>;
}

// Keep dark theme for backwards compatibility
export function getDarkLayoutOverrides(): Partial<Layout> {
  return {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', color: '#E2E8F0' },
    xaxis: {
      gridcolor: 'rgba(255,255,255,0.06)',
      zeroline: false,
      ticks: 'outside',
      tickcolor: 'rgba(255,255,255,0.12)',
      tickfont: { color: '#A6B0BF' },
    },
    yaxis: {
      gridcolor: 'rgba(255,255,255,0.06)',
      zeroline: false,
      ticks: 'outside',
      tickcolor: 'rgba(255,255,255,0.12)',
      tickfont: { color: '#A6B0BF' },
    },
    legend: { font: { color: '#A6B0BF' } },
    hoverlabel: { bgcolor: 'rgba(20,26,38,0.95)', bordercolor: 'rgba(255,255,255,0.08)', font: { family: 'JetBrains Mono, monospace', size: 12, color: '#E2E8F0' } },
    margin: { l: 40, r: 40, t: 40, b: 40 },
  } as Partial<Layout>;
}
