import { STREAM_STORAGE_KEYS, streamingStorage } from './streamingStorage';
import { API_BASE } from './api';

// Types imported only where needed to avoid runtime deps

type StreamMessage =
  | { type: 'content'; content: string }
  | { type: 'status'; message: string }
  | { type: 'sources'; sources: unknown[] }
  | { type: 'charts'; charts: unknown[] }
  | { type: 'extras'; extras: Record<string, unknown> }
  | { type: string; rawType?: string; event?: Record<string, unknown> }
  | Record<string, unknown>;

interface StreamingOptions {
  onMessage: (data: StreamMessage) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

interface StreamContextPayload {
  agentMode?: string;
  portfolioId?: string;
  sessionId?: string;
  fileIds?: string[];
  selectedModel?: string;
  deepAnalysisMode?: boolean;
  prioritizedTools?: string[];
  isResume?: boolean;
  isBlocking?: boolean;
  messageId?: string;
  lastEventId?: string;
  extraParams?: Record<string, string>;
  /** Custom cancel endpoint for non-chat streaming (e.g., postmortem analysis) */
  cancelEndpoint?: string;
}

interface StreamingServiceOptions {
  streamEndpoint?: string;
  healthEndpoint?: string;
}

const CONTEXT_KEY = STREAM_STORAGE_KEYS.context;
const MESSAGE_ID_KEY = STREAM_STORAGE_KEYS.messageId;
const LAST_EVENT_ID_KEY = STREAM_STORAGE_KEYS.lastEventId;
const SESSION_ID_KEY = STREAM_STORAGE_KEYS.sessionId;

const IDLE_FINALIZE_MS = Number(((import.meta as any).env?.VITE_STREAM_IDLE_FINALIZE_MS) || 1200000);

export class StreamingService {
  private eventSource: EventSource | null = null;
  private reconnecting = false;
  private cancelled = false;
  private retries = 0;
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private lastMessageTs = 0;
  private streamVersion = 1;
  private resuming = false;
  private navigating = false;
  private finished = false;
  private readonly structuredEventTypeMap: Record<string, string> = {
    // Response lifecycle
    'response.created': 'response_created',
    'response.queued': 'response_queued',
    'response.in_progress': 'response_in_progress',
    'response.incomplete': 'response_incomplete',
    'response.completed': 'response_completed',
    'response.failed': 'response_failed',

    // Output text
    'response.output_text.delta': 'output_text_delta',
    'response.output_text.done': 'output_text_done',
    'response.output_text.annotation.added': 'output_text_annotation_added',
    'output_text.delta': 'output_text_delta',
    'output_text.done': 'output_text_done',
    'output_text.annotation_added': 'output_text_annotation_added',

    // Reasoning
    'response.reasoning_text.delta': 'reasoning_delta',
    'response.reasoning_text.done': 'reasoning_done',
    'response.reasoning_summary_text.delta': 'reasoning_delta',
    'response.reasoning_summary_part.added': 'reasoning_summary_part',
    'response.reasoning_summary_text.done': 'reasoning_summary_done',
    'reasoning.delta': 'reasoning_delta',
    'reasoning.done': 'reasoning_done',
    'reasoning.summary_part': 'reasoning_summary_part',
    'reasoning.summary_done': 'reasoning_summary_done',

    // Refusal
    'response.refusal.delta': 'refusal_delta',
    'response.refusal.done': 'refusal_done',
    'refusal.delta': 'refusal_delta',
    'refusal.done': 'refusal_done',

    // Function calls
    'response.function_call_arguments.delta': 'function_call_arguments_delta',
    'response.function_call_arguments.done': 'function_call_arguments_done',
    'function_call.arguments_delta': 'function_call_arguments_delta',
    'function_call.arguments_done': 'function_call_arguments_done',

    // MCP calls
    'response.mcp_call.in_progress': 'mcp_call_in_progress',
    'response.mcp_call.completed': 'mcp_call_completed',
    'response.mcp_call.failed': 'mcp_call_failed',
    'response.mcp_call_arguments.delta': 'mcp_call_arguments_delta',
    'response.mcp_call_arguments.done': 'mcp_call_arguments_done',
    'mcp_call.in_progress': 'mcp_call_in_progress',
    'mcp_call.completed': 'mcp_call_completed',
    'mcp_call.failed': 'mcp_call_failed',
    'mcp_call.arguments_delta': 'mcp_call_arguments_delta',
    'mcp_call.arguments_done': 'mcp_call_arguments_done',
    'response.mcp_list_tools.in_progress': 'mcp_list_tools_in_progress',
    'response.mcp_list_tools.completed': 'mcp_list_tools_completed',
    'response.mcp_list_tools.failed': 'mcp_list_tools_failed',
    'mcp_list_tools.in_progress': 'mcp_list_tools_in_progress',
    'mcp_list_tools.completed': 'mcp_list_tools_completed',
    'mcp_list_tools.failed': 'mcp_list_tools_failed',

    // Search lifecycle
    'response.web_search_call.in_progress': 'web_search_in_progress',
    'response.web_search_call.searching': 'web_search_searching',
    'response.web_search_call.completed': 'web_search_completed',
    'response.file_search_call.in_progress': 'file_search_in_progress',
    'response.file_search_call.searching': 'file_search_searching',
    'response.file_search_call.completed': 'file_search_completed',
    'web_search.in_progress': 'web_search_in_progress',
    'web_search.searching': 'web_search_searching',
    'web_search.completed': 'web_search_completed',
    'file_search.in_progress': 'file_search_in_progress',
    'file_search.searching': 'file_search_searching',
    'file_search.completed': 'file_search_completed',

    // Code interpreter
    'response.code_interpreter_call.in_progress': 'code_interpreter_in_progress',
    'response.code_interpreter_call.interpreting': 'code_interpreter_interpreting',
    'response.code_interpreter_call.completed': 'code_interpreter_completed',
    'response.code_interpreter_call_code.delta': 'code_interpreter_code_delta',
    'response.code_interpreter_call_code.done': 'code_interpreter_code_done',
    'code_interpreter.in_progress': 'code_interpreter_in_progress',
    'code_interpreter.interpreting': 'code_interpreter_interpreting',
    'code_interpreter.completed': 'code_interpreter_completed',
    'code_interpreter.code_delta': 'code_interpreter_code_delta',
    'code_interpreter.code_done': 'code_interpreter_code_done',

    // Custom tool call input
    'response.custom_tool_call_input.delta': 'custom_tool_call_input_delta',
    'response.custom_tool_call_input.done': 'custom_tool_call_input_done',
    'custom_tool_call.input_delta': 'custom_tool_call_input_delta',
    'custom_tool_call.input_done': 'custom_tool_call_input_done',

    // Output/content parts
    'response.output_item.added': 'output_item_added',
    'response.output_item.done': 'output_item_done',
    'response.content_part.added': 'content_part_added',
    'response.content_part.done': 'content_part_done',
    'output_item.added': 'output_item_added',
    'output_item.done': 'output_item_done',
    'content_part.added': 'content_part_added',
    'content_part.done': 'content_part_done',

    // Image generation lifecycle
    'response.image_generation_call.in_progress': 'image_generation_in_progress',
    'response.image_generation_call.generating': 'image_generation_generating',
    'response.image_generation_call.partial_image': 'image_generation_partial_image',
    'response.image_generation_call.completed': 'image_generation_completed',
    'image_generation.in_progress': 'image_generation_in_progress',
    'image_generation.generating': 'image_generation_generating',
    'image_generation.partial_image': 'image_generation_partial_image',
    'image_generation.completed': 'image_generation_completed',

    // Synthesised LangGraph events
    'tool_call.started': 'tool_call_started',
    'tool_call.completed': 'tool_call_completed',
    'tool_call.output': 'tool_call_output',
    'agent.updated': 'agent_updated',

    // Default error catch-all
    'error': 'stream_error',
  };
  private readonly loggedStructuredEvents = new Set<string>();
  private maxRetryMs = Number(((import.meta as any).env?.VITE_STREAM_MAX_RETRY_MS) || 20000);
  // private pollHealthMs = Number(((import.meta as any).env?.VITE_POLL_HEALTH_MS) || 30000);
  private currentMessage = '';
  private currentOptions: StreamingOptions | null = null;
  private currentPayload: { message: string } | null = null;
  private currentContext: StreamContextPayload | null = null;
  private customStreamEndpoint?: string;
  private customHealthEndpoint?: string;
  /** Override endpoint passed to startStream - stored for reconnects */
  private activeOverrideEndpoint?: string;
  // Always target the backend base URL; endpoints live under /v6 in our API
  private get streamEndpoint(): string {
    // Prefer active override (set per-call) over constructor-configured endpoint
    return this.activeOverrideEndpoint || this.customStreamEndpoint || `${API_BASE}/v6/chat/stream`;
  }
  private get healthEndpoint(): string {
    return this.customHealthEndpoint || `${API_BASE}/v6/health`;
  }

