/**
 * chatStreamManager.ts
 *
 * Module-level manager that owns SSE lifecycle and event handling for canvas
 * AI chat streams.  All mutable state lives on ActiveStream objects tracked in
 * a Map<tabId, Map<runId, ActiveStream>>.  UI state is written through the
 * Zustand chatStreamStore (accessible outside React via .getState()).
 *
 * Store writes target **thread-level** state (keyed by threadId), while
 * tab-level operations (addThreadToTab, setActiveThreadId, etc.) still use
 * tabId.
 */

import { StreamingService } from '@/services/streaming';
import { API_BASE } from '@/services/api';
import { useChatStreamStore } from '../stores/chatStreamStore';
import { useDataWorkspaceStore } from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';
import { validateAction } from '../utils/actionValidator';
import type { ToolEvent, ModelId } from '@/types';
import type {
  Message,
  ChatThread,
  DataContext,
  SavedProcess,
  AgentAction,
  ActionResult,
} from '../types';
import { debugLog } from '../utils/debugLog';

// ---------------------------------------------------------------------------
// ActiveStream – replaces all the useRef values from the hook
// ---------------------------------------------------------------------------

export interface ActiveStream {
  runId: string;
  service: StreamingService;
  assistantMessageIndex: number;
  messageHasTools: boolean;
  preToolContentSeen: boolean;
  activeReasoningId: string | null;
  reasoningSeqCounter: number;
  reasoningBuffer: string;
  reasoningFlushTimer: ReturnType<typeof setTimeout> | null;
  pendingActionResolve: ((confirmed: boolean) => void) | null;
  activeThreadId: string | null;
  pendingThreadId: string;
  contentBuffer: string;
  contentFlushRaf: number | null;
  pendingIntervals: ReturnType<typeof setInterval>[];

  // Callbacks supplied by the caller (mirror hook options)
  getToken: () => Promise<string | null>;
  onThreadCreated?: (thread: ChatThread, initialMessage?: string) => void;
  onUpdateThread?: (threadId: string, updates: { title?: string; pinned?: boolean }) => void;
  onResultUpdate?: (result: any) => void;

  // Context carried from startStream
  process: SavedProcess | null;
  dataContext?: DataContext | null;
  trimmedText: string;
}

// ---------------------------------------------------------------------------
// StartStream options – everything the caller must supply
// ---------------------------------------------------------------------------

export interface StartStreamOptions {
  text: string;
  process: SavedProcess | null;
  dataContext?: DataContext | null;
  currentThreadId: string | null;
  selectedModel: ModelId;
  isWebSearchEnabled: boolean;
  attachedFileIds: string[];
  getToken: () => Promise<string | null>;
  onThreadCreated?: (thread: ChatThread, initialMessage?: string) => void;
  onUpdateThread?: (threadId: string, updates: { title?: string; pinned?: boolean }) => void;
  onResultUpdate?: (result: any) => void;
}

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

/** tabId -> runId -> ActiveStream */
const activeStreams = new Map<string, Map<string, ActiveStream>>();

let runIdCounter = 0;
function nextRunId(): string {
  return `run_${Date.now()}_${++runIdCounter}`;
}

// ---------------------------------------------------------------------------
// Helper: get the Zustand store (non-React)
// ---------------------------------------------------------------------------

function store() {
  return useChatStreamStore.getState();
}

// ---------------------------------------------------------------------------
// Helper: effective thread ID for a stream
// ---------------------------------------------------------------------------

