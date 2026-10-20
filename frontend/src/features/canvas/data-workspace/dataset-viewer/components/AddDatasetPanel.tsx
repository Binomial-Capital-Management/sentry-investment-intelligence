/**
 * AddDataSidebar - Sidebar for adding new datasets to workspace
 *
 * Supports multi-object with two modes:
 * 1. HOMOGENEOUS: Same endpoint for all symbols (filtered to common endpoints)
 * 2. HETEROGENEOUS: Different endpoint per object type (per-type sections)
 *
 * Flow:
 * 1. Browse endpoints by category (or per-type in heterogeneous mode)
 * 2. Click endpoint → auto-adds with all fields, shows field panel for editing
 * 3. Click added endpoint again → removes it from workspace
 * 4. Toggle fields in field panel to update the dataset
 *
 * STATE: All form state is persisted in Zustand store per-tab to survive tab switches.
 */

import { useMemo, useCallback, useRef, useEffect, useState } from 'react';
import { groupEndpointsByCategory, getSmartParamDefaults, resolveEndpointForType } from '@/features/canvas/data-workspace/query-builder/utils/queryUtils';
import type { EndpointInfo, Granularity } from '@/features/canvas/types';
import { EndpointBrowser, FieldSelector, ParametersForm, SourceFilter } from '@/features/canvas/data-workspace/query-builder';
import GranularitySelector from '@/features/canvas/data-workspace/query-builder/components/inputs/GranularitySelector';
import { useDataWorkspaceStore } from '../../stores/dataWorkspaceStore';
import {
  selectAddDataPanelEndpointMode,
  selectAddDataPanelSourceFilter,
  selectAddDataPanelSelectedEndpoint,
  selectAddDataPanelSelectedFields,
  selectAddDataPanelFormParams,
  selectAddDataPanelExpandedCategories,
  selectAddDataPanelSelectedEndpointByType,
  selectAddDataPanelFieldsByType,
  selectAddDataPanelParamsByType,
  selectAddDataPanelExpandedCategoriesByType,
  selectAddDataPanelScrollPosition,
  selectActiveGroupId,
} from '../../stores/selectors';
import { useAddDataPanelEndpoints } from '../hooks/useAddDataPanelEndpoints';
import { useAddDataPanelGroups } from '../hooks/useAddDataPanelGroups';
import { SymbolSelector } from './SymbolSelector';
import { GroupPicker } from './GroupPicker';

interface SelectedObject {
  symbol: string;
  name?: string;
  objectType: string;
}

interface ExistingDataset {
  id: string;
  symbol: string;
  endpoint: string;
  fields: string[];
  params: Record<string, any>;
}

interface AddDataSidebarProps {
  /** Selected objects with type info */
  selectedObjects: SelectedObject[];
  /** @deprecated Use store actions directly - kept for backward compat */
  onAddDataset?: (config: Omit<{ symbol: string; endpoint: string; params: Record<string, any>; fields: string[]; category?: string }, 'id' | 'addedAt'>) => Promise<void>;
  onClose: () => void;
  /** Endpoints already added to workspace - will be highlighted */
  addedEndpoints?: Set<string>;
  /** Existing datasets to pre-populate fields when clicking an added endpoint */
  existingDatasets?: ExistingDataset[];
  /** Update an existing dataset's fields and/or params */
  onUpdateDataset?: (id: string, updates: { fields?: string[]; params?: Record<string, any> }) => void;
  /** Navigate to a dataset's page in the table */
  onNavigateToDataset?: (endpoint: string) => void;
  /** Remove a dataset by id */
  onRemoveDataset?: (id: string) => void;
  /** Hide the header (when parent handles it) */
  hideHeader?: boolean;
  /** Pre-select this endpoint when sidebar opens */
  initialEndpoint?: string;
  /** When navigating from a specific dataset, use this to find its fields/params */
  initialDatasetId?: string;
  /** Clear initialEndpoint after it's been used */
  onClearInitialEndpoint?: () => void;
}

