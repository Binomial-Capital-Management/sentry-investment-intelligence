/**
 * useToolTab - Hook that provides store-backed state for a tool workflow tab.
 *
 * Reads/writes ToolTabState from the Zustand store for a given tabId.
 * Manages side effects: fetching tools, portfolios, running tools, saving processes.
 * This replaces the ~20 useState calls in the original ToolWorkflow.tsx.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { API_BASE } from '@/services/api';
import { useDataWorkspaceStore } from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';
import { selectCurrentToolState } from '@/features/canvas/data-workspace/stores/selectors';
import { inferInputType, getMinTickers } from '@/features/canvas/types';
import type { Tool, Portfolio, Step } from '@/features/canvas/types';
import type { ToolTabState, PerToolState } from '@/features/canvas/data-workspace/stores/types';

export interface UseToolTabReturn {
  // Tool tab state (from store)
  toolState: ToolTabState;
  update: (updates: Partial<ToolTabState>) => void;
  setToolId: (toolId: string) => void;

  // Fetched data (local, shared across tool tabs)
  tools: Tool[];
  loadingTools: boolean;
  portfolios: Portfolio[];
  loadingPortfolios: boolean;

  // Derived
  selectedTool: Tool | undefined;
  inputType: ReturnType<typeof inferInputType>;
  canProceed: boolean;
  /** Non-null when current inputs fail pre-run validation (e.g. not enough tickers) */
  validationError: string | null;

  // Local UI state (not worth persisting in store)
  runningTime: number;
  showParams: boolean;
  setShowParams: (v: boolean) => void;
  isEditingName: boolean;
  setIsEditingName: (v: boolean) => void;
  editNameValue: string;
  setEditNameValue: (v: string) => void;
  showDeleteConfirm: boolean;
  setShowDeleteConfirm: (v: boolean) => void;
  isDeleting: boolean;
  isGraphView: boolean;
  setIsGraphView: (v: boolean) => void;
  loadingProcess: boolean;

  // Actions
  setStep: (step: Step) => void;
  runTool: () => Promise<void>;
  handleSave: () => Promise<void>;
  handleRenameProcess: () => Promise<void>;
  handleDeleteProcess: () => Promise<void>;
  handleRerun: () => void;
  fetchProcess: (processId: string) => Promise<void>;
  downloadChartPng: (divId: string, filename: string) => Promise<void>;
  downloadStatsCsv: () => void;
  downloadStatsExcel: () => void;
}

// Default assembled state for tabs with no tool selected yet
const EMPTY_TOOL_STATE: ToolTabState = {
  toolId: '',
  toolStep: 1,
  toolParams: {},
  manualTickers: '',
  selectedPortfolioId: '',
  toolResults: [],
  activeResultId: null,
  error: null,
  isRunning: false,
  isSaving: false,
};

