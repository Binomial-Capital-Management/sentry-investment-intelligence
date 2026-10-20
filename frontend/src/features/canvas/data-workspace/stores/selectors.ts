/**
 * Data Workspace Store Selectors
 * 
 * Derived state selectors that read from the single source of truth (tabs array).
 * These replace direct access to flat state (datasets, selectedObjects, selectedFields).
 * 
 * Usage:
 *   import { useDataWorkspaceStore, selectDatasets } from '../stores/dataWorkspaceStore';
 *   const datasets = useDataWorkspaceStore(selectDatasets);
 */

import type {
  DatasetConfig,
  DatasetGroup,
  SelectedObject,
  WorkspaceTab,
  TabMode,
  PivotConfig,
  ChartConfig,
  SingleObjectFormState,
  MultiObjectFormState,
  AddDatasetPanelState,
  TabFormState,
  ToolTabState,
  PerToolState,
} from './types';
import type { EndpointInfo, FormMode } from '@/features/canvas/types';

// Type for the store state (no more flat state - tabs are the source of truth)
interface StoreState {
  tabs: WorkspaceTab[];
  activeTabId: string | null;
}

// ============================================================================
// DEPRECATION TRACKING
// ============================================================================

const deprecationWarnings = new Set<string>();

function warnDeprecated(selectorName: string, replacement: string): void {
  if (process.env.NODE_ENV === 'development' && !deprecationWarnings.has(selectorName)) {
    deprecationWarnings.add(selectorName);
    console.warn(
      `[DataWorkspaceStore] Deprecated: Direct access to "${selectorName}" is deprecated. ` +
      `Use "${replacement}" selector instead. This will be removed in the next major version.`
    );
  }
}

// ============================================================================
// PRIMARY SELECTORS (Use These)
// ============================================================================

/**
 * Get the currently active tab
 */
export const selectActiveTab = (s: StoreState): WorkspaceTab | null =>
  s.tabs.find(t => t.id === s.activeTabId) ?? null;

/**
 * Get datasets from the active tab (replaces s.datasets)
 */
export const selectDatasets = (s: StoreState): DatasetConfig[] =>
  selectActiveTab(s)?.datasets ?? [];

/**
 * Get symbols from the active tab (replaces s.selectedObjects)
 */
export const selectSymbols = (s: StoreState): SelectedObject[] =>
  selectActiveTab(s)?.symbols ?? [];

/**
 * Assemble the current tool's state for a tab: combines tab.currentToolId with
 * the matching perToolState slice. Returns undefined when the tab has no tool
 * state initialized or no tool is currently selected.
 */
export const selectCurrentToolState = (tab: WorkspaceTab | null | undefined): ToolTabState | undefined => {
  if (!tab?.currentToolId) return undefined;
  const slice = tab.perToolState?.[tab.currentToolId];
  if (!slice) return undefined;
  return { toolId: tab.currentToolId, ...slice };
};

/**
 * Get the per-tool slice for a specific toolId on a tab (no toolId pointer).
 */
export const selectPerToolState = (tab: WorkspaceTab | null | undefined, toolId: string): PerToolState | undefined =>
  tab?.perToolState?.[toolId];

/**
 * Get fields derived from active tab's datasets (replaces s.selectedFields)
 */
export const selectFields = (s: StoreState): string[] =>
  selectDatasets(s).flatMap(d => d.fields);

/**
 * Get the active tab's mode
 */
export const selectTabMode = (s: StoreState): TabMode =>
  selectActiveTab(s)?.mode ?? 'empty';

/**
 * Check if form is currently visible
 */
export const selectIsFormMode = (s: StoreState): boolean =>
  selectTabMode(s) === 'form';

/**
 * Get active tab's type
 */
export const selectTabType = (s: StoreState): WorkspaceTab['type'] | null =>
  selectActiveTab(s)?.type ?? null;

/**
 * Get all tabs
 */
export const selectTabs = (s: StoreState): WorkspaceTab[] => s.tabs;

/**
 * Get active tab ID
 */
export const selectActiveTabId = (s: StoreState): string | null => s.activeTabId;

