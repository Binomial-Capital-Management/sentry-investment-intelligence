/**
 * DataWorkspace - Full data exploration and dataset creation component
 * 
 * Orchestrates:
 * - Sidebar: Object types and portfolios
 * - Tabs: Isolated workflow contexts
 * - SingleObjectForm: Dataset creation form
 * - PropertyTable: Data display
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { ChevronRight } from 'lucide-react';
import { useAuth } from '@clerk/clerk-react';
import {
  useDataWorkspaceStore,
  selectDatasets,
  selectSymbols,
  selectFields,
  selectDatasetGroups,
} from './stores/dataWorkspaceStore';
import { selectCurrentToolState, selectActiveGroupDatasets, selectMergedDatasetIds, selectMergeAnchorDatasetId } from './stores/selectors';
import { DatasetTable as PropertyTable, DatasetsDropdown } from './dataset-viewer';
import { PivotTable as PivotTableView } from './pivot-table';
import ChartTabView from './chart';
import CanvasAIChatPanel from '@/features/canvas/shared/AIChat';
import { ToolResultsContent } from '@/features/canvas/tool-workflow/components';
import type { DataContext } from '@/features/canvas/shared/AIChat/types';
import type { Toast } from '@/features/canvas/types';
import * as chatStreamManager from '@/features/canvas/shared/AIChat/services/chatStreamManager';
import { useChatStreamStore } from '@/features/canvas/shared/AIChat/stores/chatStreamStore';

// Import extracted hooks
import { useTabPersistence } from './hooks/useTabPersistence';

// Import extracted components
import {
  TabBar,
  WorkspaceSidebar,
} from './components';
import ArchivedTabsMenu from './components/ArchivedTabsMenu';
import { ToolEmptyState } from './components/EmptyState';

interface DataWorkspaceProps {
  onBack: () => void;
  /** Auto-create a tool tab on mount (used when entering from landing page "Tool Workflow" button) */
  autoCreateToolTab?: boolean;
}

// Helper function
const detectObjectType = (symbol: string, exchange?: string): string => {
  const sym = symbol.toUpperCase();
  if (sym === '_MARKET_' || sym === 'MARKET' || sym === '') return 'market';
  if (sym.includes('-USD') || sym.includes('USDT') || sym.endsWith('BTC') || sym.endsWith('ETH')) return 'crypto';
  if (sym.match(/^[A-Z]{3}\/[A-Z]{3}$/) || (sym.match(/^[A-Z]{6}$/) && !exchange)) return 'forex';
  if (exchange && ['ARCA', 'BATS'].includes(exchange.toUpperCase())) return 'etf';
  return 'equity';
};


