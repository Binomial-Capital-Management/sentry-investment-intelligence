import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Message, Thread, ModelId, AgentMode, ChatArtifact, ChartData } from '@/types';
import { getModelById } from '@/config/models';
import chatApiService from '@/services/chatApi';
import { STREAM_STORAGE_KEYS, streamingStorage } from '@services/streamingStorage';

interface ChatStore {
  threads: Thread[];
  currentThreadId: string | null;
  isLoading: boolean;
  isCreatingThread: boolean; // Dedicated flag for "New Chat" button
  error: string | null;
  loadingThreads: Record<string, boolean>;
  agentMode: AgentMode;
  selectedModel: ModelId;
  selectedChatPortfolioId: string | null;
  deepAnalysisMode: boolean;
  prioritizedTools: string[]; // Tools to prioritize for the current agent
  draftMessages: Record<string, string>; // Draft messages per thread
  scrollPositions: Record<string, number>; // Scroll positions per thread
  compactionInfo: { isCompacting: boolean; from?: string; to?: string; tokens?: number }; // Compaction state

  // API-connected methods
  loadThreads: () => Promise<void>;
  createNewThread: (title?: string) => Promise<string>;
  deleteThread: (threadId: string) => Promise<void>;
  bulkDeleteThreads: (threadIds: string[]) => Promise<number>;
  loadMessages: (threadId: string) => Promise<void>;
  sendMessage: (threadId: string, message: string, portfolioId?: string, agentMode?: AgentMode) => Promise<void>;

  // Local state methods
  setCurrentThread: (threadId: string) => void;
  updateThreadTitle: (threadId: string, title: string) => void;
  addMessage: (threadId: string, message: Message) => void;
  updateMessage: (threadId: string, messageId: string, updates: Partial<Message>) => void;
  addArtifact: (threadId: string, artifact: ChatArtifact) => void;
  clearError: () => void;
  setAgentMode: (mode: AgentMode) => void;
  getCurrentThreadAgentMode: () => AgentMode;
  setSelectedModel: (model: ModelId) => void;
  getCurrentThreadModel: () => ModelId;
  setSelectedChatPortfolioId: (id: string | null) => void;
  setDeepAnalysisMode: (enabled: boolean) => void;
  setPrioritizedTools: (tools: string[]) => void;
  setDraftMessage: (threadId: string, message: string) => void;
  setScrollPosition: (threadId: string, position: number) => void;
  setCompactionInfo: (info: { isCompacting: boolean; from?: string; to?: string; tokens?: number }) => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

const STREAM_CONTEXT_TTL_MS = 5 * 60 * 1000;


export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
  threads: [],
  currentThreadId: null,
  isLoading: false,
  isCreatingThread: false,
  error: null,
  loadingThreads: {},
  agentMode: 'auto' as AgentMode,
  selectedModel: 'gpt-6.1-sol' as ModelId,
  selectedChatPortfolioId: null,
  deepAnalysisMode: false,
  prioritizedTools: [],
  draftMessages: {},
  scrollPositions: {},
  compactionInfo: { isCompacting: false },