function streamThreadId(stream: ActiveStream): string {
  return stream.activeThreadId ?? stream.pendingThreadId;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Start a new SSE stream for the given tab.
 * Returns the assigned runId.
 */
export function startStream(tabId: string, options: StartStreamOptions): string {
  const {
    text,
    process,
    dataContext,
    currentThreadId,
    selectedModel,
    isWebSearchEnabled,
    attachedFileIds,
    getToken,
    onThreadCreated,
    onUpdateThread,
    onResultUpdate,
  } = options;

  const trimmedText = text.trim();
  if (!trimmedText) return '';

  const s = store();

  // Create the ActiveStream early so we can derive the threadId
  const runId = nextRunId();

  // Track thread ID for action result reporting
  let initialThreadId: string | null = null;
  if (currentThreadId && !currentThreadId.startsWith('thread-')) {
    initialThreadId = currentThreadId;
  }

  // Generate a pending thread ID when no real thread exists yet
  const pendingThreadId = `pending-${runId}`;

  // The effective thread ID for store writes
  const threadId = initialThreadId ?? pendingThreadId;

  // Ensure thread state exists
  s.getOrCreateThread(threadId);

  // Mark thread loading
  s.setIsLoading(threadId, true);

  // Append user message
  const userMessage: Message = {
    id: `user-${Date.now()}`,
    role: 'user',
    content: trimmedText,
    created_at: new Date().toISOString(),
  };
  s.appendMessage(threadId, userMessage);

  // Reset per-message streaming state
  s.setReasoningStreaming(threadId, false);
  s.setReasoningText(threadId, '');
  s.setStatusMessage(threadId, '');

  // Append empty assistant placeholder
  const assistantMessage: Message = {
    id: `temp-assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString(),
  };
  s.appendMessage(threadId, assistantMessage);
  const assistantIdx = s.getOrCreateThread(threadId).messages.length - 1;

  const service = new StreamingService();

  const stream: ActiveStream = {
    runId,
    service,
    assistantMessageIndex: assistantIdx,
    messageHasTools: false,
    preToolContentSeen: false,
    activeReasoningId: null,
    reasoningSeqCounter: 0,
    reasoningBuffer: '',
    reasoningFlushTimer: null,
    pendingActionResolve: null,
    activeThreadId: initialThreadId,
    pendingThreadId,
    contentBuffer: '',
    contentFlushRaf: null,
    pendingIntervals: [],
    getToken,
    onThreadCreated,
    onUpdateThread,
    onResultUpdate,
    process,
    dataContext,
    trimmedText,
  };

  // Register in the map
  if (!activeStreams.has(tabId)) {
    activeStreams.set(tabId, new Map());
  }
  activeStreams.get(tabId)!.set(runId, stream);

  // Build SSE endpoint
  const endpoint = `${API_BASE}/api/canvas/chat/stream`;

  // Generate session_id for cancel endpoint targeting
  const canvasSessionId = `canvas-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  // Fire the SSE
  service.startStream(
    trimmedText,
    {
      onMessage: (data: any) => handleStreamEvent(tabId, stream, data),
      onError: (err: Error) => {
        console.error('[ChatStreamManager] Stream error:', err);
        flushContentBuffer(stream);
        s.setIsLoading(streamThreadId(stream), false);
        s.setReasoningStreaming(streamThreadId(stream), false);
      },
      onComplete: () => {
        flushContentBuffer(stream);
        s.setIsLoading(streamThreadId(stream), false);
        s.setReasoningStreaming(streamThreadId(stream), false);
        s.setStatusMessage(streamThreadId(stream), '');
        finalizeReasoning(tabId, stream);
        activeStreams.get(tabId)?.delete(runId);
      },
    },
    {
      selectedModel,
      fileIds: attachedFileIds,
      sessionId: canvasSessionId,
      cancelEndpoint: `${API_BASE}/api/canvas/chat/cancel`,
      extraParams: {
        session_id: canvasSessionId,
        // Pass process_id
        ...(process?.id
          ? { process_id: process.id }
          : dataContext?.tools?.find(t => t.tabId === dataContext.activeTabId)?.processId
            ? { process_id: dataContext.tools.find(t => t.tabId === dataContext.activeTabId)!.processId! }
            : {}),
        // Only pass thread_id if it's a valid UUID
        ...(currentThreadId && !currentThreadId.startsWith('thread-') ? { thread_id: currentThreadId } : {}),
        ...(isWebSearchEnabled ? { web_search: 'true' } : {}),
        // Pass data context
        ...(dataContext
          ? { data_context: JSON.stringify(dataContext) }
          : (process && !process.id)
            ? {
                data_context: JSON.stringify({
                  type: 'unsaved_process',
                  tool_id: process.tool_id,
                  name: process.name || `${process.tool_id} Analysis`,
                  tickers: process.tickers || [],
                  weights: process.weights || [],
                  params: process.params || {},
                  metric_cards: process.metric_cards || [],
                  stats_table: process.stats_table || [],
                  hmm_enabled: process.hmm_enabled || false,
                  current_regime: process.current_regime,
                }),
              }
            : {}),
      },
    },
    endpoint,
  );

  return runId;
}

/**
 * Cancel a specific run for a tab, or all runs if runId is omitted.
 */
export function cancelStream(tabId: string, runId?: string): void {
  const tabMap = activeStreams.get(tabId);
  if (!tabMap) return;

  const s = store();

  function cleanupStream(stream: ActiveStream) {
    const tid = streamThreadId(stream);
    stream.service.close(true);
    clearReasoningTimer(stream);
    stream.pendingIntervals.forEach(clearInterval);
    stream.pendingIntervals.length = 0;
    flushContentBuffer(stream);
    if (stream.contentFlushRaf !== null) {
      cancelAnimationFrame(stream.contentFlushRaf);
      stream.contentFlushRaf = null;
    }
    s.setIsLoading(tid, false);
    s.setReasoningStreaming(tid, false);
    s.setReasoningText(tid, '');
    s.setStatusMessage(tid, '');
    finalizeReasoning(tabId, stream);
    savePartialMessage(stream);
  }

  if (runId) {
    const stream = tabMap.get(runId);
    if (stream) {
      cleanupStream(stream);
      tabMap.delete(runId);
    }
  } else {
    tabMap.forEach(cleanupStream);
    tabMap.clear();
  }
}

/**
 * Resolve a pending action confirmation for a given stream.
 */
export function confirmAction(tabId: string, runId: string, confirmed: boolean): void {
  const stream = activeStreams.get(tabId)?.get(runId);
  if (stream?.pendingActionResolve) {
    stream.pendingActionResolve(confirmed);
    stream.pendingActionResolve = null;
  }
  if (stream) {
    store().setPendingActionConfirmation(streamThreadId(stream), null);
  }
}

/**
 * Convenience: confirm or cancel the action on the first active stream for a tab.
 */
export function confirmActionForTab(tabId: string, confirmed: boolean): void {
  const tabMap = activeStreams.get(tabId);
  if (!tabMap) return;
  // Find the first stream with a pending action resolve
  let found = false;
  tabMap.forEach((stream, runId) => {
    if (!found && stream.pendingActionResolve) {
      confirmAction(tabId, runId, confirmed);
      found = true;
    }
  });
  if (found) return;
  // No pending action found — just clear the UI state for all streams
  tabMap.forEach((stream) => {
    store().setPendingActionConfirmation(streamThreadId(stream), null);
  });
}

/**
 * Report an action result back to the backend.
 */
export async function reportActionResult(
  tabId: string,
  runId: string,
  actionId: string,
  action: AgentAction,
  result: ActionResult,
): Promise<void> {
  const stream = activeStreams.get(tabId)?.get(runId);
  const threadId = stream?.activeThreadId;
  if (!threadId) {
    console.warn('[ChatStreamManager] No active thread ID for action result reporting');
    return;
  }

  try {
    const token = await stream!.getToken();
    await fetch(`${API_BASE}/api/canvas/chat/action-result`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        thread_id: threadId,
        action_id: actionId || `action-${Date.now()}`,
        action_type: action.type,
        symbol: 'symbol' in action ? action.symbol : undefined,
        success: result.success,
        error: result.error,
        cancelled: result.cancelled,
      }),
    });
    console.log('[ChatStreamManager] Action result reported:', { actionType: action.type, success: result.success });
  } catch (err) {
    console.error('[ChatStreamManager] Failed to report action result:', err);
  }
}

/**
 * Apply a pending process update (saved process).
 * `getToken` is required because this may be called outside a stream context.
 */