export default function DataWorkspace({ onBack, autoCreateToolTab }: DataWorkspaceProps) {
  const { getToken } = useAuth();

  // ===== Zustand Store State =====
  // Using selectors for derived state (migrated from flat state)
  const workspaceObjects = useDataWorkspaceStore(selectSymbols);
  const workspaceFields = useDataWorkspaceStore(selectFields);
  const workspaceTypeFilter = useDataWorkspaceStore(s => s.objectTypeFilter);
  const workspaceDateFrom = useDataWorkspaceStore(s => s.dateFrom);
  const workspaceDateTo = useDataWorkspaceStore(s => s.dateTo);
  const workspacePeriod = useDataWorkspaceStore(s => s.period);
  const workspaceLimit = useDataWorkspaceStore(s => s.limit);
  const addWorkspaceObject = useDataWorkspaceStore(s => s.addObject);
  const setWorkspaceTypeFilter = useDataWorkspaceStore(s => s.setObjectTypeFilter);
  const setDateRange = useDataWorkspaceStore(s => s.setDateRange);
  const resetWorkspace = useDataWorkspaceStore(s => s.resetWorkspace);
  const workspaceDatasets = useDataWorkspaceStore(selectDatasets);
  const activeGroupDatasets = useDataWorkspaceStore(selectActiveGroupDatasets);
  const datasetGroups = useDataWorkspaceStore(selectDatasetGroups);
  const updateDataset = useDataWorkspaceStore(s => s.updateDataset);
  const addDatasetWithMetadata = useDataWorkspaceStore(s => s.addDatasetWithMetadata);
  const createDatasetGroup = useDataWorkspaceStore(s => s.createDatasetGroup);
  const addDatasetToGroup = useDataWorkspaceStore(s => s.addDatasetToGroup);
  
  // Additional store selectors
  const clearWorkspaceObjects = useDataWorkspaceStore(s => s.clearObjects);
  const removeDataset = useDataWorkspaceStore(s => s.removeDataset);
  const renameTab = useDataWorkspaceStore(s => s.renameTab);
  const workspaceTabs = useDataWorkspaceStore(s => s.tabs) || [];
  const activeTabId = useDataWorkspaceStore(s => s.activeTabId);
  const removeTabRaw = useDataWorkspaceStore(s => s.removeTab);
  const removeTab = (tabId: string) => {
    chatStreamManager.destroyTab(tabId);
    useChatStreamStore.getState().removeTab(tabId);
    removeTabRaw(tabId);
  };
  const setActiveWorkspaceTab = useDataWorkspaceStore(s => s.setActiveTab);
  const addWorkspaceTab = useDataWorkspaceStore(s => s.addTab);
  const reorderTabs = useDataWorkspaceStore(s => s.reorderTabs);
  const updateTabType = useDataWorkspaceStore(s => s.updateTabType);
  const setTabMode = useDataWorkspaceStore(s => s.setTabMode);
  const setViewMode = useDataWorkspaceStore(s => s.setViewMode);
  const saveTabFormState = useDataWorkspaceStore(s => s.saveTabFormState);

  const fieldPickerOpen = useDataWorkspaceStore(s => s.fieldPickerOpen);
  const setFieldPickerOpen = useDataWorkspaceStore(s => s.setFieldPickerOpen);
  const activeViewMode = useDataWorkspaceStore(s => s.sidebarViewMode);
  const setSidebarViewMode = useDataWorkspaceStore(s => s.setSidebarViewMode);
  const setCurrentToolId = useDataWorkspaceStore(s => s.setCurrentToolId);
  const updatePerToolState = useDataWorkspaceStore(s => s.updatePerToolState);
  const setSidebarInitialEndpoint = useDataWorkspaceStore(s => s.setSidebarInitialEndpoint);
  const setSidebarInitialDatasetId = useDataWorkspaceStore(s => s.setSidebarInitialDatasetId);

  // Computed: active workspace tab
  const activeWorkspaceTab = useMemo(() =>
    workspaceTabs.find(t => t.id === activeTabId) || null
  , [workspaceTabs, activeTabId]);

  const activeContentView = activeWorkspaceTab?.contentView ?? { type: 'data' as const };
  const setContentView = useDataWorkspaceStore(s => s.setContentView);

  // Build unified data context for AI Chat — includes data tabs AND tool tabs
  // so the AI has full awareness of everything in the workspace
  const dataContext = useMemo((): DataContext | null => {
    const tab = activeWorkspaceTab;
    if (!tab) return null;

    const chartResults = (tab.chartResults ?? []).map(cr => ({ ...cr, tabId: tab.id, tabName: tab.name }));
    const inlinePivots = (tab.pivotResults ?? []).map(pr => ({ ...pr, tabId: tab.id, tabName: tab.name }));
    const inlineTools = Object.entries(tab.perToolState ?? {}).flatMap(([toolId, pts]) =>
      (pts.toolResults ?? []).map(tr => ({ ...tr, tabId: tab.id, tabName: tab.name, toolId, pts }))
    );
    const isToolTab = ((tab.viewMode || tab.type) === 'tools' || tab.type === 'tool') && selectCurrentToolState(tab);

    if (workspaceDatasets.length === 0 && chartResults.length === 0 && inlinePivots.length === 0 && inlineTools.length === 0 && !isToolTab) {
      return null;
    }

    const descParts: string[] = [];
    if (workspaceDatasets.length > 0) descParts.push(`${workspaceDatasets.length} dataset(s)`);
    if (chartResults.length > 0) descParts.push(`${chartResults.length} chart(s)`);
    if (inlinePivots.length > 0) descParts.push(`${inlinePivots.length} pivot table(s)`);
    const totalTools = (isToolTab ? 1 : 0) + inlineTools.length;
    if (totalTools > 0) descParts.push(`${totalTools} tool analysis(es)`);

    const tools: DataContext['tools'] & {} = [];

    // Legacy: dedicated tool tab with active tool state
    if (isToolTab) {
      const ts = selectCurrentToolState(tab)!;
      const results = ts.toolResults ?? [];
      const activeResult = results.find(r => r.localId === ts.activeResultId) ?? null;
      tools.push({
        tabId: tab.id,
        tabName: tab.name,
        toolId: ts.toolId,
        tickers: ts.manualTickers?.split(',').map(s => s.trim()).filter(Boolean) || [],
        step: ts.toolStep,
        hasResults: results.length > 0,
        processId: activeResult?.processId ?? null,
        processName: activeResult?.processName ?? '',
        metricCards: activeResult?.result?.metric_cards?.slice(0, 10)?.map(mc => ({
          label: mc.label,
          value: mc.value,
          type: mc.type,
        })),
        params: ts.toolParams,
      });
    }

    // Inline tool results on this tab
    if (!isToolTab) {
      for (const itr of inlineTools) {
        tools.push({
          tabId: itr.tabId,
          tabName: itr.tabName,
          toolId: itr.toolId,
          tickers: itr.tickers ?? [],
          step: 4,
          hasResults: true,
          processId: itr.processId ?? null,
          processName: itr.processName ?? '',
          metricCards: itr.result?.metric_cards?.slice(0, 10)?.map((mc: any) => ({
            label: mc.label,
            value: mc.value,
            type: mc.type,
          })),
          params: itr.pts.toolParams,
        });
      }
    }

    return {
      type: 'workspace',
      datasets: workspaceDatasets.map(ds => ({
        id: ds.id,
        tabId: tab.id,
        symbol: ds.symbol,
        endpoint: ds.endpoint,
        fields: ds.fields,
        groupId: ds.groupId,
      })),
      charts: chartResults.map(cr => ({
        id: cr.localId,
        name: cr.name,
        chartType: cr.config?.chartType,
      })),
      pivots: inlinePivots.map(pr => ({
        id: pr.localId,
        name: pr.name,
        tabId: pr.tabId,
        groupId: pr.groupId,
        rows: pr.config.rows,
        columns: pr.config.columns,
        values: pr.config.values?.map(v => ({ field: v.field, aggregation: v.aggregation })),
      })),
      tools,
      symbols: [...new Set(workspaceDatasets.map(ds => ds.symbol))],
      activeTabId: activeTabId || undefined,
      activeTabType: activeViewMode || tab.type,
      description: `${tab.name}: ${descParts.join(', ')}`,
      datasetGroups: (tab.datasetGroups ?? []).map(g => ({
        id: g.id,
        name: g.name,
        datasetCount: (tab.datasets ?? []).filter(d => d.groupId === g.id).length,
      })),
      activeGroupId: tab.activeGroupId ?? undefined,
      contentView: activeContentView,
      sidebarViewMode: activeViewMode,
    };
  }, [workspaceDatasets, activeTabId, activeWorkspaceTab, activeViewMode]);

  // Listen for AI-initiated tool analysis results — create a new tool tab with results
  useEffect(() => {
    const handler = (event: CustomEvent<{
      tool_id: string;
      tool_name: string;
      tickers: string[];
      result: any;
      activeTabId?: string;
    }>) => {
      const { tool_id, tool_name, tickers, result } = event.detail;

      // Create a new tool tab with the analysis results
      const store = useDataWorkspaceStore.getState();
      const tabName = tool_name || `${tool_id} Analysis`;
      const newTabId = store.addTab('single', tabName, 'tools');

      const chartKeys = result.charts
        ? Object.keys(result.charts).filter((k: string) => result.charts[k]?.plotly)
        : [];

      const localId = `ai-result-${Date.now()}`;
      store.setCurrentToolId(newTabId, tool_id);
      store.updatePerToolState(newTabId, {
        manualTickers: tickers.join(', '),
        toolParams: result.params || {},
        toolStep: 4,
      });
      const newTab = store.tabs.find(t => t.id === newTabId);
      const newTabGroupId = newTab?.activeAnalysisGroupId ?? newTab?.activeGroupId;
      store.addToolResult(newTabId, tool_id, {
        localId,
        result: {
          tool_id,
          tickers,
          weights: result.weights,
          metrics: result.metrics,
          charts: result.charts,
          stats_table: result.stats_table,
          metric_cards: result.metric_cards,
          params: result.params,
          hmm_enabled: result.hmm_enabled,
          current_regime: result.current_regime,
          regime_params: result.regime_params,
        },
        toolId: tool_id,
        processName: `${tabName} - ${tickers.slice(0, 3).join(', ') || 'Analysis'}`,
        processId: null,
        tickers,
        activeChart: chartKeys.length > 0 ? chartKeys[0] : 'stats',
        groupId: newTabGroupId,
      });
      store.setContentView(newTabId, { type: 'tool-result', toolTabId: newTabId, resultLocalId: localId });
    };

    window.addEventListener('tool-analysis-complete', handler as EventListener);
    return () => window.removeEventListener('tool-analysis-complete', handler as EventListener);
  }, []);

  // PropertyTable: stays mounted for header portaling whenever there's data
  const hasPropertyTableData = workspaceObjects.length > 0 || fieldPickerOpen || activeWorkspaceTab?.mode === 'data';

  // Whether the tab has datasets (used to enable/disable pivot/chart modes)
  const hasDatasets = (activeWorkspaceTab?.datasets?.length ?? 0) > 0;


  // Tool results for DatasetsDropdown — flatten all results across every tool in every tab
  const toolResultsForDropdown = useMemo(() => {
    return workspaceTabs.flatMap(t =>
      Object.values(t.perToolState ?? {}).flatMap(pts =>
        (pts.toolResults ?? []).map(tr => ({
          tabId: t.id,
          localId: tr.localId,
          toolId: tr.toolId,
          processName: tr.processName || t.name,
          tickers: tr.tickers,
          groupId: tr.groupId,
        }))
      )
    );
  }, [workspaceTabs]);

  // Pivot results for the active tab — rendered nested under their DatasetGroup
  const pivotResultsForDropdown = useMemo(() => {
    return (activeWorkspaceTab?.pivotResults ?? []).map(pv => {
      const rowCount = pv.config.rows?.length ?? 0;
      const colCount = pv.config.columns?.length ?? 0;
      const valCount = pv.config.values?.length ?? 0;
      const summary = [
        rowCount > 0 ? `${rowCount} row${rowCount === 1 ? '' : 's'}` : null,
        colCount > 0 ? `${colCount} col${colCount === 1 ? '' : 's'}` : null,
        valCount > 0 ? `${valCount} val${valCount === 1 ? '' : 's'}` : null,
      ].filter(Boolean).join(' · ');
      return {
        tabId: activeWorkspaceTab!.id,
        localId: pv.localId,
        name: pv.name,
        summary: summary || undefined,
        groupId: pv.groupId,
      };
    });
  }, [activeWorkspaceTab]);

  // Chart results for the active tab — rendered nested under their DatasetGroup
  const chartResultsForDropdown = useMemo(() => {
    return (activeWorkspaceTab?.chartResults ?? []).map(cr => {
      const seriesCount = cr.config.ySeries?.length ?? 0;
      const summary = [
        cr.config.chartType,
        seriesCount > 0 ? `${seriesCount} series` : null,
      ].filter(Boolean).join(' · ');
      return {
        tabId: activeWorkspaceTab!.id,
        localId: cr.localId,
        name: cr.name,
        chartType: cr.config.chartType,
        summary: summary || undefined,
        groupId: cr.groupId,
      };
    });
  }, [activeWorkspaceTab]);

  // ===== Local UI State =====
  const [toast, setToast] = useState<Toast | null>(null);
  
  // View state (table vs ontology) - derived from store
  const activeView = activeWorkspaceTab?.activeView ?? 'table';
  const updateTabView = useDataWorkspaceStore(s => s.updateTabView);
  const setActiveView = useCallback((view: 'table' | 'ontology') => {
    if (activeTabId) updateTabView(activeTabId, view);
  }, [activeTabId, updateTabView]);
  
  
  // Ref for PropertyTable to register its navigate-to-dataset callback
  const navigateToDatasetRef = useRef<((endpoint: string) => void) | null>(null);

  // Track which dataset DatasetTable is currently viewing (for dropdown highlighting)
  const [viewingDataset, setViewingDataset] = useState<import('./stores/types').DatasetConfig | null>(null);

  // Merge state from store — shared between DatasetsDropdown and PropertyTable
  const mergedDatasetIdsArray = useDataWorkspaceStore(selectMergedDatasetIds);
  const mergedDatasetIdsSet = useMemo(() => new Set(mergedDatasetIdsArray), [mergedDatasetIdsArray]);
  const toggleMergeDataset = useDataWorkspaceStore(s => s.toggleMergeDataset);
  const mergeAnchorDatasetId = useDataWorkspaceStore(selectMergeAnchorDatasetId);

  // Portal refs for shared header card — mode-specific content renders into these
  const headerLeftSlotRef = useRef<HTMLDivElement>(null);
  const headerRightSlotRef = useRef<HTMLDivElement>(null);

  // Tab renaming state
  const [renamingTabId, setRenamingTabId] = useState<string | null>(null);
  const [renamingTabName, setRenamingTabName] = useState('');
  
  // AI Chat Panel (persisted to localStorage, defaults to open)
  const [showAIPanel, setShowAIPanel] = useState(() => {
    const stored = localStorage.getItem('aiChatPanelOpen');
    return stored !== null ? stored === 'true' : true;
  });
  
  // Persist AI panel state to localStorage
  useEffect(() => {
    localStorage.setItem('aiChatPanelOpen', String(showAIPanel));
  }, [showAIPanel]);
  
  // Track pending tab (created when opening form, removed if cancelled)
  const [pendingTabId, setPendingTabId] = useState<string | null>(null);
  
  // NOTE: isRestoringRef and saveTimeoutRef are no longer needed.
  // Form state is now stored directly in the store via formStateSlice.

  // ===== Use Extracted Hooks =====

  // Per-tab backend persistence (auto-save, soft-delete, restore)
  const {
    archivedTabs,
    fetchArchivedTabs,
    restoreTab,
    permanentDeleteTab,
    isInitializing,
  } = useTabPersistence(getToken);

  // Auto-create a tool tab when entering from landing page "Tool Workflow" button
  useEffect(() => {
    if (autoCreateToolTab && !isInitializing) {
      addWorkspaceTab('single', 'New Analysis', 'tools');
    }
  }, [isInitializing]); // eslint-disable-line react-hooks/exhaustive-deps

  // ===== Effects =====
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);


  // Auto-open sources panel when workspace has no tabs
  useEffect(() => {
    if (workspaceTabs.length === 0 && !fieldPickerOpen) {
      setFieldPickerOpen(true);
    }
  }, [workspaceTabs.length, fieldPickerOpen, setFieldPickerOpen]);

  const handleResetWorkspace = useCallback(() => {
    resetWorkspace();
    setWorkspaceTypeFilter('all');
  }, [resetWorkspace, setWorkspaceTypeFilter]);

  const openSingleObjectForm = useCallback((createNewTab = true) => {
    if (createNewTab) {
      if (pendingTabId) {
        removeTab(pendingTabId);
      }
      addWorkspaceTab('single', 'New Tab');
      // Go straight to data view — sidebar handles symbol selection
      setPendingTabId(null);
    }
    // Open the Add Data sidebar so user can pick symbol + endpoint
    setFieldPickerOpen(true);
  }, [addWorkspaceTab, pendingTabId, removeTab, setFieldPickerOpen]);


  return (
    <div className="bg-white flex flex-col overflow-hidden" style={{ zoom: 1.2, height: 'calc(100vh / 1.2)', width: 'calc(100vw / 1.2)' }}>
      {/* Tab Bar (primary top bar — spans full width above content + AI chat) */}
      <TabBar
            workspaceTabs={workspaceTabs}
            activeTabId={activeTabId}
            addWorkspaceTab={addWorkspaceTab}
            setActiveWorkspaceTab={setActiveWorkspaceTab}
            renameTab={renameTab}
            reorderTabs={reorderTabs}
            removeTab={removeTab}
            renamingTabId={renamingTabId}
            setRenamingTabId={setRenamingTabId}
            renamingTabName={renamingTabName}
            setRenamingTabName={setRenamingTabName}
            openNewTab={openSingleObjectForm}
            workspaceMenuSlot={
              <ArchivedTabsMenu
                archivedTabs={archivedTabs}
                onOpen={fetchArchivedTabs}
                onRestore={restoreTab}
                onPermanentDelete={permanentDeleteTab}
              />
            }
            rightSlot={null}
      />

      {/* Main Content (below tab bar) */}
      <div className="flex-1 overflow-hidden flex p-1.5 pt-0" style={{ background: '#E3E3E3' }}>
        <div className="flex-1 flex gap-2 bg-white rounded-xl overflow-hidden relative p-2">
        {/* Persistent sidebar — stays mounted across all modes */}
        <WorkspaceSidebar
          viewMode={activeViewMode}
          tabId={activeTabId ?? undefined}
          onModeChange={(mode) => {
            setSidebarViewMode(mode);
            if (activeTabId) setViewMode(activeTabId, mode);
          }}
          selectedObjects={workspaceObjects}
          onRemoveDataset={removeDataset}
          onNavigateToDataset={(ep) => {
            // Adding a new endpoint should pull the user out of tool-result view
            // back to the data table so the new dataset is actually visible.
            if (activeTabId && activeContentView.type !== 'data') {
              setContentView(activeTabId, { type: 'data' });
            }
            navigateToDatasetRef.current?.(ep);
          }}
        />

        {/* Persistent content panel — header + content cards */}
        <div className="flex-1 flex flex-col min-w-0 gap-2">
          {/* SHARED HEADER CARD */}
          <div
            className="flex-shrink-0 overflow-hidden"
            style={{
              backgroundColor: 'white',
              borderRadius: '1.5rem',
              boxShadow: '0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)',
              border: '1px solid hsl(30 3.3% 11.8% / 15%)',
            }}
          >
            <div className="px-3 flex items-center justify-between gap-3 flex-shrink-0" style={{ height: 44 }}>
              <div className="flex items-center gap-2 min-w-0 overflow-hidden">
                {!fieldPickerOpen && (
                  <button
                    onClick={() => setFieldPickerOpen(true)}
                    className="flex items-center justify-center flex-shrink-0 px-2.5 py-1 rounded-md text-xs transition-colors"
                    title="Show Sources panel"
                    style={{ color: 'hsl(30 3.3% 11.8% / 45%)' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <ChevronRight size={16} strokeWidth={2} />
                  </button>
                )}
                {/* DatasetsDropdown — always visible regardless of content view */}
                <div className="flex-shrink-0">
                  <DatasetsDropdown
                    onRemove={removeDataset}
                    onNavigate={(ep) => navigateToDatasetRef.current?.(ep)}
                    onOpenSidebarWithEndpoint={(endpoint, datasetId) => {
                      setSidebarInitialEndpoint(endpoint);
                      setSidebarInitialDatasetId(datasetId ?? null);
                      setFieldPickerOpen(true);
                    }}
                    toolResults={toolResultsForDropdown}
                    onToolResultClick={(localId) => {
                      let foundToolId: string | undefined;
                      let foundResult: import('@/features/canvas/data-workspace/stores/types').TabToolResult | undefined;
                      const owner = workspaceTabs.find(t => {
                        for (const [toolId, pts] of Object.entries(t.perToolState ?? {})) {
                          const r = pts.toolResults?.find(r => r.localId === localId);
                          if (r) {
                            foundToolId = toolId;
                            foundResult = r;
                            return true;
                          }
                        }
                        return false;
                      });
                      if (owner && activeTabId) {
                        setContentView(activeTabId, { type: 'tool-result', toolTabId: owner.id, resultLocalId: localId });
                        setSidebarViewMode('tools');
                        setViewMode(activeTabId, 'tools');
                        if (foundToolId) setCurrentToolId(activeTabId, foundToolId);
                        if (foundResult) {
                          updatePerToolState(activeTabId, {
                            manualTickers: foundResult.tickers.join(', '),
                            toolParams: foundResult.result.params || {},
                          });
                        }
                      }
                    }}
                    onSwitchToDataView={() => {
                      if (activeTabId) {
                        setContentView(activeTabId, { type: 'data' });
                        setSidebarViewMode('explorer');
                        setViewMode(activeTabId, 'explorer');
                      }
                    }}
                    activeContentView={activeContentView}
                    currentDataset={viewingDataset ?? activeGroupDatasets[0]}
                    pivotResults={pivotResultsForDropdown}
                    onPivotClick={(localId) => {
                      if (activeTabId) {
                        setContentView(activeTabId, { type: 'pivot', pivotLocalId: localId });
                        setSidebarViewMode('pivot');
                        setViewMode(activeTabId, 'pivot');
                      }
                    }}
                    chartResults={chartResultsForDropdown}
                    onChartClick={(localId) => {
                      if (activeTabId) {
                        setContentView(activeTabId, { type: 'chart', chartLocalId: localId });
                        setSidebarViewMode('chart');
                        setViewMode(activeTabId, 'chart');
                      }
                    }}
                    mergedDatasetIds={mergedDatasetIdsSet}
                    mergeAnchorDatasetId={mergeAnchorDatasetId}
                    onToggleMerge={toggleMergeDataset}
                  />
                </div>
                {/* Portal slot for mode-specific left header content */}
                <div ref={headerLeftSlotRef} className="flex items-center gap-2 min-w-0 overflow-hidden" />
              </div>
              {/* Portal slot for mode-specific right header content */}
              <div ref={headerRightSlotRef} className="flex items-center gap-1 flex-shrink-0" />
            </div>
          </div>

          {/* SHARED CONTENT CARD */}
          <div
            className="flex-1 flex flex-col overflow-hidden min-h-0"
            style={{
              position: 'relative',
              backgroundColor: 'white',
              borderRadius: '1.5rem',
              boxShadow: '0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)',
              border: '1px solid hsl(30 3.3% 11.8% / 15%)',
            }}
          >
            {isInitializing ? (
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
            ) : (
              <>
                {/* PropertyTable: stays mounted when data exists (portals header), hidden when not explorer */}
                {hasPropertyTableData && (
                  <PropertyTable
                    symbols={workspaceObjects.map(o => o.symbol)}
                    objectType={workspaceObjects[0]?.objectType}
                    selectedObjects={workspaceObjects}
                    dateFrom={workspaceDateFrom || undefined}
                    dateTo={workspaceDateTo || undefined}
                    period={workspacePeriod || undefined}
                    limit={workspaceLimit || undefined}
                    onRemoveDataset={removeDataset}
                    onResetWorkspace={handleResetWorkspace}
                    onToggleOntology={() => setActiveView(activeView === 'ontology' ? 'table' : 'ontology')}
                    ontologyActive={activeView === 'ontology'}
                    showAIPanel={showAIPanel}
                    onToggleAIPanel={() => setShowAIPanel(true)}
                    registerNavigateToDataset={(fn) => { navigateToDatasetRef.current = fn; }}
                    headerLeftPortal={headerLeftSlotRef.current}
                    headerRightPortal={headerRightSlotRef.current}
                    hidden={activeContentView.type !== 'data'}
                    onCurrentDatasetChange={setViewingDataset}
                  />
                )}

                {/* Tool result content */}
                {activeContentView.type === 'tool-result' && (
                  Object.values(activeWorkspaceTab?.perToolState ?? {}).some(pts =>
                    pts.toolResults?.some(r => r.localId === activeContentView.resultLocalId)
                  )
                    ? <ToolResultsContent
                        tabId={activeContentView.toolTabId}
                        resultLocalId={activeContentView.resultLocalId}
                        headerLeftPortal={headerLeftSlotRef.current}
                        headerRightPortal={headerRightSlotRef.current}
                        showAIPanel={showAIPanel}
                        onToggleAIPanel={() => setShowAIPanel(true)}
                      />
                    : <ToolEmptyState />
                )}

                {/* Pivot table content */}
                {activeContentView.type === 'pivot' && activeTabId && (
                  <PivotTableView
                    tabId={activeTabId}
                    pivotLocalId={activeContentView.pivotLocalId}
                    headerLeftPortal={headerLeftSlotRef.current}
                    headerRightPortal={headerRightSlotRef.current}
                    showAIPanel={showAIPanel}
                    onToggleAIPanel={() => setShowAIPanel(true)}
                  />
                )}

                {activeContentView.type === 'chart' && activeTabId && (
                  <ChartTabView
                    tabId={activeTabId}
                    chartLocalId={activeContentView.chartLocalId}
                    headerLeftPortal={headerLeftSlotRef.current}
                    headerRightPortal={headerRightSlotRef.current}
                    showAIPanel={showAIPanel}
                    onToggleAIPanel={() => setShowAIPanel(true)}
                  />
                )}

                {activeContentView.type === 'data' && !hasDatasets && (
                  <div style={{
                    position: 'absolute', inset: 0,
                    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    gap: '0.75rem', pointerEvents: 'none',
                  }}>
                    <div style={{
                      width: 56, height: 56, borderRadius: '50%',
                      backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {activeViewMode === 'tools' ? (
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="hsl(60 2.5% 23.3% / 30%)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                        </svg>
                      ) : (
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="hsl(60 2.5% 23.3% / 30%)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                          <ellipse cx="12" cy="5" rx="9" ry="3" />
                          <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
                          <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
                        </svg>
                      )}
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '0.938rem', fontWeight: 500, color: 'hsl(60 2.5% 23.3% / 50%)', marginBottom: '0.375rem' }}>
                        {activeViewMode === 'tools' ? 'No analysis results' : 'No data sources'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'hsl(60 2.5% 23.3% / 30%)' }}>
                        {activeViewMode === 'tools' ? 'Select a tool and run an analysis' : 'Add datasets in Sources first'}
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}

          </div>
        </div>

        {/* AI Chat Panel - same level as all panels */}
        <CanvasAIChatPanel
          isOpen={showAIPanel}
          onClose={() => setShowAIPanel(false)}
          process={null}
          dataContext={dataContext}
          activeTabId={activeTabId || undefined}
          onEnsureTab={() => addWorkspaceTab('single')}
          tabThreadId={activeWorkspaceTab?.chatThreadId}
          onTabThreadIdChange={(threadId) => {
            if (!activeTabId) return;
            const store = useDataWorkspaceStore.getState();
            store.setChatThreadId(activeTabId, threadId);
            store.addChatThreadId(activeTabId, threadId);
          }}
          onResultUpdate={(newResult) => {
            // Route tool re-run results to the active tool tab's current tool
            if (activeViewMode !== 'tools' || !activeTabId) return;
            const ts = selectCurrentToolState(activeWorkspaceTab);
            if (!ts) return;
            const activeEntry = (ts.toolResults ?? []).find(r => r.localId === ts.activeResultId);
            if (!activeEntry) return;
            useDataWorkspaceStore.getState().patchToolResult(activeTabId, ts.toolId, activeEntry.localId, {
              result: {
                ...activeEntry.result,
                ...newResult,
                charts: newResult.charts || activeEntry.result.charts,
                metric_cards: newResult.metric_cards || activeEntry.result.metric_cards,
                stats_table: newResult.stats_table || activeEntry.result.stats_table,
                params: newResult.params || activeEntry.result.params,
              },
            });
          }}
        />
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-lg text-sm font-medium z-50 ${
          toast.type === 'success' ? 'bg-emerald-500 text-white' :
          toast.type === 'error' ? 'bg-red-500 text-white' :
          'bg-blue-500 text-white'
        }`}>
          {toast.message}
        </div>
      )}


    </div>
  );
}
