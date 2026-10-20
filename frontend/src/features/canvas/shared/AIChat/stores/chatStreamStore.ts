import { create } from 'zustand';
import type { ToolEvent } from '@/types';
import type { Message, ChatThread, PendingUpdate, AgentAction } from '../types';

// ---------------------------------------------------------------------------
// Tab-level state (per workspace tab)
// ---------------------------------------------------------------------------

export interface TabState {
  activeThreadId: string | null;
  threadIds: string[];
  threads: ChatThread[];
  loadingThreads: boolean;
}

const DEFAULT_TAB_STATE: TabState = {
  activeThreadId: null,
  threadIds: [],
  threads: [],
  loadingThreads: false,
};

// ---------------------------------------------------------------------------
// Thread-level state (per conversation thread)
// ---------------------------------------------------------------------------

export interface ThreadState {
  messages: Message[];
  toolEvents: ToolEvent[];
  isLoading: boolean;
  reasoningText: string;
  reasoningStreaming: boolean;
  statusMessage: string;
  pendingUpdate: PendingUpdate | null;
  applyingUpdate: boolean;
  pendingActionConfirmation: AgentAction | null;
}

const DEFAULT_THREAD_STATE: ThreadState = {
  messages: [],
  toolEvents: [],
  isLoading: false,
  reasoningText: '',
  reasoningStreaming: false,
  statusMessage: '',
  pendingUpdate: null,
  applyingUpdate: false,
  pendingActionConfirmation: null,
};

// ---------------------------------------------------------------------------
// Combined return type for useTabChatState (flattened view)
// ---------------------------------------------------------------------------

export type TabChatView = TabState & ThreadState & { currentThreadId: string | null };

// ---------------------------------------------------------------------------
// Store interface
// ---------------------------------------------------------------------------

export interface ChatStreamStore {
  tabStates: Record<string, TabState>;
  threadStates: Record<string, ThreadState>;

  // --- Tab actions ---
  getOrCreateTab: (tabId: string) => TabState;
  setActiveThreadId: (tabId: string, threadId: string | null) => void;
  addThreadToTab: (tabId: string, threadId: string) => void;
  setThreads: (tabId: string, threads: ChatThread[]) => void;
  setLoadingThreads: (tabId: string, loading: boolean) => void;
  clearTab: (tabId: string) => void;
  removeTab: (tabId: string) => void;

