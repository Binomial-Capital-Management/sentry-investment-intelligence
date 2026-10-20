import { useState, useEffect, useRef, useCallback } from 'react';
import api from '@/services/api';
import { useDataWorkspaceStore } from '../stores/dataWorkspaceStore';
import { useChatStreamStore } from '@/features/canvas/shared/AIChat/stores/chatStreamStore';
import type { WorkspaceTab } from '../stores/types';

export interface ArchivedTab {
  id: string;
  name: string;
  archivedAt: string;
  tabType: string;
  datasetCount: number;
}

interface UseTabPersistenceReturn {
  archivedTabs: ArchivedTab[];
  fetchArchivedTabs: () => Promise<void>;
  restoreTab: (processId: string) => Promise<void>;
  permanentDeleteTab: (processId: string) => Promise<void>;
  isInitializing: boolean;
}

const AUTOSAVE_DEBOUNCE_MS = 1500;

function serializeTab(tab: WorkspaceTab) {
  const { backendId, ...config } = tab;
  return {
    name: tab.name,
    tool_id: 'tab',
    process_type: 'tab',
    tickers: tab.symbols?.map(s => s.symbol) || [],
    params: {},
    config,
  };
}

function deserializeTab(process: any): WorkspaceTab {
  const config = process.config || {};
  return {
    ...config,
    id: config.id || `tab-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    backendId: process.id,
    name: process.name || config.name || 'Untitled',
    type: config.type || 'single',
    datasets: config.datasets || [],
    symbols: config.symbols || [],
    activeView: config.activeView || 'table',
    createdAt: config.createdAt || Date.now(),
  };
}

export function useTabPersistence(
  getToken: () => Promise<string | null>,
): UseTabPersistenceReturn {
  const [archivedTabs, setArchivedTabs] = useState<ArchivedTab[]>([]);
  const [isInitializing, setIsInitializing] = useState(true);

  const saveTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const pendingCreationsRef = useRef<Set<string>>(new Set());
  const initializedRef = useRef(false);
  const hydratedRef = useRef(false);

  const debouncedSave = useCallback(async (tab: WorkspaceTab) => {
    if (!tab.backendId) return;

    const existing = saveTimersRef.current.get(tab.id);
    if (existing) clearTimeout(existing);

    const timer = setTimeout(async () => {
      saveTimersRef.current.delete(tab.id);
      try {
        const token = await getToken();
        await api.put(`/api/canvas/processes/${tab.backendId}`, serializeTab(tab), {
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (e) {
        console.error('Tab auto-save failed:', e);
      }
    }, AUTOSAVE_DEBOUNCE_MS);

    saveTimersRef.current.set(tab.id, timer);
  }, [getToken]);

  const createTabOnBackend = useCallback(async (tab: WorkspaceTab) => {
    if (tab.backendId || pendingCreationsRef.current.has(tab.id)) return;
    pendingCreationsRef.current.add(tab.id);

    try {
      const token = await getToken();
      const res = await api.post('/api/canvas/processes', serializeTab(tab), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.data?.id) {
        useDataWorkspaceStore.getState().setTabBackendId(tab.id, res.data.id);
      }
    } catch (e) {
      console.error('Failed to create tab on backend:', e);
    } finally {
      pendingCreationsRef.current.delete(tab.id);
    }
  }, [getToken]);

  const archiveTabOnBackend = useCallback(async (backendId: string) => {
    try {
      const token = await getToken();
      await api.delete(`/api/canvas/processes/${backendId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (e) {
      console.error('Failed to archive tab:', e);
    }
  }, [getToken]);

  // Initial hydration from backend
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    (async () => {
      try {
        const token = await getToken();
        const res = await api.get('/api/canvas/processes', {
          headers: { Authorization: `Bearer ${token}` },
          params: { process_type: 'tab', archived: false },
        });

        const processes = res.data?.processes || [];

        if (processes.length > 0) {
          const tabs = processes.map(deserializeTab);
          useDataWorkspaceStore.getState().loadTabs(tabs);

          // loadTabs remaps IDs, so re-read the store
          // backendId is already set by deserializeTab and preserved through loadTabs spread
          const loadedTabs = useDataWorkspaceStore.getState().tabs;

          // Seed chatStreamStore with persisted thread IDs so all threads survive refresh
          const chatStore = useChatStreamStore.getState();
          for (const tab of loadedTabs) {
            const allThreadIds = [...(tab.chatThreadIds || [])];
            if (tab.chatThreadId && !allThreadIds.includes(tab.chatThreadId)) {
              allThreadIds.push(tab.chatThreadId);
            }
            for (const threadId of allThreadIds) {
              chatStore.addThreadToTab(tab.id, threadId);
            }
            if (tab.chatThreadId) {
              chatStore.setActiveThreadId(tab.id, tab.chatThreadId);
            }
          }
        } else {
          // No backend tabs — persist any existing localStorage tabs
          const currentTabs = useDataWorkspaceStore.getState().tabs;
          for (const tab of currentTabs) {
            if (!tab.backendId) {
              await createTabOnBackend(tab);
            }
          }
        }

      } catch (e) {
        console.error('Failed to hydrate tabs from backend:', e);
      } finally {
        hydratedRef.current = true;
        setIsInitializing(false);
      }
    })();
  }, [getToken, createTabOnBackend]);

  // Subscribe to store changes for auto-save, tab creation, and tab archival
  useEffect(() => {
    const buildSnapshot = (tabs: WorkspaceTab[]) =>
      new Map(tabs.map(t => [t.id, t]));

    let prevSnapshot = buildSnapshot(useDataWorkspaceStore.getState().tabs);

    const unsub = useDataWorkspaceStore.subscribe((state) => {
      if (!hydratedRef.current) {
        prevSnapshot = buildSnapshot(state.tabs);
        return;
      }

      const currentSnapshot = buildSnapshot(state.tabs);

      // Detect removed tabs (soft-delete) and add to archived list immediately
      for (const [id, prevTab] of prevSnapshot) {
        if (!currentSnapshot.has(id) && prevTab.backendId) {
          archiveTabOnBackend(prevTab.backendId);
          setArchivedTabs(prev => [{
            id: prevTab.backendId!,
            name: prevTab.name,
            archivedAt: new Date().toISOString(),
            tabType: prevTab.type,
            datasetCount: prevTab.datasets?.length || 0,
          }, ...prev]);
        }
      }

      // Detect new tabs (create) and changed tabs (auto-save)
      for (const [id, tab] of currentSnapshot) {
        const prevTab = prevSnapshot.get(id);

        if (!prevTab) {
          if (!tab.backendId) {
            createTabOnBackend(tab);
          }
        } else if (tab.backendId) {
          if (tab !== prevTab) {
            debouncedSave(tab);
          }
        }
      }

      prevSnapshot = currentSnapshot;
    });

    return () => {
      unsub();
      // Flush pending saves on unmount
      for (const timer of saveTimersRef.current.values()) {
        clearTimeout(timer);
      }
    };
  }, [createTabOnBackend, archiveTabOnBackend, debouncedSave]);

  const fetchArchivedTabs = useCallback(async () => {
    try {
      const token = await getToken();
      const res = await api.get('/api/canvas/processes', {
        headers: { Authorization: `Bearer ${token}` },
        params: { process_type: 'tab', archived: true },
      });

      const processes = res.data?.processes || [];
      // Filter out any that are currently active in the store
      const activeBackendIds = new Set(
        useDataWorkspaceStore.getState().tabs
          .map(t => t.backendId)
          .filter(Boolean)
      );
      setArchivedTabs(processes
        .filter((p: any) => !activeBackendIds.has(p.id))
        .map((p: any) => ({
          id: p.id,
          name: p.name || p.config?.name || 'Untitled',
          archivedAt: p.archived_at,
          tabType: p.config?.type || 'single',
          datasetCount: p.config?.datasets?.length || 0,
        })));
    } catch (e) {
      console.error('Failed to fetch archived tabs:', e);
    }
  }, [getToken]);

  const restoreTab = useCallback(async (processId: string) => {
    try {
      const token = await getToken();
      await api.post(`/api/canvas/processes/${processId}/restore`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });

      const res = await api.get(`/api/canvas/processes/${processId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      const tab = deserializeTab(res.data);
      useDataWorkspaceStore.getState().insertTab(tab);

      // Seed chatStreamStore with all thread IDs so chat history is restored
      const allThreadIds = tab.chatThreadIds || [];
      if (tab.chatThreadId && !allThreadIds.includes(tab.chatThreadId)) {
        allThreadIds.push(tab.chatThreadId);
      }
      if (allThreadIds.length > 0) {
        const chatStore = useChatStreamStore.getState();
        for (const threadId of allThreadIds) {
          chatStore.addThreadToTab(tab.id, threadId);
        }
        if (tab.chatThreadId) {
          chatStore.setActiveThreadId(tab.id, tab.chatThreadId);
        }
      }

      setArchivedTabs(prev => prev.filter(t => t.id !== processId));
    } catch (e) {
      console.error('Failed to restore tab:', e);
    }
  }, [getToken]);

  const permanentDeleteTab = useCallback(async (processId: string) => {
    try {
      const token = await getToken();
      await api.delete(`/api/canvas/processes/${processId}`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { permanent: true },
      });
      setArchivedTabs(prev => prev.filter(t => t.id !== processId));
    } catch (e) {
      console.error('Failed to permanently delete tab:', e);
    }
  }, [getToken]);

  return {
    archivedTabs,
    fetchArchivedTabs,
    restoreTab,
    permanentDeleteTab,
    isInitializing,
  };
}
