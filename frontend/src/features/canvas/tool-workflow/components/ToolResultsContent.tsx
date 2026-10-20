/**
 * ToolResultsContent - Renders tool execution results (charts, stats, metric cards).
 *
 * Extracted from ToolWorkflowContent Step 4. Used both in the new 3-panel layout
 * (DataWorkspace renders this in center) and the legacy wizard path.
 */

import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { RefreshCw, Workflow, Image, FileDown, FileSpreadsheet, Maximize } from 'lucide-react';
import { Tooltip } from '@/features/canvas/shared/Tooltip';
import { useDataWorkspaceStore } from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';
import { fmtCurrency, fmtPercent } from '../utils/formatters';
import type { MetricCard, StatsRow } from '@/features/canvas/shared/AIChat/types';
import { useToolTab } from '../hooks/useToolTab';
import { type Sentiment } from './metricCardStyles';
import { ToolMetricsPanel, type NormalizedMetricCard } from './ToolMetricsPanel';

const Plot = lazy(() => import('react-plotly.js'));
const ProcessFlowView = lazy(() => import('./ProcessFlowView'));

interface ToolResultsContentProps {
  tabId: string;
  /** Which stored result to display */
  resultLocalId: string;
  /** Portal target for left header content (process name, tickers) */
  headerLeftPortal?: HTMLDivElement | null;
  /** Portal target for right header content (action buttons) */
  headerRightPortal?: HTMLDivElement | null;
  showAIPanel?: boolean;
  onToggleAIPanel?: () => void;
}

