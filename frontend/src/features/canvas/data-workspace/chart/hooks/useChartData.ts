/**
 * useChartData - Fetches and formats data for chart rendering
 * Supports both regular datasets and pivot table sources
 * Applies chart-level filters via backend API
 */

import { useState, useEffect, useMemo } from 'react';
import { ChartConfig, ChartFilter, WorkspaceSheet, WorkspaceTab } from '../../stores/dataWorkspaceStore';
import { API_BASE } from '@/services/api';
import { joinDatasets } from '@/utils/dataJoin';

// Maximum data points to render (prevents browser freeze with large datasets)
const MAX_CHART_POINTS = 10000;

interface ChartDataResult {
  data: any[];
  loading: boolean;
  error: string | null;
  // Filtering metadata
  originalCount: number;
  filteredCount: number;
}

// Apply filters client-side (fast, works offline)
function applyFiltersClientSide(data: any[], filters: ChartFilter[]): {
  data: any[];
  originalCount: number;
  filteredCount: number;
} {
  if (!filters || filters.length === 0) {
    return { data, originalCount: data.length, filteredCount: data.length };
  }

  const originalCount = data.length;
  let filtered = [...data];

  for (const filter of filters) {
    if (!filter.field) continue;

    filtered = filtered.filter(row => {
      const val = row[filter.field];
      if (val === null || val === undefined) return false;

      if (filter.filterType === 'date_range') {
        // Parse date value
        const dateVal = typeof val === 'string' ? val : String(val);
        if (!dateVal.match(/^\d{4}-\d{2}/)) return true; // Not a date, include

        if (filter.minValue && dateVal < String(filter.minValue)) return false;
        if (filter.maxValue && dateVal > String(filter.maxValue)) return false;
      } else {
        // Numeric range
        const numVal = typeof val === 'number' ? val : parseFloat(String(val));
        if (isNaN(numVal)) return true; // Not a number, include

        if (filter.minValue !== undefined && filter.minValue !== null) {
          const min = typeof filter.minValue === 'number' ? filter.minValue : parseFloat(String(filter.minValue));
          if (!isNaN(min) && numVal < min) return false;
        }
        if (filter.maxValue !== undefined && filter.maxValue !== null) {
          const max = typeof filter.maxValue === 'number' ? filter.maxValue : parseFloat(String(filter.maxValue));
          if (!isNaN(max) && numVal > max) return false;
        }
      }

      return true;
    });
  }

  return {
    data: filtered,
    originalCount,
    filteredCount: filtered.length,
  };
}