export async function applyPendingUpdate(
  threadId: string,
  getToken: () => Promise<string | null>,
): Promise<void> {
  const s = store();
  const threadState = s.getOrCreateThread(threadId);
  const pendingUpdate = threadState.pendingUpdate;
  if (!pendingUpdate?.processId) return;

  s.setApplyingUpdate(threadId, true);
  try {
    const token = await getToken();

    let fullResult = { ...pendingUpdate.fullResult };

    // Fetch cached charts if needed
    const chartsCacheId = fullResult.charts_cache_id;
    if (chartsCacheId && !fullResult.charts) {
      console.log('[ChatStreamManager] Fetching cached charts:', chartsCacheId);
      try {
        const chartsResponse = await fetch(
          `${API_BASE}/api/canvas/data/cache/charts/${chartsCacheId}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (chartsResponse.ok) {
          const chartsData = await chartsResponse.json();
          fullResult.charts = chartsData.charts;
          console.log('[ChatStreamManager] Fetched charts:', Object.keys(chartsData.charts || {}));
        } else {
          console.warn('[ChatStreamManager] Failed to fetch cached charts, proceeding without');
        }
      } catch (e) {
        console.warn('[ChatStreamManager] Error fetching cached charts:', e);
      }
    }

    const response = await fetch(`${API_BASE}/api/canvas/processes/${pendingUpdate.processId}/apply-update`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        process_id: pendingUpdate.processId,
        tool_id: pendingUpdate.toolId,
        tickers: pendingUpdate.tickers,
        weights: pendingUpdate.weights,
        params: pendingUpdate.params,
        full_result: fullResult,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to apply update');
    }

    s.setPendingUpdate(threadId, null);

    s.appendMessage(threadId, {
      id: `system-${Date.now()}`,
      role: 'assistant',
      content: '\u2705 **Changes applied!** The process has been updated with the new parameters. Refresh the page to see the updated charts and metrics.',
      created_at: new Date().toISOString(),
    });
  } catch (error) {
    console.error('[ChatStreamManager] Failed to apply update:', error);
  } finally {
    s.setApplyingUpdate(threadId, false);
  }
}

/**
 * Dismiss a pending update for a thread.
 */
export function dismissPendingUpdate(threadId: string): void {
  store().setPendingUpdate(threadId, null);
}

/**
 * Check if a tab has any running streams.
 */
export function hasActiveStreams(tabId: string): boolean {
  const tabMap = activeStreams.get(tabId);
  return !!tabMap && tabMap.size > 0;
}

/**
 * Clean up all streams for a tab (e.g. on unmount).
 */
export function destroyTab(tabId: string): void {
  cancelStream(tabId);
  activeStreams.delete(tabId);
}

// ---------------------------------------------------------------------------
// Internal: reasoning helpers
// ---------------------------------------------------------------------------

function clearReasoningTimer(stream: ActiveStream): void {
  if (stream.reasoningFlushTimer) {
    clearTimeout(stream.reasoningFlushTimer);
    stream.reasoningFlushTimer = null;
  }
}

function finalizeReasoning(_tabId: string, stream: ActiveStream): void {
  if (!stream.activeReasoningId) return;
  clearReasoningTimer(stream);

  const finId = stream.activeReasoningId;
  const finalText = stream.reasoningBuffer;
  stream.reasoningBuffer = '';
  stream.activeReasoningId = null;

  const s = store();
  const tid = streamThreadId(stream);
  const events = s.getOrCreateThread(tid).toolEvents;
  s.setToolEvents(
    tid,
    events.map(e =>
      e.id === finId && e.status === 'in_progress'
        ? { ...e, result: finalText || e.result, status: 'completed' as const, endTime: Date.now() }
        : e,
    ),
  );
}

/** Finalize reasoning unconditionally (even if not in_progress) – used when a tool starts */
function finalizeReasoningUnconditional(_tabId: string, stream: ActiveStream): void {
  if (!stream.activeReasoningId) return;
  clearReasoningTimer(stream);

  const finId = stream.activeReasoningId;
  const finalText = stream.reasoningBuffer;
  stream.reasoningBuffer = '';
  stream.activeReasoningId = null;

  const s = store();
  const tid = streamThreadId(stream);
  const events = s.getOrCreateThread(tid).toolEvents;
  s.setToolEvents(
    tid,
    events.map(e =>
      e.id === finId && e.status === 'in_progress'
        ? { ...e, result: finalText || e.result, status: 'completed' as const, endTime: Date.now() }
        : e,
    ),
  );
}

// ---------------------------------------------------------------------------
// Internal: finalize any lingering in-progress tool events
// ---------------------------------------------------------------------------

const IN_PROGRESS_STATUSES = ['in_progress', 'arguments_delta', 'arguments_done'] as const;

function finalizeLingeringToolEvents(threadId: string): void {
  const s = store();
  const threadState = s.getOrCreateThread(threadId);
  const lingering = threadState.toolEvents.filter(e =>
    (IN_PROGRESS_STATUSES as readonly string[]).includes(e.status),
  );
  if (lingering.length > 0) {
    console.warn('[ChatStreamManager] Finalizing lingering in-progress tool events:', lingering.map(e => e.id));
    s.setToolEvents(
      threadId,
      threadState.toolEvents.map(e =>
        (IN_PROGRESS_STATUSES as readonly string[]).includes(e.status)
          ? { ...e, status: 'completed' as const, endTime: Date.now() }
          : e,
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Internal: serialize tool events & reasoning into persistable metadata
// ---------------------------------------------------------------------------

function serializeToolEvents(events: ToolEvent[]): Record<string, any> | undefined {
  if (events.length === 0) return undefined;

  const toolEventsSerialized: any[] = [];
  const reasoningSegments: string[] = [];
  const reasoningTimestamps: { startTime: number; endTime?: number }[] = [];

  for (const evt of events) {
    if (evt.toolType === 'reasoning') {
      reasoningSegments.push(evt.result || '');
      reasoningTimestamps.push({ startTime: evt.startTime, endTime: evt.endTime });
    } else {
      toolEventsSerialized.push({
        type: 'tool_call_started',
        event: {
          item_id: evt.id,
          tool_name: evt.toolName,
          name: evt.toolName,
          arguments: evt.arguments,
          startTime: evt.startTime,
          endTime: evt.endTime,
        },
      });
      if (evt.result !== undefined) {
        toolEventsSerialized.push({
          type: 'tool_call_output',
          event: {
            item_id: evt.id,
            output: evt.result,
          },
        });
      }
    }
  }

  const metadata: Record<string, any> = {};
  if (toolEventsSerialized.length > 0) metadata.toolEvents = toolEventsSerialized;
  if (reasoningSegments.length > 0) {
    metadata.reasoningSegments = reasoningSegments;
    metadata.reasoningTimestamps = reasoningTimestamps;
  }
  return Object.keys(metadata).length > 0 ? metadata : undefined;
}

// ---------------------------------------------------------------------------
// Internal: persist tool events & reasoning to backend message metadata
// ---------------------------------------------------------------------------

async function persistMessageMetadata(
  stream: ActiveStream,
  messageId: string,
): Promise<void> {
  const tid = streamThreadId(stream);
  const threadState = store().getOrCreateThread(tid);
  const metadata = serializeToolEvents(threadState.toolEvents);
  if (!metadata) return;

  try {
    debugLog('MetadataPersist', { action: 'PATCH', messageId, toolEvents: metadata.toolEvents?.length ?? 0, reasoning: metadata.reasoningSegments?.length ?? 0 });
    const token = await stream.getToken();
    const resp = await fetch(`${API_BASE}/api/canvas/chat/messages/${messageId}/metadata`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ metadata }),
    });
    debugLog('MetadataPersist', { action: 'PATCH_response', messageId, status: resp.status });
  } catch (e) {
    console.error('Failed to persist message metadata:', e);
  }
}

// ---------------------------------------------------------------------------
// Internal: save partial assistant message on cancel (fire-and-forget)
// ---------------------------------------------------------------------------

async function savePartialMessage(stream: ActiveStream): Promise<void> {
  const tid = streamThreadId(stream);
  const threadId = stream.activeThreadId;
  if (!threadId) return;

  const threadState = store().getOrCreateThread(tid);
  const msg = threadState.messages[stream.assistantMessageIndex];
  const content = msg?.content || '';
  const metadata = serializeToolEvents(threadState.toolEvents);

  if (!content.trim() && !metadata) return;

  try {
    const token = await stream.getToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    } else {
      const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
      const isLocal = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
      if (isLocal && devSecret) {
        headers['X-Dev-Secret'] = devSecret;
        headers['X-Dev-User-Id'] = 'dev-local-user';
      }
    }

    await fetch(`${API_BASE}/api/canvas/chat/threads/${threadId}/messages`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        role: 'assistant',
        content,
        metadata,
        process_id: stream.process?.id || null,
      }),
    });
    debugLog('SavePartial', { action: 'saved', threadId, contentLen: content.length, hasMetadata: !!metadata });
  } catch (e) {
    console.error('Failed to save partial message on cancel:', e);
  }
}

// ---------------------------------------------------------------------------
// Internal: request confirmation (Promise-based)
// ---------------------------------------------------------------------------

function requestConfirmation(_tabId: string, stream: ActiveStream, action: AgentAction): Promise<boolean> {
  return new Promise((resolve) => {
    store().setPendingActionConfirmation(streamThreadId(stream), action);
    stream.pendingActionResolve = resolve;
  });
}

// ---------------------------------------------------------------------------
// Internal: handle add_dataset action
// ---------------------------------------------------------------------------

async function handleAddDatasetAction(
  stream: ActiveStream,
  action: { type: string; dataset_id: string; symbol: string; endpoint: string; fields?: string[]; row_count: number },
): Promise<void> {
  console.log('[ChatStreamManager] Fetching cached dataset:', action.dataset_id);

  const token = await stream.getToken();
  const response = await fetch(`${API_BASE}/api/canvas/data/cache/${action.dataset_id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    if (response.status === 404) {
      console.warn('[ChatStreamManager] Dataset expired');
      return;
    }
    throw new Error(`Failed to fetch cached dataset: ${response.status}`);
  }

  const cachedData = await response.json();

  console.log('[ChatStreamManager] Cached data received:', {
    symbol: cachedData.symbol,
    endpoint: cachedData.endpoint,
    params: cachedData.params,
    fields: cachedData.fields,
    rowCount: cachedData.row_count,
    dataLength: cachedData.data?.length,
  });

  const wsStore = useDataWorkspaceStore.getState();
  wsStore.addDatasetDirect({
    id: action.dataset_id,
    symbol: cachedData.symbol || action.symbol,
    endpoint: cachedData.endpoint || action.endpoint,
    params: cachedData.params || {},
    fields: cachedData.fields || action.fields || null,
    data: cachedData.data || [],
    rowCount: cachedData.row_count || action.row_count || 0,
  });

  console.log('[ChatStreamManager] Dataset added successfully:', action.dataset_id);
}

// ---------------------------------------------------------------------------
// handleStreamEvent – the big event handler, extracted from the hook
// ---------------------------------------------------------------------------

function handleStreamEvent(tabId: string, stream: ActiveStream, data: any): void {
  const s = store();
  const type = data?.type;
  const tid = streamThreadId(stream);

  switch (type) {
    // ---------------------------------------------------------------
    // Thread lifecycle
    // ---------------------------------------------------------------
    case 'thread_id': {
      if (data?.thread_id) {
        const newThreadId = data.thread_id;

        // Migrate state from pending thread to real thread
        if (!stream.activeThreadId && stream.pendingThreadId) {
          s.renameThread(stream.pendingThreadId, newThreadId);
        }

        // Register the thread on the tab
        s.addThreadToTab(tabId, newThreadId);
        s.setActiveThreadId(tabId, newThreadId);

        stream.activeThreadId = newThreadId;
        if (stream.onThreadCreated) {
          stream.onThreadCreated(
            {
              id: newThreadId,
              process_id: stream.process?.id || '',
              title: 'New Chat',
              pinned: false,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            stream.trimmedText,
          );
        }
      }
      break;
    }

    case 'title_update': {
      if (data?.title && data?.thread_id) {
        const tabState = s.tabStates[tabId];
        if (tabState) {
          const updatedThreads = tabState.threads.map(t =>
            t.id === data.thread_id ? { ...t, title: data.title } : t
          );
          s.setThreads(tabId, updatedThreads);
        }
      }
      break;
    }

    // ---------------------------------------------------------------
    // Content events
    // ---------------------------------------------------------------
    case 'content': {
      const chunk = (data as any).content ?? '';
      if (!chunk) return;

      appendContentChunk(tabId, stream, chunk);
      break;
    }

    case 'output_text_delta':
    case 'response.output_text.delta': {
      const payload = (data as any).event ?? data;
      const delta = typeof payload?.delta === 'string' ? payload.delta : '';
      if (!delta) return;

      appendContentChunk(tabId, stream, delta);
      break;
    }

    case 'output_text_done':
    case 'response.output_text.done': {
      const payload = (data as any).event ?? data;
      const fullText = typeof payload?.text === 'string' ? payload.text : '';
      if (fullText) {
        s.updateMessage(tid, stream.assistantMessageIndex, m => ({
          ...m,
          content: fullText,
        }));
      }
      break;
    }

    // ---------------------------------------------------------------
    // Tool call started
    // ---------------------------------------------------------------
    case 'tool_call_started':
    case 'tool_call.started': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? payload?.id ?? `tool_${Date.now()}`;
      const rawToolName = payload?.tool_name ?? payload?.name ?? 'Tool Call';
      const toolName = rawToolName
        .replace(/_/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/\b\w/g, (c: string) => c.toUpperCase());
      const tn = (rawToolName || '').toLowerCase();

      let toolType: ToolEvent['toolType'] = 'function_call';
      if (tn.includes('code') || tn.includes('interpreter')) {
        toolType = 'code_interpreter';
      } else if (tn.includes('mcp') || tn.includes('fmp') || tn.includes('market')) {
        toolType = 'mcp_call';
      } else if (tn.includes('file') && tn.includes('search')) {
        toolType = 'file_search';
      } else if (tn.includes('web') || tn.includes('search')) {
        toolType = 'web_search';
      }

      const toolArgs = payload?.arguments;
      const newEvent: ToolEvent = {
        id: callId,
        toolType,
        toolName,
        status: 'in_progress',
        startTime: Date.now(),
        arguments: toolArgs ? (typeof toolArgs === 'string' ? toolArgs : JSON.stringify(toolArgs)) : undefined,
        messageIndex: stream.assistantMessageIndex,
      };

      stream.messageHasTools = true;
      finalizeReasoningUnconditional(tabId, stream);

      const events = s.getOrCreateThread(tid).toolEvents;
      if (events.some(e => e.id === callId)) {
        console.log('[ChatStreamManager] Skipping duplicate event with same ID:', callId);
      } else {
        s.setToolEvents(tid, [...events, newEvent]);
      }
      break;
    }

    // ---------------------------------------------------------------
    // Tool call completed (no action payload)
    // ---------------------------------------------------------------
    case 'tool_call_completed':
    case 'tool_call.completed': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? payload?.id;
      const toolName = payload?.tool_name ?? payload?.name;

      console.log('[ChatStreamManager] Tool call completed:', { callId, toolName });

      if (callId) {
        s.updateToolEvent(tid, callId, te => ({
          ...te,
          status: 'completed' as const,
          endTime: Date.now(),
        }));
      }
      break;
    }

    // ---------------------------------------------------------------
    // Function call arguments streaming
    // ---------------------------------------------------------------
    case 'function_call_arguments_delta':
    case 'response.function_call_arguments.delta': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? payload?.call_id;
      if (callId) {
        const delta = payload?.delta ?? '';
        const events = s.getOrCreateThread(tid).toolEvents;
        if (events.some(e => e.id === callId)) {
          s.updateToolEvent(tid, callId, e => ({
            ...e,
            arguments: (e.arguments || '') + delta,
          }));
        }
      }
      break;
    }

    case 'function_call_arguments_done':
    case 'response.function_call_arguments.done': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? payload?.call_id;
      const args = payload?.arguments ?? '';
      if (callId) {
        const events = s.getOrCreateThread(tid).toolEvents;
        if (events.some(e => e.id === callId)) {
          s.updateToolEvent(tid, callId, te => ({
            ...te,
            arguments: args || te.arguments,
          }));
        }
      }
      break;
    }

    // ---------------------------------------------------------------
    // Tool call output (with pending_update detection)
    // ---------------------------------------------------------------
    case 'tool_call_output':
    case 'tool_call.output': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? payload?.id;
      const output = payload?.output ?? '';

      // Check for pending_update in output
      try {
        let outputData = output;
        if (typeof outputData === 'string') {
          outputData = JSON.parse(outputData);
          if (typeof outputData === 'string') {
            outputData = JSON.parse(outputData);
          }
        }
        console.log('[ChatStreamManager] Tool output parsed:', outputData);
        if (outputData?.pending_update) {
          const update = outputData.pending_update;
          console.log('[ChatStreamManager] Pending update detected:', update);

          const savedProcessId = stream.process?.id && stream.process.id !== 'unsaved'
            ? stream.process.id
            : stream.dataContext?.tools?.find(t => t.tabId === stream.dataContext?.activeTabId)?.processId || null;

          if (savedProcessId) {
            console.log('[ChatStreamManager] Setting pending update for saved process:', savedProcessId);
            s.setPendingUpdate(tid, {
              processId: savedProcessId,
              toolId: update.tool_id,
              tickers: update.tickers,
              weights: update.weights,
              params: update.params,
              fullResult: update.full_result,
            });
          } else {
            console.log('[ChatStreamManager] Unsaved process - emitting result update via callback');
            if (stream.onResultUpdate) {
              (async () => {
                const chartsCacheId = update.full_result?.charts_cache_id;
                let fullResult = { ...update.full_result };

                if (chartsCacheId && !fullResult.charts) {
                  console.log('[ChatStreamManager] Fetching cached charts for unsaved update:', chartsCacheId);
                  try {
                    const token = await stream.getToken();
                    const chartsResponse = await fetch(
                      `${API_BASE}/api/canvas/data/cache/charts/${chartsCacheId}`,
                      { headers: { Authorization: `Bearer ${token}` } },
                    );
                    if (chartsResponse.ok) {
                      const chartsData = await chartsResponse.json();
                      fullResult.charts = chartsData.charts;
                      console.log('[ChatStreamManager] Fetched charts:', Object.keys(chartsData.charts || {}));
                    }
                  } catch (e) {
                    console.warn('[ChatStreamManager] Error fetching cached charts:', e);
                  }
                }

                stream.onResultUpdate!({
                  toolId: update.tool_id,
                  tickers: update.tickers,
                  weights: update.weights,
                  params: update.params,
                  ...fullResult,
                });
              })();
            }
          }
        }
      } catch (e) {
        console.log('[ChatStreamManager] Tool output not JSON:', output, e);
      }

      if (callId) {
        // Skip if this is an action payload — agent_action handler will complete it
        let isActionPayload = false;
        try {
          const parsed = typeof output === 'string' ? JSON.parse(output) : output;
          if (parsed?.status && parsed?.action) {
            isActionPayload = true;
          }
        } catch {
          // not JSON, proceed normally
        }

        if (!isActionPayload) {
          s.updateToolEvent(tid, callId, te => ({
            ...te,
            status: 'completed' as const,
            result: output,
            endTime: Date.now(),
          }));
        }
      }
      break;
    }

    // ---------------------------------------------------------------
    // MCP call events
    // ---------------------------------------------------------------
    case 'mcp_call_in_progress': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? payload?.call_id ?? `mcp_${Date.now()}`;
      const toolName = payload?.name ?? payload?.tool_name ?? 'MCP Call';

      stream.messageHasTools = true;

      console.log('[ChatStreamManager] MCP call started:', { callId, toolName, messageIndex: stream.assistantMessageIndex });
      s.appendToolEvent(tid, {
        id: callId,
        toolType: 'mcp_call',
        toolName,
        status: 'in_progress',
        startTime: Date.now(),
        messageIndex: stream.assistantMessageIndex,
      });
      break;
    }

    case 'mcp_call_completed': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? payload?.call_id;
      console.log('[ChatStreamManager] MCP call completed:', { callId });
      if (callId) {
        s.updateToolEvent(tid, callId, te => ({
          ...te,
          status: 'completed' as const,
          endTime: Date.now(),
        }));
      }
      break;
    }

    case 'mcp_call_failed': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? payload?.call_id;
      const error = payload?.error ?? 'MCP call failed';
      console.log('[ChatStreamManager] MCP call failed:', { callId, error });
      if (callId) {
        s.updateToolEvent(tid, callId, te => ({
          ...te,
          status: 'failed' as const,
          error,
          endTime: Date.now(),
        }));
      }
      break;
    }

    // ---------------------------------------------------------------
    // Web search events
    // ---------------------------------------------------------------
    case 'web_search_in_progress':
    case 'web_search_searching': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? `websearch_${Date.now()}`;

      stream.messageHasTools = true;

      console.log('[ChatStreamManager] Web search started:', { callId, messageIndex: stream.assistantMessageIndex });
      const events = s.getOrCreateThread(tid).toolEvents;
      if (!events.some(e => e.id === callId)) {
        s.appendToolEvent(tid, {
          id: callId,
          toolType: 'web_search',
          toolName: 'Web Search',
          status: 'searching',
          startTime: Date.now(),
          messageIndex: stream.assistantMessageIndex,
        });
      }
      break;
    }

    case 'web_search_completed': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id;
      console.log('[ChatStreamManager] Web search completed:', { callId });
      if (callId) {
        s.updateToolEvent(tid, callId, te => ({
          ...te,
          status: 'completed' as const,
          endTime: Date.now(),
        }));
      }
      break;
    }

    // ---------------------------------------------------------------
    // File search events
    // ---------------------------------------------------------------
    case 'file_search_in_progress':
    case 'file_search_searching': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? `filesearch_${Date.now()}`;

      stream.messageHasTools = true;

      console.log('[ChatStreamManager] File search started:', { callId, messageIndex: stream.assistantMessageIndex });
      const events = s.getOrCreateThread(tid).toolEvents;
      if (!events.some(e => e.id === callId)) {
        s.appendToolEvent(tid, {
          id: callId,
          toolType: 'file_search',
          toolName: 'File Search',
          status: 'searching',
          startTime: Date.now(),
          messageIndex: stream.assistantMessageIndex,
        });
      }
      break;
    }

    case 'file_search_completed': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id;
      console.log('[ChatStreamManager] File search completed:', { callId });
      if (callId) {
        s.updateToolEvent(tid, callId, te => ({
          ...te,
          status: 'completed' as const,
          endTime: Date.now(),
        }));
      }
      break;
    }

    // ---------------------------------------------------------------
    // Code interpreter events
    // ---------------------------------------------------------------
    case 'code_interpreter_in_progress':
    case 'code_interpreter_interpreting': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id ?? `code_${Date.now()}`;

      stream.messageHasTools = true;

      console.log('[ChatStreamManager] Code interpreter started:', { callId, messageIndex: stream.assistantMessageIndex });
      const events = s.getOrCreateThread(tid).toolEvents;
      if (!events.some(e => e.id === callId)) {
        s.appendToolEvent(tid, {
          id: callId,
          toolType: 'code_interpreter',
          toolName: 'Code Interpreter',
          status: 'interpreting',
          startTime: Date.now(),
          messageIndex: stream.assistantMessageIndex,
        });
      }
      break;
    }

    case 'code_interpreter_completed': {
      const payload = (data as any).event ?? data;
      const callId = payload?.item_id;
      console.log('[ChatStreamManager] Code interpreter completed:', { callId });
      if (callId) {
        s.updateToolEvent(tid, callId, te => ({
          ...te,
          status: 'completed' as const,
          endTime: Date.now(),
        }));
      }
      break;
    }

    // ---------------------------------------------------------------
    // Reasoning events
    // ---------------------------------------------------------------
    case 'reasoning_delta':
    case 'response.reasoning_summary_text.delta': {
      const payload = (data as any).event ?? data;
      const delta = typeof payload?.delta === 'string' ? payload.delta : '';
      if (!delta) return;

      s.setReasoningStreaming(tid, true);
      const threadState = s.getOrCreateThread(tid);
      s.setReasoningText(tid, threadState.reasoningText + delta);

      if (!stream.activeReasoningId) {
        // Create new reasoning segment
        const newId = `reasoning_${++stream.reasoningSeqCounter}`;
        stream.activeReasoningId = newId;
        stream.reasoningBuffer = delta;
        s.appendToolEvent(tid, {
          id: newId,
          toolType: 'reasoning' as const,
          toolName: 'Reasoning',
          status: 'in_progress' as const,
          startTime: Date.now(),
          result: delta,
          messageIndex: stream.assistantMessageIndex,
        });
      } else {
        // Buffer the delta
        stream.reasoningBuffer += delta;
        // Schedule a flush if not already pending
        if (!stream.reasoningFlushTimer) {
          stream.reasoningFlushTimer = setTimeout(() => {
            stream.reasoningFlushTimer = null;
            const buffered = stream.reasoningBuffer;
            const id = stream.activeReasoningId;
            if (id && buffered) {
              store().updateToolEvent(streamThreadId(stream), id, e => ({
                ...e,
                result: buffered,
              }));
            }
          }, 300);
        }
      }
      break;
    }

    case 'reasoning_summary_done':
    case 'response.reasoning_summary_text.done': {
      s.setReasoningStreaming(tid, false);
      finalizeReasoningUnconditional(tabId, stream);
      break;
    }

    // ---------------------------------------------------------------
    // Status / progress
    // ---------------------------------------------------------------
    case 'status':
    case 'progress': {
      const statusMsg = (data as any).message ?? (data as any).status ?? 'Analyzing...';
      s.setStatusMessage(tid, statusMsg);
      break;
    }

    // ---------------------------------------------------------------
    // Error
    // ---------------------------------------------------------------
    case 'error': {
      const errorMsg = (data as any).error ?? 'An error occurred';
      const fatal = (data as any).fatal ?? false;
      console.error('[ChatStreamManager] Canvas chat error:', errorMsg);
      if (fatal) {
        stream.service.close();
      }
      break;
    }

    // ---------------------------------------------------------------
    // Done / complete
    // ---------------------------------------------------------------
    case 'done':
    case 'complete': {
      debugLog('MetadataPersist', { event: 'done', message_id: data?.message_id, thread_id: data?.thread_id });
      s.setIsLoading(tid, false);
      s.setReasoningStreaming(tid, false);
      s.setStatusMessage(tid, '');
      finalizeReasoning(tabId, stream);
      finalizeLingeringToolEvents(tid);

      const messageId = data?.message_id;
      if (messageId) {
        const threadState = s.getOrCreateThread(tid);
        debugLog('MetadataPersist', { action: 'persist', messageId, toolEventsCount: threadState.toolEvents.length });
        persistMessageMetadata(stream, messageId);
      } else {
        debugLog('MetadataPersist', { warn: 'no message_id in done event' });
      }
      break;
    }

    case 'cancelled': {
      debugLog('MetadataPersist', { event: 'cancelled', message_id: data?.message_id });
      s.setIsLoading(tid, false);
      s.setReasoningStreaming(tid, false);
      s.setStatusMessage(tid, '');
      finalizeReasoning(tabId, stream);
      finalizeLingeringToolEvents(tid);

      const cancelledMessageId = data?.message_id;
      if (cancelledMessageId) {
        debugLog('MetadataPersist', { action: 'persist_cancelled', messageId: cancelledMessageId });
        persistMessageMetadata(stream, cancelledMessageId);
      }
      break;
    }

    case 'resume_rejected': {
      // Silently ignore
      break;
    }

    // ---------------------------------------------------------------
    // Agent action events
    // ---------------------------------------------------------------
    case 'agent_action': {
      handleAgentAction(tabId, stream, data);
      break;
    }

    case 'agent_error': {
      handleAgentError(tabId, stream, data);
      break;
    }

    // ---------------------------------------------------------------
    // Default
    // ---------------------------------------------------------------
    default: {
      if (
        type &&
        ![
          'response.output_text.delta',
          'response.content_part.delta',
          'response.function_call_arguments.delta',
        ].includes(type)
      ) {
        console.log('[ChatStreamManager] Unhandled event type:', type, data);
      }
      break;
    }
  }
}