  // Load all threads from backend
  loadThreads: async () => {
    set({ isLoading: true, error: null });
    try {
      const sessions = await chatApiService.listSessions();
      const state = get();
      const threads: Thread[] = sessions.map(session => {
        const existing = state.threads.find(t => t.id === session.id);
        return {
          id: session.id,
          title: session.title,
          messages: existing?.messages && existing.messages.length > 0 ? existing.messages : [],
          createdAt: new Date(session.created_at),
          updatedAt: session.updated_at ? new Date(session.updated_at) : new Date(session.created_at),
          selectedModel: existing?.selectedModel || state.selectedModel || 'gpt-6.1-sol',
          agentMode: existing?.agentMode || state.agentMode || 'auto',
          artifacts: existing?.artifacts ? [...existing.artifacts] : [],
          hasLoadedMessages: existing?.hasLoadedMessages ?? false,
        };
      });
      set({ threads, isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  // Create new thread via API
  createNewThread: async (title?: string) => {
    // Use dedicated flag to avoid race conditions with other loading states
    set({ isCreatingThread: true, error: null });
    try {
      const session = await chatApiService.createSession(title);
      const state = get();
      const newThread: Thread = {
        id: session.id,
        title: session.title,
        messages: [],
        createdAt: new Date(session.created_at),
        updatedAt: new Date(session.created_at),
        selectedModel: state.selectedModel || 'gpt-6.1-sol', // Use current or default model
        agentMode: state.agentMode || 'auto', // Use current or default agent mode
        artifacts: [],
        hasLoadedMessages: true,
      };

      set((state) => ({
        threads: [newThread, ...state.threads.filter(t => t.id !== newThread.id)],
        currentThreadId: newThread.id,
        isCreatingThread: false,
      }));

      return newThread.id;
    } catch (error) {
      set({ error: (error as Error).message, isCreatingThread: false });
      throw error; // Re-throw so caller can handle
    }
  },

  // Delete thread via API
  deleteThread: async (threadId: string) => {
    set({ isLoading: true, error: null });
    try {
      await chatApiService.deleteSession(threadId);
      set((state) => {
        const newThreads = state.threads.filter(t => t.id !== threadId);
        const newCurrentId = state.currentThreadId === threadId
          ? (newThreads[0]?.id || null)
          : state.currentThreadId;
        return {
          threads: newThreads,
          currentThreadId: newCurrentId,
          isLoading: false,
        };
      });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  // Bulk delete multiple threads via API
  bulkDeleteThreads: async (threadIds: string[]) => {
    if (!threadIds.length) return 0;
    
    set({ isLoading: true, error: null });
    try {
      const result = await chatApiService.bulkDeleteSessions(threadIds);
      set((state) => {
        const deletedSet = new Set(threadIds);
        const newThreads = state.threads.filter(t => !deletedSet.has(t.id));
        const newCurrentId = deletedSet.has(state.currentThreadId || '')
          ? (newThreads[0]?.id || null)
          : state.currentThreadId;
        return {
          threads: newThreads,
          currentThreadId: newCurrentId,
          isLoading: false,
        };
      });
      return result.deleted_count;
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      return 0;
    }
  },

  // Load messages for a thread
  loadMessages: async (threadId: string) => {
    const contextRaw = streamingStorage.read(STREAM_STORAGE_KEYS.context);
    if (contextRaw) {
      try {
        const parsed = JSON.parse(contextRaw);
        const contextThread = parsed?.threadId;
        const timestamp = typeof parsed?.timestamp === 'number' ? parsed.timestamp : 0;
        const contextFresh = !timestamp || (Date.now() - timestamp) <= STREAM_CONTEXT_TTL_MS;
        if (contextThread === threadId && contextFresh) {
          console.log('[ChatStore] Skipping loadMessages - resume context active');
          return;
        }
      } catch {
        // Ignore parse errors and fall through to normal loading
      }
    }

    // Don't reload if actively streaming - prevents race condition
    const thread = get().threads.find(t => t.id === threadId);
    const hasStreamingMessage = thread?.messages.some(m => m.isStreaming);
    if (hasStreamingMessage) {
      console.log('[ChatStore] Skipping loadMessages - streaming in progress');
      return;
    }
    if (get().loadingThreads[threadId]) {
      return;
    }

    set((state) => ({
      isLoading: true,
      error: null,
      threads: state.threads.map((t) =>
        t.id === threadId ? { ...t, hasLoadedMessages: true } : t,
      ),
      loadingThreads: { ...state.loadingThreads, [threadId]: true },
    }));
    try {
      const data = await chatApiService.getMessages(threadId);
      const newArtifacts: ChatArtifact[] = [];
      const messages: Message[] = data.messages
        .map((msg) => {
          if (msg.metadata?.status === 'cancelled') {
            const note = typeof msg.metadata?.note === 'string' ? msg.metadata.note : undefined;
            const partial = typeof msg.metadata?.partialContent === 'string' ? msg.metadata.partialContent : undefined;
            const fallbackPartial = note && msg.content ? msg.content.replace(note, '').trim() || undefined : msg.content || undefined;
            newArtifacts.push({
              id: msg.id || generateId(),
              type: 'cancelled',
              createdAt: new Date(msg.timestamp || Date.now()),
              data: {
                reason: (msg.metadata?.reason as 'user' | 'backend' | 'disconnect') || 'backend',
                partialContent: partial ?? fallbackPartial,
              },
            });
            return null;
          }

          // Extract charts from metadata and populate message.charts
          const charts = msg.metadata?.charts as ChartData[] | undefined;

          return {
            id: msg.id || generateId(),
            role: msg.role,
            content: msg.content,
            timestamp: new Date(msg.timestamp || Date.now()),
            charts: charts || undefined,
            extras: msg.metadata || undefined,
            // Never mark messages as streaming when loading from backend
            // (streaming state is only for active real-time streams)
            isStreaming: false,
          } as Message;
        })
        .filter((msg): msg is Message => msg !== null);

      set((state) => ({
        threads: state.threads.map(thread =>
          thread.id === threadId
            ? {
                ...thread,
                messages,
                artifacts: (() => {
                  const existing = thread.artifacts || [];
                  if (!newArtifacts.length) return existing;
                  const existingIds = new Set(existing.map((a) => a.id));
                  const additions = newArtifacts.filter((artifact) => {
                    if (existingIds.has(artifact.id)) return false;
                    return !existing.some((current) => {
                      const sameReason = current.data.reason === artifact.data.reason;
                      const currentPartial = current.data.partialContent || '';
                      const newPartial = artifact.data.partialContent || '';
                      return sameReason && currentPartial === newPartial;
                    });
                  });
                  return additions.length ? [...existing, ...additions] : existing;
                })(),
                hasLoadedMessages: true,
              }
            : thread,
        ),
        isLoading: false,
        loadingThreads: Object.fromEntries(
          Object.entries(state.loadingThreads).filter(([key]) => key !== threadId),
        ),
      }));
    } catch (error) {
      set((state) => ({
        error: (error as Error).message,
        isLoading: false,
        threads: state.threads.map((t) =>
          t.id === threadId ? { ...t, hasLoadedMessages: false } : t,
        ),
        loadingThreads: Object.fromEntries(
          Object.entries(state.loadingThreads).filter(([key]) => key !== threadId),
        ),
      }));
    }
  },

  // Send message via API
  sendMessage: async (threadId: string, message: string, portfolioId?: string, agentMode?: AgentMode) => {
    // Add user message optimistically
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: message,
      timestamp: new Date(),
    };

    set((state) => ({
      threads: state.threads.map(thread =>
        thread.id === threadId
          ? {
              ...thread,
              messages: [...thread.messages, userMessage],
              updatedAt: new Date(),
            }
          : thread,
      ),
    }));

    set({ isLoading: true, error: null });

    try {
      const mode = agentMode || get().agentMode;
      const response = await chatApiService.sendMessage(threadId, message, portfolioId, mode);

      // Add assistant response
      const assistantMessage: Message = {
        id: response.message_id || generateId(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(response.timestamp),
        sources: response.sources,
        charts: response.charts,
      };

      set((state) => ({
        threads: state.threads.map(thread =>
          thread.id === threadId
            ? {
                ...thread,
                messages: [...thread.messages, assistantMessage],
                updatedAt: new Date(),
              }
            : thread,
        ),
        isLoading: false,
      }));

      // Auto-update title if it's still "New Chat" and we have messages
      const thread = get().threads.find(t => t.id === threadId);
      if (thread && thread.title === 'New Chat' && thread.messages.length > 1) {
        // Generate title from first user message (first 50 chars)
        const firstUserMsg = thread.messages.find(m => m.role === 'user');
        if (firstUserMsg) {
          const newTitle = firstUserMsg.content.slice(0, 50) + (firstUserMsg.content.length > 50 ? '...' : '');
          get().updateThreadTitle(threadId, newTitle);
        }
      }
    } catch (error) {
      // Remove optimistic user message on error
      set((state) => ({
        threads: state.threads.map(thread =>
          thread.id === threadId
            ? {
                ...thread,
                messages: thread.messages.filter(m => m.id !== userMessage.id),
              }
            : thread,
        ),
        error: (error as Error).message,
        isLoading: false,
      }));
    }
  },

  // Local state management
  setCurrentThread: (threadId) => {
    set({ currentThreadId: threadId });
    // Note: loadMessages should be called explicitly by the component when needed
    // to avoid infinite loops in useEffect dependencies
  },

  updateThreadTitle: (threadId, title) => {
    set((state) => ({
      threads: state.threads.map((thread) =>
        thread.id === threadId ? { ...thread, title } : thread,
      ),
    }));
    // TODO: Also update title in backend
  },

  addMessage: (threadId, message) => {
    set((state) => ({
      threads: state.threads.map((thread) =>
        thread.id === threadId
          ? {
              ...thread,
              messages: [...thread.messages, message],
              updatedAt: new Date(),
            }
          : thread,
      ),
    }));
  },

  addArtifact: (threadId, artifact) => {
    set((state) => ({
      threads: state.threads.map((thread) =>
        thread.id === threadId
          ? {
              ...thread,
              artifacts: [...(thread.artifacts || []), artifact],
              updatedAt: new Date(),
            }
          : thread,
      ),
    }));
  },

  updateMessage: (threadId, messageId, updates) => {
    set((state) => ({
      threads: state.threads.map((thread) => {
        if (thread.id === threadId) {
          return {
            ...thread,
            messages: thread.messages.map((msg) =>
              msg.id === messageId ? { ...msg, ...updates } : msg,
            ),
          };
        }
        return thread;
      }),
    }));
  },

  clearError: () => {
    set({ error: null });
  },

  setAgentMode: (mode: AgentMode) => {
    const { currentThreadId } = get();
    // Clear prioritized tools when agent changes (tools are agent-specific)
    set({ prioritizedTools: [] });
    if (currentThreadId) {
      set((state) => ({
        threads: state.threads.map((t) =>
          t.id === currentThreadId ? { ...t, agentMode: mode } : t,
        ),
      }));
    } else {
      // Fallback to global if no active thread
      set({ agentMode: mode });
    }
  },

  getCurrentThreadAgentMode: () => {
    const { currentThreadId, threads, agentMode } = get();
    if (currentThreadId) {
      const thread = threads.find(t => t.id === currentThreadId);
      return thread?.agentMode || agentMode;
    }
    return agentMode;
  },

  setSelectedModel: (model: ModelId) => {
    const { currentThreadId } = get();
    const provider = getModelById(model).provider;
    const allowCodeExecution = provider === 'OpenAI';

    set((state) => {
      const updatedThreads = state.threads.map((thread) => {
        if (thread.id !== currentThreadId) {
          return thread;
        }
        return {
          ...thread,
          selectedModel: model,
        };
      });

      return {
        threads: updatedThreads,
        selectedModel: model,
      };
    });
  },

  getCurrentThreadModel: () => {
    const { currentThreadId, threads, selectedModel } = get();
    if (currentThreadId) {
      const thread = threads.find(t => t.id === currentThreadId);
      return thread?.selectedModel || selectedModel;
    }
    return selectedModel;
  },


  setSelectedChatPortfolioId: (id) => set({ selectedChatPortfolioId: id }),
  setDeepAnalysisMode: (enabled) => set({ deepAnalysisMode: enabled }),
  setPrioritizedTools: (tools) => set({ prioritizedTools: tools }),

  setDraftMessage: (threadId: string, message: string) => {
    const drafts = { ...get().draftMessages, [threadId]: message };
    set({ draftMessages: drafts });
  },

  setScrollPosition: (threadId: string, position: number) => {
    const positions = { ...get().scrollPositions, [threadId]: position };
    set({ scrollPositions: positions });
  },

  setCompactionInfo: (info) => {
    set({ compactionInfo: info });
  },
    }),
    {
      name: 'sentry-chat',
      partialize: (state) => ({
        threads: state.threads,
        currentThreadId: state.currentThreadId,
        agentMode: state.agentMode,
        selectedModel: state.selectedModel,
        selectedChatPortfolioId: state.selectedChatPortfolioId,
        deepAnalysisMode: state.deepAnalysisMode,
        draftMessages: state.draftMessages,
        scrollPositions: state.scrollPositions,
        // Don't persist: isLoading, error (fresh on reload)
      }),
    },
  ),
);
