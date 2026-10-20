/**
 * Core Slice - Tabs, Datasets, Objects, and Settings
 * 
 * REFACTORED: Single source of truth is now the tabs array.
 * No more flat state syncing - all data lives in tabs.
 * 
 * This slice handles:
 * - Tab management (CRUD, switching, loading)
 * - Dataset management (add, update, remove)
 * - Object/symbol management
 * - Date range, period, limit settings
 * - Field picker UI state
 */

import { StateCreator } from 'zustand';
import type {
  WorkspaceTab,
  DatasetConfig,
  DatasetGroup,
  SelectedObject,
  FieldConfig,
  TabMode,
  TabType,
  PerToolState,
  TabToolResult,
  TabPivotResult,
  TabChartResult,
  WorkspaceViewMode,
  ContentViewType,
} from '../types';

// Default state for a fresh per-tool slice
export const DEFAULT_PER_TOOL_STATE: PerToolState = {
  toolStep: 1,
  toolParams: {},
  manualTickers: '',
  selectedPortfolioId: '',
  error: null,
  isRunning: false,
  isSaving: false,
  toolResults: [],
  activeResultId: null,
};
import { fetchEndpointMetadata } from '../dataWorkspaceStore';

// Counter for unique group IDs
let groupIdCounter = 0;

// Counter to ensure unique IDs even within the same millisecond
let tabIdCounter = 0;

// Helper to create default tab
export const createDefaultTab = (): WorkspaceTab => {
  const timestamp = Date.now();
  const counter = tabIdCounter++;
  return {
    id: `tab-${timestamp}-${counter}`,
    name: 'Untitled',
    type: 'single',
    datasets: [],
    symbols: [],
    activeView: 'table',
    createdAt: timestamp,
    mode: 'empty',
    viewMode: 'explorer',
  };
};

export interface CoreSlice {
  // State - tabs are the single source of truth
  tabs: WorkspaceTab[];
  activeTabId: string | null;
  
  // Settings (global, not per-tab)
  objectTypeFilter: string | null;
  dateFrom: string | null;
  dateTo: string | null;
  period: string | null;
  limit: number | null;
  
  // UI state
  fieldPickerOpen: boolean;
  /** Global sidebar view mode — tab-independent, like fieldPickerOpen */
  sidebarViewMode: WorkspaceViewMode;
  lastUpdated: string | null;
  sidebarInitialEndpoint: string | null;
  sidebarInitialDatasetId: string | null;
  
  // Legacy field configs (global for backward compat)
  fieldConfigs: FieldConfig[];
  
  // Tab actions
  addTab: (type: TabType, name?: string, viewMode?: WorkspaceViewMode) => string;
  insertTab: (tab: WorkspaceTab) => void;
  removeTab: (id: string) => void;
  setActiveTab: (id: string) => void;
  setTabMode: (id: string, mode: TabMode) => void;
  renameTab: (id: string, name: string) => void;
  reorderTabs: (from: number, to: number) => void;
  updateTabType: (id: string, type: TabType) => void;
  updateTabView: (id: string, view: 'table' | 'ontology') => void;
  setCurrentToolId: (tabId: string, toolId: string) => void;
  updatePerToolState: (tabId: string, updates: Partial<PerToolState>) => void;
  addToolResult: (tabId: string, toolId: string, entry: TabToolResult) => void;
  patchToolResult: (tabId: string, toolId: string, localId: string, patch: Partial<TabToolResult>) => void;
  removeToolResult: (tabId: string, toolId: string, localId: string) => void;
  addPivotResult: (tabId: string, entry: TabPivotResult) => void;
  patchPivotResult: (tabId: string, localId: string, patch: Partial<TabPivotResult>) => void;
  removePivotResult: (tabId: string, localId: string) => void;
  addChartResult: (tabId: string, entry: TabChartResult) => void;
  patchChartResult: (tabId: string, localId: string, patch: Partial<TabChartResult>) => void;
  removeChartResult: (tabId: string, localId: string) => void;
  setActiveChartGroup: (groupId: string) => void;
  setViewMode: (id: string, mode: WorkspaceViewMode) => void;
  setContentView: (id: string, view: ContentViewType) => void;
  setChatThreadId: (tabId: string, threadId: string) => void;
  addChatThreadId: (tabId: string, threadId: string) => void;
  loadTabs: (tabs: WorkspaceTab[], activeTabId?: string) => void;
  getActiveTab: () => WorkspaceTab | null;
  setTabBackendId: (tabId: string, backendId: string) => void;

  // Merge actions
  toggleMergeDataset: (datasetId: string) => void;
  setMergedDatasetIds: (ids: string[]) => void;
  setActiveDatasetId: (datasetId: string | undefined) => void;

  // Dataset actions
  addDataset: (config: Omit<DatasetConfig, 'id' | 'addedAt'>) => void;
  addDatasetWithMetadata: (config: Omit<DatasetConfig, 'id' | 'addedAt'>) => Promise<void>;
  addDatasetDirect: (config: {
    id: string;
    symbol: string;
    endpoint: string;
    params?: Record<string, any>;
    fields: string[] | null;
    data: unknown[];
    rowCount: number;
  }) => void;
  addDatasetToGroup: (groupId: string, config: Omit<DatasetConfig, 'id' | 'addedAt' | 'groupId'>) => Promise<void>;
  updateDataset: (id: string, updates: Partial<Omit<DatasetConfig, 'id' | 'addedAt'>>) => void;
  removeDataset: (id: string) => void;
  clearDatasets: () => void;
  getDatasets: () => DatasetConfig[];
  