// ============================================================================
// DEPRECATED SELECTORS (For Migration Tracking)
// These now read from active tab but still warn - remove in next major version
// ============================================================================

/**
 * @deprecated Use selectDatasets instead
 */
export const selectDatasetsDeprecated = (s: StoreState): DatasetConfig[] => {
  warnDeprecated('s.datasets', 'selectDatasets');
  return selectDatasets(s);
};

/**
 * @deprecated Use selectSymbols instead
 */
export const selectSymbolsDeprecated = (s: StoreState): SelectedObject[] => {
  warnDeprecated('s.selectedObjects', 'selectSymbols');
  return selectSymbols(s);
};

/**
 * @deprecated Use selectFields instead
 */
export const selectFieldsDeprecated = (s: StoreState): string[] => {
  warnDeprecated('s.selectedFields', 'selectFields');
  return selectFields(s);
};

// ============================================================================
// COMPUTED SELECTORS
// ============================================================================

/**
 * Get unique symbols from datasets
 */
export const selectUniqueSymbols = (s: StoreState): string[] =>
  [...new Set(selectDatasets(s).map(d => d.symbol))];

/**
 * Get dataset count
 */
export const selectDatasetCount = (s: StoreState): number =>
  selectDatasets(s).length;

/**
 * Check if workspace has any data
 */
export const selectHasData = (s: StoreState): boolean =>
  selectDatasetCount(s) > 0;

/**
 * Get tab by ID
 */
export const selectTabById = (tabId: string) => (s: StoreState): WorkspaceTab | null =>
  s.tabs.find(t => t.id === tabId) ?? null;

/**
 * Get pivot config for a tab
 */
export const selectPivotConfig = (tabId: string) => (s: StoreState): PivotConfig | null =>
  s.tabs.find(t => t.id === tabId)?.pivotConfig ?? null;

/**
 * Get chart config for a tab
 */
export const selectChartConfig = (tabId: string) => (s: StoreState): ChartConfig | null =>
  s.tabs.find(t => t.id === tabId)?.chartConfig ?? null;

/**
 * Get form state for a tab
 */
export const selectFormState = (tabId: string) => (s: StoreState) =>
  s.tabs.find(t => t.id === tabId)?.formState;

/**
 * Check if active tab is a specific type
 */
export const selectIsTabType = (type: WorkspaceTab['type']) => (s: StoreState): boolean =>
  selectTabType(s) === type;

/**
 * Get datasets for a specific tab (not just active)
 */
export const selectDatasetsForTab = (tabId: string) => (s: StoreState): DatasetConfig[] =>
  s.tabs.find(t => t.id === tabId)?.datasets ?? [];

/**
 * Get symbols for a specific tab (not just active)
 */
export const selectSymbolsForTab = (tabId: string) => (s: StoreState): SelectedObject[] =>
  s.tabs.find(t => t.id === tabId)?.symbols ?? [];

// ============================================================================
// FORM STATE SELECTORS
// ============================================================================

/**
 * Get the active tab's form state
 */
export const selectActiveFormState = (s: StoreState): TabFormState | undefined =>
  selectActiveTab(s)?.formState;

/**
 * Get single object form state from active tab
 */
export const selectSingleFormState = (s: StoreState): SingleObjectFormState | undefined =>
  selectActiveTab(s)?.formState?.single;

/**
 * Get multi object form state from active tab
 */
export const selectMultiFormState = (s: StoreState): MultiObjectFormState | undefined =>
  selectActiveTab(s)?.formState?.multi;

// ============================================================================
// SINGLE FORM FIELD SELECTORS
// ============================================================================

export const selectFormMode = (s: StoreState): FormMode =>
  selectSingleFormState(s)?.formMode ?? 'symbol';

export const selectFormSelectedSymbol = (s: StoreState): { symbol: string; name: string; objectType: string } | null =>
  selectSingleFormState(s)?.formSelectedSymbol ?? null;

export const selectFormCustomIdentifier = (s: StoreState): string =>
  selectSingleFormState(s)?.formCustomIdentifier ?? '';

export const selectFormSelectedEndpoint = (s: StoreState): EndpointInfo | null =>
  selectSingleFormState(s)?.formSelectedEndpoint ?? null;

