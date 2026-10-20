import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '@/services/api';
import type { ChatThread, Message } from '../types';
import { useChatStreamStore } from '../stores/chatStreamStore';
import { useTabChatState } from './useTabChatState';
import { debugLog } from '../utils/debugLog';

interface UseCanvasChatOptions {
  activeTabId?: string;
  processId?: string;
  isOpen: boolean;
  isLoaded: boolean;
  getToken: () => Promise<string | null>;
  tabThreadId?: string | null;
  onTabThreadIdChange?: (threadId: string) => void;
}

interface UseCanvasChatReturn {
  threads: ChatThread[];
  currentThreadId: string | null;
  loadingThreads: boolean;
  isThreadMenuOpen: boolean;
  setIsThreadMenuOpen: (open: boolean) => void;
  setCurrentThreadId: (id: string | null) => void;
  loadThreads: () => Promise<ChatThread[]>;
  loadThreadMessages: (threadId: string) => Promise<Message[]>;
  createNewThread: () => Promise<string | null>;
  deleteThread: (threadId: string) => Promise<void>;
  updateThread: (threadId: string, updates: { title?: string; pinned?: boolean }) => Promise<void>;
}

export function useCanvasChat({
  activeTabId,
  processId,
  isOpen,
  isLoaded,
  getToken,
  tabThreadId,
  onTabThreadIdChange,
}: UseCanvasChatOptions): UseCanvasChatReturn {
  const { threads, loadingThreads, currentThreadId, threadIds } = useTabChatState(activeTabId);
  const [isThreadMenuOpen, setIsThreadMenuOpen] = useState(false);

  // Initialize activeThreadId from tabThreadId when tab first gets state
  useEffect(() => {
    if (activeTabId && tabThreadId && !currentThreadId) {
      const s = useChatStreamStore.getState();
      s.setActiveThreadId(activeTabId, tabThreadId);
      s.addThreadToTab(activeTabId, tabThreadId);
    }
  }, [activeTabId, tabThreadId, currentThreadId]);

  const setCurrentThreadId = useCallback((id: string | null) => {
    if (!activeTabId) return;
    const s = useChatStreamStore.getState();
    s.setActiveThreadId(activeTabId, id);
    if (id) {
      s.addThreadToTab(activeTabId, id);
      onTabThreadIdChange?.(id);
    }
  }, [activeTabId, onTabThreadIdChange]);

  const loadThreads = useCallback(async () => {
    if (!activeTabId) return [];
    const s = useChatStreamStore.getState();
    s.setLoadingThreads(activeTabId, true);
    try {
      const token = await getToken();

      const response = await fetch(`${API_BASE}/api/canvas/chat/threads`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Cache-Control': 'no-cache',
        },
      });

      if (response.ok) {
        const data = await response.json();
        const loadedThreads: ChatThread[] = (data.threads || []).map((t: any) => ({
          id: t.id,
          process_id: t.last_process_id || '',
          title: t.title || `Chat ${new Date(t.created_at).toLocaleDateString()}`,
          pinned: t.pinned || false,
          created_at: t.created_at,
          updated_at: t.updated_at,
        }));
        // Only show threads that belong to this tab
        const tabState = s.tabStates[activeTabId];
        const knownIds = new Set(tabState?.threadIds ?? []);
        if (tabThreadId) knownIds.add(tabThreadId);
        const tabThreads = knownIds.size > 0
          ? loadedThreads.filter(t => knownIds.has(t.id))
          : [];
        s.setThreads(activeTabId, tabThreads);

        return tabThreads;
      }
    } catch (error) {
      console.error('Failed to load threads:', error);
    } finally {
      useChatStreamStore.getState().setLoadingThreads(activeTabId, false);
    }
    return [];
  }, [getToken, activeTabId, tabThreadId]);

  const loadThreadMessages = useCallback(async (threadId: string): Promise<Message[]> => {
    try {
      const token = await getToken();

      const response = await fetch(`${API_BASE}/api/canvas/chat/threads/${threadId}/messages`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        const loadedMessages: Message[] = (data.messages || []).map((m: any) => {
          debugLog('LoadMessages', { id: m.id, role: m.role, hasMetadata: !!m.metadata, toolEvents: m.metadata?.toolEvents?.length ?? 0, reasoning: m.metadata?.reasoningSegments?.length ?? 0 });
          return {
            id: m.id,
            role: m.role as 'user' | 'assistant',
            content: m.content,
            created_at: m.created_at,
            toolEvents: m.metadata?.toolEvents || [],
            reasoningSegments: m.metadata?.reasoningSegments || [],
            reasoningTimestamps: m.metadata?.reasoningTimestamps || [],
          };
        });
        return loadedMessages;
      }
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
    return [];
  }, [getToken]);

  const createNewThread = useCallback(async (): Promise<string | null> => {
    if (!activeTabId) return null;
    try {
      const token = await getToken();

      const response = await fetch(`${API_BASE}/api/canvas/chat/threads`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: 'New Chat' }),
      });

      if (!response.ok) throw new Error('Failed to create thread');

      const data = await response.json();
      const newThread: ChatThread = {
        id: data.id,
        process_id: '',
        title: data.title || 'New Chat',
        pinned: data.pinned || false,
        created_at: data.created_at,
        updated_at: data.updated_at,
      };

      const s = useChatStreamStore.getState();
      s.addThreadToTab(activeTabId, newThread.id);
      const current = s.tabStates[activeTabId]?.threads ?? [];
      s.setThreads(activeTabId, [newThread, ...current]);
      s.setActiveThreadId(activeTabId, newThread.id);
      onTabThreadIdChange?.(newThread.id);
      return newThread.id;
    } catch (error) {
      console.error('Failed to create thread:', error);
      return null;
    }
  }, [getToken, activeTabId, onTabThreadIdChange]);

  const deleteThread = useCallback(async (threadId: string): Promise<void> => {
    if (!activeTabId) return;
    try {
      const token = await getToken();

      const response = await fetch(`${API_BASE}/api/canvas/chat/threads/${threadId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) throw new Error(`Delete failed: ${response.status}`);

      useChatStreamStore.getState().removeThread(threadId);
    } catch (error) {
      console.error('Failed to delete thread:', error);
    }
  }, [getToken, activeTabId]);

  const updateThread = useCallback(async (
    threadId: string,
    updates: { title?: string; pinned?: boolean }
  ): Promise<void> => {
    if (!activeTabId) return;

    // Update local store immediately so the UI reflects changes right away
    const s = useChatStreamStore.getState();
    const current = s.tabStates[activeTabId]?.threads ?? [];
    const updated = current.map(t =>
      t.id === threadId
        ? {
            ...t,
            ...updates,
            updated_at: new Date().toISOString(),
          }
        : t
    ).sort((a, b) => {
      if (a.pinned !== b.pinned) return b.pinned ? 1 : -1;
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    });
    s.setThreads(activeTabId, updated);

    // Persist to backend (best-effort — backend may already have the update from SSE title generation)
    try {
      const token = await getToken();
      await fetch(`${API_BASE}/api/canvas/chat/threads/${threadId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(updates),
      });
    } catch (error) {
      console.error('Failed to persist thread update:', error);
    }
  }, [getToken, activeTabId]);

  // Load threads when panel opens or tab changes
  useEffect(() => {
    if (isOpen && isLoaded && activeTabId) {
      loadThreads();
    }
  }, [isOpen, isLoaded, activeTabId, loadThreads]);

  return {
    threads,
    currentThreadId,
    loadingThreads,
    isThreadMenuOpen,
    setIsThreadMenuOpen,
    setCurrentThreadId,
    loadThreads,
    loadThreadMessages,
    createNewThread,
    deleteThread,
    updateThread,
  };
}
