/**
 * PropertyTable - Dataset-centric table view with optional joining
 * 
 * Supports two modes:
 * - Separate: Each dataset is rendered as its own table section
 * - Joined: Datasets in the same sheet are joined on their time key
 */

import React, { useEffect, useCallback, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import api from '@/services/api';
// DatasetsDropdown is now rendered by DataWorkspace directly in the shared header
import { VirtualTable } from './VirtualTable';
import { Tooltip } from '@/features/canvas/shared/Tooltip';
import { Network, RefreshCw, FileDown, FileSpreadsheet, ChevronLeft, ChevronRight, ChevronDown, TriangleAlert } from 'lucide-react';

/** Wrapper that shows edge fades only when content is clipped.
 *  Uses overlay gradients (not mask-image) so the native scrollbar is never affected. */
function TableFadeWrapper({ children, className = '', style }: { children: React.ReactNode; className?: string; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null);
  const [fades, setFades] = useState({ top: false, right: false, bottom: false, left: false });
  const [scrollbarSize, setScrollbarSize] = useState({ x: 0, y: 0 });

  const update = useCallback(() => {
    const el = ref.current?.querySelector('[class*="overflow-auto"]') as HTMLElement | null;
    if (!el) return;
    setScrollbarSize({
      y: el.offsetWidth - el.clientWidth,
      x: el.offsetHeight - el.clientHeight,
    });
    setFades({
      top: el.scrollTop > 2,
      right: el.scrollLeft + el.clientWidth < el.scrollWidth - 2,
      bottom: el.scrollTop + el.clientHeight < el.scrollHeight - 2,
      left: el.scrollLeft > 2,
    });
  }, []);

  useEffect(() => {
    const el = ref.current?.querySelector('[class*="overflow-auto"]') as HTMLElement | null;
    if (!el) return;
    update();
    el.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', update); ro.disconnect(); };
  }, [update]);

  const sbY = scrollbarSize.y;
  const sbX = scrollbarSize.x;

  return (
    <div ref={ref} className={`relative ${className}`} style={style}>
      {children}
      {fades.top    && <div className="pointer-events-none absolute left-0 h-10 z-20" style={{ top: 33, right: sbY, background: 'linear-gradient(to bottom, white, transparent)' }} />}
      {fades.right  && <div className="pointer-events-none absolute z-20" style={{ top: 43, right: sbY, bottom: sbX, width: 48, background: 'linear-gradient(to left, white, transparent)' }} />}
      {fades.bottom && <div className="pointer-events-none absolute left-0 h-10 z-20" style={{ bottom: sbX, right: sbY, background: 'linear-gradient(to top, white, transparent)' }} />}
      {fades.left   && <div className="pointer-events-none absolute left-0 z-20" style={{ top: 43, bottom: sbX, width: 48, background: 'linear-gradient(to right, white, transparent)' }} />}
    </div>
  );
}
import { OntologyGraph } from '../../components';
import { useDataWorkspaceStore, DatasetConfig } from '../../stores/dataWorkspaceStore';
import {
  selectActiveGroupDatasets,
  selectActiveGroup,
  selectMergedDatasetIds,
  selectActiveDatasetId,
} from '../../stores/selectors';
import { joinDatasets, getJoinDescription } from '@/utils/dataJoin';
import { aggregateToGranularity, detectGranularity, Granularity } from '@/utils/timeAlignment';

interface SelectedObject {
  symbol: string;
  name?: string;
  objectType: string;
}

interface PropertyTableProps {
  symbols: string[];
  objectType?: string;
  /** Full selected objects with type info - used for multi-object support */
  selectedObjects?: SelectedObject[];
  dateFrom?: string;
  dateTo?: string;
  period?: string;
  limit?: number;
  onExport?: (data: { columns: string[]; rows: any[][] }) => void;
  /** When true, joins data on date only (not symbol+date) for cross-asset joins */
  /** Dataset management handlers */
  onRemoveDataset?: (id: string) => void;
  onResetWorkspace?: () => void;
  /** Toggle ontology graph view */
  onToggleOntology?: () => void;
  /** Whether ontology view is active */
  ontologyActive?: boolean;
  /** Whether AI chat panel is open */
  showAIPanel?: boolean;
  /** Toggle AI chat panel */
  onToggleAIPanel?: () => void;
  /** Register navigate-to-dataset callback with parent (for WorkspaceSidebar) */
  registerNavigateToDataset?: (fn: (endpoint: string) => void) => void;
  /** Portal target for left header content (dataset info, join controls) */
  headerLeftPortal?: HTMLDivElement | null;
  /** Portal target for right header content (toolbar icons) */
  headerRightPortal?: HTMLDivElement | null;
  /** When true, component renders with display:none (preserves state) */
  hidden?: boolean;
  onCurrentDatasetChange?: (dataset: DatasetConfig) => void;
}

// Dataset result with all rows preserved
interface DatasetResult {
  dataset: DatasetConfig;
  columns: string[];
  rows: Record<string, any>[];
  error?: string;
}

// Join mode options
type JoinMode = 'symbol_date' | 'date_only';

// Target granularity for aggregation
type TargetGranularity = 'raw' | 'daily' | 'weekly' | 'monthly' | 'quarterly';

// ============================================================================
// MODULE-LEVEL CACHE - Persists across component unmounts and tab switches
// ============================================================================
const datasetCache = new Map<string, DatasetResult>();

// Generate a cache key for a dataset
function generateCacheKey(ds: { symbol: string; endpoint: string; params?: Record<string, any>; fields: string[] }): string {
  return `${ds.symbol}:${ds.endpoint}:${JSON.stringify(ds.params || {})}:${ds.fields.join(',')}`;
}

const GRANULARITY_OPTIONS: { value: TargetGranularity; label: string; description: string }[] = [
  { value: 'raw', label: 'Raw', description: 'No aggregation' },
  { value: 'daily', label: 'Daily', description: 'Aggregate to daily' },
  { value: 'weekly', label: 'Weekly', description: 'Aggregate to weekly' },
  { value: 'monthly', label: 'Monthly', description: 'Aggregate to monthly' },
  { value: 'quarterly', label: 'Quarterly', description: 'Aggregate to quarterly' },
];

export const PropertyTable: React.FC<PropertyTableProps> = ({
  symbols,
  objectType = 'equity',
  selectedObjects,
  onExport,
  onRemoveDataset,
  onResetWorkspace,
  onToggleOntology,
  ontologyActive,
  showAIPanel,
  onToggleAIPanel,
  registerNavigateToDataset,
  headerLeftPortal,
  headerRightPortal,
  hidden,
  onCurrentDatasetChange,
}) => {
  // Use selector for datasets (from active group in active tab)
  const datasets = useDataWorkspaceStore(selectActiveGroupDatasets);
  const activeGroup = useDataWorkspaceStore(selectActiveGroup);

  const showFieldPicker = useDataWorkspaceStore(s => s.fieldPickerOpen);
  const setSidebarInitialEndpoint = useDataWorkspaceStore(s => s.setSidebarInitialEndpoint);
  const setSidebarInitialDatasetId = useDataWorkspaceStore(s => s.setSidebarInitialDatasetId);
  
  // Store results per dataset, preserving all rows
  const [datasetResults, setDatasetResults] = React.useState<DatasetResult[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  
  // Explicit merge: user picks which datasets to merge with the current page (persisted in store)
  const mergedDatasetIdsArray = useDataWorkspaceStore(selectMergedDatasetIds);
  const mergedDatasetIds = useMemo(() => new Set(mergedDatasetIdsArray), [mergedDatasetIdsArray]);

  // Join mode: 'symbol_date' (default) or 'date_only' (cross-asset)
  // Auto-switches to 'date_only' when multiple symbols detected
  const [joinMode, setJoinMode] = React.useState<JoinMode>('symbol_date');
  const [showJoinOptions, setShowJoinOptions] = React.useState(false);
  const joinButtonRef = useRef<HTMLButtonElement>(null);

  const getJoinDropdownPosition = useCallback(() => {
    if (!joinButtonRef.current) return { top: 0, left: 0 };
    const rect = joinButtonRef.current.getBoundingClientRect();
    return { top: rect.bottom + 4, left: rect.left };
  }, []);
  
  // Target granularity for aggregation
  const [targetGranularity, setTargetGranularity] = React.useState<TargetGranularity>('raw');
  const [showGranularityOptions, setShowGranularityOptions] = React.useState(false);
  const granularityButtonRef = useRef<HTMLButtonElement>(null);

  const getGranularityDropdownPosition = useCallback(() => {
    if (!granularityButtonRef.current) return { top: 0, left: 0 };
    const rect = granularityButtonRef.current.getBoundingClientRect();
    return { top: rect.bottom + 4, left: rect.left };
  }, []);
  
  // Pagination: derive currentPage from persisted activeDatasetId
  const activeDatasetId = useDataWorkspaceStore(selectActiveDatasetId);
  const setActiveDatasetId = useDataWorkspaceStore(s => s.setActiveDatasetId);

  const currentPage = useMemo(() => {
    if (!activeDatasetId || datasets.length === 0) return 0;
    const idx = datasets.findIndex(d => d.id === activeDatasetId);
    return idx >= 0 ? idx : 0;
  }, [activeDatasetId, datasets]);

  const navigateToPage = useCallback((pageIdx: number) => {
    const clamped = Math.max(0, Math.min(datasets.length - 1, pageIdx));
    setActiveDatasetId(datasets[clamped]?.id);
  }, [datasets, setActiveDatasetId]);
  
  // Get compatibility group from first dataset (smart join handles cross-group joining)
  const compatibilityGroup = datasets[0]?.compatibilityGroup || 'unknown';
  
  // Check if we have multiple symbols (makes date-only join relevant)
  const hasMultipleSymbols = useMemo(() => {
    const uniqueSymbols = new Set(datasets.map(d => d.symbol));
    return uniqueSymbols.size > 1;
  }, [datasets]);

  // Get all symbol-endpoint pairs for display (supports multiple endpoints per symbol)
  const datasetDisplayList = useMemo(() => {
    return datasets.map(d => ({
      symbol: d.symbol,
      endpoint: d.endpoint,
      id: d.id,
    }));
  }, [datasets]);
  
  // Track previous hasMultipleSymbols to detect transitions
  const prevHasMultipleSymbolsRef = React.useRef(hasMultipleSymbols);
  
  // Auto-switch to date_only ONLY when hasMultipleSymbols transitions from false to true
  // This prevents fighting with explicit user selection of 'symbol_date'
  React.useEffect(() => {
    const wasMultiple = prevHasMultipleSymbolsRef.current;
    prevHasMultipleSymbolsRef.current = hasMultipleSymbols;
    
    // Only auto-switch when transitioning TO multiple symbols (not when user changes joinMode)
    if (!wasMultiple && hasMultipleSymbols && joinMode === 'symbol_date') {
      setJoinMode('date_only');
    }
  }, [hasMultipleSymbols, joinMode]);


  // Whether the merge view is active (user has selected datasets to merge)
  const isMerged = mergedDatasetIds.size > 0;


  // Compute joined data only when user has explicitly merged datasets
  const joinedData = useMemo(() => {
    if (!isMerged || datasetResults.length === 0) {
      return null;
    }

    // Filter to only the current page's dataset + the user-selected merged datasets
    const currentDataset = datasets[currentPage];
    if (!currentDataset) return null;
    const mergeIds = new Set([currentDataset.id, ...mergedDatasetIds]);
    let processedResults = datasetResults.filter(r => mergeIds.has(r.dataset.id));
    if (processedResults.length <= 1) return null;

    // If a target granularity is selected (not 'raw'), aggregate each dataset first
    if (targetGranularity !== 'raw') {
      processedResults = processedResults.map(result => {
        if (result.rows.length === 0 || result.error) return result;

        const sourceGranularity = detectGranularity(
          result.dataset.structureType,
          result.rows as Record<string, unknown>[]
        );

        const dateField = result.columns.find(c =>
          ['date', 'datetime', 'timestamp'].includes(c.toLowerCase())
        ) || 'date';

        const aggregatedRows = aggregateToGranularity(
          result.rows as Record<string, unknown>[],
          sourceGranularity,
          targetGranularity as Granularity,
          dateField,
          undefined,
          'symbol'
        );

        const newColumns = aggregatedRows.length > 0
          ? Object.keys(aggregatedRows[0])
          : result.columns;

        return {
          ...result,
          rows: aggregatedRows as Record<string, any>[],
          columns: newColumns,
        };
      });
    }

    return joinDatasets(processedResults, compatibilityGroup, { crossSymbolJoin: joinMode === 'date_only' });
  }, [isMerged, datasetResults, datasets, currentPage, mergedDatasetIds, compatibilityGroup, joinMode, targetGranularity]);

  // Use module-level cache key generator
  const getDatasetKey = useCallback((ds: DatasetConfig) => generateCacheKey(ds), []);
  
  // Track previous datasets key to detect actual changes (not just reference changes)
  const prevDatasetsKeyRef = React.useRef<string>('');

  // Fetch a single dataset
  const fetchSingleDataset = useCallback(async (ds: DatasetConfig): Promise<DatasetResult> => {
    try {
      const response = await api.post('/api/canvas/data/endpoint/fetch', {
        symbol: ds.symbol,
        endpoint: ds.endpoint,
        params: ds.params || {},
        fields: ds.fields.length > 0 ? ds.fields : undefined,
      });
      
      const endpointData = response.data?.data?.[ds.endpoint];
      
      if (!endpointData) {
        return {
          dataset: ds,
          columns: [],
          rows: [],
          error: 'No data returned',
        };
      }
      
      // Keep ALL rows - FMP returns data newest-first (future estimates first)
      const rows = Array.isArray(endpointData) ? endpointData : [endpointData];
      
      // Filter to selected fields if specified, but only if fields actually exist in data
      let filteredRows = rows;
      if (ds.fields.length > 0 && rows.length > 0) {
        const firstRowKeys = new Set(Object.keys(rows[0] || {}));
        const validFields = ds.fields.filter(f => firstRowKeys.has(f));
        
        // Only filter if we have valid matching fields
        if (validFields.length > 0) {
          filteredRows = rows.map(row => {
            const filtered: Record<string, any> = {};
            validFields.forEach(field => {
              if (field in row) {
                filtered[field] = row[field];
              }
            });
            return filtered;
          });
        }
        // else: keep all data unfiltered (bogus field names)
      }
      
      // Get columns from first row
      const columns = filteredRows.length > 0 ? Object.keys(filteredRows[0]) : [];
      
      return {
        dataset: ds,
        columns,
        rows: filteredRows,
      };
    } catch (e: any) {
      return {
        dataset: ds,
        columns: [],
        rows: [],
        error: e.message || 'Fetch failed',
      };
    }
  }, []);

  // Fetch data - only refetch datasets that have changed
  // Uses MODULE-LEVEL cache that persists across tab switches and component remounts
  const fetchData = useCallback(async (forceAll = false) => {
    if (datasets.length === 0) {
      setDatasetResults([]);
      return;
    }

    setError(null);
    
    // Determine which datasets need fetching (check module-level cache)
    const toFetch: DatasetConfig[] = [];
    const cachedResultsByKey: Map<string, DatasetResult> = new Map();
    
    for (const ds of datasets) {
      const key = getDatasetKey(ds);
      const cached = datasetCache.get(key);
      if (!forceAll && cached) {
        // Use cached result but update the dataset reference (in case id changed but content same)
        cachedResultsByKey.set(key, { ...cached, dataset: ds });
      } else {
        toFetch.push(ds);
      }
    }
    
    // If nothing to fetch, just reorder from cache
    if (toFetch.length === 0) {
      console.log('[DatasetTable] All datasets from cache, skipping fetch');
      const orderedResults = datasets.map(ds => cachedResultsByKey.get(getDatasetKey(ds))!);
      setDatasetResults(orderedResults);
      return;
    }
    
    console.log(`[DatasetTable] Fetching ${toFetch.length} datasets, ${datasets.length - toFetch.length} from cache`);
    
    // Show loading only if fetching
    setLoading(true);
    
    try {
      // Fetch only the changed datasets in parallel
      const newResults = await Promise.all(
        toFetch.map(ds => fetchSingleDataset(ds))
      );
      
      // Update module-level cache with new results
      for (const result of newResults) {
        const key = getDatasetKey(result.dataset);
        datasetCache.set(key, result);
        cachedResultsByKey.set(key, result);
      }
      
      // Build ordered results maintaining dataset order
      const orderedResults = datasets.map(ds => cachedResultsByKey.get(getDatasetKey(ds))!);
      setDatasetResults(orderedResults);
    } catch (e: any) {
      setError(e.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [datasets, getDatasetKey, fetchSingleDataset]);

  // Force refresh all datasets (for manual refresh button)
  const forceRefreshAll = useCallback(() => {
    // Clear only the datasets currently in view from cache
    for (const ds of datasets) {
      datasetCache.delete(getDatasetKey(ds));
    }
    fetchData(true);
  }, [fetchData, datasets, getDatasetKey]);

  // Create a stable key that represents the actual dataset content (not just array reference)
  const datasetsContentKey = React.useMemo(() =>
    datasets.map(d => getDatasetKey(d)).sort().join('|'),
    [datasets, getDatasetKey]
  );

  // Trigger fetch when datasets actually change (content-based, not reference-based)
  useEffect(() => {
    // Skip if the content hasn't actually changed (just a re-render with same data)
    if (prevDatasetsKeyRef.current === datasetsContentKey) {
      console.log('[DatasetTable] Skipping fetch - content unchanged');
      return;
    }
    prevDatasetsKeyRef.current = datasetsContentKey;
    fetchData();
  }, [datasetsContentKey, fetchData]);

  // Notify parent of the currently-viewed dataset
  useEffect(() => {
    const ds = datasetResults[currentPage]?.dataset;
    if (ds) onCurrentDatasetChange?.(ds);
  }, [currentPage, datasetResults, onCurrentDatasetChange]);

  // Pagination helpers
  const totalPages = datasetResults.length;
  const canGoPrev = currentPage > 0;
  const canGoNext = currentPage < totalPages - 1;
  const goToPage = useCallback((page: number) => navigateToPage(page), [navigateToPage]);

  // User-initiated navigation - also syncs sidebar to show the navigated dataset
  const navigateToPageWithSidebarSync = useCallback((page: number) => {
    const targetPage = Math.max(0, Math.min(totalPages - 1, page));
    navigateToPage(targetPage);
    if (showFieldPicker) {
      const targetDataset = datasetResults[targetPage];
      if (targetDataset) {
        setSidebarInitialEndpoint(targetDataset.dataset.endpoint);
        setSidebarInitialDatasetId(targetDataset.dataset.id);
      }
    }
  }, [totalPages, showFieldPicker, datasetResults, navigateToPage]);
  
  const goToPrev = () => navigateToPageWithSidebarSync(currentPage - 1);
  const goToNext = () => navigateToPageWithSidebarSync(currentPage + 1);

  // Pending navigation (for newly added datasets that aren't in results yet)
  const [pendingNavigate, setPendingNavigate] = React.useState<string | null>(null);

  // Navigate to a dataset by ID (dropdown) or endpoint (sidebar)
  const handleNavigateToDataset = useCallback((idOrEndpoint: string) => {
    let idx = datasetResults.findIndex(r => r.dataset.id === idOrEndpoint);
    if (idx < 0) {
      idx = datasetResults.findIndex(r => r.dataset.endpoint === idOrEndpoint);
    }
    if (idx >= 0) {
      goToPage(idx);
    } else {
      setPendingNavigate(idOrEndpoint);
    }
  }, [datasetResults, goToPage]);

  // Register navigate callback with parent (WorkspaceSidebar uses this)
  React.useEffect(() => {
    registerNavigateToDataset?.(handleNavigateToDataset);
  }, [handleNavigateToDataset, registerNavigateToDataset]);

  // Handle pending navigation when datasetResults update
  React.useEffect(() => {
    if (!pendingNavigate) return;

    let idx = datasetResults.findIndex(r => r.dataset.id === pendingNavigate);
    if (idx < 0) {
      idx = datasetResults.findIndex(r => r.dataset.endpoint === pendingNavigate);
    }
    if (idx >= 0) {
      goToPage(idx);
      setPendingNavigate(null);
    }
  }, [datasetResults, pendingNavigate, goToPage]);

  // NOTE: Removed the sync effect that was setting sidebarInitialEndpoint on page change.
  // This was causing issues where the sidebar would reset to the current page's endpoint
  // while the user was in the middle of adding a new endpoint.
  // Now the sidebar only changes when explicitly set via onOpenSidebarWithEndpoint.

  // Export all datasets to CSV
  const handleExport = useCallback(() => {
    if (datasetResults.length === 0) return;
    
    const sections: string[] = [];
    
    datasetResults.forEach(result => {
      if (result.rows.length === 0) return;
      
      sections.push(`# ${result.dataset.symbol} - ${result.dataset.endpoint}`);
      sections.push(result.columns.join(','));
      result.rows.forEach(row => {
        sections.push(result.columns.map(col => {
          const val = row[col];
          if (val === null || val === undefined) return '';
          if (typeof val === 'string' && val.includes(',')) return `"${val}"`;
          return String(val);
        }).join(','));
      });
      sections.push(''); // Empty line between datasets
    });

    const csvContent = sections.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `data_export_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);

    if (onExport) {
      const allCols = datasetResults.flatMap(r => r.columns);
      const allRows = datasetResults.flatMap(r => r.rows.map(row => r.columns.map(c => row[c])));
      onExport({ columns: [...new Set(allCols)], rows: allRows });
    }
  }, [datasetResults, onExport]);

  // Export to Excel (XLSX format using simple XML-based approach)
  const handleExcelExport = useCallback(() => {
    if (datasetResults.length === 0) return;
    
    // Build tab-separated content that Excel can open
    const sections: string[] = [];
    
    datasetResults.forEach(result => {
      if (result.rows.length === 0) return;
      
      sections.push(`${result.dataset.symbol}\t${result.dataset.endpoint}`);
      sections.push(result.columns.join('\t'));
      result.rows.forEach(row => {
        sections.push(result.columns.map(col => {
          const val = row[col];
          if (val === null || val === undefined) return '';
          return String(val).replace(/\t/g, ' ');
        }).join('\t'));
      });
      sections.push('');
    });

    const content = sections.join('\n');
    const blob = new Blob([content], { type: 'application/vnd.ms-excel;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `data_export_${new Date().toISOString().split('T')[0]}.xls`;
    link.click();
    URL.revokeObjectURL(url);
  }, [datasetResults]);

  // Calculate totals
  const totalRows = datasetResults.reduce((sum, r) => sum + r.rows.length, 0);
  const totalDatasets = datasetResults.length;


  // ========== HEADER CONTENT (extracted for portal support) ==========

  const headerLeftContent = (
    <>
      {/* Dataset-specific header — only rendered when the data table is the active content view */}
      {!hidden && (<>
      {/* Current dataset info — separate view shows single dataset, joined view shows merged summary */}
      {joinedData && joinedData.canJoin ? (
        <div className="flex items-center gap-1.5 min-w-0">
          <div className="relative min-w-0">
            <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-4 z-10 bg-gradient-to-r from-white to-transparent" />
            <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-4 z-10 bg-gradient-to-l from-white to-transparent" />
            <div className="flex items-center overflow-x-auto scrollbar-none whitespace-nowrap px-5">
              {datasetDisplayList.filter(ds => ds.id === datasets[currentPage]?.id || mergedDatasetIds.has(ds.id)).map((ds, idx) => (
                <span key={ds.id} className="text-xs text-slate-500 inline-flex items-center gap-1 leading-none">
                  {idx > 0 && <span className="text-slate-300" style={{ margin: '0 0.375rem 0 0.625rem' }}>+</span>}
                  <span className="font-medium text-slate-600">{ds.symbol}</span>
                  <span className="text-slate-300">—</span>
                  <span className="font-mono text-slate-400">{ds.endpoint}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : !joinedData && datasetResults.length > 0 && currentPage < datasetResults.length ? (
        <div className="flex items-center gap-2">
          <span className="font-mono font-semibold text-slate-900 text-xs leading-none">{datasetResults[currentPage].dataset.symbol}</span>
          <span className="text-slate-400 text-xs leading-none">→</span>
          <span className="text-xs text-slate-600 font-mono leading-none">{datasetResults[currentPage].dataset.endpoint}</span>
        </div>
      ) : null}
      {/* Show join info when datasets are merged */}
      {joinedData && joinedData.canJoin && joinedData.joinKeyDisplay && joinedData.joinKeyDisplay.length > 0 && (
        hasMultipleSymbols ? (
          <div className="flex-shrink-0">
            <button
              ref={joinButtonRef}
              onClick={() => setShowJoinOptions(!showJoinOptions)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
              style={{
                fontFamily: "system-ui, -apple-system, sans-serif",
                backgroundColor: showJoinOptions ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                color: 'hsl(30 3.3% 11.8% / 85%)',
              }}
              onMouseEnter={e => { if (!showJoinOptions) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
              onMouseLeave={e => { if (!showJoinOptions) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
              title="Click to change join parameters"
            >
              {getJoinDescription(joinedData.joinKey, joinedData.joinKeyDisplay)}
              <ChevronDown
                size={13}
                strokeWidth={2}
                className={`transition-transform ${showJoinOptions ? 'rotate-180' : ''}`}
                style={{ color: 'hsl(30 3.3% 11.8% / 45%)' }}
              />
            </button>
            {showJoinOptions && createPortal(
              <>
                <div className="fixed inset-0 z-[9998]" onClick={() => setShowJoinOptions(false)} />
                <div
                  className="fixed z-[9999] overflow-hidden"
                  style={{
                    ...getJoinDropdownPosition(),
                    width: 200,
                    backgroundColor: '#fff',
                    border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                    borderRadius: '0.75rem',
                    boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
                    fontFamily: "system-ui, -apple-system, sans-serif",
                    padding: '0.375rem',
                  }}
                >
                  {([
                    { value: 'symbol_date' as JoinMode, label: 'Symbol + Date', desc: 'Match both' },
                    { value: 'date_only' as JoinMode, label: 'Date Only', desc: 'Cross-asset' },
                  ]).map(opt => {
                    const isSelected = joinMode === opt.value;
                    return (
                      <button
                        key={opt.value}
                        onClick={() => { setJoinMode(opt.value); setShowJoinOptions(false); }}
                        className="w-full text-left"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          padding: '0.4rem 0.625rem',
                          margin: '1px 0',
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          cursor: 'pointer',
                          border: isSelected ? '0.5px solid hsl(30 3.3% 11.8% / 18%)' : '0.5px solid transparent',
                          borderRadius: '0.5rem',
                          backgroundColor: isSelected ? 'hsl(30 3.3% 11.8% / 6%)' : 'transparent',
                          color: isSelected ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 65%)',
                          transition: 'all 0.1s ease',
                          fontFamily: 'inherit',
                        }}
                        onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 4%)'; }}
                        onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
                      >
                        <span style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          flexShrink: 0,
                          backgroundColor: isSelected ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 20%)',
                          transition: 'background-color 0.15s ease',
                        }} />
                        <span>{opt.label}</span>
                        <span style={{
                          fontSize: '0.625rem',
                          color: 'hsl(60 2.5% 23.3% / 35%)',
                          marginLeft: 'auto',
                          fontWeight: 400,
                        }}>
                          {opt.desc}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </>,
              document.body
            )}
          </div>
        ) : (
          <span
            className="text-xs font-medium px-2.5 py-1 rounded-md leading-none"
            style={{
              fontFamily: "system-ui, -apple-system, sans-serif",
              color: 'hsl(30 3.3% 11.8% / 85%)',
            }}
          >
            {getJoinDescription(joinedData.joinKey, joinedData.joinKeyDisplay)}
          </span>
        )
      )}
      {/* Granularity selector */}
      {joinedData && joinedData.canJoin && !joinedData.isSnapshotJoin && (
        <div>
          <button
            ref={granularityButtonRef}
            onClick={() => setShowGranularityOptions(!showGranularityOptions)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
            style={{
              fontFamily: "system-ui, -apple-system, sans-serif",
              backgroundColor: showGranularityOptions ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
              color: 'hsl(30 3.3% 11.8% / 85%)',
            }}
            onMouseEnter={e => { if (!showGranularityOptions) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
            onMouseLeave={e => { if (!showGranularityOptions) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
          >
            {GRANULARITY_OPTIONS.find(g => g.value === targetGranularity)?.label || 'Raw'}
            <ChevronDown
              size={13}
              strokeWidth={2}
              className={`transition-transform ${showGranularityOptions ? 'rotate-180' : ''}`}
              style={{ color: 'hsl(30 3.3% 11.8% / 45%)' }}
            />
          </button>
          {showGranularityOptions && createPortal(
            <>
              <div className="fixed inset-0 z-[9998]" onClick={() => setShowGranularityOptions(false)} />
              <div
                className="fixed z-[9999] overflow-hidden"
                style={{
                  ...getGranularityDropdownPosition(),
                  width: 200,
                  backgroundColor: '#fff',
                  border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                  borderRadius: '0.75rem',
                  boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
                  fontFamily: "system-ui, -apple-system, sans-serif",
                  padding: '0.375rem',
                }}
              >
                {GRANULARITY_OPTIONS.map(opt => {
                  const isSelected = targetGranularity === opt.value;
                  return (
                    <button
                      key={opt.value}
                      onClick={() => { setTargetGranularity(opt.value); setShowGranularityOptions(false); }}
                      className="w-full text-left"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.4rem 0.625rem',
                        margin: '1px 0',
                        fontSize: '0.75rem',
                        fontWeight: 500,
                        cursor: 'pointer',
                        border: isSelected ? '0.5px solid hsl(30 3.3% 11.8% / 18%)' : '0.5px solid transparent',
                        borderRadius: '0.5rem',
                        backgroundColor: isSelected ? 'hsl(30 3.3% 11.8% / 6%)' : 'transparent',
                        color: isSelected ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 65%)',
                        transition: 'all 0.1s ease',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 4%)'; }}
                      onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
                    >
                      <span style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        flexShrink: 0,
                        backgroundColor: isSelected ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 20%)',
                        transition: 'background-color 0.15s ease',
                      }} />
                      <span>{opt.label}</span>
                      <span style={{
                        fontSize: '0.625rem',
                        color: 'hsl(60 2.5% 23.3% / 35%)',
                        marginLeft: 'auto',
                        fontWeight: 400,
                      }}>
                        {opt.description}
                      </span>
                    </button>
                  );
                })}
              </div>
            </>,
            document.body
          )}
        </div>
      )}
      {/* Show warning icon when join not possible */}
      {joinedData && !joinedData.canJoin && (
        <Tooltip label={joinedData.reason || 'Cannot join - showing separate'}>
          <span className="flex items-center text-amber-600 cursor-default">
            <TriangleAlert className="w-3.5 h-3.5" />
          </span>
        </Tooltip>
      )}
      </>)}
    </>
  );

  const hslIcon = 'hsl(30 3.3% 11.8% / 85%)';
  const hslIconActive = 'hsl(30 3.3% 11.8% / 85%)';
  const hslIconDisabled = 'hsl(30 3.3% 11.8% / 25%)';
  const hslHoverBg = 'hsl(30 3.3% 11.8% / 6%)';
  const hslActiveBg = 'hsl(30 3.3% 11.8% / 8%)';

  const headerRightContent = (
    <div className="flex items-center gap-0.5 flex-shrink-0">
      {onToggleOntology && (
        <Tooltip label="Ontology Graph">
          <button
            onClick={onToggleOntology}
            className="p-1.5 rounded-md transition-colors"
            style={{
              color: ontologyActive ? hslIconActive : hslIcon,
              backgroundColor: ontologyActive ? hslActiveBg : 'transparent',
            }}
            onMouseEnter={e => { if (!ontologyActive) e.currentTarget.style.backgroundColor = hslHoverBg; }}
            onMouseLeave={e => { if (!ontologyActive) e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <Network className="w-4 h-4" />
          </button>
        </Tooltip>
      )}
      <Tooltip label="Refresh data">
        <button
          onClick={forceRefreshAll}
          disabled={loading}
          className="p-1.5 rounded-md transition-colors disabled:cursor-not-allowed"
          style={{ color: loading ? hslIconDisabled : hslIcon }}
          onMouseEnter={e => { if (!loading) e.currentTarget.style.backgroundColor = hslHoverBg; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </Tooltip>
      <Tooltip label="Export as CSV">
        <button
          onClick={handleExport}
          disabled={totalRows === 0}
          className="p-1.5 rounded-md transition-colors disabled:cursor-not-allowed"
          style={{ color: totalRows === 0 ? hslIconDisabled : hslIcon }}
          onMouseEnter={e => { if (totalRows > 0) e.currentTarget.style.backgroundColor = hslHoverBg; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <FileDown className="w-4 h-4" />
        </button>
      </Tooltip>
      <Tooltip label="Export as Excel">
        <button
          onClick={() => handleExcelExport()}
          disabled={totalRows === 0}
          className="p-1.5 rounded-md transition-colors disabled:cursor-not-allowed"
          style={{ color: totalRows === 0 ? hslIconDisabled : hslIcon }}
          onMouseEnter={e => { if (totalRows > 0) e.currentTarget.style.backgroundColor = hslHoverBg; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <FileSpreadsheet className="w-4 h-4" />
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
      {/* Portal header content into shared header card when portals provided */}
      {headerLeftPortal && createPortal(headerLeftContent, headerLeftPortal)}
      {headerRightPortal && !hidden && createPortal(headerRightContent, headerRightPortal)}

      <div className="flex-1 flex flex-col min-w-0 min-h-0 gap-2" style={hidden ? { display: 'none' } : undefined}>
        {/* Table Content / Ontology Graph */}
        <div
          className="flex-1 overflow-auto min-h-0"
        >
          {ontologyActive && datasets.length > 0 ? (
            <OntologyGraph />
          ) : loading ? (
            <div className="h-full flex flex-col items-center justify-center p-8">
              <div className="flex gap-1 mb-4">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-pulse-quick" />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-pulse-quick" style={{ animationDelay: '0.2s' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-pulse-quick" style={{ animationDelay: '0.4s' }} />
              </div>
              <div className="text-xs font-medium text-slate-400 tracking-wide">Loading data</div>
              <div className="mt-5 w-48 space-y-2.5">
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full w-1/2 rounded-full bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 animate-shimmer" />
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full w-3/4 rounded-full bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 animate-shimmer" style={{ animationDelay: '0.3s' }} />
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full w-1/3 rounded-full bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 animate-shimmer" style={{ animationDelay: '0.6s' }} />
                </div>
              </div>
            </div>
          ) : error ? (
            <div className="p-8 text-center">
              <svg className="w-8 h-8 mx-auto mb-3 text-rose-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div className="text-sm text-rose-600">{error}</div>
            </div>
          ) : datasets.length === 0 ? null
          : joinedData && joinedData.canJoin && joinedData.rows.length > 0 ? (
            /* Joined View - Single merged table */
            <div className="flex flex-col h-full">
              {/* Joined table - virtualized for performance */}
              <div className="flex-1 min-h-0">
                <TableFadeWrapper className="h-full overflow-hidden">
                  <VirtualTable
                    columns={joinedData.columns}
                    rows={joinedData.rows}
                    joinKeyDisplay={joinedData.joinKeyDisplay}
                    rowHeight={35}
                    overscan={20}
                    className="h-full scrollbar-visible"
                  />
                </TableFadeWrapper>
              </div>
            </div>
          ) : datasetResults.length > 0 && currentPage < datasetResults.length ? (
            /* Separate View - Paginated: One table per page */
            <div className="flex flex-col h-full">
              {/* Current Dataset Table */}
              {(() => {
                const result = datasetResults[currentPage];
                if (!result) return null;
                
                return (
                  <div className="flex-1 flex flex-col overflow-hidden">
                    {/* Dataset Table or Error - virtualized for performance */}
                    {result.error ? (
                      <div className="h-full flex flex-col items-center justify-center p-8 text-center">
                        <div className="w-10 h-10 mb-3 rounded-full bg-rose-50 flex items-center justify-center">
                          <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                          </svg>
                        </div>
                        <div className="text-sm font-medium text-slate-600 mb-1">{result.error}</div>
                        <div className="text-xs text-slate-400">Try adjusting the parameters or selecting a different endpoint</div>
                      </div>
                    ) : result.rows.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center p-8 text-center">
                        <div className="w-10 h-10 mb-3 rounded-full bg-slate-50 flex items-center justify-center">
                          <svg className="w-5 h-5 text-slate-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776" />
                          </svg>
                        </div>
                        <div className="text-sm font-medium text-slate-500 mb-1">No data returned</div>
                        <div className="text-xs text-slate-400">This endpoint returned an empty result set</div>
                      </div>
                    ) : (
                      <TableFadeWrapper className="flex-1 min-h-0 overflow-hidden">
                        <VirtualTable
                          columns={result.columns}
                          rows={result.rows}
                          rowHeight={35}
                          overscan={20}
                          className="h-full"
                        />
                      </TableFadeWrapper>
                    )}
                  </div>
                );
              })()}

              {totalPages > 1 && (
                <div className="flex-shrink-0 flex items-center justify-center gap-2" style={{ padding: '0.5rem 1rem' }}>
                  <button
                    onClick={goToPrev}
                    disabled={!canGoPrev}
                    style={{
                      padding: '0.25rem',
                      borderRadius: '0.375rem',
                      color: canGoPrev ? 'hsl(60 2.5% 23.3% / 45%)' : 'hsl(60 2.5% 23.3% / 15%)',
                      cursor: canGoPrev ? 'pointer' : 'not-allowed',
                      transition: 'background-color 0.1s',
                    }}
                    onMouseEnter={e => { if (canGoPrev) e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
                    onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                  >
                    <ChevronLeft size={14} strokeWidth={2} />
                  </button>

                  <div className="flex items-center gap-1">
                    {totalPages <= 8 ? (
                      datasetResults.map((result, idx) => (
                        <button
                          key={idx}
                          onClick={() => navigateToPageWithSidebarSync(idx)}
                          title={`${result.dataset.symbol} · ${result.dataset.endpoint}`}
                          style={{
                            width: idx === currentPage ? 18 : 6,
                            height: 6,
                            borderRadius: 3,
                            backgroundColor: idx === currentPage ? 'hsl(60 2.5% 23.3% / 70%)' : 'hsl(60 2.5% 23.3% / 15%)',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                          }}
                          onMouseEnter={e => { if (idx !== currentPage) e.currentTarget.style.backgroundColor = 'hsl(60 2.5% 23.3% / 30%)'; }}
                          onMouseLeave={e => { if (idx !== currentPage) e.currentTarget.style.backgroundColor = 'hsl(60 2.5% 23.3% / 15%)'; }}
                        />
                      ))
                    ) : (() => {
                      const isMiddle = currentPage >= 3 && currentPage < totalPages - 3;
                      return (
                        <>
                          {[0, 1, 2].map(idx => (
                            <button
                              key={idx}
                              onClick={() => navigateToPageWithSidebarSync(idx)}
                              style={{
                                width: idx === currentPage ? 18 : 6, height: 6, borderRadius: 3,
                                backgroundColor: idx === currentPage ? 'hsl(60 2.5% 23.3% / 70%)' : 'hsl(60 2.5% 23.3% / 15%)',
                                cursor: 'pointer', transition: 'all 0.15s ease',
                              }}
                            />
                          ))}
                          <span style={{ fontSize: '0.625rem', color: 'hsl(60 2.5% 23.3% / 25%)', padding: '0 1px' }}>···</span>
                          <button
                            onClick={isMiddle ? () => navigateToPageWithSidebarSync(currentPage) : undefined}
                            style={{
                              width: isMiddle ? 18 : 6, height: 6, borderRadius: 3,
                              backgroundColor: isMiddle ? 'hsl(60 2.5% 23.3% / 70%)' : 'transparent',
                              visibility: isMiddle ? 'visible' : 'hidden',
                              transition: 'all 0.15s ease',
                            }}
                          />
                          <span style={{ fontSize: '0.625rem', color: 'hsl(60 2.5% 23.3% / 25%)', padding: '0 1px' }}>···</span>
                          {[totalPages - 3, totalPages - 2, totalPages - 1].map(idx => (
                            <button
                              key={idx}
                              onClick={() => navigateToPageWithSidebarSync(idx)}
                              style={{
                                width: idx === currentPage ? 18 : 6, height: 6, borderRadius: 3,
                                backgroundColor: idx === currentPage ? 'hsl(60 2.5% 23.3% / 70%)' : 'hsl(60 2.5% 23.3% / 15%)',
                                cursor: 'pointer', transition: 'all 0.15s ease',
                              }}
                            />
                          ))}
                        </>
                      );
                    })()}
                  </div>

                  <button
                    onClick={goToNext}
                    disabled={!canGoNext}
                    style={{
                      padding: '0.25rem',
                      borderRadius: '0.375rem',
                      color: canGoNext ? 'hsl(60 2.5% 23.3% / 45%)' : 'hsl(60 2.5% 23.3% / 15%)',
                      cursor: canGoNext ? 'pointer' : 'not-allowed',
                      transition: 'background-color 0.1s',
                    }}
                    onMouseEnter={e => { if (canGoNext) e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
                    onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                  >
                    <ChevronRight size={14} strokeWidth={2} />
                  </button>

                  <span style={{
                    fontSize: '0.625rem',
                    fontWeight: 500,
                    color: 'hsl(60 2.5% 23.3% / 35%)',
                    fontVariantNumeric: 'tabular-nums',
                    marginLeft: 2,
                  }}>
                    {currentPage + 1}/{totalPages}
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center">
              <svg className="w-12 h-12 mb-4 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div className="text-sm text-slate-500 mb-2">No data available</div>
              <div className="text-xs text-slate-400">Add datasets to view data</div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default PropertyTable;