  constructor(options?: StreamingServiceOptions) {
    if (options?.streamEndpoint) {
      this.customStreamEndpoint = options.streamEndpoint;
    }
    if (options?.healthEndpoint) {
      this.customHealthEndpoint = options.healthEndpoint;
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => {
        this.navigating = true;
      });
    }
  }

  async startStream(
    message: string,
    options: StreamingOptions,
    context?: StreamContextPayload,
    overrideEndpoint?: string,
  ) {
    this.navigating = false;
    // Close any existing connection
    this.close();
    this.finished = false;
    this.cancelled = false;
    this.currentMessage = '';
    this.currentOptions = options;
    this.currentPayload = { message };
    this.currentContext = context ? { ...context } : null;
    this.resuming = Boolean(context?.isResume);
    this.retries = 0;
    this.lastMessageTs = Date.now();
    // Build query parameters with full context
    const params = new URLSearchParams({ message });

    // Add agent mode if provided
    if (context?.agentMode) {
      params.set('agent_mode', context.agentMode);
    }

    // Add portfolio ID if provided
    console.log('[Streaming] context received:', context);
    if (context?.portfolioId) {
      console.log('[Streaming] Setting portfolio_id param:', context.portfolioId);
      params.set('portfolio_id', context.portfolioId);
    } else {
      console.log('[Streaming] NO PORTFOLIO ID IN CONTEXT');
    }

    // Add file IDs if provided
    if (context?.fileIds && context.fileIds.length > 0) {
      params.set('file_ids', context.fileIds.join(','));
    }

    // Add selected model if provided
    if (context?.selectedModel) {
      params.set('selected_model', context.selectedModel);
      // Some endpoints (e.g., postmortems) expect `model`; send both for compatibility
      params.set('model', context.selectedModel);
    }

    // Add deep analysis mode if provided
    console.log('[Streaming] deepAnalysisMode in context:', context?.deepAnalysisMode);
    if (context?.deepAnalysisMode !== undefined) {
      params.set('deep_analysis_mode', String(context.deepAnalysisMode));
      console.log('[Streaming] Set deep_analysis_mode param to:', String(context.deepAnalysisMode));
    }

    // Add prioritized tools if provided
    if (context?.prioritizedTools && context.prioritizedTools.length > 0) {
      params.set('prioritized_tools', context.prioritizedTools.join(','));
      console.log('[Streaming] Set prioritized_tools param to:', context.prioritizedTools.join(','));
    }

    // Ensure we have a session_id for continuity across streaming turns
    try {
      let sid = context?.sessionId || localStorage.getItem('session_id');
      if (!sid) {
        // Only generate web_* session IDs in development environments
        const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (isLocal) {
          // Generate a client-side session id when absent (server accepts any unique id)
          sid = `web_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;
          localStorage.setItem('session_id', sid);
        }
        // In production, let server handle session generation
      }
      if (sid) {
        params.set('session_id', sid);
      }
    } catch (error) {
      console.error('Failed to attach session ID:', error);
    }

    // Attach client-supplied message id so backend can align run identifiers before first event
    if (context?.messageId) {
      params.set('client_message_id', context.messageId);
    }

    // Attach auth for SSE using short-lived tickets (preferred) or token fallback
    // Tickets prevent JWT exposure in URLs which would be logged by proxies/CDNs
    try {
      const token = await this.getAuthToken();
      if (token) {
        // Exchange JWT for short-lived SSE ticket
        const ticket = await this.exchangeTokenForTicket(token);
        if (ticket) {
          params.set('ticket', ticket);
        } else {
          // Fallback to token if ticket exchange fails (legacy support)
          params.set('token', token);
        }
      } else {
        // Dev bypass via query params if configured
        const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
        const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (isLocal && devSecret) {
          params.set('x_dev_secret', devSecret);
          params.set('x_dev_user_id', 'dev-local-user');
        }
      }
    } catch (error) {
      console.error('Failed to attach auth for SSE:', error);
    }

    // Attach organization context for SSE (headers not supported by EventSource)
    try {
      const activeOrgId = localStorage.getItem('activeOrganization');
      if (activeOrgId) {
        params.set('org_id', activeOrgId);
      }
    } catch (error) {
      console.error('Failed to attach organization ID:', error);
    }

    // Check for resume parameters from storage (SSE resumption after page refresh)
    const allowResume = Boolean(this.resuming || context?.isResume);
    let resumeCandidate: string | null = null;
    let resumeMessageId: string | null = null;
    let shouldResume = false;
    if (allowResume) {
      try {
        console.log('[Streaming Debug] context?.lastEventId:', context?.lastEventId);
        console.log('[Streaming Debug] context?.isResume:', context?.isResume);
        resumeCandidate = context?.lastEventId ?? null;
        console.log('[Streaming Debug] resumeCandidate after context assignment:', resumeCandidate);
        const storedEventId = streamingStorage.read(LAST_EVENT_ID_KEY);
        const storedSessionId = streamingStorage.read(SESSION_ID_KEY);
        const storedMessageId = streamingStorage.read(MESSAGE_ID_KEY);
        console.log('[Streaming Debug] Storage reads:', {
          storedEventId,
          storedSessionId,
          storedMessageId,
        });
        const currentSessionId = this.currentContext?.sessionId || localStorage.getItem('session_id') || '';
        const pendingMessageId = this.currentContext?.messageId;
        console.log('[Streaming Debug] currentContext check:', {
          currentSessionId,
          pendingMessageId,
        });
        const sameMessage =
          storedEventId &&
          storedMessageId &&
          pendingMessageId &&
          storedMessageId === pendingMessageId;
        const sameSession =
          !storedSessionId ||
          !currentSessionId ||
          storedSessionId === currentSessionId;

        if (!resumeCandidate && sameMessage && storedEventId) {
          if (!sameSession) {
            console.warn('[Streaming] Resume session mismatch', {
              storedSessionId,
              currentSessionId,
            });
          }
          resumeCandidate = storedEventId;
        }

        resumeMessageId = this.currentContext?.messageId ?? null;
        const hasServerMessageId =
          typeof resumeMessageId === 'string' && /^[0-9a-f]{24,}$/i.test(resumeMessageId);
        if ((!resumeMessageId || !hasServerMessageId) && (sameMessage || context?.isResume)) {
          resumeMessageId =
            storedMessageId && /^[0-9a-f]{24,}$/i.test(storedMessageId)
              ? storedMessageId
              : resumeMessageId ?? null;
        }
        if (resumeCandidate) {
          shouldResume = true;
          params.set('last_event_id', resumeCandidate);
          this.resuming = true;
          console.log('[Streaming] Attempting resume from:', resumeCandidate);
          this.currentContext = {
            ...(this.currentContext || {}),
            lastEventId: resumeCandidate,
          };
          const storedContextRaw = streamingStorage.read(CONTEXT_KEY);
          if (storedContextRaw) {
            try {
              const parsed = JSON.parse(storedContextRaw);
              if (parsed && typeof parsed === 'object') {
                parsed.streamContext = {
                  ...(parsed.streamContext || {}),
                  lastEventId: resumeCandidate,
                };
                streamingStorage.write(CONTEXT_KEY, JSON.stringify(parsed));
              }
            } catch {
              // ignore persistence parse errors
            }
          }
        } else {
          shouldResume = false;
          this.resuming = false;
        }
      } catch (e) {
        console.warn('[Streaming] Failed to read resume params:', e);
      }
    } else {
      this.resuming = false;
    }

    if (shouldResume && resumeCandidate && resumeMessageId) {
      params.set('resume_message_id', resumeMessageId);
    }

    // Add last_event_id to query params since EventSource doesn't send it as header
    if (shouldResume && resumeCandidate) {
      params.set('last_event_id', resumeCandidate);
      const parts = resumeCandidate.split('_');
      const seqToken = parts.length > 1 ? parts[parts.length - 1] : '';
      const seqValue = Number(seqToken);
      if (!Number.isNaN(seqValue) && seqValue >= 0) {
        params.set('resume_last_seq', String(seqValue));
      } else {
        params.set('resume_last_seq', '0');
      }
    }

    // Apply extra params if provided
    if (context?.extraParams) {
      Object.entries(context.extraParams).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.set(key, String(value));
        }
      });
    }

    // Use V6 endpoint if configured
    // Store override for reconnects
    this.activeOverrideEndpoint = overrideEndpoint || undefined;
    const targetEndpoint = overrideEndpoint || this.streamEndpoint;
    this.eventSource = new EventSource(`${targetEndpoint}?${params}`);

    this.eventSource.onmessage = (event) => {
      // Immediately bail if cancelled - don't process any more messages
      if (this.cancelled) {
        return;
      }
      try {
        if (this.currentContext?.sessionId) {
          streamingStorage.write(SESSION_ID_KEY, this.currentContext.sessionId);
        }
        // Store event ID for resumption (browser provides lastEventId from SSE 'id:' field)
        if (event.lastEventId) {
          streamingStorage.write(LAST_EVENT_ID_KEY, event.lastEventId);
          if (this.currentContext?.sessionId) {
            streamingStorage.write(SESSION_ID_KEY, this.currentContext.sessionId);
          }
          this.currentContext = {
            ...(this.currentContext || {}),
            lastEventId: event.lastEventId,
          };
          const storedContextRaw = streamingStorage.read(CONTEXT_KEY);
          if (storedContextRaw) {
            try {
              const parsed = JSON.parse(storedContextRaw);
              if (parsed && typeof parsed === 'object') {
                parsed.streamContext = {
                  ...(parsed.streamContext || {}),
                  lastEventId: event.lastEventId,
                };
                streamingStorage.write(CONTEXT_KEY, JSON.stringify(parsed));
              }
            } catch {
              // ignore persistence parse errors
            }
          }
        }

        const data = JSON.parse(event.data);
        // Tolerate field name differences for streaming payloads
        if (data && typeof data === 'object') {
          // Handle start event
          if (data.type === 'start' && data.message_id) {
            console.log('[Streaming] Message started:', data.message_id);
            streamingStorage.write(MESSAGE_ID_KEY, data.message_id);
            this.lastMessageTs = Date.now();
            this.currentContext = {
              ...(this.currentContext || {}),
              messageId: data.message_id,
            };
            const storedContext = streamingStorage.read(CONTEXT_KEY);
            if (storedContext) {
              try {
                const parsed = JSON.parse(storedContext);
                if (parsed && typeof parsed === 'object') {
                  parsed.streamContext = {
                    ...(parsed.streamContext || {}),
                    messageId: data.message_id,
                  };
                  streamingStorage.write(CONTEXT_KEY, JSON.stringify(parsed));
                }
              } catch {
                // Ignore persistence issues
              }
            }
          }

          if (data.type === 'initial_update') {
            if (typeof data.stream_payload_version === 'number') {
              this.streamVersion = data.stream_payload_version;
              console.log('[Streaming] Negotiated payload version:', this.streamVersion);
            }
            this.lastMessageTs = Date.now();
            const resolvedSessionId: string | undefined =
              (typeof data.session_id === 'string' && data.session_id) ||
              (typeof data.sessionId === 'string' && data.sessionId) ||
              undefined;
            if (resolvedSessionId) {
              this.currentContext = { ...(this.currentContext || {}), sessionId: resolvedSessionId };
              try {
                if (typeof localStorage !== 'undefined') {
                  localStorage.setItem('session_id', resolvedSessionId);
                }
              } catch {
                // Ignore persistence errors (e.g., private mode)
              }
            }
          }
          if (data.type === 'stream_event') {
            this.lastMessageTs = Date.now();
            this.handleStructuredEvent(data);
            return;
          }
          if (data.type === 'content' || data.type === 'chunk' || data.type === 'text') {
            const chunk = data.content ?? data.chunk ?? data.text ?? '';
            this.currentMessage += chunk;
            this.lastMessageTs = Date.now();
            options.onMessage({ type: 'content', content: chunk });
            return;
          }
          if (data.type === 'status' || data.type === 'progress') {
            this.lastMessageTs = Date.now();
            options.onMessage({ type: 'status', message: data.message ?? data.status ?? '' });
            return;
          }
          if (data.type === 'sources' && data.sources) {
            options.onMessage({ type: 'sources', sources: data.sources });
            return;
          }
          if (data.type === 'charts' && data.charts) {
            options.onMessage({ type: 'charts', charts: data.charts });
            return;
          }
          if (data.type === 'extras' && data.extras) {
            options.onMessage({ type: 'extras', extras: data.extras });
            return;
          }
          // Handle done/complete arriving via generic onmessage (no named SSE event)
          if (data.type === 'done' || data.type === 'complete') {
            this.finished = true;
            this.clearIdle();
            streamingStorage.remove(LAST_EVENT_ID_KEY);
            streamingStorage.remove(SESSION_ID_KEY);
            streamingStorage.remove(MESSAGE_ID_KEY);
            options.onMessage(data);
            options.onComplete?.();
            this.close();
            return;
          }
        }
        // Fallback: pass through
        options.onMessage(data);
      } catch (error) {
        console.error('Failed to parse streaming data:', error);
      }
    };

    this.eventSource.onerror = (error) => {
      if (this.navigating || this.finished || this.cancelled) {
        return;
      }
      const source = this.eventSource;
      const closed = source && source.readyState === EventSource.CLOSED;
      // When connection is closed, it's likely the server finished normally
      // The 'done' event listener will handle cleanup - don't treat as error
      if (closed) {
        // If resuming, clean up resume state
        if (this.resuming) {
          this.clearIdle();
          this.resuming = false;
          streamingStorage.remove(LAST_EVENT_ID_KEY);
          streamingStorage.remove(SESSION_ID_KEY);
          streamingStorage.remove(MESSAGE_ID_KEY);
        }
        // Give the 'done' event listener a chance to fire
        // If it doesn't within 100ms, finalize gracefully
        setTimeout(() => {
          if (!this.finished && !this.cancelled) {
            this.finished = true;
            this.clearIdle();
            options.onComplete?.();
            this.close();
          }
        }, 100);
        return;
      }
      console.error('Streaming error:', error);
      if (this.cancelled) return;
      // If we already received content, allow an idle finalize to avoid spinner
      this.scheduleIdleFinalize();
      // Try reconnect with backoff (health-gated)
      this.retryConnect();
    };

    // Accept both 'done' and 'complete' end events
    const handleComplete = () => {
      this.finished = true;
      this.clearIdle();
      // Clear resume state on successful completion
      streamingStorage.remove(LAST_EVENT_ID_KEY);
      streamingStorage.remove(SESSION_ID_KEY);
      streamingStorage.remove(MESSAGE_ID_KEY);
      options.onComplete?.();
      this.close();
    };
    this.eventSource.addEventListener('done', handleComplete);
    this.eventSource.addEventListener('complete', handleComplete);

    // Handle compaction events for model switching
    this.eventSource.addEventListener('compaction', (event) => {
      try {
        const payload = JSON.parse(event.data);

        // Dynamically import the chat store to avoid circular dependencies
        import('../stores/chatStore').then(({ useChatStore }) => {
          const store = useChatStore.getState();

          if (payload.status === 'start') {
            store.setCompactionInfo({
              isCompacting: true,
              from: payload.from_provider || 'previous',
              to: payload.to_provider || 'current',
              tokens: payload.original_tokens || 0,
            });
          } else if (payload.status === 'complete') {
            store.setCompactionInfo({
              isCompacting: false,
              from: payload.from_provider || 'previous',
              to: payload.to_provider || 'current',
              tokens: payload.summary_tokens || payload.tokens || 0,
            });

            // Clear compaction info after 3 seconds
            setTimeout(() => {
              store.setCompactionInfo({ isCompacting: false });
            }, 3000);
          }
        });
      } catch (error) {
        console.error('[Streaming] Failed to handle compaction event:', error);
      }
    });
  }

  close(cancelled: boolean = false) {
    if (cancelled) {
      this.cancelled = true;
      void this.sendCancelRequest();
    }
    this.finished = true;
    if (this.eventSource) {
      // Clean up handlers before closing to prevent memory leaks
      this.eventSource.onmessage = null;
      this.eventSource.onerror = null;
      this.eventSource.close();
      this.eventSource = null;
    }
    this.clearIdle();
    this.reconnecting = false;
    this.resuming = false;
    // Clear override endpoint on close so next stream can use fresh config
    this.activeOverrideEndpoint = undefined;
  }

  private clearIdle() {
    if (this.idleTimer) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
  }

  private scheduleIdleFinalize() {
    if (!IDLE_FINALIZE_MS || IDLE_FINALIZE_MS <= 0) {
      return;
    }
    this.clearIdle();
    this.idleTimer = setTimeout(() => {
      const since = Date.now() - this.lastMessageTs;
      if (since >= IDLE_FINALIZE_MS && this.currentOptions) {
        if (this.navigating) {
          return;
        }
        this.finished = true;
        // Finalize to avoid stuck spinner
        this.currentOptions.onComplete?.();
        this.close();
      }
    }, IDLE_FINALIZE_MS);
  }

  private async getAuthToken(): Promise<string | null> {
    try {
      const mod = await import('./authService');
      const getter = (mod as any).getAuthToken;
      if (typeof getter === 'function') {
        const token = await getter();
        return typeof token === 'string' ? token : null;
      }
    } catch {
      // No auth token available
    }
    return null;
  }

  /**
   * Exchange a JWT for a short-lived SSE ticket.
   * Tickets are single-use and expire in 30 seconds.
   * This prevents JWT exposure in URL query parameters.
   */
  private async exchangeTokenForTicket(token: string): Promise<string | null> {
    try {
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };

      // Include org context in ticket request
      const activeOrgId = localStorage.getItem('activeOrganization');
      if (activeOrgId) {
        headers['X-Organization-ID'] = activeOrgId;
      }

      const response = await fetch(`${API_BASE}/auth/sse-ticket`, {
        method: 'POST',
        headers,
      });

      if (!response.ok) {
        console.warn('[Streaming] SSE ticket exchange failed:', response.status);
        return null;
      }

      const data = await response.json();
      return data.ticket || null;
    } catch (error) {
      console.warn('[Streaming] SSE ticket exchange error:', error);
      return null;
    }
  }

  private async sendCancelRequest(): Promise<void> {
    try {
      // If a custom cancel endpoint is configured in context, use it
      // Otherwise fall back to the default /v6/chat/cancel
      const customCancelEndpoint = this.currentContext?.cancelEndpoint;

      const sessionId =
        this.currentContext?.sessionId ||
        (typeof localStorage !== 'undefined' ? localStorage.getItem('session_id') : null);

      // For custom cancel endpoints (e.g., postmortem), session_id might not be required
      // Only require session_id for default chat cancel
      if (!customCancelEndpoint && !sessionId) return;

      const params = new URLSearchParams();
      if (sessionId) {
        params.set('session_id', sessionId);
      }

      const token = await this.getAuthToken();
      const headers: Record<string, string> = {};

      // Use headers for auth (not query params) to avoid logging tokens in URLs
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

      // Use custom cancel endpoint if provided, otherwise default to chat cancel
      const cancelUrl = customCancelEndpoint
        ? `${customCancelEndpoint}${params.toString() ? '?' + params.toString() : ''}`
        : `${API_BASE}/v6/chat/cancel?${params.toString()}`;

      console.log('[Streaming] Sending cancel to:', cancelUrl);

      await fetch(cancelUrl, {
        method: 'POST',
        headers: Object.keys(headers).length > 0 ? headers : undefined,
        keepalive: true,
      });
    } catch (error) {
      console.warn('[Streaming] Failed to send cancel request:', error);
    }
  }

  private async retryConnect() {
    if (this.reconnecting || !this.currentOptions || !this.currentPayload) return;
    this.reconnecting = true;

      const start = Date.now();
    while (Date.now() - start < this.maxRetryMs) {
      // Optional health gating
      try {
        const res = await fetch(this.healthEndpoint, { cache: 'no-store' });
        if (!res.ok) throw new Error('health not ok');
      } catch {
        await this.sleep(800);
        continue;
      }

      const delay = this.backoffDelay(this.retries++);
      await this.sleep(delay);

      try {
        // Attempt to start new stream seamlessly
        this.eventSource?.close();
        const params = new URLSearchParams({ message: this.currentPayload.message });

        // Restore context parameters
        if (this.currentContext?.agentMode) {
          params.set('agent_mode', this.currentContext.agentMode);
        }
        if (this.currentContext?.portfolioId) {
          params.set('portfolio_id', this.currentContext.portfolioId);
        }
        if (this.currentContext?.fileIds && this.currentContext.fileIds.length > 0) {
          params.set('file_ids', this.currentContext.fileIds.join(','));
        }
        if (this.currentContext?.selectedModel) {
          params.set('selected_model', this.currentContext.selectedModel);
          params.set('model', this.currentContext.selectedModel);
        }
        if (this.currentContext?.deepAnalysisMode !== undefined) {
          params.set('deep_analysis_mode', String(this.currentContext.deepAnalysisMode));
        }
        if (this.currentContext?.prioritizedTools && this.currentContext.prioritizedTools.length > 0) {
          params.set('prioritized_tools', this.currentContext.prioritizedTools.join(','));
        }

        // Restore extraParams (includes data_context for Canvas unsaved processes)
        if (this.currentContext?.extraParams) {
          Object.entries(this.currentContext.extraParams).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
              params.set(key, String(value));
            }
          });
        }

        if (this.currentContext?.messageId) {
          params.set('client_message_id', this.currentContext.messageId);
        }

        try {
          let sid = this.currentContext?.sessionId || localStorage.getItem('session_id');
          if (!sid) {
            // Only generate web_* session IDs in development environments
            const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
            if (isLocal) {
              sid = `web_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;
              localStorage.setItem('session_id', sid);
            }
            // In production, let server handle session generation
          }
          if (sid) {
            params.set('session_id', sid);
          }

          try {
            let resumeCandidate: string | null = this.currentContext?.lastEventId ?? null;
            const storedEventId = streamingStorage.read(LAST_EVENT_ID_KEY);
            const storedSessionId = streamingStorage.read(SESSION_ID_KEY);
            const storedMessageId = streamingStorage.read(MESSAGE_ID_KEY);
            const currentSessionId = this.currentContext?.sessionId || sid || '';
            const pendingMessageId = this.currentContext?.messageId;
            const sameMessage =
              storedEventId &&
              storedMessageId &&
              pendingMessageId &&
              storedMessageId === pendingMessageId;
            const sameSession =
              !storedSessionId ||
              !currentSessionId ||
              storedSessionId === currentSessionId;
            if (!resumeCandidate && sameMessage && storedEventId) {
              if (!sameSession) {
                console.warn('[Streaming] Resume session mismatch', {
                  storedSessionId,
                  currentSessionId,
                });
              }
              resumeCandidate = storedEventId;
            }
            if (resumeCandidate) {
              params.set('last_event_id', resumeCandidate);
              const parts = resumeCandidate.split('_');
              const seqToken = parts.length > 1 ? parts[parts.length - 1] : '';
              const seqValue = Number(seqToken);
              if (!Number.isNaN(seqValue) && seqValue >= 0) {
                params.set('resume_last_seq', String(seqValue));
              } else {
                params.set('resume_last_seq', '0');
              }
              this.resuming = true;
              this.currentContext = {
                ...(this.currentContext || {}),
                lastEventId: resumeCandidate,
              };
              if (pendingMessageId && /^[0-9a-f]{24,}$/i.test(pendingMessageId)) {
                params.set('resume_message_id', pendingMessageId);
              }
            } else {
              this.resuming = false;
            }
          } catch (e) {
            console.warn('[Streaming] Failed to read resume params (reconnect):', e);
          }
        } catch (error) {
          console.error('Failed to process reconnect resume params:', error);
        }
        // Attach auth for SSE reconnects using tickets (preferred) or token fallback
        try {
          const token = await this.getAuthToken();
          if (token) {
            // Exchange JWT for short-lived SSE ticket
            const ticket = await this.exchangeTokenForTicket(token);
            if (ticket) {
              params.set('ticket', ticket);
            } else {
              // Fallback to token if ticket exchange fails
              params.set('token', token);
            }
          } else {
            const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
            const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
            if (isLocal && devSecret) {
              params.set('x_dev_secret', devSecret);
              params.set('x_dev_user_id', 'dev-local-user');
            }
          }
        } catch (error) {
          console.error('Failed to attach reconnect auth:', error);
        }

        this.finished = false;
        this.eventSource = new EventSource(`${this.streamEndpoint}?${params}`);

        // Re-bind handlers using the stored options
        const options = this.currentOptions;
        this.eventSource.onmessage = (event) => {
          // Immediately bail if cancelled
          if (this.cancelled) {
            return;
          }
          try {
            if (this.currentContext?.sessionId) {
              streamingStorage.write(SESSION_ID_KEY, this.currentContext.sessionId);
            }
            if (event.lastEventId) {
              streamingStorage.write(LAST_EVENT_ID_KEY, event.lastEventId);
              if (this.currentContext?.sessionId) {
                streamingStorage.write(SESSION_ID_KEY, this.currentContext.sessionId);
              }
              this.currentContext = {
                ...(this.currentContext || {}),
                lastEventId: event.lastEventId,
              };
              const storedContextRaw = streamingStorage.read(CONTEXT_KEY);
              if (storedContextRaw) {
                try {
                  const parsed = JSON.parse(storedContextRaw);
                  if (parsed && typeof parsed === 'object') {
                    parsed.streamContext = {
                      ...(parsed.streamContext || {}),
                      lastEventId: event.lastEventId,
                    };
                    streamingStorage.write(CONTEXT_KEY, JSON.stringify(parsed));
                  }
                } catch {
                  // ignore persistence parse errors
                }
              }
            }

            const data = JSON.parse(event.data);
            if (data && typeof data === 'object') {
              if (data.type === 'start' && data.message_id) {
                streamingStorage.write(MESSAGE_ID_KEY, data.message_id);
              }
            if (data.type === 'initial_update') {
              if (typeof data.stream_payload_version === 'number') {
                this.streamVersion = data.stream_payload_version;
                console.log('[Streaming] Negotiated payload version (reconnect):', this.streamVersion);
              }
              this.lastMessageTs = Date.now();
                const resolvedSessionId: string | undefined =
                  (typeof data.session_id === 'string' && data.session_id) ||
                  (typeof data.sessionId === 'string' && data.sessionId) ||
                  undefined;
                if (resolvedSessionId) {
                  this.currentContext = { ...(this.currentContext || {}), sessionId: resolvedSessionId };
                  try {
                    localStorage.setItem('session_id', resolvedSessionId);
                  } catch {
                    // Ignore persistence errors
                  }
                }
              }
            if (data.type === 'stream_event') {
              this.lastMessageTs = Date.now();
              this.handleStructuredEvent(data);
              return;
            }
            if (data.type === 'content' || data.type === 'chunk' || data.type === 'text') {
              const chunk = data.content ?? data.chunk ?? data.text ?? '';
              this.currentMessage += chunk;
              this.lastMessageTs = Date.now();
              options.onMessage({ type: 'content', content: chunk });
              return;
            }
            if (data.type === 'status' || data.type === 'progress') {
              this.lastMessageTs = Date.now();
              options.onMessage({ type: 'status', message: data.message ?? data.status ?? '' });
              return;
            }
              if (data.type === 'sources' && data.sources) {
                options.onMessage({ type: 'sources', sources: data.sources });
                return;
              }
              if (data.type === 'charts' && data.charts) {
                options.onMessage({ type: 'charts', charts: data.charts });
                return;
              }
              if (data.type === 'extras' && data.extras) {
                options.onMessage({ type: 'extras', extras: data.extras });
                return;
              }
            }
            options.onMessage(data);
          } catch (e) {
            console.error('Failed to parse streaming data (reconnect):', e);
          }
        };
        this.eventSource.onerror = (e) => {
          if (this.navigating || this.finished || this.cancelled) {
            return;
          }
          const source = this.eventSource;
          const closed = source && source.readyState === EventSource.CLOSED;
          // When connection is closed, it's likely the server finished normally
          // The 'done' event listener will handle cleanup - don't treat as error
          if (closed) {
            // If resuming, clean up resume state
            if (this.resuming) {
              this.clearIdle();
              this.resuming = false;
              streamingStorage.remove(LAST_EVENT_ID_KEY);
              streamingStorage.remove(SESSION_ID_KEY);
              streamingStorage.remove(MESSAGE_ID_KEY);
            }
            // Give the 'done' event listener a chance to fire
            // If it doesn't within 100ms, finalize gracefully
            setTimeout(() => {
              if (!this.finished && !this.cancelled) {
                this.finished = true;
                this.clearIdle();
                options.onComplete?.();
                this.close();
              }
            }, 100);
            return;
          }
          console.error('Streaming error (reconnect):', e);
          this.scheduleIdleFinalize();
        };

        // End events
        const handleComplete = () => {
          if (this.navigating) {
            return;
          }
          this.finished = true;
          this.clearIdle();
          options.onComplete?.();
          this.close();
        };
        this.eventSource.addEventListener('done', handleComplete);
        this.eventSource.addEventListener('complete', handleComplete);

        // Handle compaction events for model switching (reconnect)
        this.eventSource.addEventListener('compaction', (event) => {
          try {
            const payload = JSON.parse(event.data);

            // Dynamically import the chat store to avoid circular dependencies
            import('../stores/chatStore').then(({ useChatStore }) => {
              const store = useChatStore.getState();

              if (payload.status === 'start') {
                store.setCompactionInfo({
                  isCompacting: true,
                  from: payload.from_provider || 'previous',
                  to: payload.to_provider || 'current',
                  tokens: payload.original_tokens || 0,
                });
              } else if (payload.status === 'complete') {
                store.setCompactionInfo({
                  isCompacting: false,
                  from: payload.from_provider || 'previous',
                  to: payload.to_provider || 'current',
                  tokens: payload.summary_tokens || payload.tokens || 0,
                });

                // Clear compaction info after 3 seconds
                setTimeout(() => {
                  store.setCompactionInfo({ isCompacting: false });
                }, 3000);
              }
            });
          } catch (error) {
            console.error('[Streaming] Failed to handle compaction event (reconnect):', error);
          }
        });

        this.reconnecting = false;
        return;
      } catch (e) {
        console.error('Reconnect attempt failed:', e);
      }
    }

    // Exceeded retry budget
    this.reconnecting = false;
    this.currentOptions?.onError?.(new Error('Streaming reconnection timeout'));
  }

  private backoffDelay(attempt: number): number {
    const base = Math.min(1000 * Math.pow(2, attempt), 4000);
    const jitter = Math.floor(Math.random() * 400);
    return base + jitter;
  }

  private handleStructuredEvent(data: any): void {
    if (!this.currentOptions) {
      return;
    }
    const event = data?.event ?? data ?? {};
    const rawType = typeof event.type === 'string' ? event.type : undefined;
    if (!rawType) {
      return;
    }

    const mappedType = this.structuredEventTypeMap[rawType];
    if (!mappedType) {
      if (!this.loggedStructuredEvents.has(rawType)) {
        this.loggedStructuredEvents.add(rawType);
        console.warn('[Streaming] Unhandled structured event:', rawType);
      }
      return;
    }

    if (!this.loggedStructuredEvents.has(rawType)) {
      this.loggedStructuredEvents.add(rawType);
      console.log('[Streaming] Structured event received:', rawType);
    }

    this.currentOptions.onMessage({
      type: mappedType,
      rawType,
      event,
    });
  }

  private sleep(ms: number) {
    return new Promise((r) => setTimeout(r, ms));
  }
}

