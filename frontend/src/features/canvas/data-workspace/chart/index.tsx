/**
 * ChartTabView - Renders chart tabs using Plotly
 * 
 * Features:
 * - Full inline configuration via sidebar panel
 * - Data selection editing (X-axis, Y-series)
 * - Series styling (colors, labels)
 * - Axis range controls
 * - Data filtering
 * - Toggle-able data table view
 * - Regression with visible stats
 */

import { useMemo, useState, useRef, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { lazy, Suspense } from 'react';
import { Pin, Download, Maximize } from 'lucide-react';
import { Tooltip } from '@/features/canvas/shared/Tooltip';
import { useDataWorkspaceStore, WorkspaceTab } from '../stores/dataWorkspaceStore';
import { usePinToSources } from '@/hooks/usePinToSources';
import { useChartData } from './hooks/useChartData';
import { getLightLayoutOverrides } from '@/config/plotly-theme';
import { getChartType } from './chartTypes';
import type { DotPlotChartOptions } from './chartTypes/dotPlot/DotPlotChart';
import type { HeatmapChartOptions } from './chartTypes/heatmap/HeatmapChart';
import type { Surface3DChartOptions } from './chartTypes/surface3d/Surface3DChart';
import type { ScatterChartOptions } from './chartTypes/scatter/ScatterChart';
import { getDotPlotAxisConfig } from './chartTypes/dotPlot/DotPlotChart';
import { ChartDataTable } from './components/ChartDataTable';
import ErrorBoundary from '@/components/Common/ErrorBoundary';

// Convert internal field names to user-friendly display names
const FIELD_DISPLAY_NAMES: Record<string, string> = {
  '_source_symbol': 'Symbol',
  '_row': 'Row',
  'fiscalYear': 'Fiscal Year',
  'calendarYear': 'Calendar Year',
};

function getFieldDisplayName(field: string): string {
  return FIELD_DISPLAY_NAMES[field] || field;
}

const Plot = lazy(() => import('react-plotly.js'));

// Default color palette for auto-expanded series
const SYMBOL_COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6', '#F97316', '#EF4444', '#6366F1', '#84CC16'];

/**
 * Auto-expand ySeries fields to include symbol-prefixed variants.
 * 
 * When data has multi-symbol columns like AAPL_close, GOOGL_close, AMZN_close,
 * and the user specifies just "close", this function expands it to all variants.
 * 
 * @param ySeries Original series configuration
 * @param dataFields Available fields in the data
 * @returns Expanded ySeries with symbol-prefixed fields
 */
function expandSymbolPrefixedSeries(
  ySeries: { field: string; label?: string; color?: string }[],
  dataFields: string[]
): { field: string; label?: string; color?: string }[] {
  const expandedSeries: { field: string; label?: string; color?: string }[] = [];
  
  for (const series of ySeries) {
    const field = series.field;
    
    // If the field exists directly, use it as-is
    if (dataFields.includes(field)) {
      expandedSeries.push(series);
      continue;
    }
    
    // Look for symbol-prefixed versions (e.g., AAPL_close, GOOGL_close for "close")
    const suffixPattern = new RegExp(`^([A-Z0-9]+)_${field}$`);
    const prefixedFields = dataFields.filter(f => suffixPattern.test(f));
    
    if (prefixedFields.length > 0) {
      // Sort alphabetically for consistent ordering
      prefixedFields.sort();
      
      // Expand to one series per symbol
      prefixedFields.forEach((prefixedField, idx) => {
        const match = prefixedField.match(suffixPattern);
        const symbol = match ? match[1] : prefixedField;
        
        expandedSeries.push({
          field: prefixedField,
          label: series.label ? `${symbol} ${series.label}` : `${symbol} ${field}`,
          color: series.color || SYMBOL_COLORS[idx % SYMBOL_COLORS.length],
        });
      });
      
      console.log(`[ChartTabView] Auto-expanded "${field}" to ${prefixedFields.length} symbol-prefixed fields:`, prefixedFields);
    } else {
      // Field not found anywhere - keep original (will likely show no data)
      expandedSeries.push(series);
    }
  }
  
  return expandedSeries;
}

interface Props {
  tabId: string;
  chartLocalId?: string;
  headerLeftPortal?: HTMLDivElement | null;
  headerRightPortal?: HTMLDivElement | null;
  showAIPanel?: boolean;
  onToggleAIPanel?: () => void;
}

function DataTableScrollArea({ children }: { children: React.ReactNode }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showTopFade, setShowTopFade] = useState(false);
  const [showBottomFade, setShowBottomFade] = useState(false);

  const updateFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setShowTopFade(el.scrollTop > 2);
    setShowBottomFade(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
  }, []);

  useEffect(() => { requestAnimationFrame(updateFades); }, [children, updateFades]);

  return (
    <div className="flex-1 relative min-h-0 overflow-hidden">
      {showTopFade && <div style={{ position: 'absolute', top: 28, left: 0, right: 0, height: 24, background: 'linear-gradient(to bottom, #f8f8f7, transparent)', zIndex: 15, pointerEvents: 'none' }} />}
      <div ref={scrollRef} onScroll={updateFades} className="h-full overflow-y-auto overflow-x-auto">
        {children}
      </div>
      {showBottomFade && <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 24, background: 'linear-gradient(to top, white, transparent)', zIndex: 5, pointerEvents: 'none' }} />}
    </div>
  );
}