export default function ToolResultsContent({ tabId, resultLocalId, headerLeftPortal, headerRightPortal, showAIPanel, onToggleAIPanel }: ToolResultsContentProps) {
  const {
    toolState,
    selectedTool,
    isEditingName,
    setIsEditingName,
    editNameValue,
    setEditNameValue,
    showDeleteConfirm,
    setShowDeleteConfirm,
    isDeleting,
    isGraphView,
    setIsGraphView,
    handleRerun,
    handleRenameProcess,
    handleDeleteProcess,
    downloadChartPng,
    downloadStatsCsv,
    downloadStatsExcel,
  } = useToolTab(tabId);

  const { toolId: selectedToolId } = toolState;
  const activeEntry = (toolState.toolResults ?? []).find(r => r.localId === resultLocalId) ?? null;
  const patchToolResult = useDataWorkspaceStore(s => s.patchToolResult);
  const setActiveChart = useCallback((chart: string) => {
    if (!activeEntry) return;
    patchToolResult(tabId, activeEntry.toolId, resultLocalId, { activeChart: chart });
  }, [patchToolResult, tabId, resultLocalId, activeEntry]);
  const result = activeEntry?.result ?? null;
  const activeChart = activeEntry?.activeChart ?? 'stats';
  const currentProcessId = activeEntry?.processId ?? null;
  const processName = activeEntry?.processName ?? '';

  const [metricsOpen, setMetricsOpen] = useState(false);
  const [metricsHeight, setMetricsHeight] = useState(45);

  useEffect(() => { setMetricsOpen(false); }, [resultLocalId]);

  const metricCards: NormalizedMetricCard[] = useMemo(() => {
    if (!result) return [];
    if (result.metric_cards && result.metric_cards.length > 0) {
      return result.metric_cards.map((c: MetricCard) => ({
        id: c.id,
        label: c.label,
        value: c.value,
        sentiment: (c.sentiment || 'neutral') as Sentiment,
      }));
    }
    if (result.tool_id === 'monte_carlo' && result.metrics) {
      return [
        { id: 'var95', label: 'VaR 95%', value: fmtCurrency(result.metrics.var_95), sentiment: 'negative' as Sentiment },
        { id: 'cvar95', label: 'CVaR 95%', value: fmtCurrency(result.metrics.cvar_95), sentiment: 'negative' as Sentiment },
        { id: 'exp_ret', label: 'Expected Return', value: fmtPercent(result.metrics.expected_return), sentiment: 'positive' as Sentiment },
        { id: 'vol', label: 'Volatility', value: fmtPercent(result.metrics.volatility), sentiment: 'neutral' as Sentiment },
      ];
    }
    if (result.tool_id === 'barra_factors' && result.metrics) {
      const cards: NormalizedMetricCard[] = [
        { id: 'mean_r2', label: 'Mean R²', value: fmtPercent(result.metrics.mean_r_squared), sentiment: 'info' as Sentiment },
      ];
      if (result.metrics.total_risk != null) {
        cards.push({ id: 'total_risk', label: 'Total Risk', value: fmtPercent(result.metrics.total_risk), sentiment: 'negative' as Sentiment });
      }
      return cards;
    }
    return [];
  }, [result]);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = chartContainerRef.current;
    if (!el) return;
    let rafId = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const plot = el.querySelector('.js-plotly-plot') as HTMLElement | null;
        if (plot) {
          import('plotly.js/dist/plotly').then((Plotly: any) => Plotly.Plots.resize(plot));
        }
      });
    });
    ro.observe(el);
    return () => { ro.disconnect(); cancelAnimationFrame(rafId); };
  }, [activeChart]);

  if (!result) return null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* CSS for smooth chart resize */}
      <style>{`
        html[data-resizing="true"] .plotly-chart-container .js-plotly-plot {
          visibility: hidden;
        }
        html[data-resizing="true"] .plotly-chart-container .resize-placeholder {
          opacity: 1 !important;
        }
        @keyframes resize-spin { to { transform: rotate(360deg); } }
        @keyframes resize-pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }
        .resize-spinner { animation: resize-spin 1s linear infinite; }
        .resize-dots span { animation: resize-pulse 1.4s ease-in-out infinite; }
        .resize-dots span:nth-child(2) { animation-delay: 0.2s; }
        .resize-dots span:nth-child(3) { animation-delay: 0.4s; }
        .plotly-chart-container .drag { cursor: default !important; }
        .plotly-chart-container .drag:active { cursor: grabbing !important; }
      `}</style>

      {/* ========== HEADER CONTENT (extracted for portal support) ========== */}
      {(() => {
        const chartEntries = result.charts
          ? Object.entries(result.charts).filter(([, c]: [string, any]) => c?.plotly)
          : [];

        const headerLeft = (
          <div className="flex items-center gap-0.5 min-w-0 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
            {chartEntries.map(([key, chart]: [string, any]) => {
              const isActive = activeChart === key;
              return (
                <button
                  key={key}
                  onClick={() => setActiveChart(key)}
                  className="flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
                  style={{
                    backgroundColor: isActive ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                    color: isActive ? 'hsl(30 3.3% 11.8% / 85%)' : 'hsl(30 3.3% 11.8% / 45%)',
                  }}
                  onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
                  onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
                >
                  {chart.label || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </button>
              );
            })}
            <button
              onClick={() => setActiveChart('stats')}
              className="flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
              style={{
                backgroundColor: activeChart === 'stats' ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                color: activeChart === 'stats' ? 'hsl(30 3.3% 11.8% / 85%)' : 'hsl(30 3.3% 11.8% / 45%)',
              }}
              onMouseEnter={e => { if (activeChart !== 'stats') (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
              onMouseLeave={e => { if (activeChart !== 'stats') (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
            >
              Statistics
            </button>
            {metricCards.length > 0 && (
              <button
                onClick={() => setMetricsOpen(prev => !prev)}
                className="flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
                style={{
                  backgroundColor: metricsOpen ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                  color: metricsOpen ? 'hsl(30 3.3% 11.8% / 85%)' : 'hsl(30 3.3% 11.8% / 45%)',
                }}
                onMouseEnter={e => { if (!metricsOpen) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
                onMouseLeave={e => { if (!metricsOpen) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
              >
                Metrics
              </button>
            )}
          </div>
        );


        const hslIcon = 'hsl(30 3.3% 11.8% / 85%)';
        const hslHoverBg = 'hsl(30 3.3% 11.8% / 6%)';
        const hslActiveBg = 'hsl(30 3.3% 11.8% / 8%)';

        const headerRight = (
          <div className="flex items-center gap-0.5 flex-shrink-0">
            {/* Export buttons — context-sensitive to active tab */}
            {activeChart !== 'stats' && result.charts?.[activeChart]?.plotly && (
              <>
                <Tooltip label="Reset axes">
                  <button
                    onClick={() => {
                      const gd = chartContainerRef.current?.querySelector('.js-plotly-plot') as HTMLElement | null;
                      if (gd) import('plotly.js/dist/plotly').then((Plotly: any) => Plotly.relayout(gd, { 'xaxis.autorange': true, 'yaxis.autorange': true }));
                    }}
                    className="p-1.5 rounded-md transition-colors"
                    style={{ color: hslIcon }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <Maximize className="w-4 h-4" />
                  </button>
                </Tooltip>
                <Tooltip label="Export as PNG">
                  <button
                    onClick={() => downloadChartPng(`twc-chart-${tabId}-${activeChart}`, `${selectedToolId}_${activeChart}_${(result.tickers || []).slice(0, 3).join('_')}`)}
                    className="p-1.5 rounded-md transition-colors"
                    style={{ color: hslIcon }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <Image className="w-4 h-4" />
                  </button>
                </Tooltip>
              </>
            )}
            {activeChart === 'stats' && result.stats_table && result.stats_table.length > 0 && (
              <>
                <Tooltip label="Export as CSV">
                  <button
                    onClick={downloadStatsCsv}
                    className="p-1.5 rounded-md transition-colors"
                    style={{ color: hslIcon }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <FileDown className="w-4 h-4" />
                  </button>
                </Tooltip>
                <Tooltip label="Export as Excel">
                  <button
                    onClick={downloadStatsExcel}
                    className="p-1.5 rounded-md transition-colors"
                    style={{ color: hslIcon }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <FileSpreadsheet className="w-4 h-4" />
                  </button>
                </Tooltip>
              </>
            )}
            {/* Divider */}
            <div className="w-px h-4 mx-0.5" style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 10%)' }} />
            {currentProcessId && (
              <Tooltip label="Edit & Re-run">
                <button
                  onClick={handleRerun}
                  className="p-1.5 rounded-md transition-colors"
                  style={{ color: hslIcon }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </Tooltip>
            )}
            <Tooltip label={isGraphView ? 'Show charts' : 'Show graph'}>
              <button
                onClick={() => setIsGraphView(!isGraphView)}
                className="p-1.5 rounded-md transition-colors"
                style={{
                  color: hslIcon,
                  backgroundColor: isGraphView ? hslActiveBg : 'transparent',
                }}
                onMouseEnter={e => { if (!isGraphView) e.currentTarget.style.backgroundColor = hslHoverBg; }}
                onMouseLeave={e => { if (!isGraphView) e.currentTarget.style.backgroundColor = 'transparent'; }}
              >
                <Workflow className="w-4 h-4" />
              </button>
            </Tooltip>
            {onToggleAIPanel && !showAIPanel && (
              <Tooltip label="Open Agent">
                <button
                  onClick={onToggleAIPanel}
                  className="p-1.5 rounded-md transition-colors"
                  style={{ color: hslIcon }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <img src="/sentry-icon.png" alt="" className="w-5 h-5 block" />
                </button>
              </Tooltip>
            )}
          </div>
        );

        return (
          <>
            {headerLeftPortal && createPortal(headerLeft, headerLeftPortal)}
            {headerRightPortal && createPortal(headerRight, headerRightPortal)}
          </>
        );
      })()}

      <div className="flex flex-col flex-1 min-h-0 relative">

        {/* Graph / Charts+Stats */}
        {isGraphView ? (
          <div style={{ width: '100%', height: '700px' }}>
            <Suspense fallback={<div className="h-full flex items-center justify-center text-gray-400 text-sm">Loading graph...</div>}>
              <ProcessFlowView process={result} />
            </Suspense>
          </div>
        ) : (
          <>
            {/* Chart/Stats Container */}
            <div className="flex flex-col flex-1 min-h-0 pt-2 pb-4">
              <Suspense fallback={<div className="flex-1 flex items-center justify-center text-sm text-gray-400">Loading chart...</div>}>
                  {/* Chart */}
                  {activeChart !== 'stats' && result.charts?.[activeChart]?.plotly && (
                    <div ref={chartContainerRef} className="relative flex-1 min-h-0 overflow-hidden plotly-chart-container">
                      <div className="resize-placeholder absolute inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-gray-50 to-slate-100 opacity-0 pointer-events-none z-10">
                        <div className="flex flex-col items-center gap-3">
                          <svg className="resize-spinner w-8 h-8 text-slate-400" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          <div className="flex items-center gap-1 text-sm text-slate-500 font-medium">
                            <span>Adjusting layout</span>
                            <span className="resize-dots flex gap-0.5">
                              <span className="w-1 h-1 bg-slate-400 rounded-full" />
                              <span className="w-1 h-1 bg-slate-400 rounded-full" />
                              <span className="w-1 h-1 bg-slate-400 rounded-full" />
                            </span>
                          </div>
                        </div>
                      </div>
                      <Plot
                        divId={`twc-chart-${tabId}-${activeChart}`}
                        data={result.charts[activeChart].plotly.data}
                        layout={(() => {
                          const { width: _w, height: _h, ...rest } = result.charts[activeChart].plotly.layout || {};
                          return {
                            ...rest,
                            autosize: true,
                            margin: { t: 40, r: 40, b: 60, l: 80 },
                            paper_bgcolor: 'white',
                            plot_bgcolor: 'white',
                            font: { family: 'system-ui, sans-serif', size: 12 },
                            dragmode: 'pan',
                          };
                        })()}
                        config={{ responsive: false, displayModeBar: false, displaylogo: false, scrollZoom: true }}
                        style={{ position: 'absolute', inset: 0 }}
                      />
                    </div>
                  )}
                  {activeChart !== 'stats' && !result.charts?.[activeChart]?.plotly && (
                    <div className="flex-1 flex items-center justify-center text-sm text-gray-400">No chart data</div>
                  )}

                  {/* Stats Table */}
                  {activeChart === 'stats' && (
                    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
                      {result.stats_table && result.stats_table.length > 0 ? (
                        <>
                          <div className="overflow-auto">
                            <table className="w-full text-sm">
                              <thead className="sticky top-0 bg-white">
                                <tr className="border-b border-gray-200">
                                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase bg-white">Category</th>
                                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase bg-white">Metric</th>
                                  <th className="text-right py-2 px-3 text-xs font-semibold text-gray-500 uppercase bg-white">Value</th>
                                  <th className="text-right py-2 px-3 text-xs font-semibold text-gray-500 uppercase bg-white">%</th>
                                </tr>
                              </thead>
                              <tbody>
                                {result.stats_table.map((r: StatsRow, i: number) => (
                                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                                    <td className="py-2 px-3 text-gray-600">{r.category}</td>
                                    <td className="py-2 px-3 font-medium text-gray-900">{r.metric}</td>
                                    <td className="py-2 px-3 text-right font-mono text-gray-900">{r.value}</td>
                                    <td className="py-2 px-3 text-right font-mono text-gray-500">{r.pct || '—'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      ) : (
                        <div className="flex items-center justify-center text-sm text-gray-400" style={{ height: 200 }}>No statistics available</div>
                      )}
                    </div>
                  )}
                </Suspense>
            </div>

          </>
        )}

        {/* Metrics Panel — slide-up overlay (matches PivotStatsPanel pattern) */}
        {!isGraphView && metricCards.length > 0 && (
          <ToolMetricsPanel
            cards={metricCards}
            isOpen={metricsOpen}
            height={metricsHeight}
            onHeightChange={setMetricsHeight}
            onClose={() => setMetricsOpen(false)}
          />
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-sm mx-4 shadow-xl">
            <h3 className="text-lg font-medium text-slate-900 mb-2">Delete Process</h3>
            <p className="text-sm text-slate-600 mb-4">
              Are you sure you want to delete &quot;{processName}&quot;? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowDeleteConfirm(false)} className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded transition-colors">
                Cancel
              </button>
              <button onClick={handleDeleteProcess} disabled={isDeleting} className="px-4 py-2 text-sm font-medium bg-red-600 text-white hover:bg-red-700 rounded transition-colors disabled:opacity-50">
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