// ---------------------------------------------------------------------------
// Internal: append a content chunk (handles post-tool message splitting)
// ---------------------------------------------------------------------------

function flushContentBuffer(stream: ActiveStream): void {
  stream.contentFlushRaf = null;
  const buffered = stream.contentBuffer;
  if (!buffered) return;
  stream.contentBuffer = '';

  const s = store();
  const tid = streamThreadId(stream);

  if (stream.messageHasTools && stream.preToolContentSeen) {
    const threadState = s.getOrCreateThread(tid);
    const idx = stream.assistantMessageIndex;
    const existingContent = (idx >= 0 && idx < threadState.messages.length) ? (threadState.messages[idx].content || '') : '';

    if (existingContent.length > 10) {
      const newMsg: Message = {
        id: `temp-assistant-${Date.now()}`,
        role: 'assistant',
        content: buffered,
        created_at: new Date().toISOString(),
      };
      s.appendMessage(tid, newMsg);
      stream.assistantMessageIndex = s.getOrCreateThread(tid).messages.length - 1;
    } else {
      s.updateMessage(tid, idx, m => ({
        ...m,
        content: (m.content || '') + buffered,
      }));
    }
    stream.messageHasTools = false;
    stream.preToolContentSeen = true;
  } else {
    s.updateMessage(tid, stream.assistantMessageIndex, m => ({
      ...m,
      content: (m.content || '') + buffered,
    }));
    stream.preToolContentSeen = true;
  }
}

