/**
 * Data Workspace Store - Persists data explorer state across page refreshes
 * 
 * Uses Zustand with persist middleware to maintain:
 * - Workspace tabs (each tab is an isolated workflow context)
 * - Selected symbols
 * - Selected fields
 * - Object type filter
 * - Date range and other parameters
 * 
 * REFACTORED: Uses slices pattern for modularity. Types in types.ts, selectors in selectors.ts.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { API_BASE } from '@/services/api';

// Re-export all types for backward compatibility
export type {
  SelectedObject,
  FieldConfig,
  DatasetConfig,
  DatasetGroup,
  CompatibilityResult,
  PivotValueConfig,
  PivotConfig,
  ChartSeriesConfig,
  ChartFilter,
  OHLCFields,
  ChartType,
  ChartConfig,
  WorkspaceSheet,
  SingleObjectFormState,
  MultiObjectFormState,
  TabFormState,
  TabMode,
  TabType,
  WorkspaceViewMode,
  ContentViewType,
  WorkspaceTab,
  EndpointMetadata,
  ToolTabState,
  TabToolResult,
  TabPivotResult,
  TabChartResult,
} from './types';

import type { DatasetGroup } from './types';

// Import types for internal use
import type { EndpointMetadata } from './types';

// Import slices
import {
  createCoreSlice,
  createDefaultTab,
  type CoreSlice,
} from './slices/coreSlice';
import { createVisualizationSlice, type VisualizationSlice } from './slices/visualizationSlice';
import { createFormStateSlice, type FormStateSlice } from './slices/formStateSlice';

// API path for canvas data endpoints
const CANVAS_DATA_PATH = '/api/canvas/data';

export async function fetchEndpointMetadata(endpoint: string): Promise<EndpointMetadata> {
  try {
    const response = await fetch(`${API_BASE}${CANVAS_DATA_PATH}/compatibility/endpoint/${endpoint}`);
    if (!response.ok) throw new Error('Failed to fetch endpoint metadata');
    const data = await response.json();
    return {
      endpoint: data.endpoint,
      structureType: data.structure_type,
      compatibilityGroup: data.compatibility_group,
      timeKey: data.time_key,
      cardinality: data.cardinality,
    };
  } catch (error) {
    console.warn(`Could not fetch metadata for ${endpoint}:`, error);
    return {
      endpoint,
      structureType: 'unknown',
      compatibilityGroup: 'unknown',
      timeKey: null,
      cardinality: 'single',
    };
  }
}

export async function checkEndpointCompatibility(endpoints: string[]): Promise<{
  compatible: boolean;
  group?: string;
  groups?: string[];
  reason?: string;
}> {
  if (endpoints.length <= 1) {
    return { compatible: true };
  }
  try {
    const params = endpoints.map(e => `endpoints=${encodeURIComponent(e)}`).join('&');
    const response = await fetch(`${API_BASE}${CANVAS_DATA_PATH}/compatibility/check?${params}`);
    if (!response.ok) throw new Error('Failed to check compatibility');
    return await response.json();
  } catch (error) {
    console.warn('Compatibility check failed:', error);
    return { compatible: true }; // Fail open
  }
}

// ============================================================================
// COMBINED STORE TYPE
// ============================================================================

export type BoundStore = CoreSlice & VisualizationSlice & FormStateSlice;

// For backward compatibility, export as DataWorkspaceState
export type DataWorkspaceState = BoundStore;


// ============================================================================
// STORE IMPLEMENTATION
// ============================================================================

export const useDataWorkspaceStore = create<BoundStore>()(
  persist(
    (...a) => ({
      ...createCoreSlice(...a),
      ...createVisualizationSlice(...a),
      ...createFormStateSlice(...a),
    }),
    {
      name: 'binomial-data-workspace',
      version: 16, // v16 adds backendId to WorkspaceTab for per-tab persistence
      
      // Migrate old localStorage data to new schema
      migrate: (persistedState: any, version: number) => {
        let state = persistedState;
        
        if (version < 2) {
          // Old data doesn't have tabs - create a default tab with existing datasets
          const newDefaultTab = createDefaultTab();
          if (state.datasets && state.datasets.length > 0) {
            newDefaultTab.datasets = state.datasets;
            newDefaultTab.symbols = state.selectedObjects || [];
            newDefaultTab.name = 'Tab 1';
          }
          state = {
            ...state,
            tabs: [newDefaultTab],
            activeTabId: newDefaultTab.id,
          };
        }
        
        if (version < 4) {
          // Migrate tabs with sheets to flat datasets on tab
          const migratedTabs = (state.tabs || []).map((tab: any) => {
            if (tab.sheets && tab.sheets.length > 0) {
              const activeSheet = tab.sheets.find((s: any) => s.id === tab.activeSheetId) || tab.sheets[0];
              const datasets = activeSheet?.datasets || [];
              const { sheets, activeSheetId, primaryCompatibilityGroup, ...rest } = tab;
              return { ...rest, datasets };
            }
            return { ...tab, datasets: tab.datasets || [] };
          });
          
          const { activeSheetId, ...restState } = state;
          state = { ...restState, tabs: migratedTabs };
        }
        
        if (version < 5) {
          // Add 'mode' field to tabs
          const migratedTabs = (state.tabs || []).map((tab: any) => ({
            ...tab,
            mode: (tab.datasets && tab.datasets.length > 0) ? 'data' : 'empty',
          }));
          state = { ...state, tabs: migratedTabs };
        }
        
        // v6 adds chart support + form state
        // v7 adds slices pattern - flat state is now deprecated but still persisted for backward compat
        
        if (version < 7) {
          // Ensure tabs have all required fields
          const migratedTabs = (state.tabs || []).map((tab: any) => ({
            ...tab,
            mode: tab.mode || (tab.datasets?.length > 0 ? 'data' : 'empty'),
            datasets: tab.datasets || [],
            symbols: tab.symbols || [],
          }));
          state = { ...state, tabs: migratedTabs };
        }
        
        if (version < 8) {
          // v8: Migrate existing datasets to dataset groups
          // For each tab with datasets but no groups, create a default group
          const migratedTabs = (state.tabs || []).map((tab: any) => {
            const datasets = tab.datasets || [];
            const hasGroups = tab.datasetGroups && tab.datasetGroups.length > 0;
            
            // Skip if no datasets or already has groups
            if (datasets.length === 0 || hasGroups) {
              return tab;
            }
            
            // Create a default group for existing datasets
            const defaultGroupId = `group-migrated-${Date.now()}`;
            const defaultGroup: DatasetGroup = {
              id: defaultGroupId,
              name: 'Data',
              createdAt: Date.now(),
            };
            
            // Assign all existing datasets to the default group
            const migratedDatasets = datasets.map((d: any) => ({
              ...d,
              groupId: d.groupId || defaultGroupId,
            }));
            
            return {
              ...tab,
              datasets: migratedDatasets,
              datasetGroups: [defaultGroup],
              activeGroupId: defaultGroupId,
            };
          });
          state = { ...state, tabs: migratedTabs };
        }
        
        if (version < 9) {
          // v9: previously added origin field (removed) — strip it
          const migratedTabs = (state.tabs || []).map((tab: any) => {
            const { origin: _, ...rest } = tab;
            return rest;
          });
          state = { ...state, tabs: migratedTabs };
        }

        // v10: Add tool tab type - no migration needed (existing workspaces have no tool tabs)

        if (version < 11) {
          // v11: Add viewMode for unified workspace tabs
          const migratedTabs = (state.tabs || []).map((tab: any) => {
            if (tab.viewMode) return tab;
            let viewMode: string;
            switch (tab.type) {
              case 'tool': viewMode = 'tools'; break;
              case 'pivot': viewMode = 'pivot'; break;
              case 'chart': viewMode = 'chart'; break;
              default: viewMode = 'explorer'; break;
            }
            return { ...tab, viewMode };
          });
          state = { ...state, tabs: migratedTabs };
        }

        if (version < 12) {
          // v12: Add contentView for independent middle panel state
          const migratedTabs = (state.tabs || []).map((tab: any) => ({
            ...tab,
            contentView: tab.contentView ?? { type: 'data' },
          }));
          state = { ...state, tabs: migratedTabs };
        }

        if (version < 13) {
          // v13: tool-result contentView now requires toolTabId — reset any stale entries
          const migratedTabs = (state.tabs || []).map((tab: any) => ({
            ...tab,
            contentView: tab.contentView?.type === 'tool-result' && !tab.contentView.toolTabId
              ? { type: 'data' }
              : tab.contentView,
          }));
          state = { ...state, tabs: migratedTabs };
        }

        if (version < 14) {
          // v14: ToolTabState migrates from scalar toolResult to toolResults array
          const migratedTabs = (state.tabs || []).map((tab: any) => {
            if (!tab.toolState) return tab;
            const ts = tab.toolState;
            // Already migrated
            if (Array.isArray(ts.toolResults)) return tab;
            let toolResults: TabToolResult[] = [];
            let activeResultId: string | null = null;
            if (ts.toolResult != null) {
              const localId = `migrated-${tab.id}`;
              toolResults = [{
                localId,
                result: ts.toolResult,
                toolId: ts.toolId || '',
                processName: ts.processName || '',
                processId: ts.currentProcessId ?? null,
                tickers: ts.manualTickers
                  ? ts.manualTickers.split(',').map((s: string) => s.trim()).filter(Boolean)
                  : (ts.toolResult.tickers || []),
                activeChart: ts.activeChart || 'stats',
              }];
              activeResultId = localId;
            }
            const { toolResult, currentProcessId, processName, activeChart, ...rest } = ts;
            return {
              ...tab,
              toolState: { ...rest, toolResults, activeResultId },
              // Reset contentView if it was pointing at old-style tool-result without resultLocalId
              contentView: tab.contentView?.type === 'tool-result' && !tab.contentView.resultLocalId
                ? activeResultId
                  ? { type: 'tool-result', toolTabId: tab.id, resultLocalId: activeResultId }
                  : { type: 'data' }
                : tab.contentView,
            };
          });
          state = { ...state, tabs: migratedTabs };
        }

        if (version < 15) {
          // v15: split tab.toolState into tab.currentToolId + tab.perToolState keyed by toolId
          const migratedTabs = (state.tabs || []).map((tab: any) => {
            const { toolState, ...rest } = tab;
            if (!toolState) return tab;
            const { toolId = '', ...perTool } = toolState;
            return {
              ...rest,
              currentToolId: toolId,
              perToolState: toolId ? { [toolId]: perTool } : {},
            };
          });
          state = { ...state, tabs: migratedTabs };
        }

        // Initialize tabs array if undefined
        if (!state.tabs) {
          state = { ...state, tabs: [], activeTabId: null };
        }
        
        // Ensure activeTabId is valid
        if (state.tabs?.length > 0 && !state.activeTabId) {
          state = { ...state, activeTabId: state.tabs[0].id };
        }
        
        return state;
      },
      
      // Persist tabs and settings only - tabs are the single source of truth
      partialize: (state) => ({
        tabs: state.tabs.map(tab => ({
          ...tab,
          perToolState: tab.perToolState
            ? Object.fromEntries(
                Object.entries(tab.perToolState).map(([toolId, pts]) => [
                  toolId,
                  {
                    ...pts,
                    toolResults: pts.toolResults?.map(tr => ({
                      ...tr,
                      result: { id: tr.result?.id, name: tr.result?.name, tool_id: tr.result?.tool_id },
                    })) ?? [],
                  },
                ]),
              )
            : undefined,
        })),
        activeTabId: state.activeTabId,
        objectTypeFilter: state.objectTypeFilter,
        dateFrom: state.dateFrom,
        dateTo: state.dateTo,
        period: state.period,
        limit: state.limit,
        fieldPickerOpen: state.fieldPickerOpen,
        sidebarViewMode: state.sidebarViewMode,
        lastUpdated: state.lastUpdated,
      }),
      
      // Ensure valid state after rehydration
      onRehydrateStorage: () => (state) => {
        if (state) {
          let { tabs, activeTabId } = state;
          let needsUpdate = false;
          
          // Initialize empty array if undefined
          if (!tabs) {
            tabs = [];
            activeTabId = null;
            needsUpdate = true;
          }
          
          // Clear activeTabId if no tabs exist
          if (tabs.length === 0 && activeTabId !== null) {
            activeTabId = null;
            needsUpdate = true;
          }
          
          // Ensure activeTabId points to a valid tab
          if (tabs.length > 0 && (!activeTabId || !tabs.find(t => t.id === activeTabId))) {
            activeTabId = tabs[0].id;
            needsUpdate = true;
          }
          
          // Ensure tabs with datasets have groups set up
          tabs = tabs.map(tab => {
            const datasets = tab.datasets || [];
            const hasGroups = tab.datasetGroups && tab.datasetGroups.length > 0;
            
            // Create default group if datasets exist but no groups
            if (datasets.length > 0 && !hasGroups) {
              needsUpdate = true;
              const defaultGroupId = `group-rehydrate-${Date.now()}-${Math.random().toString(36).slice(2)}`;
              const defaultGroup: DatasetGroup = {
                id: defaultGroupId,
                name: 'Data',
                createdAt: Date.now(),
              };
              
              return {
                ...tab,
                datasets: datasets.map(d => ({ ...d, groupId: d.groupId || defaultGroupId })),
                datasetGroups: [defaultGroup],
                activeGroupId: defaultGroupId,
              };
            }
            
            // Ensure activeGroupId is valid if groups exist
            if (hasGroups && !tab.activeGroupId) {
              needsUpdate = true;
              return { ...tab, activeGroupId: tab.datasetGroups![0].id };
            }

            // Ensure activeDatasetId is valid if set
            if (tab.activeDatasetId) {
              const dsExists = (tab.datasets || []).some(d => d.id === tab.activeDatasetId);
              if (!dsExists) {
                needsUpdate = true;
                return { ...tab, activeDatasetId: undefined };
              }
            }

            // Ensure mergeAnchorDatasetId is valid if set
            if (tab.mergeAnchorDatasetId) {
              const anchorExists = (tab.datasets || []).some(d => d.id === tab.mergeAnchorDatasetId);
              if (!anchorExists) {
                needsUpdate = true;
                return { ...tab, mergeAnchorDatasetId: undefined };
              }
            }

            return tab;
          });
          
          if (needsUpdate) {
            useDataWorkspaceStore.setState({ tabs, activeTabId });
          }
        }
      },
    },
  ),
);

// ============================================================================
// SELECTOR HOOKS (for backward compatibility)
// ============================================================================

export const useSelectedSymbols = () => 
  useDataWorkspaceStore(state => {
    const tab = state.tabs.find(t => t.id === state.activeTabId);
    return (tab?.symbols || []).map(o => o.symbol);
  });

export const useSelectedObjectType = () => {
  const objects = useDataWorkspaceStore(state => {
    const tab = state.tabs.find(t => t.id === state.activeTabId);
    return tab?.symbols || [];
  });
  if (objects.length === 0) return 'equity';
  const types = objects.map(o => o.objectType);
  return types[0] || 'equity';
};

export const useActiveTab = () => 
  useDataWorkspaceStore(state => state.tabs.find(t => t.id === state.activeTabId) || null);

export const useTabs = () => 
  useDataWorkspaceStore(state => state.tabs);

export const useActiveTabId = () => 
  useDataWorkspaceStore(state => state.activeTabId);

// Re-export selectors for easy access
export * from './selectors';