  // Dataset group actions
  createDatasetGroup: (name?: string) => string;
  removeDatasetGroup: (groupId: string) => void;
  renameDatasetGroup: (groupId: string, name: string) => void;
  setActiveGroup: (groupId: string) => void;
  setActiveAnalysisGroup: (groupId: string) => void;
  setActivePivotGroup: (groupId: string) => void;
  getActiveGroup: () => DatasetGroup | null;
  getDatasetGroups: () => DatasetGroup[];
  getActiveGroupDatasets: () => DatasetConfig[];
  clearActiveGroupDatasets: () => void;
  
  // Object actions
  addObject: (obj: SelectedObject) => void;
  removeObject: (symbol: string) => void;
  clearObjects: () => void;
  setObjects: (objects: SelectedObject[]) => void;
  
  // Field actions (operate on active tab's datasets - kept for backward compat)
  addField: (field: string) => void;
  removeField: (field: string) => void;
  toggleField: (field: string) => void;
  addFields: (fields: string[]) => void;
  clearFields: () => void;
  setFields: (fields: string[]) => void;
  
  // Field config actions (legacy - global)
  addFieldConfig: (config: FieldConfig) => void;
  removeFieldConfig: (field_name: string) => void;
  clearFieldConfigs: () => void;
  getFieldConfigs: () => FieldConfig[];
  
  // Settings
  setDateRange: (from: string | null, to: string | null) => void;
  setObjectTypeFilter: (type: string | null) => void;
  setPeriod: (period: string | null) => void;
  setLimit: (limit: number | null) => void;
  setFieldPickerOpen: (open: boolean) => void;
  setSidebarViewMode: (mode: WorkspaceViewMode) => void;
  setSidebarInitialEndpoint: (endpoint: string | null) => void;
  setSidebarInitialDatasetId: (id: string | null) => void;

  // Reset
  resetWorkspace: () => void;
}