export const selectFormSelectedFields = (s: StoreState): string[] =>
  selectSingleFormState(s)?.formSelectedFields ?? [];

export const selectFormParams = (s: StoreState): Record<string, string> =>
  selectSingleFormState(s)?.formParams ?? {};

export const selectFormExpandedCategories = (s: StoreState): string[] =>
  selectSingleFormState(s)?.formExpandedCategories ?? [];

export const selectFormSourceFilter = (s: StoreState): string =>
  selectSingleFormState(s)?.formSourceFilter ?? 'all';

// ============================================================================
// MULTI FORM FIELD SELECTORS  
// ============================================================================

export const selectMultiSelectedSymbols = (s: StoreState): Array<{ symbol: string; name: string; objectType: string }> =>
  selectMultiFormState(s)?.selectedSymbols ?? [];

export const selectMultiSearchMode = (s: StoreState): 'symbol' | 'forex' | 'crypto' =>
  selectMultiFormState(s)?.searchMode ?? 'symbol';

export const selectMultiEndpointSelectionMode = (s: StoreState): 'homogeneous' | 'heterogeneous' =>
  selectMultiFormState(s)?.endpointSelectionMode ?? 'homogeneous';

export const selectMultiSelectedEndpoint = (s: StoreState): EndpointInfo | null =>
  selectMultiFormState(s)?.selectedEndpoint ?? null;

export const selectMultiSelectedFields = (s: StoreState): string[] =>
  selectMultiFormState(s)?.selectedFields ?? [];

export const selectMultiFormParams = (s: StoreState): Record<string, string> =>
  selectMultiFormState(s)?.formParams ?? {};

export const selectMultiExpandedCategories = (s: StoreState): string[] =>
  selectMultiFormState(s)?.expandedCategories ?? [];

export const selectMultiSourceFilter = (s: StoreState): string =>
  selectMultiFormState(s)?.sourceFilter ?? 'all';

export const selectMultiEndpointByType = (s: StoreState): Record<string, any> =>
  selectMultiFormState(s)?.endpointByType ?? {};

export const selectMultiFieldsByType = (s: StoreState): Record<string, string[]> =>
  selectMultiFormState(s)?.fieldsByType ?? {};

export const selectMultiParamsByType = (s: StoreState): Record<string, Record<string, string>> =>
  selectMultiFormState(s)?.paramsByType ?? {};

export const selectMultiExpandedCategoriesByType = (s: StoreState): Record<string, string[]> =>
  selectMultiFormState(s)?.expandedCategoriesByType ?? {};

export const selectMultiSourceFilterByType = (s: StoreState): Record<string, string> =>
  selectMultiFormState(s)?.sourceFilterByType ?? {};

export const selectMultiTargetGranularity = (s: StoreState): string | undefined =>
  selectMultiFormState(s)?.targetGranularity;

// ============================================================================
// ADD DATASET PANEL SELECTORS
// ============================================================================

/**
 * Get AddDatasetPanel state from active tab
 */
export const selectAddDataPanelState = (s: StoreState): AddDatasetPanelState | undefined =>
  selectActiveTab(s) ? selectActiveTab(s)?.formState?.addDataPanel : s.globalAddDataPanel;

export const selectAddDataPanelEndpointMode = (s: StoreState): 'homogeneous' | 'heterogeneous' =>
  selectAddDataPanelState(s)?.endpointSelectionMode ?? 'homogeneous';

export const selectAddDataPanelSourceFilter = (s: StoreState): string =>
  selectAddDataPanelState(s)?.sourceFilter ?? 'all';

// Homogeneous mode selectors
export const selectAddDataPanelSelectedEndpoint = (s: StoreState): EndpointInfo | null =>
  selectAddDataPanelState(s)?.selectedEndpoint ?? null;

export const selectAddDataPanelSelectedFields = (s: StoreState): string[] =>
  selectAddDataPanelState(s)?.selectedFields ?? [];

export const selectAddDataPanelFormParams = (s: StoreState): Record<string, string> =>
  selectAddDataPanelState(s)?.formParams ?? {};

export const selectAddDataPanelExpandedCategories = (s: StoreState): string[] =>
  selectAddDataPanelState(s)?.expandedCategories ?? [];