export default function ChartTabView({ tabId, chartLocalId, headerLeftPortal, headerRightPortal, showAIPanel, onToggleAIPanel }: Props) {
  const tabs = useDataWorkspaceStore((s) => s.tabs);
  const { canPin, pinChart } = usePinToSources();

  // UI state
  const [showDataTable, setShowDataTable] = useState(false);
  const [isPinning, setIsPinning] = useState(false);
  const plotContainerRef = useRef<HTMLDivElement>(null);
  const plotDivRef = useRef<any>(null);
  const [dataTableHeight, setDataTableHeight] = useState(55);
  const dataTableRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = true;
    const container = dataTableRef.current?.parentElement;
    if (!container) return;

    const onMove = (ev: MouseEvent) => {
      if (!draggingRef.current) return;
      const rect = container.getBoundingClientRect();
      const pct = ((rect.bottom - ev.clientY) / rect.height) * 100;
      setDataTableHeight(Math.max(20, Math.min(85, pct)));
    };
    const onUp = () => {
      draggingRef.current = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, []);

  // Find the tab and resolve chart config
  const chartTab = tabs.find((t) => t.id === tabId) as WorkspaceTab | undefined;
  const config = chartLocalId
    ? chartTab?.chartResults?.find(r => r.localId === chartLocalId)?.config
    : chartTab?.chartConfig;

  const handleDownloadPng = useCallback(() => {
    const svg = plotContainerRef.current?.querySelector('.main-svg') as SVGSVGElement | null;
    if (!svg) return;
    const svgData = new XMLSerializer().serializeToString(svg);
    const canvas = document.createElement('canvas');
    const scale = 2;
    canvas.width = svg.clientWidth * scale;
    canvas.height = svg.clientHeight * scale;
    const ctx = canvas.getContext('2d')!;
    const img = new Image();
    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const link = document.createElement('a');
      link.download = `${config?.title || 'chart'}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    };
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
  }, [config?.title]);

  // Find source sheet
  const sourceTab = tabs.find((t) => t.id === config?.sourceTabId);
  const isLegacySheet = config?.sourceSheetId?.startsWith('legacy-');
  const sourceSheet = useMemo(() => {
    if (isLegacySheet) {
      return sourceTab?.datasets && sourceTab.datasets.length > 0
        ? { id: config?.sourceSheetId || '', name: sourceTab?.name || 'Unknown', datasets: sourceTab.datasets, compatibilityGroup: 'unknown' }
        : undefined;
    }
    return sourceTab?.sheets?.find((s) => s.id === config?.sourceSheetId);
  }, [isLegacySheet, sourceTab?.datasets, sourceTab?.sheets, sourceTab?.name, config?.sourceSheetId]);

  // Fetch chart data
  const { data, loading, error } = useChartData(config, sourceSheet, tabs);

  // Compute data min/max for X-axis (used for range fallbacks)
  const xAxisDataRange = useMemo(() => {
    if (!config?.xAxis || data.length === 0) return { min: null, max: null };
    const values = data.map(row => row[config.xAxis]).filter(v => v != null);
    if (values.length === 0) return { min: null, max: null };
    
    // Check if date or numeric
    const sample = values[0];
    if (typeof sample === 'string' && sample.match(/^\d{4}-\d{2}/)) {
      // Date - sort as strings
      const sorted = [...values].sort();
      return { min: sorted[0], max: sorted[sorted.length - 1] };
    } else if (typeof sample === 'number') {
      return { min: Math.min(...values as number[]), max: Math.max(...values as number[]) };
    }
    return { min: null, max: null };
  }, [config?.xAxis, data]);

  // Get the chart type definition
  const chartTypeDef = useMemo(() => getChartType(config?.chartType || 'line'), [config?.chartType]);
  
  // Get type-specific options with defaults
  const typeOptions = useMemo(() => {
    if (!chartTypeDef) return {};
    return { ...chartTypeDef.defaultOptions, ...(config?.typeOptions || {}) };
  }, [chartTypeDef, config?.typeOptions]);

    // Build Plotly traces (regression is computed inside buildTraces for scatter)
    const { traces, traceError } = useMemo(() => {
      if (!config || !data.length || !chartTypeDef) {
        console.log('[ChartTabView] Skipping trace build:', { hasConfig: !!config, dataLength: data.length, hasChartTypeDef: !!chartTypeDef });
        return { traces: [], traceError: null };
      }
      
      // Get all available fields from data
      const dataFields = data.length > 0 ? Object.keys(data[0]) : [];
      
      // Auto-expand symbol-prefixed fields (e.g., "close" -> ["AAPL_close", "GOOGL_close", ...])
      const expandedYSeries = expandSymbolPrefixedSeries(config.ySeries, dataFields);
    
      console.log('[ChartTabView] Building traces with:', {
        chartType: config.chartType,
        xAxis: config.xAxis,
        originalYSeries: config.ySeries,
        expandedYSeries,
        dataLength: data.length,
        dataSample: data.slice(0, 2),
        dataFields: dataFields.slice(0, 20),
      });
      
      const builtTraces = chartTypeDef.buildTraces(data, config.xAxis, expandedYSeries, typeOptions, config.ohlcFields);
      
      console.log('[ChartTabView] Built traces:', {
        tracesCount: builtTraces.length,
        tracesSummary: builtTraces.map(t => ({ name: t.name, xLength: t.x?.length, yLength: t.y?.length, xSample: t.x?.slice(0, 2), ySample: t.y?.slice(0, 2) })),
      });
    
    // Generate user-friendly error messages when traces are empty
    if (builtTraces.length === 0) {
      let errorMsg: string | null = null;
      
      if (config.chartType === 'heatmap') {
        const heatmapOpts = typeOptions as HeatmapChartOptions;
        if (heatmapOpts.correlationMode && config.ySeries.length < 2) {
          errorMsg = `Correlation heatmap requires at least 2 Y-series columns. Currently: ${config.ySeries.length}. Add more columns (e.g., open, high, low, close) or switch to "Custom Matrix" mode.`;
        } else if (!heatmapOpts.correlationMode && (!heatmapOpts.xField || !heatmapOpts.yField || !heatmapOpts.zField)) {
          errorMsg = 'Custom Matrix mode requires X, Y, and Z fields to be selected. Open Options panel to configure.';
        } else {
          errorMsg = 'Unable to build heatmap. Check that your data has the required fields and values.';
        }
      } else if (config.chartType === 'surface3d') {
        const surfaceOpts = typeOptions as Surface3DChartOptions;
        if (!surfaceOpts.xField || !surfaceOpts.yField || !surfaceOpts.zField) {
          errorMsg = '3D Surface requires X, Y, and Z fields. Open Options to select fields.';
        } else {
          errorMsg = 'Unable to build 3D surface. Need at least 3 valid data points.';
        }
      } else if (config.chartType === 'box' || config.chartType === 'violin') {
        errorMsg = `Add Y-series fields to compare distributions (e.g., P/E, P/B, Close). Each field becomes one ${config.chartType === 'box' ? 'box' : 'violin'}.`;
      } else if (config.chartType === 'radar') {
        errorMsg = 'Radar charts need at least 3 Y-series fields (e.g., PE, PB, ROE, CurrentRatio) to form a meaningful polygon.';
      } else {
        errorMsg = 'Unable to render chart. Check your data and configuration.';
      }
      
      return { traces: [], traceError: errorMsg };
    }
      return { traces: builtTraces, traceError: null };
    }, [config, data, chartTypeDef, typeOptions]);

  // Check if regression is enabled (for showing stats)
  const regressionEnabled = config?.chartType === 'scatter' && 
    (typeOptions as ScatterChartOptions).regression?.enabled;

  // Detect if box/violin is in "field comparison mode" (X = field names, not data column)
  const isFieldComparisonMode = useMemo(() => {
    if (!config || !data.length) return false;
    if (config.chartType !== 'box' && config.chartType !== 'violin') return false;
    
    // Same check as in buildTraces
    const categoryCount = new Map<string, number>();
    data.forEach(row => {
      const cat = String(row[config.xAxis] ?? '_none_');
      categoryCount.set(cat, (categoryCount.get(cat) || 0) + 1);
    });
    const avgPerCategory = data.length / categoryCount.size;
    return avgPerCategory < 3 || !config.xAxis;
  }, [config, data]);

  // Build layout
  const layout = useMemo(() => {
    const baseLayout = getLightLayoutOverrides();
    
    // Determine X-axis label - use "Field" for box/violin in field comparison mode
    let xAxisTitle = config?.xAxisLabel || (config?.xAxis ? getFieldDisplayName(config.xAxis) : undefined);
    if (isFieldComparisonMode) {
      xAxisTitle = config?.xAxisLabel || 'Field';
    }
    
    // Determine Y-axis label - indicate normalization for box/violin
    let yAxisTitle = config?.yAxisLabel;
    if ((config?.chartType === 'box' || config?.chartType === 'violin') && typeOptions.normalize && typeOptions.normalize !== 'none') {
      const normLabels: Record<string, string> = {
        zscore: 'Z-Score (σ)',
        minmax: 'Normalized (0-100)',
        percent: '% from Mean',
      };
      yAxisTitle = config?.yAxisLabel || normLabels[typeOptions.normalize] || 'Value';
    }
    
    let finalLayout: any = {
      ...baseLayout,
      title: config?.title || undefined,
      showlegend: config?.showLegend ?? true,
      dragmode: 'pan',
      xaxis: {
        ...baseLayout.xaxis,
        title: xAxisTitle,
        showgrid: config?.showGrid ?? true,
        // Apply X-axis range if any value is set (use data range as fallback)
        ...(config?.xAxisRange && (config.xAxisRange[0] !== null || config.xAxisRange[1] !== null)
          ? { 
              range: [
                config.xAxisRange[0] ?? xAxisDataRange.min,
                config.xAxisRange[1] ?? xAxisDataRange.max,
              ],
              autorange: false,
            }
          : { autorange: true }),
      },
      yaxis: {
        ...baseLayout.yaxis,
        title: yAxisTitle || undefined,
        showgrid: config?.showGrid ?? true,
        // Apply Y-axis range (requires both min and max for numeric axes)
        ...(config?.yAxisRange && config.yAxisRange[0] !== null && config.yAxisRange[1] !== null
          ? { 
              range: config.yAxisRange,
              autorange: false,
            }
          : { autorange: true }),
      },
      // For 3D charts - pass z-axis label
      zaxis: {
        title: config?.zAxisLabel || undefined,
      },
      autosize: true,
      margin: { l: 60, r: 40, t: config?.title ? 60 : 40, b: 60 },
    };
    if (chartTypeDef?.customizeLayout) {
      finalLayout = chartTypeDef.customizeLayout(finalLayout, typeOptions) as typeof finalLayout;
    }
    
    // Apply DotPlot axis config (maps numeric indices to category labels)
    if (config?.chartType === 'dotPlot' && data.length > 0 && config.xAxis) {
      const dotPlotAxisConfig = getDotPlotAxisConfig(
        data,
        config.xAxis,
        (typeOptions as DotPlotChartOptions).orientation || 'vertical'
      );
      finalLayout = {
        ...finalLayout,
        xaxis: { ...finalLayout.xaxis, ...dotPlotAxisConfig.xaxis },
        yaxis: { ...finalLayout.yaxis, ...dotPlotAxisConfig.yaxis },
      };
    }
    
    return finalLayout;
  }, [config, chartTypeDef, typeOptions, isFieldComparisonMode, xAxisDataRange, data]);

  if (!config) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
        Chart configuration not found
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <svg className="w-8 h-8 animate-spin mx-auto text-emerald-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <div className="text-sm text-slate-500 mt-2">Loading chart data...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-red-500 text-sm">
        Error: {error}
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
        No data available for this chart
      </div>
    );
  }

  const traceErrorContent = traceError ? (
    <div className="flex items-center justify-center h-full text-slate-400">
      <div className="text-center">
        <svg className="w-16 h-16 mx-auto mb-4 text-slate-200" fill="none" stroke="currentColor" strokeWidth={1} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
        <div className="text-sm font-medium">Configure Your Chart</div>
        <div className="text-xs text-slate-400 mt-1">Select fields for X-Axis and Y-Series</div>
      </div>
    </div>
  ) : null;

  const hslActiveBg = 'hsl(30 3.3% 11.8% / 8%)';
  const hslActiveText = 'hsl(30 3.3% 11.8% / 85%)';
  const hslInactiveText = 'hsl(30 3.3% 11.8% / 45%)';
  const hslHoverBg = 'hsl(30 3.3% 11.8% / 6%)';

  const headerLeftContent = (
    <>
      <button
        onClick={() => setShowDataTable(!showDataTable)}
        className="flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
        style={{
          backgroundColor: showDataTable ? hslActiveBg : 'transparent',
          color: showDataTable ? hslActiveText : hslInactiveText,
        }}
        onMouseEnter={e => { if (!showDataTable) e.currentTarget.style.backgroundColor = hslHoverBg; }}
        onMouseLeave={e => { e.currentTarget.style.backgroundColor = showDataTable ? hslActiveBg : 'transparent'; }}
      >
        Data
      </button>
    </>
  );

  const headerRightContent = (
    <>
      {canPin && config && (
        <button
          onClick={async () => {
            if (!config) return;
            setIsPinning(true);
            await pinChart({
              chartId: config.id,
              chartType: config.chartType,
              title: config.title,
              xAxis: config.xAxis,
              ySeries: config.ySeries || [],
              sourceSheet: sourceSheet?.name,
            });
            setIsPinning(false);
          }}
          disabled={isPinning}
          className="flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap disabled:opacity-50"
          style={{
            backgroundColor: 'transparent',
            color: hslInactiveText,
          }}
          onMouseEnter={e => { e.currentTarget.style.backgroundColor = hslHoverBg; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          title="Pin to Studio Sources"
        >
          <Pin className="w-3.5 h-3.5 mr-1" />
          Pin
        </button>
      )}
      <Tooltip label="Reset axes">
        <button
          onClick={() => {
            const gd = plotDivRef.current;
            if (gd) import('plotly.js/dist/plotly').then((Plotly: any) => Plotly.relayout(gd, { 'xaxis.autorange': true, 'yaxis.autorange': true }));
          }}
          className="p-1.5 rounded-md transition-colors"
          style={{ color: 'hsl(30 3.3% 11.8% / 85%)' }}
          onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <Maximize className="w-4 h-4" />
        </button>
      </Tooltip>
      <Tooltip label="Download as PNG">
        <button
          onClick={handleDownloadPng}
          className="p-1.5 rounded-md transition-colors"
          style={{ color: 'hsl(30 3.3% 11.8% / 85%)' }}
          onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <Download className="w-4 h-4" />
        </button>
      </Tooltip>
      {onToggleAIPanel && !showAIPanel && (
        <Tooltip label="Open Agent">
          <button
            onClick={onToggleAIPanel}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'hsl(30 3.3% 11.8% / 85%)' }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <img src="/sentry-icon.png" alt="" className="w-5 h-5 block" />
          </button>
        </Tooltip>
      )}
    </>
  );

  return (
    <div className="flex-1 relative flex flex-col overflow-hidden bg-white min-h-0">
      {/* Portal header content into shared header card */}
      {headerLeftPortal && createPortal(headerLeftContent, headerLeftPortal)}
      {headerRightPortal && createPortal(headerRightContent, headerRightPortal)}

      {/* Regression indicator (equation shown in legend) */}
      {regressionEnabled && (
        <div className="px-3 py-1 bg-gradient-to-r from-indigo-50 to-white border-b border-indigo-100 flex items-center gap-2 flex-shrink-0">
          <span className="text-[10px] font-medium text-indigo-600 uppercase tracking-wide">
            Regression: {(typeOptions as ScatterChartOptions).regression?.type}
          </span>
          <span className="text-[10px] text-slate-500">
            (equation & R² shown in legend)
          </span>
        </div>
      )}

      {/* Plotly Chart or Error */}
      {traceErrorContent ? (
        traceErrorContent
      ) : (
        <div ref={plotContainerRef} className="flex-1 p-2 overflow-hidden min-h-[300px]">
          <ErrorBoundary>
            <Suspense fallback={<div className="text-sm text-slate-400">Loading chart...</div>}>
              <Plot
                data={traces}
                layout={layout}
                config={{ scrollZoom: true, displayModeBar: false, displaylogo: false, responsive: true }}
                className="w-full h-full"
                useResizeHandler
                style={{ width: '100%', height: '100%' }}
                onError={(err) => console.error('[Plotly] Error:', err)}
                onInitialized={(_figure: any, graphDiv: any) => { plotDivRef.current = graphDiv; }}
              />
            </Suspense>
          </ErrorBoundary>
        </div>
      )}

      {/* Data Table — slide-up overlay (matches PivotStatsPanel) */}
      <div
        ref={dataTableRef}
        className="absolute bottom-0 left-0 right-0 z-30 bg-white flex flex-col shadow-[0_-4px_24px_rgba(0,0,0,0.08)] rounded-t-xl"
        style={{
          height: `${dataTableHeight}%`,
          borderTop: '1px solid hsl(30 3.3% 11.8% / 15%)',
          transform: showDataTable ? 'translateY(0)' : 'translateY(100%)',
          transition: draggingRef.current ? 'none' : 'transform 0.3s ease-out',
        }}
      >
        <div className="flex-shrink-0 relative" style={{ height: 44, borderBottom: '0.5px solid hsl(30 3.3% 11.8% / 10%)' }}>
          <div
            onMouseDown={onResizeStart}
            className="absolute top-0 left-0 right-0 flex justify-center pt-1.5 cursor-row-resize z-10"
          >
            <div className="w-8 h-1 rounded-full" style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }} />
          </div>
          <div className="h-full px-4 flex items-center justify-between">
            <span style={{ fontSize: '0.688rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)' }}>Data</span>
            <button
              onClick={() => setShowDataTable(false)}
              className="p-1 rounded transition-colors"
              style={{ color: 'hsl(60 2.5% 23.3% / 25%)' }}
              onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 8%)'; e.currentTarget.style.color = 'hsl(60 2.5% 23.3% / 60%)'; }}
              onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'hsl(60 2.5% 23.3% / 25%)'; }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        <DataTableScrollArea>
          {showDataTable && (
            <ChartDataTable
              data={data}
              xAxis={config?.xAxis || ''}
              ySeries={config?.ySeries || []}
              maxRows={50}
            />
          )}
        </DataTableScrollArea>
      </div>
    </div>
  );
}