// WebSocket extension for price streaming
class PriceStreamingService extends StreamingService {
  private priceWebSocket: WebSocket | null = null;
  private priceReconnectTimer: ReturnType<typeof setTimeout> | null = null;

  startPriceStream(options: {
    onMessage: (data: any) => void;
    onConnect?: () => void;
    onDisconnect?: () => void;
  }) {
    this.closePriceStream();

    // Use same backend URL logic as parent class
    const wsBase = API_BASE.replace('http://', 'ws://').replace('https://', 'wss://');
    const wsUrl = `${wsBase}/ws/prices`;

    console.log('Connecting to price WebSocket:', wsUrl);

    const connect = () => {
      try {
        this.priceWebSocket = new WebSocket(wsUrl);

        this.priceWebSocket.onopen = () => {
          console.log('Price WebSocket connected');
          options.onConnect?.();

          // Ping to keep alive
          const pingInterval = setInterval(() => {
            if (this.priceWebSocket?.readyState === WebSocket.OPEN) {
              this.priceWebSocket.send('ping');
            }
          }, 30000);

          this.priceWebSocket!.onclose = () => clearInterval(pingInterval);
        };

        this.priceWebSocket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            options.onMessage(data);
          } catch (err) {
            // Handle pong or other non-JSON
            if (event.data !== 'pong') {
              console.error('Failed to parse price data:', err);
            }
          }
        };

        this.priceWebSocket.onerror = (error) => {
          console.error('Price WebSocket error:', error);
        };

        this.priceWebSocket.onclose = () => {
          console.log('Price WebSocket disconnected');
          options.onDisconnect?.();

          // Reconnect after 5 seconds
          this.priceReconnectTimer = setTimeout(() => {
            console.log('Reconnecting price stream...');
            connect();
          }, 5000);
        };
      } catch (err) {
        console.error('Failed to create WebSocket:', err);
        options.onDisconnect?.();
      }
    };

    connect();
  }

  closePriceStream() {
    if (this.priceReconnectTimer) {
      clearTimeout(this.priceReconnectTimer);
      this.priceReconnectTimer = null;
    }
    if (this.priceWebSocket) {
      this.priceWebSocket.close();
      this.priceWebSocket = null;
    }
  }

  // Override parent close to also close price stream
  close() {
    super.close();
    this.closePriceStream();
  }
}

// Singleton instance
export const streamingService = new PriceStreamingService();

// PR2b: Minimal workflow WebSocket client (no auto-retry)
export interface WorkflowEvent {
  type: 'snapshot' | 'step_started' | 'step_succeeded' | 'step_failed' | 'run_completed' | 'ping';
  node_id?: string;
  node_label?: string;
  status?: string;
  run?: { id: string; status: string };
  steps?: { node_id: string; status: string }[];
  payload?: any;
}

export function connectWorkflow(
  runId: string,
  token: string,
  onMessage: (event: WorkflowEvent) => void,
): WebSocket | null {
  try {
    const wsBase = API_BASE.replace('http://', 'ws://').replace('https://', 'wss://');
    const wsUrl = `${wsBase}/ws/workflow/${runId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        onMessage(event);
      } catch (err) {
        console.warn('Invalid WS message:', err);
      }
    };

    ws.onerror = () => ws.close();
    ws.onclose = () => console.log('Workflow WS closed');

    return ws;
  } catch (err) {
    console.warn('Workflow WS connect failed:', err);
    return null;
  }
}