function appendContentChunk(_tabId: string, stream: ActiveStream, chunk: string): void {
  stream.contentBuffer += chunk;
  if (stream.contentFlushRaf === null) {
    stream.contentFlushRaf = requestAnimationFrame(() => flushContentBuffer(stream));
  }
}

// ---------------------------------------------------------------------------
// Internal: agent_action handler
// ---------------------------------------------------------------------------

function handleAgentAction(tabId: string, stream: ActiveStream, data: any): void {
  const s = store();
  const tid = streamThreadId(stream);
  const action = data?.action;
  const actionId = data?.actionId;
  const itemId = data?.itemId;
  const message = data?.message;
  const toolName = data?.toolName ?? action?.type ?? 'Action';

  const actionDisplayNames: Record<string, string> = {
    add_dataset: 'Add Dataset To Workspace',
    create_chart: 'Create Chart',
    create_tab: 'Create Tab',
    create_pivot: 'Create Pivot Table',
    remove_dataset: 'Remove Dataset',
    remove_chart: 'Remove Chart',
    remove_pivot: 'Remove Pivot Table',
    create_group: 'Create Dataset Group',
  };
  const displayName = actionDisplayNames[action?.type] || toolName;

  console.log('[ChatStreamManager] Received agent_action event:', {
    action,
    actionId,
    itemId,
    message,
    toolName,
    displayName,
  });

  stream.messageHasTools = true;

  // Extract parameters from action object (exclude 'type' which is the action kind)
  const actionParams = action
    ? Object.fromEntries(Object.entries(action).filter(([k]) => k !== 'type'))
    : undefined;
  const argumentsStr = actionParams && Object.keys(actionParams).length > 0
    ? JSON.stringify(actionParams)
    : undefined;

  // Mark the matching in-progress tool event as completed
  const events = s.getOrCreateThread(tid).toolEvents;
  const inProgressStatuses = ['in_progress', 'arguments_delta', 'arguments_done'];

  let updatedEvents: ToolEvent[] | null = null;

  // First priority: exact itemId match
  if (itemId) {
    const exactMatch = events.find(e => e.id === itemId);
    if (exactMatch && inProgressStatuses.includes(exactMatch.status)) {
      console.log('[ChatStreamManager] Marking exact itemId match as completed:', itemId);
      updatedEvents = events.map(e =>
        e.id === itemId
          ? { ...e, status: 'completed' as const, endTime: Date.now(), result: message, arguments: e.arguments || argumentsStr }
          : e,
      );
    }
  }

  // Second priority: matching tool name (FIFO)
  if (!updatedEvents) {
    const matchingInProgress = events.find(
      e => inProgressStatuses.includes(e.status) && e.toolName === displayName,
    );
    if (matchingInProgress) {
      console.log('[ChatStreamManager] Marking matching in-progress event as completed:', matchingInProgress.id);
      updatedEvents = events.map(e =>
        e.id === matchingInProgress.id
          ? { ...e, status: 'completed' as const, endTime: Date.now(), result: message, arguments: e.arguments || argumentsStr }
          : e,
      );
    }
  }

  // Third priority: any in-progress event
  if (!updatedEvents) {
    const anyInProgress = events.find(e => inProgressStatuses.includes(e.status));
    if (anyInProgress) {
      console.log('[ChatStreamManager] Marking any in-progress event as completed:', anyInProgress.id, '(was:', anyInProgress.toolName, ')');
      updatedEvents = events.map(e =>
        e.id === anyInProgress.id
          ? {
              ...e,
              toolName: displayName || e.toolName,
              status: 'completed' as const,
              endTime: Date.now(),
              result: message,
              arguments: e.arguments || argumentsStr,
            }
          : e,
      );
    }
  }

  // Fallback: create a new completed event
  if (!updatedEvents) {
    const newEventId = actionId || `action_${Date.now()}`;
    console.log('[ChatStreamManager] Creating new tool event for action:', { newEventId, displayName });
    updatedEvents = [
      ...events,
      {
        id: newEventId,
        toolType: 'function_call' as const,
        toolName: displayName,
        status: 'completed' as const,
        startTime: Date.now(),
        endTime: Date.now(),
        result: message,
        arguments: argumentsStr,
        messageIndex: stream.assistantMessageIndex,
      },
    ];
  }

  s.setToolEvents(tid, updatedEvents);

  // Validate action before execution
  const validation = validateAction(action);
  if (!validation.valid) {
    console.error('[ChatStreamManager] Action validation failed:', validation.error);
    reportActionResult(tabId, stream.runId, actionId, action, { success: false, error: validation.error });
    return;
  }

  // Route action based on type
  if (action?.type === 'add_dataset') {
    handleAddDatasetAction(stream, action)
      .then(() => {
        reportActionResult(tabId, stream.runId, actionId, action, { success: true });
      })
      .catch(err => {
        console.error('[ChatStreamManager] handleAddDatasetAction failed:', err);
        reportActionResult(tabId, stream.runId, actionId, action, { success: false, error: err.message });
      });
  } else if (action?.type === 'create_tab') {
    try {
      const wsStore = useDataWorkspaceStore.getState();
      const newTabId = wsStore.addTab('single', action.name || 'New Tab');
      console.log('[ChatStreamManager] Created new data tab:', { tabId: newTabId, name: action.name });
      reportActionResult(tabId, stream.runId, actionId, action, { success: true });
    } catch (err: any) {
      console.error('[ChatStreamManager] Failed to create tab:', err);
      reportActionResult(tabId, stream.runId, actionId, action, { success: false, error: err.message });
    }
  } else if (action?.type === 'remove_dataset') {
    (async () => {
      const removeValidation = validateAction(action);
      if (!removeValidation.valid) {
        console.error('[ChatStreamManager] Validation failed:', removeValidation.error);
        reportActionResult(tabId, stream.runId, actionId, action, { success: false, error: removeValidation.error });
        return;
      }

      const confirmed = await requestConfirmation(tabId, stream, action);
      if (!confirmed) {
        console.log('[ChatStreamManager] User cancelled remove_dataset');
        reportActionResult(tabId, stream.runId, actionId, action, { success: false, cancelled: true });
        return;
      }

      try {
        const wsStore = useDataWorkspaceStore.getState();
        wsStore.removeDataset(action.dataset_id);
        reportActionResult(tabId, stream.runId, actionId, action, { success: true });
      } catch (err: any) {
        console.error('[ChatStreamManager] Failed to remove dataset:', err);
        reportActionResult(tabId, stream.runId, actionId, action, { success: false, error: err.message });
      }
    })();
  } else if (action?.type === 'create_chart') {
    handleCreateChart(tabId, stream, action, actionId);
  } else if (action?.type === 'start_tool_analysis') {
    handleStartToolAnalysis(tabId, stream, action);
  } else if (action?.type === 'create_pivot') {
    handleCreatePivot(tabId, stream, action, actionId);
  } else if (action?.type === 'remove_chart' || action?.type === 'remove_pivot') {
    handleRemoveChartOrPivot(tabId, stream, action, actionId);
  } else if (action?.type === 'create_group') {
    const wsStore = useDataWorkspaceStore.getState();
    const activeTabId = wsStore.activeTabId;
    if (activeTabId) {
      wsStore.createDatasetGroup(action.name || 'New Group');
    }
    reportActionResult(tabId, stream.runId, actionId ?? '', action, { success: true });
  } else {
    console.warn('[ChatStreamManager] Unhandled action type:', action?.type);
  }
}