export const createCoreSlice: StateCreator<CoreSlice, [], [], CoreSlice> = (set, get) => {
  const defaultTab = createDefaultTab();
  
  return {
    // Initial state - tabs are single source of truth
    tabs: [defaultTab],
    activeTabId: defaultTab.id,
    fieldConfigs: [],
    objectTypeFilter: null,
    dateFrom: null,
    dateTo: null,
    period: null,
    limit: null,
    fieldPickerOpen: true,
    sidebarViewMode: 'explorer',
    lastUpdated: null,
    sidebarInitialEndpoint: null,
    sidebarInitialDatasetId: null,
    
    // ========== TAB ACTIONS ==========
    
    addTab: (type, name, viewMode) => {
      const timestamp = Date.now();
      const counter = tabIdCounter++;
      const resolvedViewMode = viewMode || (type === 'tool' ? 'tools' : type === 'pivot' ? 'pivot' : type === 'chart' ? 'chart' : 'explorer');
      const newTab: WorkspaceTab = {
        id: `tab-${timestamp}-${counter}`,
        name: name || (resolvedViewMode === 'tools' || type === 'tool' ? 'New Analysis' : 'Untitled'),
        type,
        datasets: [],
        symbols: [],
        activeView: 'table',
        createdAt: timestamp,
        mode: resolvedViewMode === 'tools' || type === 'tool' ? 'data' : 'empty',
        viewMode: resolvedViewMode,
        ...(resolvedViewMode === 'tools' || type === 'tool' ? {
          currentToolId: '',
          perToolState: {},
        } : {}),
      };
      
      set(state => ({
        tabs: [...state.tabs, newTab],
        activeTabId: newTab.id,
        lastUpdated: new Date().toISOString(),
      }));
      
      return newTab.id;
    },
    
    insertTab: (tab) => {
      set(state => ({
        tabs: [...state.tabs, tab],
        activeTabId: tab.id,
        lastUpdated: new Date().toISOString(),
      }));
    },

    removeTab: (id) => {
      const { tabs, activeTabId } = get();
      const remaining = tabs.filter(t => t.id !== id);
      
      // Allow 0 tabs - UI will show empty state
      const newActiveId = remaining.length === 0 
        ? null 
        : (id === activeTabId ? remaining[remaining.length - 1].id : activeTabId);
      
      set({
        tabs: remaining,
        activeTabId: newActiveId,
        lastUpdated: new Date().toISOString(),
      });
    },
    
    setActiveTab: (id) => {
      const { tabs } = get();
      const tab = tabs.find(t => t.id === id);
      if (!tab) return;

      // Sync sidebar to the tab's stored viewMode
      const tabViewMode = tab.viewMode
        || (tab.type === 'tool' ? 'tools'
          : tab.type === 'pivot' ? 'pivot'
          : tab.type === 'chart' ? 'chart'
          : 'explorer') as WorkspaceViewMode;

      set(() => ({
        activeTabId: id,
        sidebarViewMode: tabViewMode,
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    setTabMode: (id, mode) => {
      set(state => ({
        tabs: state.tabs.map(t => t.id === id ? { ...t, mode } : t),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    renameTab: (id, name) => {
      set(state => ({
        tabs: state.tabs.map(t => t.id === id ? { ...t, name } : t),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    reorderTabs: (from, to) => {
      const tabs = [...get().tabs];
      if (from < 0 || from >= tabs.length || to < 0 || to >= tabs.length) return;
      const [removed] = tabs.splice(from, 1);
      tabs.splice(to, 0, removed);
      set({ tabs, lastUpdated: new Date().toISOString() });
    },
    
    updateTabType: (id, type) => {
      set(state => ({
        tabs: state.tabs.map(t => t.id === id ? { ...t, type } : t),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    updateTabView: (id, view) => {
      set(state => ({
        tabs: state.tabs.map(t => t.id === id ? { ...t, activeView: view } : t),
      }));
    },

    setCurrentToolId: (tabId, toolId) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const existing = t.perToolState ?? {};
          const nextPerToolState = toolId && !existing[toolId]
            ? { ...existing, [toolId]: { ...DEFAULT_PER_TOOL_STATE } }
            : existing;
          return { ...t, currentToolId: toolId, perToolState: nextPerToolState };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    updatePerToolState: (tabId, updates) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const toolId = t.currentToolId;
          if (!toolId) return t;
          const existing = t.perToolState?.[toolId] ?? DEFAULT_PER_TOOL_STATE;
          return {
            ...t,
            perToolState: {
              ...(t.perToolState ?? {}),
              [toolId]: { ...existing, ...updates },
            },
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    addToolResult: (tabId, toolId, entry) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const existing = t.perToolState?.[toolId] ?? DEFAULT_PER_TOOL_STATE;
          const needsGroup = !t.datasetGroups || t.datasetGroups.length === 0;
          const defaultGroupId = needsGroup ? `group-default-${Date.now()}` : t.datasetGroups![0].id;
          const entryWithGroup = entry.groupId ? entry : { ...entry, groupId: defaultGroupId };
          return {
            ...t,
            ...(needsGroup ? {
              datasetGroups: [{ id: defaultGroupId, name: 'Analyses', createdAt: Date.now() }],
              activeGroupId: defaultGroupId,
            } : {}),
            perToolState: {
              ...(t.perToolState ?? {}),
              [toolId]: {
                ...existing,
                toolResults: [...(existing.toolResults ?? []), entryWithGroup],
                activeResultId: entryWithGroup.localId,
              },
            },
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    patchToolResult: (tabId, toolId, localId, patch) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const existing = t.perToolState?.[toolId];
          if (!existing) return t;
          return {
            ...t,
            perToolState: {
              ...(t.perToolState ?? {}),
              [toolId]: {
                ...existing,
                toolResults: (existing.toolResults ?? []).map(r =>
                  r.localId === localId ? { ...r, ...patch } : r
                ),
              },
            },
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    removeToolResult: (tabId, toolId, localId) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const existing = t.perToolState?.[toolId];
          if (!existing) return t;
          const nextResults = (existing.toolResults ?? []).filter(r => r.localId !== localId);
          const nextActive = existing.activeResultId === localId
            ? (nextResults[nextResults.length - 1]?.localId ?? null)
            : existing.activeResultId;
          return {
            ...t,
            perToolState: {
              ...(t.perToolState ?? {}),
              [toolId]: {
                ...existing,
                toolResults: nextResults,
                activeResultId: nextActive,
              },
            },
            // If the tab's current content view was pointing at the removed result, reset to data
            contentView: t.contentView?.type === 'tool-result' && t.contentView.resultLocalId === localId
              ? { type: 'data' }
              : t.contentView,
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    addPivotResult: (tabId, entry) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const needsGroup = !t.datasetGroups || t.datasetGroups.length === 0;
          const defaultGroupId = needsGroup ? `group-default-${Date.now()}` : t.datasetGroups![0].id;
          const entryWithGroup = entry.groupId ? entry : { ...entry, groupId: defaultGroupId };
          return {
            ...t,
            ...(needsGroup ? {
              datasetGroups: [{ id: defaultGroupId, name: 'Data', createdAt: Date.now() }],
              activeGroupId: defaultGroupId,
            } : {}),
            pivotResults: [...(t.pivotResults ?? []), entryWithGroup],
            contentView: { type: 'pivot', pivotLocalId: entryWithGroup.localId },
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    patchPivotResult: (tabId, localId, patch) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          return {
            ...t,
            pivotResults: (t.pivotResults ?? []).map(r =>
              r.localId === localId ? { ...r, ...patch } : r
            ),
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    removePivotResult: (tabId, localId) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const nextResults = (t.pivotResults ?? []).filter(r => r.localId !== localId);
          return {
            ...t,
            pivotResults: nextResults,
            contentView: t.contentView?.type === 'pivot' && t.contentView.pivotLocalId === localId
              ? { type: 'data' }
              : t.contentView,
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    addChartResult: (tabId, entry) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const needsGroup = !t.datasetGroups || t.datasetGroups.length === 0;
          const defaultGroupId = needsGroup ? `group-default-${Date.now()}` : t.datasetGroups![0].id;
          const entryWithGroup = entry.groupId ? entry : { ...entry, groupId: defaultGroupId };
          return {
            ...t,
            ...(needsGroup ? {
              datasetGroups: [{ id: defaultGroupId, name: 'Data', createdAt: Date.now() }],
              activeGroupId: defaultGroupId,
            } : {}),
            chartResults: [...(t.chartResults ?? []), entryWithGroup],
            contentView: { type: 'chart' as const, chartLocalId: entryWithGroup.localId },
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    patchChartResult: (tabId, localId, patch) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          return {
            ...t,
            chartResults: (t.chartResults ?? []).map(r =>
              r.localId === localId ? { ...r, ...patch } : r
            ),
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    removeChartResult: (tabId, localId) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const nextResults = (t.chartResults ?? []).filter(r => r.localId !== localId);
          return {
            ...t,
            chartResults: nextResults,
            contentView: t.contentView?.type === 'chart' && t.contentView.chartLocalId === localId
              ? { type: 'data' }
              : t.contentView,
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    setActiveChartGroup: (groupId) => {
      const { activeTabId } = get();
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, activeChartGroupId: groupId }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },

    setViewMode: (id, mode) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== id) return t;
          const updates: Partial<WorkspaceTab> = { viewMode: mode };
          // Lazily initialize mode-specific state
          if (mode === 'tools' && !t.perToolState) {
            updates.currentToolId = t.currentToolId ?? '';
            updates.perToolState = {};
          }
          if (mode === 'pivot' && !t.pivotConfig) {
            updates.pivotConfig = {
              id: `config-${Date.now()}`,
              sourceTabId: t.id,
              rows: [],
              columns: [],
              values: [],
              filters: {},
              filterableFields: [],
              selectedDatasetIds: [],
            };
          }
          if (mode === 'chart' && !t.chartConfig) {
            updates.chartConfig = {
              id: `config-${Date.now()}`,
              sourceTabId: t.id,
              chartType: 'line',
              xAxis: '',
              ySeries: [],
              selectedDatasetIds: [],
              showLegend: true,
              showGrid: true,
            };
          }
          return { ...t, ...updates };
        }),
      }));
    },

    setContentView: (id, view) => {
      set(state => ({
        tabs: state.tabs.map(t => t.id === id ? { ...t, contentView: view } : t),
      }));
    },

    setChatThreadId: (tabId, threadId) => {
      set(state => ({
        tabs: state.tabs.map(t => t.id === tabId ? { ...t, chatThreadId: threadId } : t),
      }));
    },

    addChatThreadId: (tabId, threadId) => {
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== tabId) return t;
          const ids = t.chatThreadIds ?? [];
          if (ids.includes(threadId)) return t;
          return { ...t, chatThreadIds: [...ids, threadId] };
        }),
      }));
    },

    loadTabs: (tabs, activeTabId) => {
      if (!tabs || tabs.length === 0) {
        const newTab = createDefaultTab();
        set({
          tabs: [newTab],
          activeTabId: newTab.id,
          lastUpdated: new Date().toISOString(),
        });
        return;
      }
      
      // Remap IDs to avoid collisions
      const tabIdMap: Record<string, string> = {};
      const timestamp = Date.now();
      
      tabs.forEach((tab, idx) => {
        tabIdMap[tab.id] = `tab-${timestamp}-${idx}`;
      });
      
      const loadedTabs = tabs.map(tab => {
        const newTabId = tabIdMap[tab.id];

        // Update pivot/chart references
        let updatedPivotConfig = tab.pivotConfig;
        if (tab.type === 'pivot' && tab.pivotConfig && tab.pivotConfig.sourceTabId) {
          updatedPivotConfig = {
            ...tab.pivotConfig,
            sourceTabId: tabIdMap[tab.pivotConfig.sourceTabId] || tab.pivotConfig.sourceTabId,
          };
        }

        // Remap sourceTabId on every accumulated pivot result's config
        const updatedPivotResults = tab.pivotResults?.map(pv => ({
          ...pv,
          config: pv.config.sourceTabId
            ? { ...pv.config, sourceTabId: tabIdMap[pv.config.sourceTabId] || pv.config.sourceTabId }
            : pv.config,
        }));

        let updatedChartConfig = tab.chartConfig;
        if (tab.type === 'chart' && tab.chartConfig && tab.chartConfig.sourceTabId) {
          updatedChartConfig = {
            ...tab.chartConfig,
            sourceTabId: tabIdMap[tab.chartConfig.sourceTabId] || tab.chartConfig.sourceTabId,
          };
        }

        const updatedChartResults = tab.chartResults?.map(cr => ({
          ...cr,
          config: cr.config.sourceTabId
            ? { ...cr.config, sourceTabId: tabIdMap[cr.config.sourceTabId] || cr.config.sourceTabId }
            : cr.config,
        }));

        let updatedContentView = tab.contentView;
        if (updatedContentView?.type === 'tool-result' && updatedContentView.toolTabId) {
          updatedContentView = {
            ...updatedContentView,
            toolTabId: tabIdMap[updatedContentView.toolTabId] || updatedContentView.toolTabId,
          };
        }

        return {
          ...tab,
          id: newTabId,
          contentView: updatedContentView,
          pivotConfig: updatedPivotConfig,
          pivotResults: updatedPivotResults,
          chartConfig: updatedChartConfig,
          chartResults: updatedChartResults,
        };
      });
      
      const activeIdx = activeTabId ? tabs.findIndex(t => t.id === activeTabId) : 0;
      const newActiveTab = loadedTabs[Math.max(0, activeIdx)];
      
      set({
        tabs: loadedTabs,
        activeTabId: newActiveTab.id,
        lastUpdated: new Date().toISOString(),
      });
    },
    
    getActiveTab: () => {
      const { tabs, activeTabId } = get();
      return tabs.find(t => t.id === activeTabId) || null;
    },

    setTabBackendId: (tabId, backendId) => {
      set(state => ({
        tabs: state.tabs.map(t => t.id === tabId ? { ...t, backendId } : t),
      }));
    },

    // ========== MERGE ACTIONS ==========

    toggleMergeDataset: (datasetId) => {
      const { activeTabId } = get();
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== activeTabId) return t;
          const current = t.mergedDatasetIds ?? [];
          const next = current.includes(datasetId)
            ? current.filter(id => id !== datasetId)
            : [...current, datasetId];
          const mergeAnchorDatasetId = next.length > 0
            ? (t.mergeAnchorDatasetId ?? t.activeDatasetId)
            : undefined;
          return { ...t, mergedDatasetIds: next, mergeAnchorDatasetId };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    setMergedDatasetIds: (ids) => {
      const { activeTabId } = get();
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== activeTabId) return t;
          const mergeAnchorDatasetId = ids.length > 0
            ? (t.mergeAnchorDatasetId ?? t.activeDatasetId)
            : undefined;
          return { ...t, mergedDatasetIds: ids, mergeAnchorDatasetId };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },

    setActiveDatasetId: (datasetId) => {
      const { activeTabId, tabs } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (activeTab?.activeDatasetId === datasetId) return;
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId ? { ...t, activeDatasetId: datasetId } : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },

    // ========== DATASET ACTIONS ==========

    addDataset: (config) => {
      const { tabs, activeTabId } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (!activeTab) return;
      
      const currentDatasets = activeTab.datasets || [];
      
      // Check for duplicate
      const exists = currentDatasets.find(
        d => d.symbol === config.symbol && d.endpoint === config.endpoint
      );
      if (exists) {
        console.warn(`Dataset already exists: ${config.symbol} - ${config.endpoint}`);
        return;
      }
      
      const id = `${config.symbol}-${config.endpoint}-${Date.now()}`;
      const dataset: DatasetConfig = { ...config, id, addedAt: Date.now() };
      
      const newDatasets = [...currentDatasets, dataset];
      
      // Add symbol to symbols if not present
      const currentSymbols = activeTab.symbols || [];
      let newSymbols = currentSymbols;
      if (!currentSymbols.find(o => o.symbol === config.symbol)) {
        newSymbols = [...currentSymbols, { symbol: config.symbol, objectType: 'equity' }];
      }
      
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, datasets: newDatasets, symbols: newSymbols, mode: 'data' as TabMode }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    addDatasetWithMetadata: async (config) => {
      let { tabs, activeTabId } = get();

      // Auto-create a tab if none exists
      if (!activeTabId || !tabs.find(t => t.id === activeTabId)) {
        const newTabId = get().addTab('single', `${config.symbol} Data`);
        activeTabId = newTabId;
      }

      // CRITICAL: Capture the target tab ID BEFORE async operation
      const targetTabId = activeTabId;

      const activeTab = get().tabs.find(t => t.id === targetTabId);
      if (!activeTab) return;
      
      const currentDatasets = activeTab.datasets || [];
      
      // Check for duplicate
      const exists = currentDatasets.find(
        d => d.symbol === config.symbol && d.endpoint === config.endpoint
      );
      if (exists) {
        console.warn(`Dataset already exists: ${config.symbol} - ${config.endpoint}`);
        return;
      }
      
      const metadata = await fetchEndpointMetadata(config.endpoint);
      
      // Re-fetch state after async (state may have changed)
      const currentState = get();
      const currentTab = currentState.tabs.find(t => t.id === targetTabId);
      if (!currentTab) return; // Tab was deleted during async
      
      const tabDatasets = currentTab.datasets || [];
      
      // Double-check for duplicate after async
      const stillExists = tabDatasets.find(
        d => d.symbol === config.symbol && d.endpoint === config.endpoint
      );
      if (stillExists) {
        console.warn(`Dataset already exists: ${config.symbol} - ${config.endpoint}`);
        return;
      }
      
      const id = `${config.symbol}-${config.endpoint}-${Date.now()}`;
      const dataset: DatasetConfig = {
        ...config,
        id,
        addedAt: Date.now(),
        structureType: metadata.structureType,
        compatibilityGroup: metadata.compatibilityGroup,
        timeKey: metadata.timeKey,
        cardinality: metadata.cardinality,
      };
      
      const newDatasets = [...tabDatasets, dataset];
      
      const currentSymbols = currentTab.symbols || [];
      let newSymbols = currentSymbols;
      if (!currentSymbols.find(o => o.symbol === config.symbol)) {
        newSymbols = [...currentSymbols, { symbol: config.symbol, objectType: 'equity' }];
      }
      
      // Use captured targetTabId to update the correct tab
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === targetTabId
            ? { ...t, datasets: newDatasets, symbols: newSymbols, mode: 'data' as TabMode }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    /**
     * Add a dataset directly with pre-fetched data from the AI agent.
     * 
     * This is used by the agentic action flow where:
     * 1. AI tool fetches data and caches it
     * 2. Frontend receives agent_action event with dataset_id
     * 3. Frontend fetches cached data from /api/canvas/data/cache/{id}
     * 4. Frontend calls this method to add the dataset with data already present
     * 
     * Unlike addDatasetWithMetadata, this does NOT trigger a fetch - data is already provided.
     */
    addDatasetDirect: (config) => {
      const { tabs, activeTabId, addTab } = get();
      let activeTab = tabs.find(t => t.id === activeTabId);
      let targetTabId = activeTabId;
      
      if (!activeTab) {
        // No tabs exist - create a new one for this dataset
        console.log('[addDatasetDirect] No active tab, creating new tab');
        targetTabId = addTab('single', `${config.symbol} Data`);
        const updatedState = get();
        activeTab = updatedState.tabs.find(t => t.id === targetTabId);
        if (!activeTab) {
          console.error('[addDatasetDirect] Failed to create new tab');
          return;
        }
      }

      // If active tab is incompatible type (pivot/chart), create a new data tab
      const incompatibleTypes: TabType[] = ['pivot', 'chart'];
      if (incompatibleTypes.includes(activeTab.type)) {
        console.log(`[addDatasetDirect] Active tab is '${activeTab.type}', creating new data tab`);
        targetTabId = addTab('single', `${config.symbol} Data`);
        // Re-fetch tabs and get the new tab
        const updatedState = get();
        activeTab = updatedState.tabs.find(t => t.id === targetTabId);
        if (!activeTab) {
          console.error('[addDatasetDirect] Failed to create new tab');
          return;
        }
      }
      
      // Different endpoints go into different groups on the same tab
      // (no auto-tab creation — groups handle data organization)
      
      // Get current datasets from the (possibly new) active tab
      const currentDatasets = activeTab.datasets || [];
      
      // Check for duplicate
      const exists = currentDatasets.find(
        d => d.symbol === config.symbol && d.endpoint === config.endpoint
      );
      if (exists) {
        console.warn(`[addDatasetDirect] Dataset already exists: ${config.symbol} - ${config.endpoint}`);
        return;
      }
      
      set(state => ({
        tabs: state.tabs.map(t => {
          if (t.id !== targetTabId) return t;

          const needsGroup = !t.datasetGroups || t.datasetGroups.length === 0;
          const defaultGroupId = needsGroup ? `group-${Date.now()}-0` : undefined;
          const groupId = config.groupId || t.activeGroupId || t.datasetGroups?.[0]?.id || defaultGroupId;

          const dataset: DatasetConfig = {
            id: config.id,
            symbol: config.symbol,
            endpoint: config.endpoint,
            params: config.params || {},
            fields: config.fields || [],
            addedAt: Date.now(),
            groupId,
          };

          const symbols = t.symbols || [];
          const newSymbols = symbols.find(o => o.symbol === config.symbol)
            ? symbols
            : [...symbols, { symbol: config.symbol, objectType: 'equity' as const }];

          return {
            ...t,
            datasets: [...(t.datasets || []), dataset],
            symbols: newSymbols,
            mode: 'data' as TabMode,
            ...(needsGroup && defaultGroupId ? {
              datasetGroups: [{ id: defaultGroupId, name: 'Data', createdAt: Date.now() }],
              activeGroupId: defaultGroupId,
            } : {}),
          };
        }),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    updateDataset: (id, updates) => {
      const { tabs, activeTabId } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (!activeTab) return;
      
      const datasets = activeTab.datasets || [];
      const index = datasets.findIndex(d => d.id === id);
      if (index === -1) return;
      
      const oldDataset = datasets[index];
      const newDataset = { ...oldDataset, ...updates };
      const newDatasets = [...datasets];
      newDatasets[index] = newDataset;
      
      // Update symbols if symbol changed
      let newSymbols = activeTab.symbols || [];
      if (updates.symbol && updates.symbol !== oldDataset.symbol) {
        const symbolsInUse = new Set(newDatasets.map(d => d.symbol));
        if (!symbolsInUse.has(oldDataset.symbol)) {
          newSymbols = newSymbols.filter(o => o.symbol !== oldDataset.symbol);
        }
        if (!newSymbols.find(o => o.symbol === updates.symbol)) {
          newSymbols = [...newSymbols, { symbol: updates.symbol, objectType: 'equity' }];
        }
      }
      
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, datasets: newDatasets, symbols: newSymbols }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    removeDataset: (id) => {
      const { tabs, activeTabId } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (!activeTab) return;
      
      const datasets = activeTab.datasets || [];
      const toRemove = datasets.find(d => d.id === id);
      if (!toRemove) return;
      
      const remaining = datasets.filter(d => d.id !== id);

      const newMode: TabMode = remaining.length === 0 ? 'empty' : 'data';

      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? {
                ...t,
                datasets: remaining,
                mode: newMode,
                activeDatasetId: t.activeDatasetId === id ? undefined : t.activeDatasetId,
                mergedDatasetIds: t.mergedDatasetIds?.filter(mid => mid !== id),
                mergeAnchorDatasetId: t.mergeAnchorDatasetId === id ? undefined : t.mergeAnchorDatasetId,
              }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },

    clearDatasets: () => {
      const { activeTabId } = get();

      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, datasets: [], symbols: [], mode: 'empty' as TabMode, activeDatasetId: undefined, mergedDatasetIds: undefined, mergeAnchorDatasetId: undefined }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },

    getDatasets: () => {
      const { tabs, activeTabId } = get();
      const tab = tabs.find(t => t.id === activeTabId);
      return tab?.datasets || [];
    },
    
    // ========== DATASET GROUP ACTIONS ==========
    
    createDatasetGroup: (name) => {
      const { tabs, activeTabId } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (!activeTab) return '';
      
      const timestamp = Date.now();
      const counter = groupIdCounter++;
      const groupId = `group-${timestamp}-${counter}`;
      
      // Auto-generate name if not provided
      const existingGroups = activeTab.datasetGroups || [];
      const groupName = name || `Group ${existingGroups.length + 1}`;
      
      const newGroup: DatasetGroup = {
        id: groupId,
        name: groupName,
        createdAt: timestamp,
      };
      
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? {
                ...t,
                datasetGroups: [...(t.datasetGroups || []), newGroup],
                activeGroupId: groupId, // Auto-activate new group
              }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
      
      return groupId;
    },
    
    removeDatasetGroup: (groupId) => {
      const { tabs, activeTabId } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (!activeTab) return;
      
      const currentGroups = activeTab.datasetGroups || [];
      const remainingGroups = currentGroups.filter(g => g.id !== groupId);
      
      // Remove all datasets belonging to this group
      const currentDatasets = activeTab.datasets || [];
      const remainingDatasets = currentDatasets.filter(d => d.groupId !== groupId);
      
      // Update active group if it was the one being removed
      let newActiveGroupId = activeTab.activeGroupId;
      if (activeTab.activeGroupId === groupId) {
        newActiveGroupId = remainingGroups.length > 0 ? remainingGroups[0].id : undefined;
      }

      const newMode: TabMode = remainingDatasets.length === 0 ? 'empty' : 'data';

      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? {
                ...t,
                datasetGroups: remainingGroups,
                datasets: remainingDatasets,
                activeGroupId: newActiveGroupId,
                mode: newMode,
              }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    renameDatasetGroup: (groupId, name) => {
      const { activeTabId } = get();
      
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? {
                ...t,
                datasetGroups: (t.datasetGroups || []).map(g =>
                  g.id === groupId ? { ...g, name } : g
                ),
              }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    setActiveGroup: (groupId) => {
      const { activeTabId } = get();

      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, activeGroupId: groupId }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },

    setActiveAnalysisGroup: (groupId) => {
      const { activeTabId } = get();

      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, activeAnalysisGroupId: groupId }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },

    setActivePivotGroup: (groupId) => {
      const { activeTabId } = get();

      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, activePivotGroupId: groupId }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },

    getActiveGroup: () => {
      const { tabs, activeTabId } = get();
      const tab = tabs.find(t => t.id === activeTabId);
      if (!tab || !tab.datasetGroups || !tab.activeGroupId) return null;
      return tab.datasetGroups.find(g => g.id === tab.activeGroupId) || null;
    },
    
    getDatasetGroups: () => {
      const { tabs, activeTabId } = get();
      const tab = tabs.find(t => t.id === activeTabId);
      return tab?.datasetGroups || [];
    },
    
    getActiveGroupDatasets: () => {
      const { tabs, activeTabId } = get();
      const tab = tabs.find(t => t.id === activeTabId);
      if (!tab) return [];
      
      // If no groups defined, return all datasets (backward compat)
      if (!tab.datasetGroups || tab.datasetGroups.length === 0) {
        return tab.datasets || [];
      }
      
      // Return only datasets belonging to the active group
      const activeGroupId = tab.activeGroupId;
      if (!activeGroupId) return [];
      
      return (tab.datasets || []).filter(d => d.groupId === activeGroupId);
    },
    
    clearActiveGroupDatasets: () => {
      const { tabs, activeTabId } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (!activeTab) return;
      
      const activeGroupId = activeTab.activeGroupId;
      
      // If no groups defined, clear all datasets (backward compat)
      if (!activeTab.datasetGroups || activeTab.datasetGroups.length === 0 || !activeGroupId) {
        set(state => ({
          tabs: state.tabs.map(t =>
            t.id === activeTabId
              ? { ...t, datasets: [], symbols: [], mode: 'empty' as TabMode, activeDatasetId: undefined, mergedDatasetIds: undefined, mergeAnchorDatasetId: undefined }
              : t
          ),
          lastUpdated: new Date().toISOString(),
        }));
        return;
      }

      // Remove only datasets belonging to the active group
      const currentDatasets = activeTab.datasets || [];
      const remainingDatasets = currentDatasets.filter(d => d.groupId !== activeGroupId);

      // Remove the group itself
      const currentGroups = activeTab.datasetGroups || [];
      const remainingGroups = currentGroups.filter(g => g.id !== activeGroupId);

      // Switch to another group if available, otherwise null
      const newActiveGroupId = remainingGroups.length > 0 ? remainingGroups[0].id : undefined;

      // Symbols still in use by remaining datasets
      const symbolsInUse = new Set(remainingDatasets.map(d => d.symbol));
      const newSymbols = (activeTab.symbols || []).filter(o => symbolsInUse.has(o.symbol));

      const newMode: TabMode = remainingDatasets.length === 0 ? 'empty' : 'data';

      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? {
                ...t,
                datasets: remainingDatasets,
                symbols: newSymbols,
                mode: newMode,
                datasetGroups: remainingGroups,
                activeGroupId: newActiveGroupId,
                activeDatasetId: remainingDatasets.some(d => d.id === t.activeDatasetId) ? t.activeDatasetId : undefined,
                mergedDatasetIds: t.mergedDatasetIds?.filter(id => remainingDatasets.some(d => d.id === id)),
                mergeAnchorDatasetId: remainingDatasets.some(d => d.id === t.mergeAnchorDatasetId) ? t.mergeAnchorDatasetId : undefined,
              }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },

    addDatasetToGroup: async (groupId, config) => {
      const { tabs, activeTabId } = get();
      
      // CRITICAL: Capture the target tab ID BEFORE async operation
      const targetTabId = activeTabId;
      
      const activeTab = tabs.find(t => t.id === targetTabId);
      if (!activeTab) return;
      
      const currentDatasets = activeTab.datasets || [];
      
      // Check for duplicate (same symbol + endpoint in the SAME group)
      const exists = currentDatasets.find(
        d => d.symbol === config.symbol && d.endpoint === config.endpoint && d.groupId === groupId
      );
      if (exists) {
        console.warn(`Dataset already exists in group: ${config.symbol} - ${config.endpoint}`);
        return;
      }
      
      const metadata = await fetchEndpointMetadata(config.endpoint);
      
      // Re-fetch state after async (state may have changed)
      const currentState = get();
      const currentTab = currentState.tabs.find(t => t.id === targetTabId);
      if (!currentTab) return; // Tab was deleted during async
      
      const tabDatasets = currentTab.datasets || [];
      
      // Double-check for duplicate after async
      const stillExists = tabDatasets.find(
        d => d.symbol === config.symbol && d.endpoint === config.endpoint && d.groupId === groupId
      );
      if (stillExists) {
        console.warn(`Dataset already exists in group: ${config.symbol} - ${config.endpoint}`);
        return;
      }
      
      const id = `${config.symbol}-${config.endpoint}-${Date.now()}`;
      const dataset: DatasetConfig = {
        ...config,
        id,
        addedAt: Date.now(),
        groupId, // Assign to the specified group
        structureType: metadata.structureType,
        compatibilityGroup: metadata.compatibilityGroup,
        timeKey: metadata.timeKey,
        cardinality: metadata.cardinality,
      };
      
      const newDatasets = [...tabDatasets, dataset];
      
      const currentSymbols = currentTab.symbols || [];
      let newSymbols = currentSymbols;
      if (!currentSymbols.find(o => o.symbol === config.symbol)) {
        newSymbols = [...currentSymbols, { symbol: config.symbol, objectType: 'equity' }];
      }
      
      // Use captured targetTabId to update the correct tab
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === targetTabId
            ? { ...t, datasets: newDatasets, symbols: newSymbols, mode: 'data' as TabMode }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    // ========== OBJECT ACTIONS ==========
    
    addObject: (obj) => {
      const { tabs, activeTabId } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (!activeTab) return;
      
      const currentSymbols = activeTab.symbols || [];
      if (currentSymbols.find(o => o.symbol === obj.symbol)) return;
      
      const newSymbols = [...currentSymbols, obj];
      
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, symbols: newSymbols }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    removeObject: (symbol) => {
      const { tabs, activeTabId } = get();
      const activeTab = tabs.find(t => t.id === activeTabId);
      if (!activeTab) return;
      
      const newSymbols = (activeTab.symbols || []).filter(o => o.symbol !== symbol);
      
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, symbols: newSymbols }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    clearObjects: () => {
      const { activeTabId } = get();
      
      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, symbols: [] }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    setObjects: (objects) => {
      const { activeTabId } = get();
      if (!activeTabId) return;

      set(state => ({
        tabs: state.tabs.map(t =>
          t.id === activeTabId
            ? { ...t, symbols: objects }
            : t
        ),
        lastUpdated: new Date().toISOString(),
      }));
    },
    
    // ========== FIELD ACTIONS (operate on datasets - kept for backward compat) ==========
    // Note: These are largely no-ops now since fields are derived from datasets
    
    addField: (_field) => {
      // Fields are derived from datasets - this is a no-op
      // Kept for backward compatibility
      set({ lastUpdated: new Date().toISOString() });
    },
    
    removeField: (_field) => {
      // Fields are derived from datasets - this is a no-op
      set({ lastUpdated: new Date().toISOString() });
    },
    
    toggleField: (_field) => {
      // Fields are derived from datasets - this is a no-op
      set({ lastUpdated: new Date().toISOString() });
    },
    
    addFields: (_fields) => {
      // Fields are derived from datasets - this is a no-op
      set({ lastUpdated: new Date().toISOString() });
    },
    
    clearFields: () => {
      // Fields are derived from datasets - this is a no-op
      set({ lastUpdated: new Date().toISOString() });
    },
    
    setFields: (_fields) => {
      // Fields are derived from datasets - this is a no-op
      set({ lastUpdated: new Date().toISOString() });
    },
    
    // ========== FIELD CONFIG ACTIONS (legacy - kept for backward compat) ==========
    
    addFieldConfig: (config) => {
      const existing = get().fieldConfigs;
      const filtered = existing.filter(f => f.field_name !== config.field_name);
      set({
        fieldConfigs: [...filtered, config],
        lastUpdated: new Date().toISOString(),
      });
    },
    
    removeFieldConfig: (field_name) => {
      set({
        fieldConfigs: get().fieldConfigs.filter(f => f.field_name !== field_name),
        lastUpdated: new Date().toISOString(),
      });
    },
    
    clearFieldConfigs: () => {
      set({ fieldConfigs: [], lastUpdated: new Date().toISOString() });
    },
    
    getFieldConfigs: () => get().fieldConfigs,
    
    // ========== SETTINGS ==========
    
    setDateRange: (from, to) => {
      set({ dateFrom: from, dateTo: to, lastUpdated: new Date().toISOString() });
    },
    
    setObjectTypeFilter: (type) => {
      set({ objectTypeFilter: type });
    },
    
    setPeriod: (period) => {
      set({ period });
    },
    
    setLimit: (limit) => {
      set({ limit });
    },
    
    setFieldPickerOpen: (open) => {
      set({ fieldPickerOpen: open });
    },

    setSidebarViewMode: (mode) => {
      set({ sidebarViewMode: mode });
    },

    setSidebarInitialEndpoint: (endpoint) => {
      set({ sidebarInitialEndpoint: endpoint });
    },
    setSidebarInitialDatasetId: (id) => {
      set({ sidebarInitialDatasetId: id });
    },

    // ========== RESET ==========
    
    resetWorkspace: () => {
      const newTab = createDefaultTab();
      set({
        tabs: [newTab],
        activeTabId: newTab.id,
        fieldConfigs: [],
        objectTypeFilter: null,
        dateFrom: null,
        dateTo: null,
        period: null,
        limit: null,
        fieldPickerOpen: true,
        sidebarViewMode: 'explorer',
        lastUpdated: new Date().toISOString(),
      });
    },
  };
};