// Heterogeneous mode selectors
export const selectAddDataPanelSelectedEndpointByType = (s: StoreState): Record<string, EndpointInfo | null> =>
  selectAddDataPanelState(s)?.selectedEndpointByType ?? {};

export const selectAddDataPanelFieldsByType = (s: StoreState): Record<string, string[]> =>
  selectAddDataPanelState(s)?.fieldsByType ?? {};

export const selectAddDataPanelParamsByType = (s: StoreState): Record<string, Record<string, string>> =>
  selectAddDataPanelState(s)?.paramsByType ?? {};

export const selectAddDataPanelExpandedCategoriesByType = (s: StoreState): Record<string, string[]> =>
  selectAddDataPanelState(s)?.expandedCategoriesByType ?? {};

// Scroll position selector
export const selectAddDataPanelScrollPosition = (s: StoreState): number =>
  selectAddDataPanelState(s)?.scrollPosition ?? 0;

// Sidebar symbol selection selectors
export const selectAddDataPanelFormMode = (s: StoreState) =>
  selectAddDataPanelState(s)?.sidebarFormMode ?? 'symbol';

export const selectAddDataPanelSelectedSymbol = (s: StoreState) =>
  selectAddDataPanelState(s)?.sidebarSelectedSymbol ?? null;

export const selectAddDataPanelCustomIdentifier = (s: StoreState): string =>
  selectAddDataPanelState(s)?.sidebarCustomIdentifier ?? '';

// ============================================================================
// DATASET GROUP SELECTORS
// ============================================================================

/**
 * Get all dataset groups from the active tab
 */
export const selectDatasetGroups = (s: StoreState): DatasetGroup[] =>
  selectActiveTab(s)?.datasetGroups ?? [];

/**
 * Get the active group ID (Sources-mode "Add to" pointer)
 */
export const selectActiveGroupId = (s: StoreState): string | null =>
  selectActiveTab(s)?.activeGroupId ?? null;

/**
 * Get the active group ID for Analysis mode. Falls back to the Sources-mode
 * pointer when Analysis has never been set, so the first analysis lands in a
 * predictable place instead of going ungrouped.
 */
export const selectActiveAnalysisGroupId = (s: StoreState): string | null => {
  const tab = selectActiveTab(s);
  return tab?.activeAnalysisGroupId ?? tab?.activeGroupId ?? null;
};

/**
 * Get the active group ID for Pivot mode. Falls back to the Sources-mode
 * pointer when Pivot has never been set, so pivots nest naturally alongside
 * their source datasets (matches Analysis behavior).
 */
export const selectActivePivotGroupId = (s: StoreState): string | null => {
  const tab = selectActiveTab(s);
  return tab?.activePivotGroupId ?? tab?.activeGroupId ?? null;
};

export const selectActiveChartGroupId = (s: StoreState): string | null => {
  const tab = selectActiveTab(s);
  return tab?.activeChartGroupId ?? tab?.activeGroupId ?? null;
};

/**
 * Get the currently active dataset group
 */
export const selectActiveGroup = (s: StoreState): DatasetGroup | null => {
  const tab = selectActiveTab(s);
  if (!tab?.datasetGroups || !tab.activeGroupId) return null;
  return tab.datasetGroups.find(g => g.id === tab.activeGroupId) ?? null;
};

/**
 * Get merged dataset IDs from the active tab
 */
export const selectMergedDatasetIds = (s: StoreState): string[] =>
  selectActiveTab(s)?.mergedDatasetIds ?? [];

export const selectMergeAnchorDatasetId = (s: StoreState): string | undefined =>
  selectActiveTab(s)?.mergeAnchorDatasetId;

/**
 * Get the active dataset ID being viewed in the paginated data view
 */
export const selectActiveDatasetId = (s: StoreState): string | undefined =>
  selectActiveTab(s)?.activeDatasetId;

/**
 * Get datasets belonging to the active group only
 * Falls back to all datasets if no groups are defined (backward compatibility)
 */
