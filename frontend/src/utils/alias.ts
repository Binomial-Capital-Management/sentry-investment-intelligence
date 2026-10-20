import type { ChartData, RiskMetrics, Source } from '@/types';

type UnknownRecord = Record<string, unknown>;

export function pickContent(payload: unknown): string {
  const p = (payload || {}) as UnknownRecord;
  const v = p['response'] ?? p['content'] ?? p['message'];
  return typeof v === 'string' ? v : '';
}

export function pickSources(payload: unknown): Source[] {
  const p = (payload || {}) as UnknownRecord;
  const v = (p['sources'] ?? p['citations']) as unknown;
  return Array.isArray(v) ? (v as Source[]) : [];
}

export function pickCharts(payload: unknown): ChartData[] {
  const p = (payload || {}) as UnknownRecord;
  const v = (p['charts'] ?? p['visualizations']) as unknown;
  return Array.isArray(v) ? (v as ChartData[]) : [];
}

export function pickMetrics(payload: unknown): RiskMetrics | undefined {
  const p = (payload || {}) as UnknownRecord;
  const v = (p['metrics'] ?? p['risk_metrics']) as unknown;
  return (v && typeof v === 'object') ? (v as RiskMetrics) : undefined;
}
