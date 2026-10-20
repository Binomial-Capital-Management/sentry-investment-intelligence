/**
 * useMultiObjectForm - Hook for managing Multi Object form state
 * 
 * State is divided into:
 * - PERSISTED state: Stored in Zustand (survives tab switches and page reload)
 * - TRANSIENT state: Local useState (search UI, loading flags, computed values)
 * 
 * Enhanced with:
 * - Dynamic endpoint equivalence for cross-asset joins (same endpoint across types)
 * - Time-key based grouping for heterogeneous joins (different endpoints per type)
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import api from '@/services/api';
import type { 
  EndpointInfo, 
  EquivalenceGroup, 
  Granularity,
  EndpointTimeInfo,
  TimeGroupEndpoints,
  JoinStrategy,
} from '@/features/canvas/types';
import {
  mapBackendToTimeStructure,
  checkStructureCompatibility,
  type TimeStructure,
} from '@/utils/compatibilityMatrix';
import { useDataWorkspaceStore } from '../../stores/dataWorkspaceStore';
import {
  selectMultiSelectedSymbols,
  selectMultiSearchMode,
  selectMultiEndpointSelectionMode,
  selectMultiSelectedEndpoint,
  selectMultiSelectedFields,
  selectMultiFormParams,
  selectMultiExpandedCategories,
  selectMultiSourceFilter,
  selectMultiEndpointByType,
  selectMultiFieldsByType,
  selectMultiParamsByType,
  selectMultiExpandedCategoriesByType,
  selectMultiSourceFilterByType,
  selectMultiTargetGranularity,
} from '../../stores/selectors';
import {
  loadEndpointsForType,
  loadEndpointsWithEquivalence,
  groupEndpointsByCategory,
  countEndpointsBySource,
  getSmartParamDefaults,
  mergeParamsWithDefaults,
  getEquivalentEndpoints,
  loadEndpointsByTimeGroup,
  analyzeJoinStrategy,
  getJoinableEndpoints,
  groupTimeEndpointsByCategory,
  getFieldsByEndpoint,
  timeInfoToEndpointInfo,
} from '../utils/queryUtils';

export interface SelectedSymbol {
  symbol: string;
  name: string;
  objectType: string;
}

export type SearchMode = 'symbol' | 'forex' | 'crypto';
export type EndpointSelectionMode = 'homogeneous' | 'heterogeneous';

export interface MultiObjectFormState {
  selectedSymbols: SelectedSymbol[];
  searchMode: SearchMode;
  endpointSelectionMode: EndpointSelectionMode;
  selectedEndpoint: EndpointInfo | null;
  selectedFields: string[];
  formParams: Record<string, string>;
  expandedCategories: string[];
  sourceFilter: string;
  endpointByType: Record<string, EndpointTimeInfo | null>;
  fieldsByType: Record<string, string[]>;
  paramsByType: Record<string, Record<string, string>>;
  expandedCategoriesByType: Record<string, string[]>;
  sourceFilterByType: Record<string, string>;
  targetGranularity?: Granularity | string;
}

export function useMultiObjectForm() {
  // ============================================================================
  // PERSISTED STATE - From Zustand store (formStateSlice)
  // ============================================================================
  
  // Multi form state from store
  const selectedSymbols = useDataWorkspaceStore(selectMultiSelectedSymbols);
  const searchMode = useDataWorkspaceStore(selectMultiSearchMode);
  const endpointSelectionMode = useDataWorkspaceStore(selectMultiEndpointSelectionMode);
  const selectedEndpoint = useDataWorkspaceStore(selectMultiSelectedEndpoint);
  const selectedFields = useDataWorkspaceStore(selectMultiSelectedFields);
  const formParams = useDataWorkspaceStore(selectMultiFormParams);
  const expandedCategoriesArray = useDataWorkspaceStore(selectMultiExpandedCategories);
  const sourceFilter = useDataWorkspaceStore(selectMultiSourceFilter);
  const endpointByType = useDataWorkspaceStore(selectMultiEndpointByType);
  const fieldsByType = useDataWorkspaceStore(selectMultiFieldsByType);
  const paramsByType = useDataWorkspaceStore(selectMultiParamsByType);
  const expandedCategoriesByTypeArray = useDataWorkspaceStore(selectMultiExpandedCategoriesByType);
  const sourceFilterByType = useDataWorkspaceStore(selectMultiSourceFilterByType);
  const targetGranularityStored = useDataWorkspaceStore(selectMultiTargetGranularity);
  
  // Store actions
  const setMultiSelectedSymbols = useDataWorkspaceStore(s => s.setMultiSelectedSymbols);
  const addMultiSelectedSymbol = useDataWorkspaceStore(s => s.addMultiSelectedSymbol);
  const removeMultiSelectedSymbol = useDataWorkspaceStore(s => s.removeMultiSelectedSymbol);
  const setMultiSearchMode = useDataWorkspaceStore(s => s.setMultiSearchMode);
  const setMultiEndpointSelectionMode = useDataWorkspaceStore(s => s.setMultiEndpointSelectionMode);
  const setMultiSelectedEndpoint = useDataWorkspaceStore(s => s.setMultiSelectedEndpoint);
  const setMultiSelectedFields = useDataWorkspaceStore(s => s.setMultiSelectedFields);
  const setMultiFormParams = useDataWorkspaceStore(s => s.setMultiFormParams);
  const setMultiExpandedCategoriesAction = useDataWorkspaceStore(s => s.setMultiExpandedCategories);
  const setMultiSourceFilter = useDataWorkspaceStore(s => s.setMultiSourceFilter);
  const setMultiEndpointByType = useDataWorkspaceStore(s => s.setMultiEndpointByType);
  const setMultiFieldsByType = useDataWorkspaceStore(s => s.setMultiFieldsByType);
  const setMultiParamsByType = useDataWorkspaceStore(s => s.setMultiParamsByType);
  const setMultiExpandedCategoriesByTypeAction = useDataWorkspaceStore(s => s.setMultiExpandedCategoriesByType);
  const setMultiSourceFilterByType = useDataWorkspaceStore(s => s.setMultiSourceFilterByType);
  const setMultiTargetGranularity = useDataWorkspaceStore(s => s.setMultiTargetGranularity);
  const resetMultiFormAction = useDataWorkspaceStore(s => s.resetMultiForm);
  
  // Convert arrays to Sets for compatibility
  const expandedCategories = useMemo(() => new Set(expandedCategoriesArray), [expandedCategoriesArray]);
  const expandedCategoriesByType = useMemo(() => {
    const result: Record<string, Set<string>> = {};
    for (const [key, arr] of Object.entries(expandedCategoriesByTypeArray)) {
      result[key] = new Set(arr);
    }
    return result;
  }, [expandedCategoriesByTypeArray]);
  const targetGranularity = targetGranularityStored as Granularity | null ?? null;
  
  // Wrapper functions to convert Set to array when updating
  const setExpandedCategories = useCallback(
    (categories: Set<string>) => setMultiExpandedCategoriesAction(Array.from(categories)),
    [setMultiExpandedCategoriesAction]
  );
  const setExpandedCategoriesByType = useCallback(
    (categoriesByType: Record<string, Set<string>>) => {
      const converted: Record<string, string[]> = {};
      for (const [key, set] of Object.entries(categoriesByType)) {
        converted[key] = Array.from(set);
      }
      setMultiExpandedCategoriesByTypeAction(converted);
    },
    [setMultiExpandedCategoriesByTypeAction]
  );
  
  // Aliases for backward compatibility
  const setSelectedSymbols = setMultiSelectedSymbols;
  const setSearchMode = setMultiSearchMode;
  const setEndpointSelectionMode = setMultiEndpointSelectionMode;
  const setSelectedEndpoint = setMultiSelectedEndpoint;
  const setSelectedFields = setMultiSelectedFields;
  const setFormParams = setMultiFormParams;
  const setSourceFilter = setMultiSourceFilter;
  const setEndpointByType = setMultiEndpointByType;
  const setFieldsByType = setMultiFieldsByType;
  const setTargetGranularity = useCallback(
    (g: Granularity | null) => setMultiTargetGranularity(g ?? undefined),
    [setMultiTargetGranularity]
  );
  
  // ============================================================================
  // TRANSIENT STATE - Local (search UI, loading flags, derived data)
  // ============================================================================
  
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  
  // Forex/Crypto pairs state
  const [forexPairs, setForexPairs] = useState<string[]>([]);
  const [cryptoPairs, setCryptoPairs] = useState<string[]>([]);
  const [loadingForexPairs, setLoadingForexPairs] = useState(false);
  const [loadingCryptoPairs, setLoadingCryptoPairs] = useState(false);
  const [forexDropdownOpen, setForexDropdownOpen] = useState(false);
  const [cryptoDropdownOpen, setCryptoDropdownOpen] = useState(false);
  const [forexSearch, setForexSearch] = useState('');
  const [cryptoSearch, setCryptoSearch] = useState('');

  // Endpoints derived data (loaded based on selected symbols)
  const [endpointsByType, setEndpointsByType] = useState<Record<string, EndpointInfo[]>>({});
  const [equivalenceGroups, setEquivalenceGroups] = useState<EquivalenceGroup[]>([]);
  const [loadingEndpoints, setLoadingEndpoints] = useState(false);
  const [endpointsByTimeGroup, setEndpointsByTimeGroup] = useState<Record<string, TimeGroupEndpoints>>({});
  const [joinStrategy, setJoinStrategy] = useState<JoinStrategy | null>(null);
  
  // Granularity (computed from selected endpoints)
  const [granularitiesDetected, setGranularitiesDetected] = useState<Granularity[]>([]);
  const [hasMixedGranularity, setHasMixedGranularity] = useState(false);
  
  // Structure type compatibility (computed from selected endpoints)
  const [structureTypesDetected, setStructureTypesDetected] = useState<TimeStructure[]>([]);
  const [hasIncompatibleStructures, setHasIncompatibleStructures] = useState(false);
  const [incompatiblePairs, setIncompatiblePairs] = useState<[TimeStructure, TimeStructure][]>([]);
  const [endpointsByStructure, setEndpointsByStructure] = useState<Record<TimeStructure, string[]>>({
    date: [], fiscal: [], snapshot: [], none: []
  });
  
  // Submitting state
  const [submitting, setSubmitting] = useState(false);

  // ============================================================================
  // COMPUTED VALUES
  // ============================================================================
  
  const hasMinimumSymbols = selectedSymbols.length >= 2;
  const hasAnySymbols = selectedSymbols.length >= 1;
  const uniqueObjectTypes = useMemo(() => 
    [...new Set(selectedSymbols.map(s => s.objectType))],
    [selectedSymbols]
  );
  const hasMultipleObjectTypes = uniqueObjectTypes.length > 1;

  // ============================================================================
  // SIDE EFFECTS - Load data based on state changes
  // ============================================================================
  
  // Load forex pairs when mode changes
  useEffect(() => {
    if (searchMode === 'forex' && forexPairs.length === 0 && !loadingForexPairs) {
      setLoadingForexPairs(true);
      api.get<{ pairs: string[]; count: number }>('/api/canvas/data/forex/pairs')
        .then(res => setForexPairs(res.data.pairs || []))
        .catch(() => setForexPairs(['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD']))
        .finally(() => setLoadingForexPairs(false));
    }
  }, [searchMode, forexPairs.length, loadingForexPairs]);

  // Load crypto pairs when mode changes
  useEffect(() => {
    if (searchMode === 'crypto' && cryptoPairs.length === 0 && !loadingCryptoPairs) {
      setLoadingCryptoPairs(true);
      api.get<{ pairs: string[]; count: number }>('/api/canvas/data/crypto/pairs')
        .then(res => setCryptoPairs(res.data.pairs || []))
        .catch(() => setCryptoPairs(['BTCUSD', 'ETHUSD', 'SOLUSD', 'DOGEUSD', 'XRPUSD', 'ADAUSD']))
        .finally(() => setLoadingCryptoPairs(false));
    }
  }, [searchMode, cryptoPairs.length, loadingCryptoPairs]);

  // Load endpoints when unique object types change
  // This effect also handles tab switches - when selectedSymbols is restored from store,
  // uniqueObjectTypes gets a new reference which triggers endpoint reload
  useEffect(() => {
    if (!hasAnySymbols) return;

    const loadAllEndpoints = async () => {
      setLoadingEndpoints(true);
      
      try {
        const [equivalenceResult, timeGroupResult] = await Promise.all([
          loadEndpointsWithEquivalence(uniqueObjectTypes),
          loadEndpointsByTimeGroup(uniqueObjectTypes),
        ]);
        
        setEndpointsByType(equivalenceResult.byType);
        setEquivalenceGroups(equivalenceResult.equivalenceGroups);
        setEndpointsByTimeGroup(timeGroupResult.byTypeAndGroup);
        
        // Initialize endpointByType for heterogeneous mode if not set
        const currentEndpointByType = { ...endpointByType };
        let needsUpdate = false;
        for (const ot of uniqueObjectTypes) {
          if (!(ot in currentEndpointByType)) {
            currentEndpointByType[ot] = null;
            needsUpdate = true;
          }
        }
        if (needsUpdate) {
          setMultiEndpointByType(currentEndpointByType);
        }
        
        // Initialize expanded categories per type if not set
        const currentExpandedByType = { ...expandedCategoriesByTypeArray };
        needsUpdate = false;
        for (const ot of uniqueObjectTypes) {
          if (!(ot in currentExpandedByType)) {
            currentExpandedByType[ot] = [];
            needsUpdate = true;
          }
        }
        if (needsUpdate) {
          setMultiExpandedCategoriesByTypeAction(currentExpandedByType);
        }
      } catch (e) {
        console.error('Failed to load endpoints:', e);
        const newEndpointsByType: Record<string, EndpointInfo[]> = {};
        for (const objectType of uniqueObjectTypes) {
          newEndpointsByType[objectType] = await loadEndpointsForType(objectType);
        }
        setEndpointsByType(newEndpointsByType);
        setEquivalenceGroups([]);
      }
      
      setLoadingEndpoints(false);
    };

    loadAllEndpoints();
  }, [uniqueObjectTypes, hasAnySymbols]); // eslint-disable-line react-hooks/exhaustive-deps

  // HOMOGENEOUS MODE: Update granularity based on selected endpoint
  useEffect(() => {
    if (endpointSelectionMode !== 'homogeneous') return;
    
    if (selectedEndpoint) {
      const gran = selectedEndpoint.granularity as Granularity || 'daily';
      setGranularitiesDetected([gran]);
      setHasMixedGranularity(false);
      setTargetGranularity(null);
    } else {
      setGranularitiesDetected([]);
      setHasMixedGranularity(false);
      setTargetGranularity(null);
    }
  }, [selectedEndpoint, endpointSelectionMode, setTargetGranularity]);

  // HETEROGENEOUS MODE: Update join strategy when endpoints are selected
  useEffect(() => {
    if (endpointSelectionMode !== 'heterogeneous') return;
    
    const selectedEndpoints: Record<string, string> = {};
    let allSelected = true;
    
    for (const [objType, ep] of Object.entries(endpointByType)) {
      if (ep) {
        selectedEndpoints[objType] = ep.endpoint;
      } else {
        allSelected = false;
      }
    }
    
    if (allSelected && Object.keys(selectedEndpoints).length >= 2) {
      analyzeJoinStrategy(selectedEndpoints).then(strategy => {
        setJoinStrategy(strategy);
        
        if (strategy.granularities.length > 0) {
          setGranularitiesDetected(strategy.granularities as Granularity[]);
          setHasMixedGranularity(strategy.needs_aggregation);
          if (strategy.aggregation_target) {
            setTargetGranularity(strategy.aggregation_target as Granularity);
          }
        }
      });
    } else {
      const selectedGranularities: Set<Granularity> = new Set();
      for (const ep of Object.values(endpointByType)) {
        if (ep?.granularity) {
          selectedGranularities.add(ep.granularity as Granularity);
        }
      }
      const granList = Array.from(selectedGranularities);
      setGranularitiesDetected(granList);
      setHasMixedGranularity(granList.length > 1);
      setJoinStrategy(null);
    }
  }, [endpointByType, endpointSelectionMode, setTargetGranularity]);

  // HETEROGENEOUS MODE: Detect structure type incompatibilities
  useEffect(() => {
    if (endpointSelectionMode !== 'heterogeneous') {
      // Reset structure type state when not in heterogeneous mode
      setStructureTypesDetected([]);
      setHasIncompatibleStructures(false);
      setIncompatiblePairs([]);
      setEndpointsByStructure({ date: [], fiscal: [], snapshot: [], none: [] });
      return;
    }
    
    const structureMap: Record<TimeStructure, string[]> = {
      date: [], fiscal: [], snapshot: [], none: []
    };
    
    // Collect structure types from selected endpoints
    Object.entries(endpointByType).forEach(([_objType, ep]) => {
      if (ep) {
        const structure = mapBackendToTimeStructure(ep.structure_type);
        structureMap[structure].push(ep.endpoint);
      }
    });
    
    // Filter to only include structures that have endpoints
    const detected = (Object.keys(structureMap) as TimeStructure[])
      .filter(s => structureMap[s].length > 0);
    
    // Check compatibility
    const { compatible, incompatiblePairs: pairs } = checkStructureCompatibility(detected);
    
    setStructureTypesDetected(detected);
    setHasIncompatibleStructures(!compatible);
    setIncompatiblePairs(pairs);
    setEndpointsByStructure(structureMap);
  }, [endpointByType, endpointSelectionMode]);

  // ============================================================================
  // COMPUTED/FILTERED VALUES
  // ============================================================================

  const filteredForexPairs = useMemo(() => {
    if (!forexSearch) return forexPairs;
    const search = forexSearch.toUpperCase();
    return forexPairs.filter(pair => pair.includes(search));
  }, [forexPairs, forexSearch]);

  const filteredCryptoPairs = useMemo(() => {
    if (!cryptoSearch) return cryptoPairs;
    const search = cryptoSearch.toUpperCase();
    return cryptoPairs.filter(pair => pair.includes(search));
  }, [cryptoPairs, cryptoSearch]);

  // HOMOGENEOUS MODE: Get displayable endpoints using equivalence groups
  const displayEndpoints = useMemo(() => {
    if (endpointSelectionMode !== 'homogeneous') return [];
    if (uniqueObjectTypes.length === 0) return [];
    
    const allEndpointSets = uniqueObjectTypes.map(type => endpointsByType[type] || []);
    if (allEndpointSets.some(set => set.length === 0)) return [];
    
    if (allEndpointSets.length === 1) {
      return allEndpointSets[0];
    }
    
    if (equivalenceGroups.length > 0) {
      return getEquivalentEndpoints(uniqueObjectTypes, endpointsByType, equivalenceGroups);
    }
    
    const firstTypeEndpoints = allEndpointSets[0];
    return firstTypeEndpoints.filter(ep => {
      return allEndpointSets.every(endpoints => 
        endpoints.some(e => e.endpoint === ep.endpoint)
      );
    });
  }, [uniqueObjectTypes, endpointsByType, equivalenceGroups, endpointSelectionMode]);

  // HOMOGENEOUS MODE: Count endpoints by source
  const endpointsBySource = useMemo(() => {
    return countEndpointsBySource(displayEndpoints);
  }, [displayEndpoints]);

  // HOMOGENEOUS MODE: Filter endpoints by source
  const filteredDisplayEndpoints = useMemo(() => {
    if (sourceFilter === 'all') return displayEndpoints;
    return displayEndpoints.filter(ep => {
      const normalizedSource = ep.source === 'unusualwhales' ? 'uw' : ep.source;
      return normalizedSource === sourceFilter;
    });
  }, [displayEndpoints, sourceFilter]);

  // HOMOGENEOUS MODE: Group endpoints by category
  const endpointsByCategory = useMemo(() => {
    return groupEndpointsByCategory(filteredDisplayEndpoints);
  }, [filteredDisplayEndpoints]);

  // HETEROGENEOUS MODE: Get joinable endpoints per type
  const joinableEndpointsByType = useMemo(() => {
    if (endpointSelectionMode !== 'heterogeneous') return {};
    
    const result: Record<string, EndpointTimeInfo[]> = {};
    for (const objType of uniqueObjectTypes) {
      result[objType] = getJoinableEndpoints(endpointsByTimeGroup, objType);
    }
    return result;
  }, [uniqueObjectTypes, endpointsByTimeGroup, endpointSelectionMode]);

  // HETEROGENEOUS MODE: Count endpoints by source per type
  const endpointsBySourceByType = useMemo(() => {
    const result: Record<string, Record<string, number>> = {};
    for (const [objType, endpoints] of Object.entries(joinableEndpointsByType)) {
      const counts: Record<string, number> = { all: endpoints.length, fmp: 0, polygon: 0, uw: 0 };
      endpoints.forEach(ep => {
        const src = (ep.source || 'fmp') === 'unusualwhales' ? 'uw' : (ep.source || 'fmp');
        if (counts[src] !== undefined) counts[src]++;
      });
      result[objType] = counts;
    }
    return result;
  }, [joinableEndpointsByType]);

  // HETEROGENEOUS MODE: Filter joinable endpoints by source per type
  const filteredJoinableEndpointsByType = useMemo(() => {
    const result: Record<string, EndpointTimeInfo[]> = {};
    for (const [objType, endpoints] of Object.entries(joinableEndpointsByType)) {
      const filter = sourceFilterByType[objType] || 'all';
      if (filter === 'all') {
        result[objType] = endpoints;
      } else {
        result[objType] = endpoints.filter(ep => {
          const normalizedSource = (ep.source || 'fmp') === 'unusualwhales' ? 'uw' : (ep.source || 'fmp');
          return normalizedSource === filter;
        });
      }
    }
    return result;
  }, [joinableEndpointsByType, sourceFilterByType]);

  // HETEROGENEOUS MODE: Group joinable endpoints by category per type
  const endpointsByCategoryByType = useMemo(() => {
    const result: Record<string, Record<string, EndpointTimeInfo[]>> = {};
    for (const [objType, endpoints] of Object.entries(filteredJoinableEndpointsByType)) {
      result[objType] = groupTimeEndpointsByCategory(endpoints);
    }
    return result;
  }, [filteredJoinableEndpointsByType]);

  // HETEROGENEOUS MODE: Get combined field info for field selector
  const heterogeneousFieldInfo = useMemo(() => {
    if (endpointSelectionMode !== 'heterogeneous') return null;
    
    const selectedEndpoints: Record<string, EndpointTimeInfo> = {};
    for (const [objType, ep] of Object.entries(endpointByType)) {
      if (ep) selectedEndpoints[objType] = ep;
    }
    
    if (Object.keys(selectedEndpoints).length === 0) return null;
    
    return getFieldsByEndpoint(selectedEndpoints);
  }, [endpointByType, endpointSelectionMode]);

  // Check if all types have an endpoint selected in heterogeneous mode
  const allTypesHaveEndpoint = useMemo(() => {
    if (endpointSelectionMode !== 'heterogeneous') return false;
    return uniqueObjectTypes.every(ot => endpointByType[ot] !== null);
  }, [uniqueObjectTypes, endpointByType, endpointSelectionMode]);

  // Check if join is compatible in heterogeneous mode
  const isJoinCompatible = useMemo(() => {
    if (!joinStrategy) return false;
    return joinStrategy.strategy !== 'incompatible';
  }, [joinStrategy]);

  // ============================================================================
  // HANDLERS
  // ============================================================================

  const handleSelectSymbol = useCallback(async (result: { symbol: string; name: string; exchange?: string }) => {
    let objectType: string;
    try {
      const detectRes = await api.post('/api/canvas/data/objects/detect', { symbol: result.symbol });
      objectType = detectRes.data.object_type || 'equity';
    } catch {
      objectType = result.exchange?.toLowerCase().includes('crypto') 
        ? 'crypto' 
        : result.exchange?.toLowerCase().includes('forex')
        ? 'forex'
        : 'equity';
    }

    addMultiSelectedSymbol({
      symbol: result.symbol,
      name: result.name,
      objectType,
    });
    setSearchQuery('');
    setShowDropdown(false);
  }, [addMultiSelectedSymbol]);

  const handleRemoveSymbol = useCallback((symbol: string) => {
    removeMultiSelectedSymbol(symbol);
  }, [removeMultiSelectedSymbol]);

  const handleAddForexPair = useCallback((pair: string) => {
    const isAlreadySelected = selectedSymbols.some(s => s.symbol === pair);
    if (!isAlreadySelected) {
      addMultiSelectedSymbol({ 
        symbol: pair, 
        name: `${pair.slice(0,3)}/${pair.slice(3)}`, 
        objectType: 'forex' 
      });
    }
    setForexDropdownOpen(false);
    setForexSearch('');
  }, [selectedSymbols, addMultiSelectedSymbol]);

  const handleAddCryptoPair = useCallback((pair: string) => {
    const isAlreadySelected = selectedSymbols.some(s => s.symbol === pair);
    if (!isAlreadySelected) {
      addMultiSelectedSymbol({ 
        symbol: pair, 
        name: `${pair.replace('USD','')}/USD`, 
        objectType: 'crypto' 
      });
    }
    setCryptoDropdownOpen(false);
    setCryptoSearch('');
  }, [selectedSymbols, addMultiSelectedSymbol]);

  const toggleCategory = useCallback((category: string) => {
    const next = new Set(expandedCategories);
    if (next.has(category)) {
      next.delete(category);
    } else {
      next.add(category);
    }
    setExpandedCategories(next);
  }, [expandedCategories, setExpandedCategories]);

  // Homogeneous mode: select same endpoint for all types
  const handleEndpointSelect = useCallback((ep: EndpointInfo) => {
    setSelectedEndpoint(ep);
    setSelectedFields([]);
    const defaults = getSmartParamDefaults(ep);
    setFormParams(mergeParamsWithDefaults(defaults, formParams));
  }, [formParams, setSelectedEndpoint, setSelectedFields, setFormParams]);

  // Heterogeneous mode: select endpoint for a specific object type
  const handleEndpointSelectForType = useCallback((objectType: string, ep: EndpointTimeInfo | null) => {
    setMultiEndpointByType({
      ...endpointByType,
      [objectType]: ep,
    });
    
    if (ep) {
      setMultiFieldsByType({
        ...fieldsByType,
        [objectType]: [],
      });
      
      const epInfo = timeInfoToEndpointInfo(ep);
      const smartDefaults = getSmartParamDefaults(epInfo);
      
      setMultiParamsByType({
        ...paramsByType,
        [objectType]: smartDefaults,
      });
    } else {
      setMultiParamsByType({
        ...paramsByType,
        [objectType]: {},
      });
    }
  }, [endpointByType, fieldsByType, paramsByType, setMultiEndpointByType, setMultiFieldsByType, setMultiParamsByType]);

  // Toggle category expansion for a specific object type (heterogeneous mode)
  const toggleCategoryForType = useCallback((objectType: string, category: string) => {
    const typeCategories = expandedCategoriesByType[objectType] || new Set();
    const next = new Set(typeCategories);
    if (next.has(category)) {
      next.delete(category);
    } else {
      next.add(category);
    }
    setExpandedCategoriesByType({ ...expandedCategoriesByType, [objectType]: next });
  }, [expandedCategoriesByType, setExpandedCategoriesByType]);

  // Handle field toggle for heterogeneous mode (per-type field selection)
  const handleFieldToggleForType = useCallback((objectType: string, field: string) => {
    const typeFields = fieldsByType[objectType] || [];
    const hasField = typeFields.includes(field);
    setMultiFieldsByType({
      ...fieldsByType,
      [objectType]: hasField 
        ? typeFields.filter(f => f !== field)
        : [...typeFields, field],
    });
  }, [fieldsByType, setMultiFieldsByType]);

  // Select all fields for a type in heterogeneous mode
  const handleSelectAllFieldsForType = useCallback((objectType: string) => {
    const ep = endpointByType[objectType];
    if (ep) {
      setMultiFieldsByType({
        ...fieldsByType,
        [objectType]: [...ep.fields],
      });
    }
  }, [endpointByType, fieldsByType, setMultiFieldsByType]);

  // Set params for a specific type in heterogeneous mode
  const setParamsForType = useCallback((objectType: string, params: Record<string, string>) => {
    setMultiParamsByType({
      ...paramsByType,
      [objectType]: params,
    });
  }, [paramsByType, setMultiParamsByType]);

  const handleFieldToggle = useCallback((field: string) => {
    if (selectedFields.includes(field)) {
      setSelectedFields(selectedFields.filter(f => f !== field));
    } else {
      setSelectedFields([...selectedFields, field]);
    }
  }, [selectedFields, setSelectedFields]);

  const handleSelectAllFields = useCallback(() => {
    if (selectedEndpoint) {
      setSelectedFields(selectedEndpoint.fields);
    }
  }, [selectedEndpoint, setSelectedFields]);

  // Reset all form state
  const resetForm = useCallback(() => {
    // Reset store state
    resetMultiFormAction();
    
    // Reset local transient state
    setSearchQuery('');
    setShowDropdown(false);
    setForexDropdownOpen(false);
    setCryptoDropdownOpen(false);
    setForexSearch('');
    setCryptoSearch('');
    setEndpointsByType({});
    setEquivalenceGroups([]);
    setEndpointsByTimeGroup({});
    setJoinStrategy(null);
    setSubmitting(false);
    setGranularitiesDetected([]);
    setHasMixedGranularity(false);
    setStructureTypesDetected([]);
    setHasIncompatibleStructures(false);
    setIncompatiblePairs([]);
    setEndpointsByStructure({ date: [], fiscal: [], snapshot: [], none: [] });
  }, [resetMultiFormAction]);

  // Get current form state for persistence (backward compatibility)
  const getFormState = useCallback((): MultiObjectFormState => ({
    selectedSymbols,
    searchMode,
    endpointSelectionMode,
    selectedEndpoint,
    selectedFields,
    formParams,
    expandedCategories: Array.from(expandedCategories),
    sourceFilter,
    endpointByType,
    fieldsByType,
    paramsByType,
    expandedCategoriesByType: Object.fromEntries(
      Object.entries(expandedCategoriesByType).map(([k, v]) => [k, Array.from(v)])
    ),
    sourceFilterByType,
    targetGranularity: targetGranularity || undefined,
  }), [selectedSymbols, searchMode, endpointSelectionMode, selectedEndpoint, selectedFields, formParams, expandedCategories, sourceFilter, endpointByType, fieldsByType, paramsByType, expandedCategoriesByType, sourceFilterByType, targetGranularity]);

  // Restore form state from persistence (backward compatibility - now a no-op since store handles this)
  const restoreFormState = useCallback((_state: MultiObjectFormState) => {
    // This is now handled automatically by the store.
    // Keeping for backward compatibility but it's a no-op.
    console.warn('[useMultiObjectForm] restoreFormState is deprecated. State is now automatically synced from the store.');
  }, []);

  // Check if there's any unsaved data
  const hasUnsavedData = selectedSymbols.length > 0 || selectedEndpoint !== null || selectedFields.length > 0;

  return {
    // Search mode
    searchMode,
    setSearchMode,
    
    // Symbol selection
    selectedSymbols,
    setSelectedSymbols,
    searchQuery,
    setSearchQuery,
    showDropdown,
    setShowDropdown,
    
    // Forex pairs
    forexPairs,
    loadingForexPairs,
    forexDropdownOpen,
    setForexDropdownOpen,
    forexSearch,
    setForexSearch,
    filteredForexPairs,
    
    // Crypto pairs
    cryptoPairs,
    loadingCryptoPairs,
    cryptoDropdownOpen,
    setCryptoDropdownOpen,
    cryptoSearch,
    setCryptoSearch,
    filteredCryptoPairs,
    
    // Endpoint selection mode
    endpointSelectionMode,
    setEndpointSelectionMode,
    hasMultipleObjectTypes,
    
    // HOMOGENEOUS MODE endpoints
    endpointsByType,
    equivalenceGroups,
    loadingEndpoints,
    displayEndpoints,
    endpointsByCategory,
    expandedCategories,
    setExpandedCategories,
    selectedEndpoint,
    setSelectedEndpoint,
    
    // Source filter (homogeneous mode)
    sourceFilter,
    setSourceFilter,
    endpointsBySource,
    
    // HETEROGENEOUS MODE endpoints
    endpointsByTimeGroup,
    endpointByType,
    setEndpointByType,
    joinStrategy,
    joinableEndpointsByType,
    endpointsByCategoryByType,
    expandedCategoriesByType,
    setExpandedCategoriesByType,
    heterogeneousFieldInfo,
    allTypesHaveEndpoint,
    isJoinCompatible,
    fieldsByType,
    setFieldsByType,
    paramsByType,
    setParamsForType,
    
    // Source filter (heterogeneous mode)
    sourceFilterByType,
    setSourceFilterByType: (filterByType: Record<string, string>) => setMultiSourceFilterByType(filterByType),
    endpointsBySourceByType,
    
    // Granularity alignment
    granularitiesDetected,
    hasMixedGranularity,
    targetGranularity,
    setTargetGranularity,
    
    // Structure type compatibility
    structureTypesDetected,
    hasIncompatibleStructures,
    incompatiblePairs,
    endpointsByStructure,
    
    // Fields (homogeneous mode)
    selectedFields,
    setSelectedFields,
    formParams,
    setFormParams,
    
    // Submission
    submitting,
    setSubmitting,
    
    // Computed
    hasMinimumSymbols,
    hasAnySymbols,
    uniqueObjectTypes,
    hasUnsavedData,
    
    // Handlers - homogeneous mode
    handleSelectSymbol,
    handleRemoveSymbol,
    handleAddForexPair,
    handleAddCryptoPair,
    toggleCategory,
    handleEndpointSelect,
    handleFieldToggle,
    handleSelectAllFields,
    
    // Handlers - heterogeneous mode
    handleEndpointSelectForType,
    toggleCategoryForType,
    handleFieldToggleForType,
    handleSelectAllFieldsForType,
    
    // State management
    resetForm,
    getFormState,
    restoreFormState,
  };
}
