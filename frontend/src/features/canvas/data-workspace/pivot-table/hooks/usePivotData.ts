import { useState, useEffect, useMemo, useRef } from 'react';
import { PivotConfig } from '../../stores/dataWorkspaceStore';
import { FieldInfo, DatasetRef } from '../types';
import { API_BASE } from '@/services/api';

interface SourceSheet {
  id: string;
  name: string;
  datasets: any[];
  compatibilityGroup: string;
}

export function usePivotData(
  config: PivotConfig | undefined,
  sourceSheet: SourceSheet | undefined,
  activeFilters: Record<string, Set<string>>
) {
  // Local state
  const [sourceData, setSourceData] = useState<Record<string, any>[]>([]);
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [loading, setLoading] = useState(false);

  // Dataset selection state
  const [selectedDatasetIndex, setSelectedDatasetIndex] = useState<number>(0);
  const [, setDatasetError] = useState<string | null>(null);
  
  // Get list of datasets - filter by selectedDatasetIds if available from config
  const availableDatasets = useMemo(() => {
    const allDatasets = sourceSheet?.datasets || [];
    // If config specifies which datasets to use, filter to those
    if (config?.selectedDatasetIds && config.selectedDatasetIds.length > 0) {
      const selectedIds = new Set(config.selectedDatasetIds);
      const filtered = allDatasets.filter((d: any) => selectedIds.has(d.id || d.endpoint + d.symbol));
      return filtered;
    }
    return allDatasets;
  }, [sourceSheet?.datasets, config?.selectedDatasetIds]);
  const _selectedDataset = useMemo(() => availableDatasets[selectedDatasetIndex], [availableDatasets, selectedDatasetIndex]);
  
  // Reset selection when source sheet changes
  useEffect(() => {
    setSelectedDatasetIndex(0);
    setDatasetError(null);
  }, [sourceSheet?.id]);
  
  // Compute unique values for each filterable field (Excel-style filter dropdowns)
  const filterOptions = useMemo(() => {
    const options: Record<string, string[]> = {};
    const filterableFields = config?.filterableFields || [];
    
    if (filterableFields.length === 0 || sourceData.length === 0) return options;
    
    filterableFields.forEach(field => {
      const uniqueValues = new Set<string>();
      sourceData.forEach(row => {
        const val = row[field];
        if (val != null && val !== '') {
          uniqueValues.add(String(val));
        }
      });
      // Sort values and limit to reasonable number
      options[field] = Array.from(uniqueValues).sort().slice(0, 100);
    });
    
    return options;
  }, [sourceData, config?.filterableFields]);
  
  // Apply active filters to source data
  const filteredData = useMemo(() => {
    if (Object.keys(activeFilters).length === 0) return sourceData;
    
    return sourceData.filter(row => {
      for (const [field, selectedValues] of Object.entries(activeFilters)) {
        if (selectedValues.size === 0) continue; // No filter = show all
        const rowValue = String(row[field] ?? '');
        if (!selectedValues.has(rowValue)) return false;
      }
      return true;
    });
  }, [sourceData, activeFilters]);
  
  // Track fetched dataset to prevent duplicate fetches
  const fetchedDatasetRef = useRef<string | null>(null);
  
  // Fetch source data when source sheet or available datasets change
  useEffect(() => {
    // Create a stable key to prevent duplicate fetches
    const fetchKey = `${sourceSheet?.id}-${availableDatasets.map((d: any) => d.endpoint + d.symbol).join(',')}`;
    if (fetchedDatasetRef.current === fetchKey) {
      return; // Already fetched these exact datasets
    }
    
    if (availableDatasets.length === 0) {
      setSourceData([]);
      setFields([]);
      return;
    }
    
    const fetchAllData = async () => {
      setLoading(true);
      setDatasetError(null);
      // Mark as fetched to prevent duplicate calls
      const currentFetchKey = `${sourceSheet?.id}-${availableDatasets.map((d: any) => d.endpoint + d.symbol).join(',')}`;
      fetchedDatasetRef.current = currentFetchKey;
      
      try {
        // Fetch data for ALL selected datasets in PARALLEL and merge
        const fetchPromises = availableDatasets.map(async (dataset: any) => {
          const symbol = dataset.symbol || '_MARKET_';
          
          const response = await fetch(`${API_BASE}/api/canvas/data/endpoint/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              endpoint: dataset.endpoint,
              symbol,
              params: dataset.params || {},
              fields: dataset.fields || [],
            }),
          });
          
          if (response.ok) {
            const result = await response.json();
            const rawData = result.data?.[dataset.endpoint];
            // Handle both array and single object responses
            let data: any[] = [];
            if (Array.isArray(rawData)) {
              data = rawData;
            } else if (rawData && typeof rawData === 'object') {
              // Single object response (e.g., snapshot endpoints like ratios-ttm)
              data = [rawData];
            }
            if (data.length > 0) {
              // Add source symbol to each row
              return data.map((row: any) => ({ ...row, _source_symbol: symbol }));
            }
          }
          return [];
        });
        
        const results = await Promise.all(fetchPromises);
        let allData = results.flat();
        
        // Apply merge mode if inner join is selected
        if (config?.mergeMode === 'inner' && results.length > 1) {
          const mergeKey = config.mergeKey || 'date'; // Default to date
          
          // Find keys that exist in ALL datasets
          const keySets = results.map(datasetRows => 
            new Set(datasetRows.map((row: any) => String(row[mergeKey] || '')))
          );
          
          // Intersection of all key sets
          const commonKeys = keySets.reduce((acc, set) => {
            return new Set([...acc].filter(key => set.has(key)));
          });
          
          // Filter to only rows with common keys
          allData = allData.filter((row: any) => commonKeys.has(String(row[mergeKey] || '')));
          
          // Also filter to common fields only
          const fieldSets = results.map(datasetRows => {
            if (datasetRows.length === 0) return new Set<string>();
            return new Set(Object.keys(datasetRows[0]));
          }).filter(s => s.size > 0);
          
          if (fieldSets.length > 1) {
            const commonFields = fieldSets.reduce((acc, set) => 
              new Set([...acc].filter(f => set.has(f)))
            );
            
            // Keep only common fields in each row
            allData = allData.map((row: any) => {
              const filtered: Record<string, any> = {};
              commonFields.forEach(f => { filtered[f] = row[f]; });
              filtered._source_symbol = row._source_symbol; // Always keep source
              return filtered;
            });
          }
        }
        
        setSourceData(allData);

        // Analyze fields server-side using refs (avoids sending raw data back)
        const refs: DatasetRef[] = availableDatasets.map((d: any) => ({
          symbol: d.symbol || '_MARKET_',
          endpoint: d.endpoint,
          params: d.params || {},
        }));
        if (refs.length > 0) {
          const fieldResponse = await fetch(`${API_BASE}/api/canvas/pivot/field-analysis-from-refs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              dataset_refs: refs,
              merge_mode: config?.mergeMode || 'union',
              merge_key: config?.mergeKey,
            }),
          });

          if (fieldResponse.ok) {
            const fieldResult = await fieldResponse.json();
            if (fieldResult.success) {
              setFields(fieldResult.fields);
            }
          }
        }
      } catch (error) {
        console.error('Error fetching pivot data:', error);
        setDatasetError(error instanceof Error ? error.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };
    
    fetchAllData();
  // Use stable primitives for dependencies to prevent infinite loops
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceSheet?.id, JSON.stringify(availableDatasets.map((d: any) => d.endpoint + d.symbol)), config?.mergeMode, config?.mergeKey]);

  const datasetRefs: DatasetRef[] = useMemo(() =>
    availableDatasets.map((d: any) => ({
      symbol: d.symbol || '_MARKET_',
      endpoint: d.endpoint,
      params: d.params || {},
    })),
    [availableDatasets],
  );

  return {
    sourceData,
    fields,
    loading,
    availableDatasets,
    filterOptions,
    filteredData,
    datasetRefs,
    _selectedDataset,
  };
}
