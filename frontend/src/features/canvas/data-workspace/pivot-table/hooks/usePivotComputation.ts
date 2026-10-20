import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { PivotConfig } from '../../stores/dataWorkspaceStore';
import { PivotResult, DatasetRef, CellMap, buildCellMap, getCell } from '../types';
import { API_BASE } from '@/services/api';

export function usePivotComputation(
  datasetRefs: DatasetRef[],
  activeFilters: Record<string, Set<string>>,
  config: PivotConfig | undefined
) {
  const [pivotResult, setPivotResult] = useState<PivotResult | null>(null);
  const [cellMap, setCellMap] = useState<CellMap>(new Map());

  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const requestRef = useRef(0);

  // Refs to access latest values inside the effect without adding them as deps
  const datasetRefsRef = useRef(datasetRefs);
  datasetRefsRef.current = datasetRefs;
  const activeFiltersRef = useRef(activeFilters);
  activeFiltersRef.current = activeFilters;
  const configRef = useRef(config);
  configRef.current = config;

  // Stable string keys that actually determine when to recompute
  const refsKey = useMemo(
    () => datasetRefs.map(r => r.endpoint + r.symbol).sort().join('|'),
    [datasetRefs],
  );

  const filtersKey = useMemo(() => {
    const entries: string[] = [];
    for (const [field, vals] of Object.entries(activeFilters)) {
      if (vals.size > 0) entries.push(`${field}:${[...vals].sort().join(',')}`);
    }
    return entries.join('|');
  }, [activeFilters]);

  const configKey = useMemo(() => {
    if (!config) return '';
    return JSON.stringify({
      rows: config.rows,
      columns: config.columns,
      values: config.values,
      mergeMode: config.mergeMode,
      mergeKey: config.mergeKey,
    });
  }, [config]);

  useEffect(() => {
    const cfg = configRef.current;
    const refs = datasetRefsRef.current;
    const filters = activeFiltersRef.current;

    console.log('[pivot-compute] Effect fired. refsKey:', refsKey, 'configKey:', configKey.slice(0, 80));
    console.log('[pivot-compute] refs.length:', refs.length, 'cfg:', !!cfg, 'values:', cfg?.values?.length);

    if (!cfg || refs.length === 0) {
      console.warn('[pivot-compute] Early return: cfg=', !!cfg, 'refs.length=', refs.length);
      return;
    }
    if (cfg.values.length === 0) {
      console.warn('[pivot-compute] No values configured, clearing result');
      setPivotResult(null);
      setCellMap(new Map());
      return;
    }

    const token = ++requestRef.current;
    console.log('[pivot-compute] Starting request token:', token, 'refs:', refs.map(r => `${r.symbol}/${r.endpoint}`));

    const compute = async () => {
      try {
        const backendFilters: Record<string, any> = {};
        for (const [field, selectedValues] of Object.entries(filters)) {
          if (selectedValues.size > 0) {
            backendFilters[field] = { operator: 'in', value: Array.from(selectedValues) };
          }
        }

        const body = {
          dataset_refs: refs,
          rows: cfg.rows,
          columns: cfg.columns,
          values: cfg.values,
          filters: Object.keys(backendFilters).length > 0 ? backendFilters : null,
          merge_mode: cfg.mergeMode || 'union',
          merge_key: cfg.mergeKey,
          include_field_analysis: false,
        };
        console.log('[pivot-compute] POST body:', JSON.stringify(body).slice(0, 300));

        const response = await fetch(`${API_BASE}/api/canvas/pivot/compute-from-refs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });

        console.log('[pivot-compute] Response status:', response.status, 'token match:', token === requestRef.current);
        if (token !== requestRef.current) {
          console.warn('[pivot-compute] Stale token, discarding. token:', token, 'current:', requestRef.current);
          return;
        }

        if (response.ok) {
          const result = await response.json();
          console.log('[pivot-compute] Result success:', result.success, 'cells:', result.cells?.length, 'rows:', result.row_headers?.length, 'error:', result.error);
          if (result.success) {
            setPivotResult(result);
            setCellMap(buildCellMap(result.cells || []));
          } else {
            console.error('[pivot-compute] Backend returned success=false:', result.error);
          }
        } else {
          const text = await response.text().catch(() => '');
          console.error('[pivot-compute] HTTP error:', response.status, text.slice(0, 500));
        }
      } catch (error) {
        console.error('[pivot-compute] Exception:', error);
      }
    };

    compute();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refsKey, filtersKey, configKey]);

  const handleSort = useCallback((column: string) => {
    if (sortColumn === column) {
      setSortDirection(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  }, [sortColumn]);

  const sortedRowHeaders = useMemo(() => {
    if (!pivotResult?.row_headers) return [];
    if (!sortColumn) return pivotResult.row_headers;

    const rowsCopy = [...pivotResult.row_headers];

    rowsCopy.sort((a, b) => {
      let aVal: number | string | null | undefined;
      let bVal: number | string | null | undefined;

      if (sortColumn === '_row') {
        aVal = a;
        bVal = b;
      } else if (sortColumn === '_grand_total') {
        aVal = pivotResult.row_totals?.[a]?.[config?.values[0]?.field ?? ''] ?? null;
        bVal = pivotResult.row_totals?.[b]?.[config?.values[0]?.field ?? ''] ?? null;
      } else {
        const aCell = getCell(cellMap, a, sortColumn);
        const bCell = getCell(cellMap, b, sortColumn);
        aVal = aCell?.values && config?.values[0] ? aCell.values[config.values[0].field] : null;
        bVal = bCell?.values && config?.values[0] ? bCell.values[config.values[0].field] : null;
      }

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return sortDirection === 'asc' ? 1 : -1;
      if (bVal == null) return sortDirection === 'asc' ? -1 : 1;

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      }
      const strA = String(aVal);
      const strB = String(bVal);
      return sortDirection === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA);
    });

    return rowsCopy;
  }, [pivotResult, cellMap, sortColumn, sortDirection, config]);

  const formatValue = useCallback((
    value: number | null | undefined,
    showAs: 'value' | 'pct_row' | 'pct_col' | 'pct_grand' | undefined,
    rowTotal: number | null | undefined,
    colTotal: number | null | undefined,
    grandTotal: number | null | undefined
  ): string => {
    if (value == null) return '-';

    const mode = showAs || 'value';
    if (mode === 'value') {
      return typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value);
    }

    let total: number | null | undefined;
    if (mode === 'pct_row') total = rowTotal;
    else if (mode === 'pct_col') total = colTotal;
    else if (mode === 'pct_grand') total = grandTotal;

    if (!total || total === 0) return '-';

    const pct = (value / total) * 100;
    return `${pct.toFixed(1)}%`;
  }, []);

  const columnTotals = useMemo(() => {
    if (!pivotResult?.cells || !config?.values) return {};

    const totals: Record<string, Record<string, number>> = {};

    pivotResult.col_headers.forEach(col => {
      totals[col] = {};
      config.values.forEach(v => {
        totals[col][v.field] = 0;
      });
    });

    pivotResult.cells.forEach(cell => {
      if (totals[cell.col_key]) {
        config.values.forEach(v => {
          const val = cell.values[v.field];
          if (typeof val === 'number') {
            totals[cell.col_key][v.field] += val;
          }
        });
      }
    });

    return totals;
  }, [pivotResult, config?.values]);

  const clearSort = useCallback(() => {
    setSortColumn(null);
    setSortDirection('asc');
  }, []);

  return {
    pivotResult,
    cellMap,
    sortColumn,
    sortDirection,
    handleSort,
    clearSort,
    sortedRowHeaders,
    formatValue,
    columnTotals,
  };
}