// ---------------------------------------------------------------------------
// Internal: create_chart handler
// ---------------------------------------------------------------------------

function handleCreateChart(tabId: string, stream: ActiveStream, action: any, actionId: string | undefined): void {
  const wsStore = useDataWorkspaceStore.getState();
  const config = action.config;

  // Find the tab that has the data (for selectedDatasetIds resolution)
  const activeTabId = wsStore.activeTabId;
  const targetTabId = activeTabId || tabId;
  const targetTab = wsStore.tabs.find(t => t.id === targetTabId);

  if (!targetTab || (targetTab.datasets?.length ?? 0) === 0) {
    // Retry: datasets may still be loading from a prior add_dataset action
    let attempts = 0;
    const interval = setInterval(() => {
      attempts++;
      const retryStore = useDataWorkspaceStore.getState();
      const retryTab = retryStore.tabs.find(t => t.id === targetTabId);
      if ((retryTab?.datasets?.length ?? 0) > 0 || attempts >= 10) {
        clearInterval(interval);
        if ((retryTab?.datasets?.length ?? 0) > 0) {
          addChartInline(retryStore, targetTabId, config, retryTab);
          reportActionResult(tabId, stream.runId, actionId ?? '', action, { success: true });
        } else {
          reportActionResult(tabId, stream.runId, actionId ?? '', action, { success: false, error: 'No datasets found after retries' });
        }
      }
    }, 500);
    stream.pendingIntervals.push(interval);
    return;
  }

  try {
    addChartInline(wsStore, targetTabId, config, targetTab);
    reportActionResult(tabId, stream.runId, actionId ?? '', action, { success: true });
  } catch (err: any) {
    console.error('[ChatStreamManager] Failed to create chart:', err);
    reportActionResult(tabId, stream.runId, actionId ?? '', action, { success: false, error: err?.message });
  }
}