export function AddDataSidebar({
  selectedObjects,
  onAddDataset: _onAddDataset,
  onClose,
  addedEndpoints = new Set(),
  existingDatasets = [],
  onUpdateDataset,
  onNavigateToDataset,
  onRemoveDataset,
  hideHeader = false,
  initialEndpoint,
  initialDatasetId,
  onClearInitialEndpoint,
}: AddDataSidebarProps) {
  // Derive unique object types
  const uniqueObjectTypes = useMemo(() =>
    [...new Set(selectedObjects.map(s => s.objectType))],
    [selectedObjects]
  );
  const hasMultipleTypes = uniqueObjectTypes.length > 1;

  // Active group for adding datasets
  const activeGroupId = useDataWorkspaceStore(selectActiveGroupId);

  // ============================================================================
  // PERSISTED STATE - From Zustand store (survives tab switches)
  // ============================================================================

  const endpointSelectionMode = useDataWorkspaceStore(selectAddDataPanelEndpointMode);
  const setEndpointSelectionMode = useDataWorkspaceStore(s => s.setAddDataPanelEndpointMode);

  const sourceFilter = useDataWorkspaceStore(selectAddDataPanelSourceFilter);


  // HOMOGENEOUS MODE state
  const selectedEndpoint = useDataWorkspaceStore(selectAddDataPanelSelectedEndpoint);
  const setSelectedEndpoint = useDataWorkspaceStore(s => s.setAddDataPanelSelectedEndpoint);
  const selectedFields = useDataWorkspaceStore(selectAddDataPanelSelectedFields);
  const setSelectedFields = useDataWorkspaceStore(s => s.setAddDataPanelSelectedFields);
  const formParams = useDataWorkspaceStore(selectAddDataPanelFormParams);
  const setFormParams = useDataWorkspaceStore(s => s.setAddDataPanelFormParams);
  const expandedCategoriesArray = useDataWorkspaceStore(selectAddDataPanelExpandedCategories);
  const setExpandedCategoriesAction = useDataWorkspaceStore(s => s.setAddDataPanelExpandedCategories);

  // HETEROGENEOUS MODE state
  const selectedEndpointByType = useDataWorkspaceStore(selectAddDataPanelSelectedEndpointByType);
  const setSelectedEndpointByType = useDataWorkspaceStore(s => s.setAddDataPanelSelectedEndpointByType);
  const fieldsByType = useDataWorkspaceStore(selectAddDataPanelFieldsByType);
  const setFieldsByType = useDataWorkspaceStore(s => s.setAddDataPanelFieldsByType);
  const paramsByType = useDataWorkspaceStore(selectAddDataPanelParamsByType);
  const setParamsByType = useDataWorkspaceStore(s => s.setAddDataPanelParamsByType);
  const expandedCategoriesByTypeArray = useDataWorkspaceStore(selectAddDataPanelExpandedCategoriesByType);
  const setExpandedCategoriesByTypeAction = useDataWorkspaceStore(s => s.setAddDataPanelExpandedCategoriesByType);

  const scrollPosition = useDataWorkspaceStore(selectAddDataPanelScrollPosition);
  const setScrollPosition = useDataWorkspaceStore(s => s.setAddDataPanelScrollPosition);

  // Convert arrays to Sets for compatibility
  const expandedCategories = useMemo(() => new Set(expandedCategoriesArray), [expandedCategoriesArray]);
  const expandedCategoriesByType = useMemo(() => {
    const result: Record<string, Set<string>> = {};
    for (const [key, arr] of Object.entries(expandedCategoriesByTypeArray)) {
      result[key] = new Set(arr);
    }
    return result;
  }, [expandedCategoriesByTypeArray]);

  const setExpandedCategories = useCallback(
    (categories: Set<string>) => setExpandedCategoriesAction(Array.from(categories)),
    [setExpandedCategoriesAction]
  );
  const setExpandedCategoriesByType = useCallback(
    (categoriesByType: Record<string, Set<string>>) => {
      const converted: Record<string, string[]> = {};
      for (const [key, set] of Object.entries(categoriesByType)) {
        converted[key] = Array.from(set);
      }
      setExpandedCategoriesByTypeAction(converted);
    },
    [setExpandedCategoriesByTypeAction]
  );

  // Reset to homogeneous when only one object type remains
  useEffect(() => {
    if (!hasMultipleTypes && endpointSelectionMode === 'heterogeneous') {
      setEndpointSelectionMode('homogeneous');
    }
  }, [hasMultipleTypes, endpointSelectionMode, setEndpointSelectionMode]);

  // ============================================================================
  // EXTRACTED HOOKS
  // ============================================================================

  const endpoints = useAddDataPanelEndpoints({
    uniqueObjectTypes,
    sourceFilter,
    endpointSelectionMode,
    selectedEndpointByType,
  });

  const groups = useAddDataPanelGroups({
    endpointSelectionMode,
    selectedEndpoint,
    selectedFields,
    formParams,
    uniqueObjectTypes,
    selectedEndpointByType,
    fieldsByType,
    paramsByType,
    selectedObjects,
    existingDatasets,
    equivalenceGroups: endpoints.equivalenceGroups,
    onNavigateToDataset,
  });

  // ============================================================================
  // INITIAL ENDPOINT HANDLING
  // ============================================================================

  const processedInitialEndpointRef = useRef<string | null>(null);
  const activeDatasetIdRef = useRef<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  // Resizable field/params split (percentage of fields section)
  const [fieldSplitPct, setFieldSplitPct] = useState(50);
  const fieldPanelRef = useRef<HTMLDivElement>(null);

  const handleSplitResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startPct = fieldSplitPct;

    const onMouseMove = (ev: MouseEvent) => {
      const panel = fieldPanelRef.current;
      if (!panel) return;
      const panelWidth = panel.getBoundingClientRect().width;
      if (panelWidth === 0) return;
      const deltaPx = ev.clientX - startX;
      const deltaPct = (deltaPx / panelWidth) * 100;
      const newPct = Math.max(25, Math.min(75, startPct + deltaPct));
      setFieldSplitPct(newPct);
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [fieldSplitPct]);


  // Keep field panel content rendered during close animation
  const [deferredEndpoint, setDeferredEndpoint] = useState(selectedEndpoint);
  const showFieldPanel = !!selectedEndpoint;
  useEffect(() => {
    if (selectedEndpoint) {
      setDeferredEndpoint(selectedEndpoint);
    } else {
      const timer = setTimeout(() => setDeferredEndpoint(null), 300);
      return () => clearTimeout(timer);
    }
  }, [selectedEndpoint]);
  const displayedEndpoint = selectedEndpoint ?? deferredEndpoint;

  // Fade indicators for endpoint browser when field panel is open
  const epBrowserRef = useRef<HTMLDivElement>(null);
  const [epFades, setEpFades] = useState({ top: false, bottom: false });
  const updateEpFades = useCallback(() => {
    const el = epBrowserRef.current;
    if (!el) return;
    setEpFades({
      top: el.scrollTop > 2,
      bottom: el.scrollTop + el.clientHeight < el.scrollHeight - 2,
    });
  }, []);
  useEffect(() => {
    const el = epBrowserRef.current;
    if (!el) return;
    updateEpFades();
    el.addEventListener('scroll', updateEpFades, { passive: true });
    const ro = new ResizeObserver(updateEpFades);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', updateEpFades); ro.disconnect(); };
  }, [updateEpFades, selectedEndpoint]);

  // Fade indicators for homogeneous fields + params scroll panes
  const fieldsScrollRef = useRef<HTMLDivElement>(null);
  const [fieldsFades, setFieldsFades] = useState({ top: false, bottom: false });
  const updateFieldsFades = useCallback(() => {
    const el = fieldsScrollRef.current;
    if (!el) return;
    setFieldsFades({
      top: el.scrollTop > 2,
      bottom: el.scrollTop + el.clientHeight < el.scrollHeight - 2,
    });
  }, []);
  useEffect(() => {
    const el = fieldsScrollRef.current;
    if (!el) return;
    updateFieldsFades();
    el.addEventListener('scroll', updateFieldsFades, { passive: true });
    const ro = new ResizeObserver(updateFieldsFades);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', updateFieldsFades); ro.disconnect(); };
  }, [updateFieldsFades, displayedEndpoint]);

  const paramsScrollRef = useRef<HTMLDivElement>(null);
  const [paramsFades, setParamsFades] = useState({ top: false, bottom: false });
  const updateParamsFades = useCallback(() => {
    const el = paramsScrollRef.current;
    if (!el) return;
    setParamsFades({
      top: el.scrollTop > 2,
      bottom: el.scrollTop + el.clientHeight < el.scrollHeight - 2,
    });
  }, []);
  useEffect(() => {
    const el = paramsScrollRef.current;
    if (!el) return;
    updateParamsFades();
    el.addEventListener('scroll', updateParamsFades, { passive: true });
    const ro = new ResizeObserver(updateParamsFades);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', updateParamsFades); ro.disconnect(); };
  }, [updateParamsFades, displayedEndpoint]);

  // Fade indicators for heterogeneous field selector
  const hetFieldRef = useRef<HTMLDivElement>(null);
  const [hetFieldFades, setHetFieldFades] = useState({ top: false, bottom: false });
  const updateHetFieldFades = useCallback(() => {
    const el = hetFieldRef.current;
    if (!el) return;
    setHetFieldFades({
      top: el.scrollTop > 2,
      bottom: el.scrollTop + el.clientHeight < el.scrollHeight - 2,
    });
  }, []);
  useEffect(() => {
    const el = hetFieldRef.current;
    if (!el) return;
    updateHetFieldFades();
    el.addEventListener('scroll', updateHetFieldFades, { passive: true });
    const ro = new ResizeObserver(updateHetFieldFades);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', updateHetFieldFades); ro.disconnect(); };
  }, [updateHetFieldFades, selectedEndpointByType]);

  useEffect(() => {
    if (!initialEndpoint || endpoints.loading) return;
    const initialKey = initialDatasetId ? `${initialEndpoint}:${initialDatasetId}` : initialEndpoint;
    if (processedInitialEndpointRef.current === initialKey) return;

    const allEndpoints = Object.values(endpoints.endpointsByType).flat();
    const ep = allEndpoints.find(e => e.endpoint === initialEndpoint);

    if (ep) {
      processedInitialEndpointRef.current = initialKey;
      setSelectedEndpoint(ep);

      const existingDataset = (initialDatasetId && existingDatasets.find(d => d.id === initialDatasetId))
        || existingDatasets.find(d => d.endpoint === ep.endpoint);
      activeDatasetIdRef.current = existingDataset?.id ?? null;
      if (existingDataset) {
        setSelectedFields([...existingDataset.fields]);
        setFormParams(existingDataset.params as Record<string, string>);
      } else {
        setSelectedFields([]);
        const defaults = getSmartParamDefaults(ep);
        setFormParams(defaults);
      }

      if (ep.category) {
        setExpandedCategories(new Set([ep.category]));
      }

      onClearInitialEndpoint?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialEndpoint, endpoints.loading, endpoints.endpointsByType]);

  // ============================================================================
  // INLINE CALLBACKS (trivial setter wrappers)
  // ============================================================================

  const getSymbolsForType = useCallback((objType: string) => {
    return selectedObjects.filter(o => o.objectType === objType).map(o => o.symbol);
  }, [selectedObjects]);

  const toggleCategory = useCallback((category: string) => {
    const next = new Set(expandedCategories);
    if (next.has(category)) next.delete(category);
    else next.add(category);
    setExpandedCategories(next);
  }, [expandedCategories, setExpandedCategories]);

  const toggleCategoryForType = useCallback((objType: string, category: string) => {
    const typeCategories = expandedCategoriesByType[objType] || new Set();
    const next = new Set(typeCategories);
    if (next.has(category)) next.delete(category);
    else next.add(category);
    setExpandedCategoriesByType({ ...expandedCategoriesByType, [objType]: next });
  }, [expandedCategoriesByType, setExpandedCategoriesByType]);

  const handleEndpointSelect = useCallback((ep: EndpointInfo) => {
    const isAlreadyAdded = addedEndpoints.has(ep.endpoint);
    if (isAlreadyAdded) {
      // Second click on added endpoint → remove it
      const datasetsToRemove = existingDatasets.filter(d => d.endpoint === ep.endpoint);
      datasetsToRemove.forEach(d => onRemoveDataset?.(d.id));
      activeDatasetIdRef.current = null;
      // Deselect if this was the selected endpoint
      if (selectedEndpoint?.endpoint === ep.endpoint) {
        setSelectedEndpoint(null);
        setSelectedFields([]);
        setFormParams({});
      }
    } else {
      // First click → auto-add with all fields, show field panel
      const allFields = [...ep.fields];
      const defaults = getSmartParamDefaults(ep);
      setSelectedEndpoint(ep);
      setSelectedFields(allFields);
      setFormParams(defaults);

      // Build datasets and add directly
      const datasets = selectedObjects.map(obj => ({
        symbol: obj.symbol,
        endpoint: ep.equivalenceGroup
          ? resolveEndpointForType(ep.equivalenceGroup, obj.objectType, endpoints.equivalenceGroups)
          : ep.endpoint,
        params: defaults,
        fields: allFields,
        category: ep.category,
      }));

      if (datasets.length > 0) {
        // Use active group from picker, or auto-create one
        let targetGroupId = activeGroupId;
        if (!targetGroupId) {
          targetGroupId = groups.createDatasetGroup('Data');
        }
        // Migrate any orphaned datasets
        const hasOrphans = groups.allDatasets.some(d => !d.groupId);
        if (hasOrphans) groups.assignOrphanedDatasetsToGroup(targetGroupId);
        groups.handleAddDirect(targetGroupId, datasets);
      }
    }
  }, [addedEndpoints, existingDatasets, selectedEndpoint, selectedObjects, endpoints.equivalenceGroups, groups, onRemoveDataset, setSelectedEndpoint, setSelectedFields, setFormParams]);

  const handleEndpointSelectForType = useCallback((objType: string, ep: EndpointInfo) => {
    setSelectedEndpointByType({ ...selectedEndpointByType, [objType]: ep });
    const existingDataset = existingDatasets.find(d => d.endpoint === ep.endpoint);
    if (existingDataset) {
      setFieldsByType({ ...fieldsByType, [objType]: [...existingDataset.fields] });
      setParamsByType({ ...paramsByType, [objType]: existingDataset.params as Record<string, string> });
      onNavigateToDataset?.(ep.endpoint);
    } else {
      setFieldsByType({ ...fieldsByType, [objType]: [] });
      const defaults = getSmartParamDefaults(ep);
      setParamsByType({ ...paramsByType, [objType]: defaults });
    }
  }, [existingDatasets, onNavigateToDataset, selectedEndpointByType, fieldsByType, paramsByType, setSelectedEndpointByType, setFieldsByType, setParamsByType]);

  const handleBack = useCallback(() => {
    setSelectedEndpoint(null);
    setSelectedFields([]);
    setFormParams({});
    setSelectedEndpointByType({});
    setFieldsByType({});
    setParamsByType({});
  }, [setSelectedEndpoint, setSelectedFields, setFormParams, setSelectedEndpointByType, setFieldsByType, setParamsByType]);

  const handleFieldToggle = useCallback((field: string) => {
    const existingDataset = activeDatasetIdRef.current
      ? existingDatasets.find(d => d.id === activeDatasetIdRef.current)
      : selectedEndpoint
        ? existingDatasets.find(d => d.endpoint === selectedEndpoint.endpoint)
        : null;
    let newFields: string[];
    if (selectedFields.includes(field)) {
      newFields = selectedFields.filter(f => f !== field);
    } else {
      const canonical = selectedEndpoint?.fields || [];
      const added = new Set([...selectedFields, field]);
      newFields = canonical.filter(f => added.has(f));
    }
    setSelectedFields(newFields);
    if (existingDataset && onUpdateDataset) {
      onUpdateDataset(existingDataset.id, { fields: newFields });
    }
  }, [selectedEndpoint, selectedFields, existingDatasets, onUpdateDataset, setSelectedFields]);

  const handleFieldToggleForType = useCallback((objType: string, field: string) => {
    const ep = selectedEndpointByType[objType];
    const existingDataset = ep
      ? existingDatasets.find(d => d.endpoint === ep.endpoint)
      : null;
    const typeFields = fieldsByType[objType] || [];
    const newFields = typeFields.includes(field)
      ? typeFields.filter(f => f !== field)
      : [...typeFields, field];
    setFieldsByType({ ...fieldsByType, [objType]: newFields });
    if (existingDataset && onUpdateDataset) {
      onUpdateDataset(existingDataset.id, { fields: newFields });
    }
  }, [selectedEndpointByType, fieldsByType, existingDatasets, onUpdateDataset, setFieldsByType]);

  const handleSelectAll = useCallback(() => {
    if (selectedEndpoint) {
      const allFields = [...selectedEndpoint.fields];
      setSelectedFields(allFields);
      const existingDataset = activeDatasetIdRef.current
        ? existingDatasets.find(d => d.id === activeDatasetIdRef.current)
        : existingDatasets.find(d => d.endpoint === selectedEndpoint.endpoint);
      if (existingDataset && onUpdateDataset) {
        onUpdateDataset(existingDataset.id, { fields: allFields });
      }
    }
  }, [selectedEndpoint, existingDatasets, onUpdateDataset, setSelectedFields]);

  const handleSelectAllForType = useCallback((objType: string) => {
    const ep = selectedEndpointByType[objType];
    if (ep) {
      const allFields = [...ep.fields];
      setFieldsByType({ ...fieldsByType, [objType]: allFields });
      const existingDataset = existingDatasets.find(d => d.endpoint === ep.endpoint);
      if (existingDataset && onUpdateDataset) {
        onUpdateDataset(existingDataset.id, { fields: allFields });
      }
    }
  }, [selectedEndpointByType, fieldsByType, existingDatasets, onUpdateDataset, setFieldsByType]);

  const handleParamsChange = useCallback((newParams: Record<string, string>) => {
    setFormParams(newParams);
    const existingDataset = activeDatasetIdRef.current
      ? existingDatasets.find(d => d.id === activeDatasetIdRef.current)
      : selectedEndpoint
        ? existingDatasets.find(d => d.endpoint === selectedEndpoint.endpoint)
        : null;
    if (existingDataset && onUpdateDataset) {
      onUpdateDataset(existingDataset.id, { params: newParams });
    }
  }, [selectedEndpoint, existingDatasets, onUpdateDataset, setFormParams]);

  const handleParamsChangeForType = useCallback((objType: string, newParams: Record<string, string>) => {
    setParamsByType({ ...paramsByType, [objType]: newParams });
    const ep = selectedEndpointByType[objType];
    const existingDataset = ep
      ? existingDatasets.find(d => d.endpoint === ep.endpoint)
      : null;
    if (existingDataset && onUpdateDataset) {
      onUpdateDataset(existingDataset.id, { params: newParams });
    }
  }, [selectedEndpointByType, paramsByType, existingDatasets, onUpdateDataset, setParamsByType]);

  // ============================================================================
  // DERIVED STATE
  // ============================================================================

  const someExistHomogeneous = selectedEndpoint
    ? existingDatasets.some(d => d.endpoint === selectedEndpoint.endpoint)
    : false;


  const allTypesHaveEndpoints = uniqueObjectTypes.every(objType =>
    selectedEndpointByType[objType] !== null && selectedEndpointByType[objType] !== undefined
  );

  const allTypesReady = uniqueObjectTypes.every(objType => {
    const ep = selectedEndpointByType[objType];
    const fields = fieldsByType[objType] || [];
    return ep && fields.length > 0;
  });



  // ============================================================================
  // RENDER
  // ============================================================================

  return (
    <div ref={containerRef} className="flex-1 flex flex-col min-h-0">
      {/* Top section: Header + Symbol selector + Group picker */}
      <div
        className="flex-shrink-0 flex flex-col min-h-0"
        style={{ flex: '0 0 auto' }}
      >
        {/* Header */}
        {!hideHeader && (
          <div className="p-3 flex items-center justify-between" style={{ borderBottom: '0.5px solid hsl(30 3.3% 11.8% / 10%)', fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif" }}>
            <span style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)' }}>Sources</span>
            <button
              onClick={onClose}
              style={{ padding: 4, background: 'none', border: 'none', cursor: 'pointer', borderRadius: '0.25rem', color: 'hsl(60 2.5% 23.3% / 30%)', display: 'flex' }}
              title="Close panel"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Data Type + Symbol selector */}
        <SymbolSelector />

        {/* Group picker — only when tickers selected */}
        {selectedObjects.length > 0 && <GroupPicker />}
      </div>

      {/* Content — only when tickers selected */}
      {selectedObjects.length === 0 ? null : <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {/* Mode toggle when multiple object types */}
        {hasMultipleTypes && (
          <div style={{ padding: '1rem 1rem 0.5rem', borderBottom: '0.5px solid hsl(30 3.3% 11.8% / 10%)', fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif" }}>
            <label style={{ display: 'block', fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', marginBottom: '0.375rem' }}>
              Endpoint Selection Mode
            </label>
            <div style={{ display: 'flex', gap: '0.25rem' }}>
              {(['homogeneous', 'heterogeneous'] as const).map(mode => {
                const isActive = endpointSelectionMode === mode;
                return (
                  <button
                    key={mode}
                    onClick={() => setEndpointSelectionMode(mode)}
                    style={{
                      flex: 1,
                      padding: '0.375rem 0.5rem',
                      fontSize: '0.625rem',
                      fontWeight: 500,
                      fontFamily: "system-ui, sans-serif",
                      borderRadius: '0.375rem',
                      transition: 'all 0.1s ease',
                      border: isActive ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid hsl(30 3.3% 11.8% / 8%)',
                      backgroundColor: isActive ? 'hsl(30 3.3% 11.8% / 8%)' : 'hsl(30 3.3% 11.8% / 3%)',
                      color: isActive ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 45%)',
                      cursor: 'pointer',
                    }}
                  >
                    {mode === 'homogeneous' ? 'Same Endpoint' : 'Per-Type Endpoint'}
                  </button>
                );
              })}
            </div>
            <p style={{ marginTop: '0.25rem', fontSize: '0.563rem', color: 'hsl(60 2.5% 23.3% / 30%)' }}>
              {endpointSelectionMode === 'homogeneous'
                ? 'Same endpoint for all symbols (e.g., prices for equity + crypto)'
                : 'Different endpoint per type (e.g., financials + FX rates)'}
            </p>
          </div>
        )}

        {/* HOMOGENEOUS MODE */}
        {endpointSelectionMode === 'homogeneous' && (
          <div className="flex-1 flex flex-col min-h-0">
            {/* Endpoint browser — constrained when endpoint selected */}
            <div className="relative flex-1 min-h-0 flex flex-col">
              {showFieldPanel && epFades.top && <div className="pointer-events-none absolute top-0 left-0 right-0 h-6 z-10 bg-gradient-to-b from-white to-transparent" />}
              {showFieldPanel && epFades.bottom && <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 z-10 bg-gradient-to-t from-white to-transparent" />}
              <div ref={showFieldPanel ? epBrowserRef : undefined} className="flex-1 min-h-0 flex flex-col">
                <EndpointBrowser
                  loading={endpoints.loading}
                  endpointsByCategory={endpoints.endpointsByCategory}
                  expandedCategories={expandedCategories}
                  onToggleCategory={toggleCategory}
                  selectedEndpoint={selectedEndpoint}
                  onEndpointSelect={handleEndpointSelect}
                  emptyMessage={hasMultipleTypes
                    ? 'No compatible endpoints found for all types'
                    : 'No endpoints found'}
                  addedEndpoints={addedEndpoints}
                  initialScrollPosition={scrollPosition}
                  onScrollChange={setScrollPosition}
                />
              </div>
            </div>

            {/* Field selection panel — slides up from bottom */}
            <div
              className="flex flex-col min-h-0 overflow-hidden mx-2 mb-2 transition-all duration-300 ease-out"
              style={{
                flex: showFieldPanel ? '1 1 0%' : '0 0 0px',
                opacity: showFieldPanel ? 1 : 0,
                maxHeight: showFieldPanel ? '65%' : '0px',
                border: showFieldPanel ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : 'none',
                borderRadius: '0.75rem',
                backgroundColor: '#fff',
                margin: showFieldPanel ? undefined : '0 0.5rem',
                fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
              }}
            >
              {displayedEndpoint && (
                <>
                  {/* Static top — endpoint name */}
                  <div
                    className="px-4 py-3 flex items-center justify-between flex-shrink-0"
                    style={{ borderBottom: '0.5px solid hsl(30 3.3% 11.8% / 10%)', background: 'hsl(30 3.3% 11.8% / 3%)' }}
                  >
                    <span style={{ fontSize: '0.688rem', fontFamily: "'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace", color: 'hsl(60 2.5% 23.3% / 75%)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {displayedEndpoint.endpoint}
                    </span>
                    <button
                      onClick={handleBack}
                      style={{ color: 'hsl(60 2.5% 23.3% / 30%)', background: 'none', border: 'none', cursor: 'pointer', flexShrink: 0, marginLeft: '0.5rem', display: 'flex' }}
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  {/* Scrollable middle — fields + params side by side */}
                  <div ref={fieldPanelRef} className="flex-1 min-h-0 overflow-hidden px-4 py-3" style={{ display: 'flex' }}>
                    {displayedEndpoint.required_params.length > 0 ? (
                      <>
                        <div style={{ flex: `0 0 calc(${fieldSplitPct}% - 5px)`, minWidth: 0, position: 'relative' }}>
                          {fieldsFades.top && <div className="pointer-events-none absolute top-0 left-0 right-0 h-4 z-10 bg-gradient-to-b from-white to-transparent" />}
                          {fieldsFades.bottom && <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-4 z-10 bg-gradient-to-t from-white to-transparent" />}
                          <div ref={fieldsScrollRef} style={{ overflow: 'auto', height: '100%', paddingRight: 8 }}>
                            <FieldSelector
                              fields={displayedEndpoint.fields}
                              selectedFields={selectedFields}
                              onFieldToggle={handleFieldToggle}
                              onSelectAll={handleSelectAll}
                            />
                          </div>
                        </div>

                        {/* Draggable resize handle */}
                        <div
                          onMouseDown={handleSplitResizeStart}
                          style={{
                            flex: '0 0 9px',
                            cursor: 'col-resize',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <div style={{
                            width: 1,
                            height: '100%',
                            minHeight: 32,
                            backgroundColor: 'hsl(30 3.3% 11.8% / 10%)',
                            borderRadius: 1,
                          }} />
                        </div>

                        <div style={{ flex: `0 0 calc(${100 - fieldSplitPct}% - 4px)`, minWidth: 0, position: 'relative' }}>
                          {paramsFades.top && <div className="pointer-events-none absolute top-0 left-0 right-0 h-4 z-10 bg-gradient-to-b from-white to-transparent" />}
                          {paramsFades.bottom && <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-4 z-10 bg-gradient-to-t from-white to-transparent" />}
                          <div ref={paramsScrollRef} style={{ overflow: 'auto', height: '100%', paddingLeft: 8 }}>
                            <ParametersForm
                              params={displayedEndpoint.required_params}
                              formParams={formParams}
                              onSetFormParams={someExistHomogeneous ? handleParamsChange : setFormParams}
                              ticker={selectedObjects[0]?.symbol}
                              isUwSource={displayedEndpoint.source === 'unusualwhales'}
                              uwExpirations={endpoints.uwExpirations}
                              uwExpirationsLoading={endpoints.uwExpirationsLoading}
                              onFetchUwExpirations={endpoints.fetchUwExpirations}
                            />
                          </div>
                        </div>
                      </>
                    ) : (
                      <div style={{ flex: 1, minWidth: 0, position: 'relative' }}>
                        {fieldsFades.top && <div className="pointer-events-none absolute top-0 left-0 right-0 h-4 z-10 bg-gradient-to-b from-white to-transparent" />}
                        {fieldsFades.bottom && <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-4 z-10 bg-gradient-to-t from-white to-transparent" />}
                        <div ref={fieldsScrollRef} style={{ overflow: 'auto', height: '100%' }}>
                          <FieldSelector
                            fields={displayedEndpoint.fields}
                            selectedFields={selectedFields}
                            onFieldToggle={handleFieldToggle}
                            onSelectAll={handleSelectAll}
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Static bottom — field count */}
                  <div
                    className="px-4 py-2 flex-shrink-0"
                    style={{ borderTop: '0.5px solid hsl(30 3.3% 11.8% / 10%)', background: 'hsl(30 3.3% 11.8% / 3%)' }}
                  >
                    <span style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 40%)' }}>
                      {selectedFields.length} field{selectedFields.length !== 1 ? 's' : ''} selected
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

          {/* HETEROGENEOUS MODE */}
          {endpointSelectionMode === 'heterogeneous' && (
            <div className="flex-1 flex flex-col min-h-0 overflow-hidden" style={{ fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif" }}>
              <div className="flex-1 flex flex-col min-h-0">
                {uniqueObjectTypes.map(objType => {
                  const typeEndpoints = endpoints.endpointsByType[objType] || [];
                  const typeSourceFilter = endpoints.sourceFilterByType[objType] || 'all';
                  const filteredTypeEndpoints = typeSourceFilter === 'all'
                    ? typeEndpoints
                    : typeEndpoints.filter(ep => ep.source === typeSourceFilter);
                  const typeCategories = groupEndpointsByCategory(filteredTypeEndpoints);
                  const expandedCats = expandedCategoriesByType[objType] || new Set();
                  const selectedEp = selectedEndpointByType[objType];
                  const typeSymbols = getSymbolsForType(objType);
                  const fields = fieldsByType[objType] || [];
                  const params = paramsByType[objType] || {};
                  const isExisting = selectedEp ? existingDatasets.some(d => d.endpoint === selectedEp.endpoint) : false;
                  const typeEndpointsBySource = endpoints.endpointsBySourceByType[objType] || { all: 0, fmp: 0, polygon: 0, uw: 0 };

                  return (
                    <div
                      key={objType}
                      className="flex-1 flex flex-col min-h-0"
                      style={{ borderBottom: '0.5px solid hsl(30 3.3% 11.8% / 10%)' }}
                    >
                      {/* Type header */}
                      <div
                        className="flex-shrink-0"
                        style={{
                          padding: '0.75rem 1rem',
                          borderBottom: '0.5px solid hsl(30 3.3% 11.8% / 10%)',
                          background: 'hsl(30 3.3% 11.8% / 3%)',
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span style={{ fontSize: '0.688rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.02em', color: 'hsl(60 2.5% 23.3% / 75%)' }}>
                              {objType}
                            </span>
                            <span style={{ fontSize: '0.563rem', color: 'hsl(60 2.5% 23.3% / 35%)' }}>
                              ({typeSymbols.join(', ')})
                            </span>
                          </div>
                          {selectedEp ? (
                            <button
                              onClick={() => setSelectedEndpointByType({ ...selectedEndpointByType, [objType]: null })}
                              style={{
                                fontSize: '0.625rem',
                                fontFamily: "'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace",
                                color: 'hsl(60 2.5% 23.3% / 60%)',
                                backgroundColor: 'hsl(30 3.3% 11.8% / 6%)',
                                padding: '0.125rem 0.375rem',
                                borderRadius: '0.25rem',
                                border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.25rem',
                              }}
                            >
                              {selectedEp.endpoint}
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          ) : (
                            <SourceFilter
                              sourceFilter={typeSourceFilter}
                              onSourceFilterChange={(filter) => endpoints.setSourceFilterByType({ ...endpoints.sourceFilterByType, [objType]: filter })}
                              endpointsBySource={typeEndpointsBySource}
                            />
                          )}
                        </div>
                      </div>

                      {!selectedEp ? (
                        <div className="flex-1 min-h-0 flex flex-col">
                          <EndpointBrowser
                            loading={endpoints.loading}
                            endpointsByCategory={typeCategories}
                            expandedCategories={expandedCats}
                            onToggleCategory={(cat) => toggleCategoryForType(objType, cat)}
                            selectedEndpoint={selectedEp}
                            onEndpointSelect={(ep) => handleEndpointSelectForType(objType, ep)}
                            emptyMessage={`No endpoints available for ${objType}`}
                            addedEndpoints={addedEndpoints}
                          />
                        </div>
                      ) : (
                        <div className="flex-1 min-h-0 relative" style={{ backgroundColor: '#fff' }}>
                          {hetFieldFades.top && <div className="pointer-events-none absolute top-0 left-0 right-0 h-6 z-10 bg-gradient-to-b from-white to-transparent" />}
                          {hetFieldFades.bottom && <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 z-10 bg-gradient-to-t from-white to-transparent" />}
                          <div ref={hetFieldRef} className="h-full overflow-y-auto" style={{ padding: '0.75rem 1rem' }}>
                            <div className="flex gap-4">
                              <div className="flex-1 min-w-0">
                                <FieldSelector
                                  fields={selectedEp.fields}
                                  selectedFields={fields}
                                  onFieldToggle={(f) => handleFieldToggleForType(objType, f)}
                                  onSelectAll={() => handleSelectAllForType(objType)}
                                />
                              </div>

                              {selectedEp.required_params.length > 0 && (
                                <div className="flex-1 min-w-0" style={{ paddingLeft: '1rem', borderLeft: '0.5px solid hsl(30 3.3% 11.8% / 10%)' }}>
                                  <ParametersForm
                                    params={selectedEp.required_params}
                                    formParams={params}
                                    onSetFormParams={(p) => isExisting
                                      ? handleParamsChangeForType(objType, p)
                                      : setParamsByType({ ...paramsByType, [objType]: p })
                                    }
                                    ticker={selectedObjects.find(o => o.objectType === objType)?.symbol}
                                    isUwSource={selectedEp.source === 'unusualwhales'}
                                    uwExpirations={endpoints.uwExpirations}
                                    uwExpirationsLoading={endpoints.uwExpirationsLoading}
                                    onFetchUwExpirations={endpoints.fetchUwExpirations}
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Mixed granularity warning + selector */}
              {endpoints.hasMixedGranularity && endpoints.granularitiesDetected.length > 1 && (
                <div className="flex-shrink-0 mx-2 my-1">
                  <GranularitySelector
                    granularitiesDetected={endpoints.granularitiesDetected as Granularity[]}
                    selectedGranularity={endpoints.targetGranularity}
                    onChange={endpoints.setTargetGranularity}
                  />
                </div>
              )}

              {/* Join strategy indicator */}
              {endpoints.joinStrategy && !endpoints.hasIncompatibleStructures && (
                <div
                  className="flex-shrink-0 mx-4 my-1 flex items-center gap-1.5"
                  style={{
                    padding: '0.5rem',
                    borderRadius: '0.375rem',
                    fontSize: '0.625rem',
                    backgroundColor: endpoints.joinStrategy.strategy === 'incompatible'
                      ? 'hsl(0 70% 97%)'
                      : endpoints.joinStrategy.needs_aggregation
                      ? 'hsl(40 70% 97%)'
                      : 'hsl(30 3.3% 11.8% / 3%)',
                    color: endpoints.joinStrategy.strategy === 'incompatible'
                      ? 'hsl(0 60% 45%)'
                      : endpoints.joinStrategy.needs_aggregation
                      ? 'hsl(40 60% 40%)'
                      : 'hsl(60 2.5% 23.3% / 50%)',
                  }}
                >
                  {endpoints.joinStrategy.strategy === 'snapshot_stack' && '✓ Snapshot data — will stack by symbol'}
                  {endpoints.joinStrategy.strategy === 'incompatible' && '✗ Cannot join these endpoints'}
                  {endpoints.joinStrategy.needs_aggregation && endpoints.targetGranularity &&
                    `⚙ Will aggregate to ${endpoints.targetGranularity}`}
                  {!endpoints.joinStrategy.needs_aggregation && endpoints.joinStrategy.strategy !== 'snapshot_stack' && endpoints.joinStrategy.strategy !== 'incompatible' &&
                    `✓ Joinable${endpoints.joinStrategy.common_time_key ? ` on ${endpoints.joinStrategy.common_time_key}` : ''}`}
                </div>
              )}

              {/* Structure type incompatibility warning */}
              {endpoints.hasIncompatibleStructures && endpoints.incompatiblePairs.length > 0 && (
                <div
                  className="flex-shrink-0 mx-4 my-2 flex items-start gap-2"
                  style={{
                    padding: '0.5rem',
                    backgroundColor: 'hsl(0 70% 97%)',
                    border: '0.5px solid hsl(0 60% 80%)',
                    borderRadius: '0.375rem',
                    fontSize: '0.688rem',
                    color: 'hsl(0 60% 40%)',
                  }}
                >
                  <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>Cannot join snapshot + time-series endpoints</span>
                </div>
              )}

              {/* Footer */}
              <div
                className="flex-shrink-0"
                style={{
                  padding: '0.5rem 1rem',
                  borderTop: '0.5px solid hsl(30 3.3% 11.8% / 10%)',
                  background: 'hsl(30 3.3% 11.8% / 3%)',
                }}
              >
                {groups.allCombosExistHeterogeneous && allTypesReady && !endpoints.hasIncompatibleStructures ? (
                  <span style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 40%)' }}>
                    {uniqueObjectTypes.filter(t => fieldsByType[t]?.length > 0).length}/{uniqueObjectTypes.length} types configured
                  </span>
                ) : allTypesReady && !endpoints.hasIncompatibleStructures ? (
                  <button
                    onClick={groups.handleAdd}
                    disabled={groups.adding}
                    style={{
                      width: '100%',
                      padding: '0.5rem 1rem',
                      fontSize: '0.688rem',
                      fontWeight: 500,
                      borderRadius: '0.375rem',
                      border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
                      backgroundColor: 'hsl(30 3.3% 11.8% / 8%)',
                      color: 'hsl(60 2.5% 23.3%)',
                      cursor: 'pointer',
                    }}
                  >
                    {groups.adding ? 'Adding...' : 'Add to Workspace'}
                  </button>
                ) : (
                  <div style={{ fontSize: '0.625rem', color: 'hsl(60 2.5% 23.3% / 35%)', textAlign: 'center' }}>
                    {allTypesHaveEndpoints
                      ? `Select fields for each type (${uniqueObjectTypes.filter(t => (fieldsByType[t]?.length || 0) > 0).length}/${uniqueObjectTypes.length} ready)`
                      : `Select an endpoint for each type (${uniqueObjectTypes.filter(t => selectedEndpointByType[t]).length}/${uniqueObjectTypes.length})`
                    }
                  </div>
                )}
              </div>
            </div>
          )}
        </div>}
    </div>
  );
}

export default AddDataSidebar;
