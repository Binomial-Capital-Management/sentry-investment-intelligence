/**
 * ToolWorkflow - Standalone wrapper for the tool workflow wizard.
 *
 * Creates a temporary tool tab in the Zustand store, renders ToolWorkflowContent
 * inside its own header + AI chat panel. Used when navigating to /canvas?mode=tool.
 *
 * For embedded usage inside DataWorkspace tabs, use ToolWorkflowContent directly.
 */

import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { API_BASE } from '@/services/api';
import CanvasAIChatPanel from '@/features/canvas/shared/AIChat';
import { useDataWorkspaceStore } from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';
import ToolWorkflowContent from './ToolWorkflowContent';
import { useToolTab } from './hooks/useToolTab';
import type { EditProcess } from '@/features/canvas/types';
import type { SavedProcess } from '@/features/canvas/shared/AIChat/types';

interface ToolWorkflowProps {
  onBack: () => void;
  loadProcessId?: string | null;
}

export default function ToolWorkflow({ onBack, loadProcessId }: ToolWorkflowProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { getToken, isLoaded } = useAuth();
  const editProcess: EditProcess | null = location.state?.editProcess || null;

  // Create a temporary tool tab in the store for this standalone view.
  // Must use effect (not useState init) so strict mode remount re-creates the tab
  // after the cleanup from the first mount removes it.
  const [tabId, setTabId] = useState<string | null>(null);

  useEffect(() => {
    const id = useDataWorkspaceStore.getState().addTab('tool', 'Tool Workflow');
    setTabId(id);
    return () => {
      useDataWorkspaceStore.getState().removeTab(id);
      setTabId(null);
    };
  }, []);

  // Apply editProcess from navigation state on mount
  useEffect(() => {
    if (editProcess && tabId) {
      const store = useDataWorkspaceStore.getState();
      store.setCurrentToolId(tabId, editProcess.tool_id);
      store.updatePerToolState(tabId, {
        manualTickers: editProcess.tickers?.join(', ') || '',
        toolParams: {
          ...editProcess.params,
          ...(editProcess.weights?.length ? { weights: editProcess.weights } : {}),
        },
        toolStep: 3,
      });
    }
  }, [editProcess, tabId]);

  // Use the hook to read state for header display + AI chat
  const { toolState, update } = useToolTab(tabId ?? '');
  const activeEntry = (toolState.toolResults ?? []).find(r => r.localId === toolState.activeResultId) ?? null;

  // AI Chat Panel state
  const [showAIPanel, setShowAIPanel] = useState(() => {
    const stored = localStorage.getItem('aiChatPanelOpen');
    return stored !== null ? stored === 'true' : true;
  });
  useEffect(() => {
    localStorage.setItem('aiChatPanelOpen', String(showAIPanel));
  }, [showAIPanel]);

  // Process switcher state
  const [savedToolProcesses, setSavedToolProcesses] = useState<SavedProcess[]>([]);
  const [showProcessSwitcher, setShowProcessSwitcher] = useState(false);

  // Fetch saved tool processes for switcher
  useEffect(() => {
    if (!isLoaded) return;
    (async () => {
      try {
        const token = await getToken();
        const res = await fetch(`${API_BASE}/api/canvas/processes?limit=50`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setSavedToolProcesses(
            (data.processes || []).filter(
              (p: any) => p.process_type !== 'data_workspace' && p.tool_id !== 'data_workspace',
            ),
          );
        }
      } catch (e) {
        console.error('Failed to fetch saved processes:', e);
      }
    })();
  }, [isLoaded, getToken]);

  // All hooks above — early return below is safe
  if (!tabId) {
    return (
      <div className="h-full bg-slate-50 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-slate-200 border-t-slate-600 rounded-full animate-spin" />
      </div>
    );
  }

  const handleSwitchProcess = (processId: string) => {
    setShowProcessSwitcher(false);
    navigate(`/canvas?mode=tool&workspace=${processId}`, { replace: true });
    update({ toolResults: [], activeResultId: null });
  };

  const handleDeleteFromSwitcher = async (processId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/api/canvas/processes/${processId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setSavedToolProcesses(prev => prev.filter(p => p.id !== processId));
        const activeEntry = (toolState.toolResults ?? []).find(r => r.localId === toolState.activeResultId);
        if (activeEntry?.processId === processId) {
          const remaining = (toolState.toolResults ?? []).filter(r => r.processId !== processId);
          update({ toolResults: remaining, activeResultId: remaining[remaining.length - 1]?.localId ?? null, toolStep: remaining.length === 0 ? 1 : 4 });
        }
      }
    } catch (e) {
      console.error('Failed to delete from switcher:', e);
    }
  };

  return (
    <div className="h-full bg-slate-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="p-2 hover:bg-slate-100 rounded text-slate-500">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          {/* Process Switcher */}
          {toolState.currentProcessId && savedToolProcesses.length > 1 && (
            <div className="relative">
              <button
                onClick={() => setShowProcessSwitcher(!showProcessSwitcher)}
                className="flex items-center gap-2 px-3 py-2 text-xs font-medium bg-white border border-slate-200 rounded hover:border-slate-300 transition-colors"
              >
                <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <span className="text-slate-700 max-w-[150px] truncate">{toolState.processName || 'Select'}</span>
                <span className="text-slate-400 text-[10px]">({savedToolProcesses.length})</span>
                <svg className={`w-3.5 h-3.5 text-slate-400 transition-transform ${showProcessSwitcher ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showProcessSwitcher && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowProcessSwitcher(false)} />
                  <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-slate-200 rounded shadow-lg z-50 max-h-80 overflow-hidden flex flex-col">
                    <div className="px-3 py-2 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
                      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">
                        Saved Processes ({savedToolProcesses.length})
                      </span>
                      <button onClick={() => setShowProcessSwitcher(false)} className="text-slate-400 hover:text-slate-600">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <div className="overflow-y-auto flex-1">
                      {savedToolProcesses.map(p => (
                        <div
                          key={p.id}
                          className={`w-full px-3 py-2.5 flex items-center gap-3 border-b border-slate-50 last:border-0 transition-colors group
                            ${toolState.currentProcessId === p.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}
                        >
                          <button
                            onClick={() => p.id && handleSwitchProcess(p.id)}
                            className="flex-1 flex items-center gap-3 text-left min-w-0"
                          >
                            <div className={`w-2 h-2 rounded-full shrink-0 ${toolState.currentProcessId === p.id ? 'bg-blue-500' : 'bg-slate-200'}`} />
                            <div className="flex-1 min-w-0">
                              <div className={`text-xs font-medium truncate ${toolState.currentProcessId === p.id ? 'text-blue-700' : 'text-slate-800'}`}>
                                {p.name || `${(p.tickers || []).slice(0, 2).join(', ')}${(p.tickers || []).length > 2 ? ` +${p.tickers.length - 2}` : ''}`}
                              </div>
                              <div className="text-[10px] text-slate-400 flex items-center gap-1.5 mt-0.5">
                                <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-500">{p.tool_id}</span>
                                {p.updated_at && <span>{new Date(p.updated_at).toLocaleDateString()}</span>}
                              </div>
                            </div>
                          </button>
                          <div className="flex items-center gap-1 shrink-0">
                            {toolState.currentProcessId === p.id && (
                              <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            )}
                            <button
                              onClick={e => p.id && handleDeleteFromSwitcher(p.id, e)}
                              className="p-1 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Delete process"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          <div>
            <h1 className="text-base font-medium text-slate-900 tracking-tight">
              {toolState.currentProcessId && toolState.processName
                ? toolState.processName
                : editProcess
                  ? `Edit: ${editProcess.tool_id}`
                  : 'Tool Workflow'}
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              {toolState.currentProcessId
                ? toolState.toolId
                : 'Select a tool to begin'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAIPanel(!showAIPanel)}
            className={`px-3 py-2 text-xs font-medium transition-colors flex items-center gap-2 rounded-md ${
              showAIPanel
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'text-gray-700 hover:bg-gray-100 border border-gray-200'
            }`}
            title={showAIPanel ? 'Close AI Panel' : 'Open AI Panel'}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            AI Chat
          </button>
        </div>
      </header>

      {/* Content + AI Panel Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main Content */}
        <ToolWorkflowContent tabId={tabId} loadProcessId={loadProcessId} />

        {/* AI Chat Panel */}
        <CanvasAIChatPanel
          isOpen={showAIPanel}
          onClose={() => setShowAIPanel(false)}
          process={toolState.toolStep === 4 ? (activeEntry?.result as any) : null}
          onResultUpdate={(newResult) => {
            if (!tabId || !activeEntry) return;
            useDataWorkspaceStore.getState().patchToolResult(tabId, toolState.toolId, activeEntry.localId, {
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
  );
}