export function useToolTab(tabId?: string): UseToolTabReturn {
  const { getToken, isLoaded } = useAuth();

  // Local state for when no tab exists (mirrors EMPTY_TOOL_STATE)
  const [localToolState, setLocalToolState] = useState<ToolTabState>(EMPTY_TOOL_STATE);

  // Assemble current-tool state from the tab's pointer + per-tool slice
  const storeToolState = useDataWorkspaceStore(state => {
    if (!tabId) return null;
    const tab = state.tabs.find(t => t.id === tabId);
    return selectCurrentToolState(tab) ?? EMPTY_TOOL_STATE;
  });

  const toolState = storeToolState ?? localToolState;

  const setCurrentToolId = useDataWorkspaceStore(s => s.setCurrentToolId);
  const updatePerToolState = useDataWorkspaceStore(s => s.updatePerToolState);

  const setToolId = useCallback(
    (toolId: string) => {
      if (tabId) {
        setCurrentToolId(tabId, toolId);
      } else {
        setLocalToolState(prev => ({ ...prev, toolId }));
      }
    },
    [tabId, setCurrentToolId],
  );

  // Routes toolId changes to setCurrentToolId; everything else merges into the
  // current tool's slice. Allows existing call sites that bundle toolId with
  // other fields to continue working with the new shape. Editing inputs
  // (tickers/portfolio/params) auto-clears any stale error from the last run.
  const update = useCallback(
    (updates: Partial<ToolTabState>) => {
      if (!tabId) {
        // No tab — update local state
        setLocalToolState(prev => {
          const { toolId, ...rest } = updates;
          const next = { ...prev, ...rest };
          if (toolId !== undefined) next.toolId = toolId;
          const touchesInputs =
            'manualTickers' in rest || 'selectedPortfolioId' in rest || 'toolParams' in rest;
          if (touchesInputs && !('error' in rest)) next.error = null;
          return next;
        });
        return;
      }
      const { toolId, ...rest } = updates;
      if (toolId !== undefined) setCurrentToolId(tabId, toolId);
      if (Object.keys(rest).length > 0) {
        const touchesInputs =
          'manualTickers' in rest || 'selectedPortfolioId' in rest || 'toolParams' in rest;
        const patch: Partial<PerToolState> =
          touchesInputs && !('error' in rest) ? { ...rest, error: null } : rest;
        updatePerToolState(tabId, patch as Partial<PerToolState>);
      }
    },
    [tabId, setCurrentToolId, updatePerToolState],
  );

  // Fetched data — shared across tool tabs, local to this hook instance
  const [tools, setTools] = useState<Tool[]>([]);
  const [loadingTools, setLoadingTools] = useState(true);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loadingPortfolios, setLoadingPortfolios] = useState(false);

  // Ephemeral UI state (not persisted in store)
  const [runningTime, setRunningTime] = useState(0);
  const [showParams, setShowParams] = useState(false);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editNameValue, setEditNameValue] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isGraphView, setIsGraphView] = useState(false);
  const [loadingProcess, setLoadingProcess] = useState(false);

  // Derived values
  const selectedTool = useMemo(() => tools.find(t => t.id === toolState.toolId), [tools, toolState.toolId]);
  const inputType = useMemo(() => inferInputType(selectedTool?.params_schema || {}), [selectedTool]);
  const canProceed = useMemo(() => {
    const { toolStep: step, toolId, selectedPortfolioId, manualTickers } = toolState;
    if (step === 1) return !!toolId;
    if (step === 2) return inputType === 'none' || !!(selectedPortfolioId || manualTickers.trim());
    return true;
  }, [toolState, inputType]);

  const validationError = useMemo<string | null>(() => {
    if (!selectedTool || inputType === 'none') return null;
    if (toolState.selectedPortfolioId) return null;
    const tickers = toolState.manualTickers.split(/[,\s]+/).map(t => t.trim()).filter(Boolean);
    if (inputType === 'single_ticker') {
      return tickers.length === 0 ? 'Select a ticker to continue' : null;
    }
    // Both 'tickers' and 'portfolio' modes accept manual tickers — enforce the
    // schema's min when the user is going the tickers route (no portfolio).
    if (inputType === 'tickers' || inputType === 'portfolio') {
      if (tickers.length === 0) {
        return inputType === 'portfolio'
          ? 'Select a portfolio or enter tickers'
          : 'Enter at least one ticker';
      }
      const min = getMinTickers(selectedTool.params_schema || {}) ?? 1;
      if (tickers.length < min) {
        return `${selectedTool.name} requires at least ${min} ticker${min === 1 ? '' : 's'}`;
      }
    }
    return null;
  }, [selectedTool, inputType, toolState.manualTickers, toolState.selectedPortfolioId]);

  // ===== Side effects =====

  // Running timer
  useEffect(() => {
    if (!toolState.isRunning) return;
    setRunningTime(0);
    const interval = setInterval(() => setRunningTime(t => t + 1), 1000);
    return () => clearInterval(interval);
  }, [toolState.isRunning]);

  // Fetch tools on mount
  useEffect(() => {
    if (!isLoaded) return;
    (async () => {
      setLoadingTools(true);
      try {
        const token = await getToken();
        const res = await fetch(`${API_BASE}/api/canvas/tools`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setTools((await res.json()).tools || []);
      } catch (e) {
        console.error('[useToolTab] Failed to fetch tools:', e);
      } finally {
        setLoadingTools(false);
      }
    })();
  }, [isLoaded, getToken]);

  // Fetch portfolios on mount
  useEffect(() => {
    if (!isLoaded) return;
    (async () => {
      setLoadingPortfolios(true);
      try {
        const token = await getToken();
        const res = await fetch(`${API_BASE}/api/portfolios`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const d = await res.json();
          setPortfolios(Array.isArray(d) ? d : []);
        }
      } catch (e) {
        console.error('[useToolTab] Failed to fetch portfolios:', e);
      } finally {
        setLoadingPortfolios(false);
      }
    })();
  }, [isLoaded, getToken]);

  // Per-tool state naturally preserves params across tool switches — no reset
  // effect needed. Each tool keeps its own params in perToolState[toolId].

  // ===== Actions =====

  const setStep = useCallback(
    (step: Step) => update({ toolStep: step }),
    [update],
  );

  const runTool = useCallback(async () => {
    update({ isRunning: true, error: null });
    try {
      const token = await getToken();
      const tickers = toolState.manualTickers
        .split(/[,\s]+/)
        .map(t => t.trim().toUpperCase())
        .filter(Boolean);
      const params: Record<string, any> = { ...toolState.toolParams };
      const schema = selectedTool?.params_schema || {};
      const it = inferInputType(schema);
      if (it !== 'none') {
        if (toolState.selectedPortfolioId) {
          params.portfolio_id = toolState.selectedPortfolioId;
        } else if (tickers.length) {
          if (it === 'single_ticker') {
            if ('underlying' in schema) params.underlying = tickers[0];
            else if ('ticker' in schema) params.ticker = tickers[0];
            else params.tickers = tickers;
          } else {
            params.tickers = tickers;
            if (toolState.toolParams.weights?.length === tickers.length)
              params.weights = toolState.toolParams.weights;
          }
        } else {
          update({ isRunning: false, error: 'Select portfolio or enter tickers' });
          return;
        }
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000);
      const res = await fetch(`${API_BASE}/api/canvas/run/${toolState.toolId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(params),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const data = await res.json();
      if (data.status === 'error') {
        update({ error: data.error || 'Failed', isRunning: false });
      } else {
        data.params = toolState.toolParams;
        const chartKeys = data.charts
          ? Object.keys(data.charts).filter((k: string) => data.charts[k]?.plotly)
          : [];
        const localId = `result-${Date.now()}`;
        const resultTickers: string[] = data.tickers || tickers;
        const activeChart = chartKeys.length > 0 ? chartKeys[0] : 'stats';

        const store = useDataWorkspaceStore.getState();

        // Auto-create a tab if none exists (like addDatasetWithMetadata does for Sources)
        let resolvedTabId = tabId;
        if (!resolvedTabId || !store.tabs.find(t => t.id === resolvedTabId)) {
          const toolName = selectedTool?.name || toolState.toolId;
          resolvedTabId = store.addTab('single', toolName, 'tools');
          store.setCurrentToolId(resolvedTabId, toolState.toolId);
          // Transfer local state to the new tab
          store.updatePerToolState(resolvedTabId, {
            manualTickers: toolState.manualTickers,
            selectedPortfolioId: toolState.selectedPortfolioId,
            toolParams: toolState.toolParams,
          });
        }

        const tab = store.tabs.find(t => t.id === resolvedTabId);
        const groupId = tab?.activeAnalysisGroupId ?? tab?.activeGroupId;
        store.addToolResult(resolvedTabId, toolState.toolId, {
          localId,
          result: data,
          toolId: toolState.toolId,
          processName: '',
          processId: null,
          tickers: resultTickers,
          activeChart,
          groupId,
        });
        update({ isRunning: false, error: null, toolStep: 4 });
        store.setContentView(resolvedTabId, { type: 'tool-result', toolTabId: resolvedTabId, resultLocalId: localId });

        // Auto-save to database so AI re-runs, rename, delete all work immediately
        try {
          const saveToken = await getToken();
          const name = `${selectedTool?.name || data.tool_id} - ${resultTickers.slice(0, 3).join(', ') || 'Analysis'}`;
          const saveRes = await fetch(`${API_BASE}/api/canvas/processes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${saveToken}` },
            body: JSON.stringify({
              tool_id: data.tool_id || toolState.toolId,
              name,
              tickers: resultTickers,
              weights: data.weights || [],
              metrics: data.metrics || {},
              metric_cards: data.metric_cards || [],
              stats_table: data.stats_table || [],
              charts: data.charts || {},
              hmm_enabled: data.hmm_enabled || false,
              current_regime: data.current_regime,
              params: data.params || {},
            }),
          });
          if (saveRes.ok) {
            const saved = await saveRes.json();
            store.patchToolResult(resolvedTabId, toolState.toolId, localId, { processId: saved.id, processName: name });
          }
        } catch {
          // Auto-save failed silently — process still works unsaved
        }
      }
    } catch (e: any) {
      update({
        error: e.name === 'AbortError' ? 'Request timed out' : e.message || 'Failed',
        isRunning: false,
      });
    }
  }, [toolState, selectedTool, getToken, update, tabId]);

  const activeEntry = (toolState.toolResults ?? []).find(r => r.localId === toolState.activeResultId) ?? null;

  const handleSave = useCallback(async () => {
    if (!tabId || !activeEntry || activeEntry.processId || toolState.isSaving) return;
    update({ isSaving: true });
    try {
      const token = await getToken();
      const result = activeEntry.result;
      const tickers = result.tickers || [];
      const name = `${selectedTool?.name || result.tool_id} - ${tickers.slice(0, 3).join(', ') || 'Analysis'}`;
      const res = await fetch(`${API_BASE}/api/canvas/processes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          tool_id: result.tool_id,
          name,
          tickers,
          weights: result.weights || [],
          metrics: result.metrics || {},
          metric_cards: result.metric_cards || [],
          stats_table: result.stats_table || [],
          charts: result.charts || {},
          hmm_enabled: result.hmm_enabled || false,
          current_regime: result.current_regime,
          params: result.params || {},
        }),
      });
      if (res.ok) {
        const data = await res.json();
        useDataWorkspaceStore.getState().patchToolResult(tabId, toolState.toolId, activeEntry.localId, { processId: data.id, processName: name });
        update({ isSaving: false });
      } else {
        update({ error: 'Failed to save', isSaving: false });
      }
    } catch {
      update({ error: 'Failed to save', isSaving: false });
    }
  }, [tabId, activeEntry, toolState.isSaving, selectedTool, getToken, update]);

  const handleRenameProcess = useCallback(async () => {
    if (!tabId || !activeEntry?.processId || !editNameValue.trim()) return;
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/api/canvas/processes/${activeEntry.processId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: editNameValue.trim() }),
      });
      if (res.ok) {
        useDataWorkspaceStore.getState().patchToolResult(tabId, toolState.toolId, activeEntry.localId, { processName: editNameValue.trim() });
        setIsEditingName(false);
      }
    } catch (e) {
      console.error('[useToolTab] Failed to rename:', e);
    }
  }, [tabId, activeEntry, editNameValue, getToken]);

  const handleDeleteProcess = useCallback(async () => {
    if (!tabId || !activeEntry?.processId) return;
    setIsDeleting(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/api/canvas/processes/${activeEntry.processId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setShowDeleteConfirm(false);
        const store = useDataWorkspaceStore.getState();
        const remaining = (toolState.toolResults ?? []).filter(r => r.localId !== activeEntry.localId);
        update({ toolResults: remaining, activeResultId: remaining[remaining.length - 1]?.localId ?? null, toolStep: remaining.length === 0 ? 1 : 4 });
        if (remaining.length === 0) {
          store.setContentView(tabId, { type: 'data' });
        }
      }
    } catch (e) {
      console.error('[useToolTab] Failed to delete:', e);
    } finally {
      setIsDeleting(false);
    }
  }, [tabId, activeEntry, toolState.toolResults, getToken, update]);

  const handleRerun = useCallback(() => {
    update({ toolStep: 3 });
  }, [update]);

  const fetchProcess = useCallback(async (processId: string) => {
    if (!tabId) return;
    setLoadingProcess(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/api/canvas/processes/${processId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const process = await res.json();
        const newToolId: string = process.tool_id || '';
        if (newToolId) setCurrentToolId(tabId, newToolId);
        updatePerToolState(tabId, {
          manualTickers: process.tickers?.join(', ') || '',
          toolParams: {
            ...process.params,
            ...(process.weights?.length ? { weights: process.weights } : {}),
          },
        });
        if (process.charts || process.metrics || process.stats_table) {
          const chartKeys = process.charts
            ? Object.keys(process.charts).filter((k: string) => process.charts[k]?.plotly)
            : [];
          const localId = `fetched-${processId}`;
          const store = useDataWorkspaceStore.getState();
          const alreadyPresent = store.tabs
            .find(t => t.id === tabId)
            ?.perToolState?.[newToolId]?.toolResults.some(r => r.processId === processId);
          if (!alreadyPresent) {
            const fetchedTab = store.tabs.find(t => t.id === tabId);
            const fetchedGroupId = fetchedTab?.activeAnalysisGroupId ?? fetchedTab?.activeGroupId;
            store.addToolResult(tabId, newToolId, {
              localId,
              result: {
                id: process.id,
                tool_id: process.tool_id,
                tickers: process.tickers,
                weights: process.weights,
                metrics: process.metrics,
                charts: process.charts,
                stats_table: process.stats_table,
                metric_cards: process.metric_cards,
                params: process.params,
                hmm_enabled: process.hmm_enabled,
                current_regime: process.current_regime,
              },
              toolId: process.tool_id || '',
              processName: process.name || '',
              processId: process.id,
              tickers: process.tickers || [],
              activeChart: chartKeys.length > 0 ? chartKeys[0] : 'stats',
              groupId: fetchedGroupId,
            });
            store.setContentView(tabId, { type: 'tool-result', toolTabId: tabId, resultLocalId: localId });
          }
          update({ toolStep: 4 });
        } else {
          update({ toolStep: 3 });
        }
      } else {
        update({ error: 'Failed to load process' });
      }
    } catch (e) {
      console.error('[useToolTab] Failed to fetch process:', e);
      update({ error: 'Failed to load process' });
    } finally {
      setLoadingProcess(false);
    }
  }, [getToken, update, tabId, setCurrentToolId, updatePerToolState]);

  const downloadChartPng = useCallback(async (divId: string, filename: string) => {
    const plotEl = document.getElementById(divId);
    if (plotEl && (plotEl as any)._fullLayout) {
      const Plotly = await import('react-plotly.js').then(
        m => (m.default as any).Plotly || (window as any).Plotly,
      );
      if (Plotly?.toImage) {
        Plotly.toImage(plotEl, { format: 'png', width: 1200, height: 600, scale: 2 }).then(
          (dataUrl: string) => {
            const a = document.createElement('a');
            a.href = dataUrl;
            a.download = `${filename}.png`;
            a.click();
          },
        );
      }
    }
  }, []);

  const downloadStatsCsv = useCallback(() => {
    const result = activeEntry?.result;
    if (!result?.stats_table) return;
    const headers = ['Category', 'Metric', 'Value', '%'];
    const rows = result.stats_table.map((r: any) => [r.category, r.metric, r.value, r.pct || '']);
    const csv = [headers.join(','), ...rows.map((r: string[]) => r.map(c => `"${c}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${toolState.toolId}_stats_${(result.tickers || []).slice(0, 3).join('_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [activeEntry, toolState.toolId]);

  const downloadStatsExcel = useCallback(() => {
    const result = activeEntry?.result;
    if (!result?.stats_table) return;
    const html = `
      <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">
      <head><meta charset="UTF-8"></head>
      <body>
        <table border="1">
          <thead><tr><th>Category</th><th>Metric</th><th>Value</th><th>%</th></tr></thead>
          <tbody>
            ${result.stats_table.map((r: any) =>
              `<tr><td>${r.category}</td><td>${r.metric}</td><td>${r.value}</td><td>${r.pct || ''}</td></tr>`,
            ).join('')}
          </tbody>
        </table>
      </body></html>`;
    const blob = new Blob([html], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${toolState.toolId}_stats_${(result.tickers || []).slice(0, 3).join('_')}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  }, [activeEntry, toolState.toolId]);

  return {
    toolState,
    update,
    setToolId,
    tools,
    loadingTools,
    portfolios,
    loadingPortfolios,
    selectedTool,
    inputType,
    canProceed,
    validationError,
    runningTime,
    showParams,
    setShowParams,
    isEditingName,
    setIsEditingName,
    editNameValue,
    setEditNameValue,
    showDeleteConfirm,
    setShowDeleteConfirm,
    isDeleting,
    isGraphView,
    setIsGraphView,
    loadingProcess,
    setStep,
    runTool,
    handleSave,
    handleRenameProcess,
    handleDeleteProcess,
    handleRerun,
    fetchProcess,
    downloadChartPng,
    downloadStatsCsv,
    downloadStatsExcel,
  };
}