  // --- Thread actions ---
  getOrCreateThread: (threadId: string) => ThreadState;
  setMessages: (threadId: string, msgs: Message[]) => void;
  updateMessage: (threadId: string, index: number, updater: (m: Message) => Message) => void;
  appendMessage: (threadId: string, msg: Message) => void;
  setToolEvents: (threadId: string, events: ToolEvent[]) => void;
  appendToolEvent: (threadId: string, event: ToolEvent) => void;
  updateToolEvent: (threadId: string, id: string, updater: (e: ToolEvent) => ToolEvent) => void;
  setIsLoading: (threadId: string, loading: boolean) => void;
  setReasoningText: (threadId: string, text: string) => void;
  setReasoningStreaming: (threadId: string, streaming: boolean) => void;
  setStatusMessage: (threadId: string, msg: string) => void;
  setPendingUpdate: (threadId: string, update: PendingUpdate | null) => void;
  setApplyingUpdate: (threadId: string, applying: boolean) => void;
  setPendingActionConfirmation: (threadId: string, action: AgentAction | null) => void;
  clearThread: (threadId: string) => void;
  removeThread: (threadId: string) => void;
  renameThread: (oldId: string, newId: string) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getTab(state: ChatStreamStore, tabId: string): TabState {
  return state.tabStates[tabId] ?? DEFAULT_TAB_STATE;
}

function updateTabState(
  state: ChatStreamStore,
  tabId: string,
  updater: (tab: TabState) => Partial<TabState>,
): { tabStates: Record<string, TabState> } {
  const tab = getTab(state, tabId);
  return { tabStates: { ...state.tabStates, [tabId]: { ...tab, ...updater(tab) } } };
}

function getThread(state: ChatStreamStore, threadId: string): ThreadState {
  return state.threadStates[threadId] ?? DEFAULT_THREAD_STATE;
}

function updateThreadState(
  state: ChatStreamStore,
  threadId: string,
  updater: (thread: ThreadState) => Partial<ThreadState>,
): { threadStates: Record<string, ThreadState> } {
  const thread = getThread(state, threadId);
  return { threadStates: { ...state.threadStates, [threadId]: { ...thread, ...updater(thread) } } };
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useChatStreamStore = create<ChatStreamStore>((set, get) => ({
  tabStates: {},
  threadStates: {},

  // --- Tab actions ---

  getOrCreateTab: (tabId) => {
    const existing = get().tabStates[tabId];
    if (existing) return existing;
    const fresh = { ...DEFAULT_TAB_STATE };
    set(s => ({ tabStates: { ...s.tabStates, [tabId]: fresh } }));
    return fresh;
  },

  setActiveThreadId: (tabId, threadId) =>
    set(s => updateTabState(s, tabId, () => ({ activeThreadId: threadId }))),

  addThreadToTab: (tabId, threadId) =>
    set(s => updateTabState(s, tabId, tab => ({
      threadIds: tab.threadIds.includes(threadId) ? tab.threadIds : [...tab.threadIds, threadId],
    }))),

  setThreads: (tabId, threads) =>
    set(s => updateTabState(s, tabId, () => ({ threads }))),

  setLoadingThreads: (tabId, loading) =>
    set(s => updateTabState(s, tabId, () => ({ loadingThreads: loading }))),

  clearTab: (tabId) =>
    set(s => ({ tabStates: { ...s.tabStates, [tabId]: { ...DEFAULT_TAB_STATE } } })),

  removeTab: (tabId) =>
    set(s => {
      const { [tabId]: removed, ...restTabs } = s.tabStates;
      const threadIds = removed?.threadIds ?? [];
      const restThreads = { ...s.threadStates };
      for (const tid of threadIds) delete restThreads[tid];
      return { tabStates: restTabs, threadStates: restThreads };
    }),

  // --- Thread actions ---

  getOrCreateThread: (threadId) => {
    const existing = get().threadStates[threadId];
    if (existing) return existing;
    const fresh = { ...DEFAULT_THREAD_STATE };
    set(s => ({ threadStates: { ...s.threadStates, [threadId]: fresh } }));
    return fresh;
  },

  setMessages: (threadId, msgs) => set(s => updateThreadState(s, threadId, () => ({ messages: msgs }))),

  updateMessage: (threadId, index, updater) =>
    set(s => updateThreadState(s, threadId, thread => ({
      messages: thread.messages.map((m, i) => (i === index ? updater(m) : m)),
    }))),

  appendMessage: (threadId, msg) =>
    set(s => updateThreadState(s, threadId, thread => ({ messages: [...thread.messages, msg] }))),

  setToolEvents: (threadId, events) => set(s => updateThreadState(s, threadId, () => ({ toolEvents: events }))),

  appendToolEvent: (threadId, event) =>
    set(s => updateThreadState(s, threadId, thread => ({ toolEvents: [...thread.toolEvents, event] }))),

  updateToolEvent: (threadId, id, updater) =>
    set(s => updateThreadState(s, threadId, thread => ({
      toolEvents: thread.toolEvents.map(e => (e.id === id ? updater(e) : e)),
    }))),

  setIsLoading: (threadId, loading) => set(s => updateThreadState(s, threadId, () => ({ isLoading: loading }))),
  setReasoningText: (threadId, text) => set(s => updateThreadState(s, threadId, () => ({ reasoningText: text }))),
  setReasoningStreaming: (threadId, streaming) => set(s => updateThreadState(s, threadId, () => ({ reasoningStreaming: streaming }))),
  setStatusMessage: (threadId, msg) => set(s => updateThreadState(s, threadId, () => ({ statusMessage: msg }))),
  setPendingUpdate: (threadId, update) => set(s => updateThreadState(s, threadId, () => ({ pendingUpdate: update }))),
  setApplyingUpdate: (threadId, applying) => set(s => updateThreadState(s, threadId, () => ({ applyingUpdate: applying }))),
  setPendingActionConfirmation: (threadId, action) => set(s => updateThreadState(s, threadId, () => ({ pendingActionConfirmation: action }))),

  clearThread: (threadId) =>
    set(s => ({ threadStates: { ...s.threadStates, [threadId]: { ...DEFAULT_THREAD_STATE } } })),

  removeThread: (threadId) =>
    set(s => {
      const { [threadId]: _, ...restThreads } = s.threadStates;
      const updatedTabs: Record<string, TabState> = {};
      for (const [tabId, tab] of Object.entries(s.tabStates)) {
        if (tab.threadIds.includes(threadId)) {
          updatedTabs[tabId] = {
            ...tab,
            threadIds: tab.threadIds.filter(id => id !== threadId),
            threads: tab.threads.filter(t => t.id !== threadId),
            activeThreadId: tab.activeThreadId === threadId ? null : tab.activeThreadId,
          };
        } else {
          updatedTabs[tabId] = tab;
        }
      }
      return { threadStates: restThreads, tabStates: updatedTabs };
    }),

  renameThread: (oldId, newId) =>
    set(s => {
      const threadState = s.threadStates[oldId];
      if (!threadState) return {};
      const { [oldId]: _, ...restThreads } = s.threadStates;
      const updatedTabs: Record<string, TabState> = {};
      for (const [tabId, tab] of Object.entries(s.tabStates)) {
        if (tab.threadIds.includes(oldId)) {
          updatedTabs[tabId] = {
            ...tab,
            threadIds: tab.threadIds.map(id => id === oldId ? newId : id),
            activeThreadId: tab.activeThreadId === oldId ? newId : tab.activeThreadId,
          };
        } else {
          updatedTabs[tabId] = tab;
        }
      }
      return {
        threadStates: { ...restThreads, [newId]: threadState },
        tabStates: { ...s.tabStates, ...updatedTabs },
      };
    }),
}));

export { DEFAULT_TAB_STATE, DEFAULT_THREAD_STATE };