export const selectActiveGroupDatasets = (s: StoreState): DatasetConfig[] => {
  const tab = selectActiveTab(s);
  if (!tab) return [];
  
  const datasets = tab.datasets ?? [];
  const groups = tab.datasetGroups ?? [];
  
  // If no groups defined, return all datasets (backward compat)
  if (groups.length === 0) {
    return datasets;
  }
  
  // Return only datasets belonging to the active group
  const activeGroupId = tab.activeGroupId;
  if (!activeGroupId) return [];
  
  return datasets.filter(d => d.groupId === activeGroupId);
};

/**
 * Get dataset count for the active group
 */
export const selectActiveGroupDatasetCount = (s: StoreState): number =>
  selectActiveGroupDatasets(s).length;

/**
 * Get total dataset count across all groups
 */
export const selectTotalDatasetCount = (s: StoreState): number =>
  selectDatasets(s).length;

/**
 * Get dataset group count
 */
export const selectGroupCount = (s: StoreState): number =>
  selectDatasetGroups(s).length;

/**
 * Check if there are multiple groups (show group selector UI)
 */
export const selectHasMultipleGroups = (s: StoreState): boolean =>
  selectGroupCount(s) > 1;

/**
 * Get group by ID
 */
export const selectGroupById = (groupId: string) => (s: StoreState): DatasetGroup | null =>
  selectDatasetGroups(s).find(g => g.id === groupId) ?? null;

/**
 * Get datasets for a specific group
 */
export const selectDatasetsForGroup = (groupId: string) => (s: StoreState): DatasetConfig[] =>
  selectDatasets(s).filter(d => d.groupId === groupId);

/**
 * Get dataset count for a specific group
 */
export const selectDatasetCountForGroup = (groupId: string) => (s: StoreState): number =>
  selectDatasetsForGroup(groupId)(s).length;

/**
 * Get groups with their dataset, tool-result, and pivot-result counts (for UI display)
 */
export const selectGroupsWithCounts = (s: StoreState): Array<DatasetGroup & { datasetCount: number; toolResultCount: number; pivotResultCount: number; chartResultCount: number }> => {
  const groups = selectDatasetGroups(s);
  const datasets = selectDatasets(s);
  const tab = selectActiveTab(s);
  const allToolResults = tab
    ? Object.values(tab.perToolState ?? {}).flatMap(pts => pts.toolResults ?? [])
    : [];
  const allPivotResults = tab?.pivotResults ?? [];
  const allChartResults = tab?.chartResults ?? [];

  return groups.map(group => ({
    ...group,
    datasetCount: datasets.filter(d => d.groupId === group.id).length,
    toolResultCount: allToolResults.filter(r => r.groupId === group.id).length,
    pivotResultCount: allPivotResults.filter(r => r.groupId === group.id).length,
    chartResultCount: allChartResults.filter(r => r.groupId === group.id).length,
  }));
};

/**
 * Get unique endpoints in a group (for display)
 */
export const selectGroupEndpoints = (groupId: string) => (s: StoreState): string[] => {
  const datasets = selectDatasetsForGroup(groupId)(s);
  return [...new Set(datasets.map(d => d.endpoint))];
};

/**
 * Get unique symbols in a group (for display)
 */
export const selectGroupSymbols = (groupId: string) => (s: StoreState): string[] => {
  const datasets = selectDatasetsForGroup(groupId)(s);
  return [...new Set(datasets.map(d => d.symbol))];
};

// ============================================================================
// PERFORMANCE VALIDATION (Development Only)
// ============================================================================

/**
 * Helper to wrap a selector with performance monitoring.
 * Usage in tests or debugging:
 *   const monitoredSelect = createPerfMonitor('selectDatasets', selectDatasets);
 *   const datasets = useStore(monitoredSelect);
 */
export const createPerfMonitor = <T>(
  name: string,
  fn: (s: StoreState) => T,
  thresholdMs = 1
) => {
  return (s: StoreState): T => {
    if (process.env.NODE_ENV !== 'development') {
      return fn(s);
    }
    
    const start = performance.now();
    const result = fn(s);
    const duration = performance.now() - start;
    
    if (duration > thresholdMs) {
      console.warn(`[Perf] ${name} took ${duration.toFixed(2)}ms`);
    }
    
    return result;
  };
};
