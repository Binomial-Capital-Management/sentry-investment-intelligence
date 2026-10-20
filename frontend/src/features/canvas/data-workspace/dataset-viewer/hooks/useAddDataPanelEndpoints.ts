import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  loadEndpointsWithEquivalence,
  groupEndpointsByCategory,
  countEndpointsBySource,
  getEquivalentEndpoints,
  analyzeJoinStrategy,
} from '@/features/canvas/data-workspace/query-builder/utils/queryUtils';
import type { EndpointInfo, EquivalenceGroup, Granularity, JoinStrategy } from '@/features/canvas/types';
import {
  mapBackendToTimeStructure,
  checkStructureCompatibility,
  type TimeStructure,
} from '@/utils/compatibilityMatrix';

interface UseAddDataPanelEndpointsArgs {
  uniqueObjectTypes: string[];
  sourceFilter: string;
  endpointSelectionMode: 'homogeneous' | 'heterogeneous';
  selectedEndpointByType: Record<string, EndpointInfo | null>;
}

export function useAddDataPanelEndpoints({
  uniqueObjectTypes,
  sourceFilter,
  endpointSelectionMode,
  selectedEndpointByType,
}: UseAddDataPanelEndpointsArgs) {
  // Endpoints loaded per type (derived from API)
  const [endpointsByType, setEndpointsByType] = useState<Record<string, EndpointInfo[]>>({});
  const [equivalenceGroups, setEquivalenceGroups] = useState<EquivalenceGroup[]>([]);
  const [loading, setLoading] = useState(true);

  // Source filter per type for heterogeneous mode
  const [sourceFilterByType, setSourceFilterByType] = useState<Record<string, string>>({});

  // UW Expirations state (for options endpoints needing expiry param)
  const [uwExpirations, setUwExpirations] = useState<Record<string, string[]>>({});
  const [uwExpirationsLoading, setUwExpirationsLoading] = useState<Set<string>>(new Set());

  // Structure type compatibility (heterogeneous mode only)
  const [structureTypesDetected, setStructureTypesDetected] = useState<TimeStructure[]>([]);
  const [hasIncompatibleStructures, setHasIncompatibleStructures] = useState(false);
  const [incompatiblePairs, setIncompatiblePairs] = useState<[TimeStructure, TimeStructure][]>([]);
  const [endpointsByStructure, setEndpointsByStructure] = useState<Record<TimeStructure, string[]>>({
    date: [], fiscal: [], snapshot: [], none: []
  });

  // Fetch UW expirations for a ticker
  const fetchUwExpirations = useCallback(async (ticker: string) => {
    if (!ticker || uwExpirations[ticker] || uwExpirationsLoading.has(ticker)) return;

    setUwExpirationsLoading(prev => new Set(prev).add(ticker));
    try {
      const response = await fetch(`/api/canvas/data/uw/expirations/${encodeURIComponent(ticker)}`);
      if (response.ok) {
        const data = await response.json();
        setUwExpirations(prev => ({ ...prev, [ticker]: data.expirations || [] }));
      }
    } catch (error) {
      console.error(`Error fetching UW expirations for ${ticker}:`, error);
      setUwExpirations(prev => ({ ...prev, [ticker]: [] }));
    } finally {
      setUwExpirationsLoading(prev => {
        const next = new Set(prev);
        next.delete(ticker);
        return next;
      });
    }
  }, [uwExpirations, uwExpirationsLoading]);

  // Stable key for uniqueObjectTypes — only re-fetch when actual values change
  const objectTypesKey = uniqueObjectTypes.slice().sort().join(',');

  // Load endpoints for each unique object type (with equivalence groups for multi-type)
  useEffect(() => {
    let cancelled = false;

    async function loadAll() {
      setLoading(true);

      try {
        const result = await loadEndpointsWithEquivalence(uniqueObjectTypes);

        if (!cancelled) {
          setEndpointsByType(result.byType);
          setEquivalenceGroups(result.equivalenceGroups);
        }
      } catch (e) {
        console.error('Failed to load endpoints:', e);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    if (uniqueObjectTypes.length > 0) {
      loadAll();
    }
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objectTypesKey]);

  // HETEROGENEOUS MODE: Detect structure type incompatibilities
  useEffect(() => {
    if (endpointSelectionMode !== 'heterogeneous') {
      setStructureTypesDetected([]);
      setHasIncompatibleStructures(false);
      setIncompatiblePairs([]);
      setEndpointsByStructure({ date: [], fiscal: [], snapshot: [], none: [] });
      return;
    }

    const structureMap: Record<TimeStructure, string[]> = {
      date: [], fiscal: [], snapshot: [], none: []
    };

    Object.entries(selectedEndpointByType).forEach(([_objType, ep]) => {
      if (ep) {
        const structure = mapBackendToTimeStructure(ep.structureType);
        structureMap[structure].push(ep.endpoint);
      }
    });

    const detected = (Object.keys(structureMap) as TimeStructure[])
      .filter(s => structureMap[s].length > 0);

    const { compatible, incompatiblePairs: pairs } = checkStructureCompatibility(detected);

    setStructureTypesDetected(detected);
    setHasIncompatibleStructures(!compatible);
    setIncompatiblePairs(pairs);
    setEndpointsByStructure(structureMap);
  }, [selectedEndpointByType, endpointSelectionMode]);

  // Granularity detection (heterogeneous mode)
  const [granularitiesDetected, setGranularitiesDetected] = useState<Granularity[]>([]);
  const [hasMixedGranularity, setHasMixedGranularity] = useState(false);
  const [targetGranularity, setTargetGranularity] = useState<Granularity | null>(null);
  const [joinStrategy, setJoinStrategy] = useState<JoinStrategy | null>(null);

  useEffect(() => {
    if (endpointSelectionMode !== 'heterogeneous') {
      setGranularitiesDetected([]);
      setHasMixedGranularity(false);
      setJoinStrategy(null);
      return;
    }

    const selectedEndpoints: Record<string, string> = {};
    const localGranularities = new Set<Granularity>();

    for (const [objType, ep] of Object.entries(selectedEndpointByType)) {
      if (ep) {
        selectedEndpoints[objType] = ep.endpoint;
        if (ep.granularity) {
          localGranularities.add(ep.granularity as Granularity);
        }
      }
    }

    const granList = Array.from(localGranularities);
    setGranularitiesDetected(granList);
    setHasMixedGranularity(granList.length > 1);

    // Call backend join strategy when all types have an endpoint
    const allTypesHaveEndpoint = uniqueObjectTypes.length > 0 &&
      uniqueObjectTypes.every(t => selectedEndpointByType[t]);

    if (allTypesHaveEndpoint && Object.keys(selectedEndpoints).length >= 2) {
      analyzeJoinStrategy(selectedEndpoints).then(strategy => {
        setJoinStrategy(strategy);
        if (strategy.granularities.length > 0) {
          setGranularitiesDetected(strategy.granularities);
          setHasMixedGranularity(strategy.needs_aggregation);
          if (strategy.aggregation_target) {
            setTargetGranularity(strategy.aggregation_target);
          }
        }
      });
    } else {
      setJoinStrategy(null);
    }
  }, [selectedEndpointByType, endpointSelectionMode, uniqueObjectTypes]);

  // HOMOGENEOUS MODE: Get common endpoints across all types using equivalence groups
  const commonEndpoints = useMemo(() => {
    if (uniqueObjectTypes.length === 0) return [];
    if (uniqueObjectTypes.length === 1) {
      return endpointsByType[uniqueObjectTypes[0]] || [];
    }

    if (equivalenceGroups.length > 0) {
      return getEquivalentEndpoints(uniqueObjectTypes, endpointsByType, equivalenceGroups);
    }

    // Fallback to strict name-based matching if no equivalence groups
    const allSets = uniqueObjectTypes.map(t =>
      new Set((endpointsByType[t] || []).map(e => e.endpoint))
    );

    if (allSets.length === 0 || allSets[0].size === 0) return [];

    const commonNames = [...allSets[0]].filter(ep =>
      allSets.every(set => set.has(ep))
    );

    return (endpointsByType[uniqueObjectTypes[0]] || [])
      .filter(e => commonNames.includes(e.endpoint));
  }, [uniqueObjectTypes, endpointsByType, equivalenceGroups]);

  // Count endpoints by source (for filter badges)
  const endpointsBySource = useMemo(() => {
    return countEndpointsBySource(commonEndpoints);
  }, [commonEndpoints]);

  // Filter endpoints by source, then group by category (for homogeneous mode)
  const filteredEndpoints = useMemo(() => {
    if (sourceFilter === 'all') return commonEndpoints;
    return commonEndpoints.filter(ep => {
      const normalizedSource = ep.source === 'unusualwhales' ? 'uw' : ep.source;
      return normalizedSource === sourceFilter;
    });
  }, [commonEndpoints, sourceFilter]);

  // Group endpoints by category (for homogeneous mode)
  const endpointsByCategory = useMemo(() => {
    return groupEndpointsByCategory(filteredEndpoints);
  }, [filteredEndpoints]);

  // HETEROGENEOUS MODE: Count endpoints by source per type
  const endpointsBySourceByType = useMemo(() => {
    const result: Record<string, Record<string, number>> = {};
    for (const objType of uniqueObjectTypes) {
      const endpoints = endpointsByType[objType] || [];
      result[objType] = countEndpointsBySource(endpoints);
    }
    return result;
  }, [uniqueObjectTypes, endpointsByType]);

  return {
    // Raw endpoint data
    endpointsByType,
    equivalenceGroups,
    loading,

    // Source filter per type (heterogeneous)
    sourceFilterByType,
    setSourceFilterByType,

    // UW expirations
    uwExpirations,
    uwExpirationsLoading,
    fetchUwExpirations,

    // Structure compatibility (heterogeneous)
    structureTypesDetected,
    hasIncompatibleStructures,
    incompatiblePairs,
    endpointsByStructure,

    // Derived endpoint collections (homogeneous)
    commonEndpoints,
    endpointsBySource,
    filteredEndpoints,
    endpointsByCategory,

    // Derived endpoint collections (heterogeneous)
    endpointsBySourceByType,

    // Granularity detection (heterogeneous)
    granularitiesDetected,
    hasMixedGranularity,
    targetGranularity,
    setTargetGranularity,
    joinStrategy,
  };
}