function addChartInline(wsStore: any, targetTabId: string, config: any, tab: any): void {
  const localId = `ai-chart-${Date.now()}`;
  const groupId = tab?.activeGroupId || tab?.datasetGroups?.[0]?.id;

  wsStore.addChartResult(targetTabId, {
    localId,
    name: config?.title || 'Chart',
    config: {
      id: localId,
      sourceTabId: targetTabId,
      sourceSheetId: 'legacy-sheet',
      chartType: config?.chartType || 'line',
      xAxis: config?.xAxis || '',
      ySeries: config?.ySeries || [],
      title: config?.title,
      showLegend: config?.showLegend ?? true,
      showGrid: config?.showGrid ?? true,
      selectedDatasetIds: config?.selectedDatasetIds,
      ohlcFields: config?.ohlcFields,
    },
    createdAt: Date.now(),
    groupId,
  });

  wsStore.setContentView(targetTabId, { type: 'chart', chartLocalId: localId });
  wsStore.setSidebarViewMode('chart');
  wsStore.setViewMode(targetTabId, 'chart');
}

// ---------------------------------------------------------------------------
// Internal: start_tool_analysis handler
// ---------------------------------------------------------------------------

function handleStartToolAnalysis(_tabId: string, stream: ActiveStream, action: any): void {
  const { analysis_id, tool_id, tool_name, tickers } = action;

  (async () => {
    try {
      const token = await stream.getToken();
      const response = await fetch(`${API_BASE}/api/canvas/analysis/cache/${analysis_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        if (response.status === 404) {
          console.warn('[ChatStreamManager] Analysis results expired');
          return;
        }
        throw new Error(`Failed to fetch analysis: ${response.status}`);
      }

      const analysisResult = await response.json();
      const wsStore = useDataWorkspaceStore.getState();
      const activeTabId = wsStore.activeTabId;
      if (!activeTabId) return;

      const activeTab = wsStore.tabs.find(t => t.id === activeTabId);
      const groupId = activeTab?.activeGroupId || activeTab?.datasetGroups?.[0]?.id;
      const localId = `ai-result-${Date.now()}`;
      const chartKeys = Object.keys(analysisResult.charts || {}).filter(k => analysisResult.charts[k]?.plotly);

      wsStore.setCurrentToolId(activeTabId, tool_id);
      wsStore.updatePerToolState(activeTabId, {
        manualTickers: tickers.join(', '),
        toolParams: analysisResult.params || {},
        toolStep: 4,
      });
      wsStore.addToolResult(activeTabId, tool_id, {
        localId,
        result: { ...analysisResult, _metric_cards: analysisResult.metric_cards },
        toolId: tool_id,
        processName: `${tool_name || tool_id} - ${(tickers || []).slice(0, 3).join(', ') || 'Analysis'}`,
        processId: null,
        tickers: tickers || [],
        activeChart: chartKeys[0] || '',
        groupId,
      });
      wsStore.setContentView(activeTabId, { type: 'tool-result', toolTabId: activeTabId, resultLocalId: localId });
      wsStore.setSidebarViewMode('tools');
      wsStore.setViewMode(activeTabId, 'tools');
    } catch (error) {
      console.error('[ChatStreamManager] Failed to fetch analysis results:', error);
    }
  })();
}

// ---------------------------------------------------------------------------
// Internal: create_pivot handler
// ---------------------------------------------------------------------------

function handleCreatePivot(_tabId: string, _stream: ActiveStream, action: any, _actionId: string | undefined): void {
  const wsStore = useDataWorkspaceStore.getState();
  const config = action.config;

  const activeTabId = wsStore.activeTabId;
  const targetTab = wsStore.tabs.find(t => t.id === activeTabId);

  if (!targetTab || (targetTab.datasets?.length ?? 0) === 0) {
    console.error('[ChatStreamManager] No datasets on active tab for pivot creation');
    return;
  }

  const localId = `ai-pivot-${Date.now()}`;
  const groupId = targetTab.activeGroupId || targetTab.datasetGroups?.[0]?.id;
  const rows = config?.rows || [];
  const values = config?.values || [];

  try {
    wsStore.addPivotResult(activeTabId!, {
      localId,
      name: `${rows.join(', ')} by ${values.map((v: any) => v.field).join(', ')}`,
      config: {
        id: localId,
        sourceTabId: activeTabId!,
        sourceSheetId: 'legacy-sheet',
        rows,
        columns: config?.columns || [],
        values,
        selectedDatasetIds: config?.selectedDatasetIds,
      },
      createdAt: Date.now(),
      groupId,
    });

    wsStore.setContentView(activeTabId!, { type: 'pivot', pivotLocalId: localId });
    wsStore.setSidebarViewMode('pivot');
    wsStore.setViewMode(activeTabId!, 'pivot');
  } catch (err) {
    console.error('[ChatStreamManager] Failed to create pivot table:', err);
  }
}

// ---------------------------------------------------------------------------
// Internal: remove_chart / remove_pivot handler
// ---------------------------------------------------------------------------

function handleRemoveChartOrPivot(tabId: string, stream: ActiveStream, action: any, actionId: string | undefined): void {
  const isChart = action.type === 'remove_chart';
  const itemType = isChart ? 'chart' : 'pivot table';

  (async () => {
    const confirmed = await requestConfirmation(tabId, stream, action);
    if (!confirmed) {
      console.log(`[ChatStreamManager] User cancelled remove_${isChart ? 'chart' : 'pivot'}`);
      reportActionResult(tabId, stream.runId, actionId ?? '', action, { success: false, cancelled: true });
      return;
    }

    try {
      const wsStore = useDataWorkspaceStore.getState();
      if (isChart) {
        const chartLocalId = action.tab_id;
        const ownerTab = wsStore.tabs.find((t: any) =>
          t.chartResults?.some((cr: any) => cr.localId === chartLocalId),
        );
        if (ownerTab) {
          wsStore.removeChartResult(ownerTab.id, chartLocalId);
        } else {
          wsStore.removeTab(action.tab_id);
        }
      } else {
        wsStore.removeTab(action.tab_id);
      }
      console.log(`[ChatStreamManager] ${itemType} removed:`, action.tab_id);
      reportActionResult(tabId, stream.runId, actionId ?? '', action, { success: true });
    } catch (err: any) {
      console.error(`[ChatStreamManager] Failed to remove ${itemType}:`, err);
      reportActionResult(tabId, stream.runId, actionId ?? '', action, { success: false, error: err.message });
    }
  })();
}

// ---------------------------------------------------------------------------
// Internal: agent_error handler
// ---------------------------------------------------------------------------

function handleAgentError(_tabId: string, stream: ActiveStream, data: any): void {
  const s = store();
  const tid = streamThreadId(stream);
  const errorMessage = data?.message || 'Agent action failed';
  const errorItemId = data?.itemId;

  console.error('[ChatStreamManager] Agent error:', {
    message: errorMessage,
    actionId: data?.actionId,
    itemId: errorItemId,
  });

  const events = s.getOrCreateThread(tid).toolEvents;
  const inProgressStatuses = ['in_progress', 'arguments_delta', 'arguments_done'];

  if (errorItemId) {
    const exact = events.find(e => e.id === errorItemId && inProgressStatuses.includes(e.status));
    if (exact) {
      s.setToolEvents(
        tid,
        events.map(e =>
          e.id === errorItemId
            ? { ...e, status: 'failed' as const, endTime: Date.now(), error: errorMessage }
            : e,
        ),
      );
      return;
    }
  }

  const lastInProgress = [...events].reverse().find(e => inProgressStatuses.includes(e.status));
  if (lastInProgress) {
    console.log('[ChatStreamManager] Marking tool event as failed:', lastInProgress.id);
    s.setToolEvents(
      tid,
      events.map(e =>
        e.id === lastInProgress.id
          ? { ...e, status: 'failed' as const, endTime: Date.now(), error: errorMessage }
          : e,
      ),
    );
  }
}