export function useChartData(
  config: ChartConfig | undefined,
  sourceSheet: WorkspaceSheet | undefined,
  allTabs?: WorkspaceTab[]
): ChartDataResult {
  const [rawData, setRawData] = useState<Record<string, any[]>>({});
  const [pivotData, setPivotData] = useState<any[]>([]);
  const [filteredData, setFilteredData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [originalCount, setOriginalCount] = useState(0);
  const [filteredCount, setFilteredCount] = useState(0);

  const isPivotSource = config?.selectedDatasetIds?.includes('_pivot_');

  // Get selected datasets from source sheet AND other tabs if needed (for non-pivot sources)
  const selectedDatasets = useMemo(() => {
    if (isPivotSource || !sourceSheet) {
      return [];
    }
    // If no selectedDatasetIds specified, use ALL datasets from source sheet
    if (!config?.selectedDatasetIds?.length) {
      return [...sourceSheet.datasets];
    }
    
    // First, get datasets from the source sheet
    const fromSourceSheet = sourceSheet.datasets.filter(
      (ds) => config.selectedDatasetIds?.includes(ds.id) || config.selectedDatasetIds?.includes(ds.endpoint)
    );
    
    // Find which IDs are missing from source sheet
    const foundIds = new Set(fromSourceSheet.map(ds => ds.id));
    const missingIds = config.selectedDatasetIds?.filter(id => !foundIds.has(id)) || [];
    
    // Search ALL tabs for missing datasets (not just the source sheet)
    const fromOtherTabs: typeof fromSourceSheet = [];
    if (missingIds.length > 0 && allTabs) {
      for (const tab of allTabs) {
        // Skip the source tab (already checked) and non-data tabs
        if (tab.id === config.sourceTabId || !tab.datasets?.length) continue;
        
        // Check tab's direct datasets
        for (const ds of tab.datasets) {
          if (missingIds.includes(ds.id) && !foundIds.has(ds.id)) {
            fromOtherTabs.push(ds);
            foundIds.add(ds.id);
          }
        }
        
        // Also check tab's sheets
        if (tab.sheets) {
          for (const sheet of tab.sheets) {
            for (const ds of sheet.datasets || []) {
              if (missingIds.includes(ds.id) && !foundIds.has(ds.id)) {
                fromOtherTabs.push(ds);
                foundIds.add(ds.id);
              }
            }
          }
        }
      }
    }
    
    const combined = [...fromSourceSheet, ...fromOtherTabs];
    
    return combined;
  }, [sourceSheet, config?.selectedDatasetIds, isPivotSource, allTabs, config?.sourceTabId]);

  // Fetch data for pivot source
  useEffect(() => {
    if (!isPivotSource || !config || !allTabs) {
      setPivotData([]);
      return;
    }

    // Find the pivot tab
    const pivotTab = allTabs.find((t) => t.id === config.sourceTabId);
    const pivotConfig = pivotTab?.pivotConfig;
    if (!pivotConfig) {
      setPivotData([]);
      return;
    }

    let cancelled = false;
    const fetchPivotData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Find source tab for the pivot (flat datasets structure, no sheets)
        const srcTab = allTabs.find((t) => t.id === pivotConfig.sourceTabId);

        if (!srcTab?.datasets?.length) {
          if (!cancelled) {
            setPivotData([]);
            setLoading(false);
          }
          return;
        }

        // Fetch source data
        const allSourceData: any[] = [];
        for (const ds of srcTab.datasets) {
          if (pivotConfig.selectedDatasetIds?.length &&
              !pivotConfig.selectedDatasetIds.includes(ds.id) &&
              !pivotConfig.selectedDatasetIds.includes(ds.endpoint)) {
            continue;
          }
          try {
            const resp = await fetch(`${API_BASE}/api/canvas/data/endpoint/fetch`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ endpoint: ds.endpoint, symbol: ds.symbol || '_MARKET_', params: ds.params || {}, fields: [] }),
            });
            const result = await resp.json();
            allSourceData.push(...(result.data?.[ds.endpoint] || []));
          } catch (e) {
            console.error('Failed to fetch pivot source data', e);
          }
        }

        if (cancelled || allSourceData.length === 0) {
          if (!cancelled) {
            setPivotData([]);
            setLoading(false);
          }
          return;
        }

        // Compute pivot
        const pivotResp = await fetch(`${API_BASE}/api/canvas/pivot/compute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data: allSourceData,
            rows: pivotConfig.rows || [],
            columns: pivotConfig.columns || [],
            values: pivotConfig.values || [],
            filters: {},
          }),
        });
        const pivotResult = await pivotResp.json();

        if (cancelled || !pivotResult.success) {
          if (!cancelled) {
            setPivotData([]);
            setLoading(false);
          }
          return;
        }

        // Convert to flat rows
        const flatRows: any[] = [];
        const rowHeaders = pivotResult.row_headers || [];
        const colHeaders = pivotResult.column_headers || [];
        const cells = pivotResult.cells || {};

        for (const rowKey of rowHeaders) {
          const row: any = {};
          if (pivotConfig.rows?.length === 1) {
            row[pivotConfig.rows[0]] = rowKey;
          } else {
            row['_row'] = rowKey;
          }
          if (colHeaders.length > 0) {
            for (const colKey of colHeaders) {
              const cellKey = `${rowKey}||${colKey}`;
              const cellVal = cells[cellKey];
              if (typeof cellVal === 'number') {
                row[colKey] = cellVal;
              }
            }
          } else {
            const totals = pivotResult.row_totals?.[rowKey];
            if (typeof totals === 'number') {
              row['value'] = totals;
            } else if (totals && typeof totals === 'object') {
              Object.entries(totals).forEach(([k, v]) => { row[k] = v; });
            }
          }
          flatRows.push(row);
        }

        if (!cancelled) {
          setPivotData(flatRows);
          setLoading(false);
        }
      } catch (err) {
        console.error('Failed to compute pivot data for chart', err);
        if (!cancelled) {
          setError('Failed to load pivot data');
          setPivotData([]);
          setLoading(false);
        }
      }
    };

    fetchPivotData();
    return () => { cancelled = true; };
  }, [isPivotSource, config, allTabs]);

  // Fetch data for regular datasets
  useEffect(() => {
    if (isPivotSource || selectedDatasets.length === 0) {
      setRawData({});
      return;
    }

    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      const results: Record<string, any[]> = {};

      for (const ds of selectedDatasets) {
        try {
          const response = await fetch(`${API_BASE}/api/canvas/data/endpoint/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              endpoint: ds.endpoint,
              symbol: ds.symbol || '_MARKET_',
              params: ds.params || {},
              fields: [],
            }),
          });
          const result = await response.json();
          if (!cancelled) {
            results[ds.id || ds.endpoint] = result.data?.[ds.endpoint] || [];
          }
        } catch (err) {
          console.error('Failed to fetch data for', ds.endpoint, err);
          if (!cancelled) {
            results[ds.id || ds.endpoint] = [];
          }
        }
      }

      if (!cancelled) {
        setRawData(results);
        setLoading(false);
      }
    };

    fetchData();
    return () => { cancelled = true; };
  }, [selectedDatasets, isPivotSource]);

  // Merge data from all datasets or return pivot data
  // For multi-symbol data, we JOIN on date and add symbol prefixes (AAPL_close, GOOGL_close, etc.)
  const mergedData = useMemo(() => {
    if (isPivotSource) {
      return pivotData;
    }

    // Collect unique symbols from datasets
    const symbolsInData = new Set<string>();
    selectedDatasets.forEach(ds => {
      if (ds.symbol && ds.symbol !== '_MARKET_') {
        symbolsInData.add(ds.symbol);
      }
    });
    
    const hasMultipleSymbols = symbolsInData.size > 1;
    
    // If multiple symbols, format depends on chart type
    if (hasMultipleSymbols) {
      // Step 1: Group datasets by symbol
      const datasetsBySymbol: Record<string, typeof selectedDatasets> = {};
      selectedDatasets.forEach(ds => {
        const symbol = ds.symbol || 'UNKNOWN';
        if (!datasetsBySymbol[symbol]) {
          datasetsBySymbol[symbol] = [];
        }
        datasetsBySymbol[symbol].push(ds);
      });
      
      // Step 2: For each symbol, join across endpoints (balance sheet + income statement)
      const joinedPerSymbol: Record<string, any[]> = {};
      
      for (const [symbol, datasets] of Object.entries(datasetsBySymbol)) {
        if (datasets.length > 1) {
          // Multiple endpoints for this symbol - join them
          const results = datasets.map(ds => ({
            dataset: ds,
            columns: Object.keys(rawData[ds.id || ds.endpoint]?.[0] || {}),
            rows: rawData[ds.id || ds.endpoint] || [],
          }));
          
          const joined = joinDatasets(results, sourceSheet?.compatibilityGroup || '');
          
          if (joined.canJoin && joined.rows.length > 0) {
            joinedPerSymbol[symbol] = joined.rows;
          } else {
            // Fallback: concatenate
            const allRows: any[] = [];
            datasets.forEach(ds => {
              const arr = rawData[ds.id || ds.endpoint];
              if (Array.isArray(arr)) allRows.push(...arr);
            });
            joinedPerSymbol[symbol] = allRows;
          }
        } else {
          // Single endpoint for this symbol
          const ds = datasets[0];
          joinedPerSymbol[symbol] = rawData[ds.id || ds.endpoint] || [];
        }
      }
      
      // Determine if we should use LONG FORMAT (rows stacked by symbol) vs WIDE FORMAT (columns prefixed)
      // Long format is better for:
      // - Scatter/bubble: X=metric, Y=metric, color by symbol
      // - Bar/pie comparing symbols: X=symbol, Y=metric
      // Wide format is better for:
      // - Line/area time series: X=date, Y=JPM_price, BAC_price, etc.
      const isScatterLike = config?.chartType === 'scatter' || config?.chartType === 'bubble' || config?.chartType === 'scatter3d';
      const isBarOrPie = config?.chartType === 'bar' || config?.chartType === 'pie';
      
      // Use long format for scatter-like charts OR bar/pie when comparing across symbols
      const useLongFormat = isScatterLike || isBarOrPie;
      
      if (useLongFormat) {
        // Long format: stack rows with symbol column, no field prefixing
        const longFormatData: any[] = [];
        
        for (const [symbol, rows] of Object.entries(joinedPerSymbol)) {
          rows.forEach(row => {
            longFormatData.push({
              ...row,
              symbol, // Add symbol as a column for coloring
              _source_symbol: symbol, // Also add _source_symbol for compatibility with chart configs
            });
          });
        }
        
        // Sort by symbol then date
        longFormatData.sort((a, b) => {
          const symbolCmp = (a.symbol || '').localeCompare(b.symbol || '');
          if (symbolCmp !== 0) return symbolCmp;
          const dateA = a['calendarYear'] && a['period'] 
            ? `${a['calendarYear']}-${a['period']}` 
            : (a['date'] || '');
          const dateB = b['calendarYear'] && b['period'] 
            ? `${b['calendarYear']}-${b['period']}` 
            : (b['date'] || '');
          return String(dateA).localeCompare(String(dateB));
        });
        
        console.log('[useChartData] Long-format result:', {
          chartType: config?.chartType,
          symbols: Array.from(symbolsInData),
          rowCount: longFormatData.length,
          sampleFields: longFormatData[0] ? Object.keys(longFormatData[0]).slice(0, 15) : [],
          sampleRow: longFormatData[0],
        });
        
        // Sample if too large
        if (longFormatData.length > MAX_CHART_POINTS) {
          const step = Math.ceil(longFormatData.length / MAX_CHART_POINTS);
          return longFormatData.filter((_, i) => i % step === 0);
        }
        
        return longFormatData;
      }
      
      // For line/bar/area charts: use WIDE FORMAT (columns prefixed by symbol)
      // This allows comparing same metric across symbols over time
      const sampleData = Object.values(rawData).find(arr => arr.length > 0)?.[0];
      const possibleDateFields = ['date', 'calendarYear', 'acceptedDate', 'filingDate', 'reportedDate'];
      const actualDateField = possibleDateFields.find(f => sampleData && f in sampleData) || 'date';
      
      const joinedByDate: Record<string, Record<string, any>> = {};
      const joinKeyFields = new Set(['date', 'calendarYear', 'period', 'symbol', 'acceptedDate', 'filingDate', 'reportedDate', '_normalized_date']);
      
      for (const [symbol, rows] of Object.entries(joinedPerSymbol)) {
        rows.forEach(row => {
          let dateKey = '';
          if (row['calendarYear'] && row['period']) {
            dateKey = `${row['calendarYear']}-${row['period']}`;
          } else if (row[actualDateField]) {
            dateKey = String(row[actualDateField]);
          } else if (row['date']) {
            dateKey = String(row['date']);
          }
          if (!dateKey) return;
          
          if (!joinedByDate[dateKey]) {
            joinedByDate[dateKey] = {};
            if (row['date']) joinedByDate[dateKey]['date'] = row['date'];
            if (row['calendarYear']) joinedByDate[dateKey]['calendarYear'] = row['calendarYear'];
            if (row['period']) joinedByDate[dateKey]['period'] = row['period'];
          }
          
          // Add all fields with symbol prefix (except join key fields)
          Object.entries(row).forEach(([field, value]) => {
            if (!joinKeyFields.has(field)) {
              const prefixedField = `${symbol}_${field}`;
              joinedByDate[dateKey][prefixedField] = value;
            }
          });
        });
      }
      
      const allData = Object.values(joinedByDate);
      allData.sort((a, b) => {
        const dateA = a['calendarYear'] && a['period'] 
          ? `${a['calendarYear']}-${a['period']}` 
          : (a[actualDateField] || a['date'] || '');
        const dateB = b['calendarYear'] && b['period'] 
          ? `${b['calendarYear']}-${b['period']}` 
          : (b[actualDateField] || b['date'] || '');
        if (typeof dateA === 'string' && typeof dateB === 'string') {
          return dateA.localeCompare(dateB);
        }
        return 0;
      });
      
      console.log('[useChartData] Multi-symbol wide-format result:', {
        symbols: Array.from(symbolsInData),
        rowCount: allData.length,
        sampleFields: allData[0] ? Object.keys(allData[0]).slice(0, 15) : [],
      });
      
      if (allData.length > MAX_CHART_POINTS) {
        const step = Math.ceil(allData.length / MAX_CHART_POINTS);
        return allData.filter((_, i) => i % step === 0);
      }
      
      return allData;
    }
    
    // Single symbol but multiple endpoints (e.g., balance sheet + income statement)
    // Join on date/period so fields from different endpoints are on the same row
    if (!hasMultipleSymbols && selectedDatasets.length > 1) {
      const results = selectedDatasets.map(ds => ({
        dataset: ds,
        columns: Object.keys(rawData[ds.id || ds.endpoint]?.[0] || {}),
        rows: rawData[ds.id || ds.endpoint] || [],
      }));
      
      const joined = joinDatasets(results, sourceSheet?.compatibilityGroup || '');
      if (joined.canJoin && joined.rows.length > 0) {
        console.log('[useChartData] Cross-endpoint join result:', {
          datasets: selectedDatasets.map(ds => ds.endpoint),
          rowCount: joined.rows.length,
          sampleFields: Object.keys(joined.rows[0] || {}).slice(0, 10),
        });
        
        // Sort by date if applicable
        if (config?.xAxis && joined.rows.length > 0) {
          const sample = joined.rows[0][config.xAxis];
          if (typeof sample === 'string' && sample.match(/^\d{4}-\d{2}/)) {
            joined.rows.sort((a, b) => new Date(a[config.xAxis]).getTime() - new Date(b[config.xAxis]).getTime());
          }
        }
        
        // Sample if too large
        if (joined.rows.length > MAX_CHART_POINTS) {
          const step = Math.ceil(joined.rows.length / MAX_CHART_POINTS);
          return joined.rows.filter((_, i) => i % step === 0);
        }
        
        return joined.rows;
      }
    }
    
    // Fallback: Single dataset or join failed - concatenate as before
    const allData: any[] = [];
    Object.values(rawData).forEach((dataArr) => {
      if (Array.isArray(dataArr)) {
        allData.push(...dataArr);
      }
    });
    // Sort by x-axis if it looks like a date field
    if (config?.xAxis && allData.length > 0) {
      const sample = allData[0][config.xAxis];
      if (typeof sample === 'string' && sample.match(/^\d{4}-\d{2}/)) {
        allData.sort((a, b) => new Date(a[config.xAxis]).getTime() - new Date(b[config.xAxis]).getTime());
      }
    }
    
    // Sample data if too large (prevents browser freeze)
    if (allData.length > MAX_CHART_POINTS) {
      console.warn(`[Chart] Sampling data: ${allData.length.toLocaleString()} → ${MAX_CHART_POINTS.toLocaleString()} points`);
      const step = Math.ceil(allData.length / MAX_CHART_POINTS);
      return allData.filter((_, i) => i % step === 0);
    }
    
    return allData;
  }, [rawData, pivotData, config?.xAxis, isPivotSource, selectedDatasets, sourceSheet?.compatibilityGroup]);

  // Apply filters to merged data (client-side for instant feedback)
  useEffect(() => {
    if (mergedData.length === 0) {
      setFilteredData([]);
      setOriginalCount(0);
      setFilteredCount(0);
      return;
    }

    // Apply filters client-side for instant response
    const result = applyFiltersClientSide(mergedData, config?.filters || []);
    setFilteredData(result.data);
    setOriginalCount(result.originalCount);
    setFilteredCount(result.filteredCount);
  }, [mergedData, config?.filters]);

  return { data: filteredData, loading, error, originalCount, filteredCount };
}

