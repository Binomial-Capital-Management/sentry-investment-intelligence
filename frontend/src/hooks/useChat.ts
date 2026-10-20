import { useCallback, useRef } from 'react';
import { useChatStore } from '@stores/chatStore';
import { useUIStore } from '@stores/uiStore';
import { usePortfolioStore } from '@stores/portfolioStore';
import { useMessageQueueStore } from '@stores/messageQueueStore';
import { chatAPI } from '@services/api';
import { streamingService } from '@services/streaming';
import { chatApiService } from '@services/chatApi';
import { STREAM_STORAGE_KEYS, streamingStorage } from '@services/streamingStorage';
import type { UploadedFile } from '@services/upload';
import type { ToolEvent, Message, Thread } from '@/types';
import toast from 'react-hot-toast';

export const STREAM_STATE_TTL_MS = 5 * 60 * 1000;
const STREAM_STATE_KEY = STREAM_STORAGE_KEYS.state;
const CONTEXT_KEY = STREAM_STORAGE_KEYS.context;
const MESSAGE_ID_KEY = STREAM_STORAGE_KEYS.messageId;
const LAST_EVENT_ID_KEY = STREAM_STORAGE_KEYS.lastEventId;
const SESSION_ID_KEY = STREAM_STORAGE_KEYS.sessionId;

interface StreamingStateSnapshot {
  content?: string;
  sources?: any[];
  charts?: any[];
  extras?: Record<string, unknown>;
  toolEvents?: ToolEvent[];
  reasoningTrace?: any;
  reasoningText?: string;
  reasoningStream?: string[];
  reasoningStreaming?: boolean;
  refusal?: { text: string };
  guardrail?: any;
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
  messageId?: string;
  isBlocking?: boolean;
  lastEventId?: string;
}

interface StreamAssistantOptions {
  messageText: string;
  threadId: string;
  assistantMessageId: string;
  streamContext: StreamContextPayload;
  initialState?: StreamingStateSnapshot;
  loadingMessage?: string;
  isResume?: boolean;
  onFinalize?: () => void;
}

const generateHexId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID().replace(/-/g, '');
  }
  let id = '';
  for (let i = 0; i < 32; i += 1) {
    id += Math.floor(Math.random() * 16).toString(16);
  }
  return id;
};

export const useChat = () => {

  const {
    currentThreadId,
    addMessage,
    updateMessage,
    updateThreadTitle,
    selectedChatPortfolioId,
    deepAnalysisMode,
    prioritizedTools,
    getCurrentThreadModel,
    getCurrentThreadAgentMode,
  } = useChatStore();
  const { setLoading } = useUIStore();
  const { getNextFromQueue, getQueueForThread } = useMessageQueueStore();
  
  // Ref to track if we're currently processing queue to prevent re-entry
  const processingQueueRef = useRef(false);

  // Get per-thread selections (not global state)
  const selectedModel = getCurrentThreadModel();
  const agentMode = getCurrentThreadAgentMode();

  const clearStreamingContext = useCallback(() => {
    streamingStorage.clear([
      CONTEXT_KEY,
      LAST_EVENT_ID_KEY,
      SESSION_ID_KEY,
      MESSAGE_ID_KEY,
      STREAM_STATE_KEY,
    ]);
  }, []);

  const persistStreamingContext = useCallback((payload: {
    message: string;
    threadId: string;
    assistantMessageId: string;
    streamContext: StreamContextPayload;
  }) => {
    try {
      streamingStorage.write(CONTEXT_KEY, JSON.stringify({ ...payload, timestamp: Date.now() }));
    } catch (error) {
      console.warn('[useChat] Failed to persist streaming context:', error);
    }
  }, []);

  const persistStreamingState = useCallback((payload: { threadId: string; messageId: string; state: StreamingStateSnapshot }) => {
    try {
      streamingStorage.write(
        STREAM_STATE_KEY,
        JSON.stringify({
          ...payload,
          timestamp: Date.now(),
        }),
      );
    } catch (error) {
      console.warn('[useChat] Failed to persist streaming state:', error);
    }
  }, []);

  const loadStreamingState = useCallback((): { threadId: string; messageId: string; state: StreamingStateSnapshot } | null => {
    try {
      const raw = streamingStorage.read(STREAM_STATE_KEY);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') {
        return null;
      }
      const createdAt = typeof parsed.timestamp === 'number' ? parsed.timestamp : 0;
      if (createdAt && Date.now() - createdAt > STREAM_STATE_TTL_MS) {
        streamingStorage.remove(STREAM_STATE_KEY);
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  }, []);

  const clearStreamingState = useCallback(() => {
    streamingStorage.remove(STREAM_STATE_KEY);
  }, []);

  const streamAssistantResponse = useCallback((options: StreamAssistantOptions) => {
    const { messageText, threadId, assistantMessageId, streamContext, initialState, loadingMessage, isResume, onFinalize } = options;

    let fullContent = initialState?.content ?? '';
    let sources: any[] = initialState?.sources ? [...initialState.sources] : [];
    let charts: any[] = initialState?.charts ? [...initialState.charts] : [];
    let reasoningText = initialState?.reasoningText;
    let reasoningStream = initialState?.reasoningStream ? [...initialState.reasoningStream] : [];
    let reasoningStreaming = initialState?.reasoningStreaming;
    const reasoningTrace = initialState?.reasoningTrace;
    let toolEvents: ToolEvent[] = initialState?.toolEvents ? [...initialState.toolEvents] : [];
    let extrasPayload: Record<string, unknown> = initialState?.extras ? { ...initialState.extras } : {};
    const refusal = initialState?.refusal;
    const guardrailInfo = initialState?.guardrail;
    let streamClosed = false;
    let structuredStreaming = false;

    const snapshotState = (): StreamingStateSnapshot => {
      const snapshot: StreamingStateSnapshot = {};
      if (fullContent) snapshot.content = fullContent;
      if (sources.length) snapshot.sources = [...sources];
      if (charts.length) snapshot.charts = [...charts];
      if (Object.keys(extrasPayload).length) snapshot.extras = { ...extrasPayload };
      if (toolEvents.length) snapshot.toolEvents = [...toolEvents];
      if (reasoningTrace) snapshot.reasoningTrace = reasoningTrace;
      if (reasoningText) snapshot.reasoningText = reasoningText;
      if (reasoningStream.length) snapshot.reasoningStream = [...reasoningStream];
      if (typeof reasoningStreaming === 'boolean') snapshot.reasoningStreaming = reasoningStreaming;
      if (refusal) snapshot.refusal = refusal;
      if (guardrailInfo) snapshot.guardrail = guardrailInfo;
      return snapshot;
    };

    const persistState = () => {
      persistStreamingState({ threadId, messageId: assistantMessageId, state: snapshotState() });
    };

    const updateStatusExtras = (status: string) => {
      const trimmed = typeof status === 'string' ? status.trim() : '';
      if (!trimmed) {
        return;
      }
      extrasPayload = { ...extrasPayload, statusMessage: trimmed };
      updateMessage(threadId, assistantMessageId, { extras: extrasPayload });
      persistState();
    };

    type ResponseStage = 'created' | 'queued' | 'in_progress' | 'completed' | 'failed' | 'incomplete';

    const responseStageStatus: Record<ResponseStage, 'in_progress' | 'completed' | 'failed'> = {
      created: 'in_progress',
      queued: 'in_progress',
      in_progress: 'in_progress',
      completed: 'completed',
      failed: 'failed',
      incomplete: 'failed',
    };

    const responseStageLabels: Record<ResponseStage, string> = {
      created: 'Response created',
      queued: 'Response queued',
      in_progress: 'Assistant response in progress',
      completed: 'Response completed',
      failed: 'Response failed',
      incomplete: 'Response incomplete',
    };

    const recordResponseLifecycle = (
      stage: ResponseStage,
      payload: Record<string, unknown> = {},
      errorMessage?: string,
    ) => {
      const nextStatus = responseStageStatus[stage];
      updateToolEvent('response_lifecycle', (prev) => ({
        id: 'response_lifecycle',
        toolType: 'response',
        toolName: 'Assistant Response',
        status: nextStatus,
        startTime: prev?.startTime ?? Date.now(),
        endTime: nextStatus !== 'in_progress' ? Date.now() : prev?.endTime,
        arguments: prev?.arguments,
        result: prev?.result,
        error: errorMessage ?? (stage !== 'completed' ? (payload.error as string | undefined) ?? prev?.error : prev?.error),
        details: { ...prev?.details, stage, ...payload },
      }));
      persistState();
    };

    const summariseValue = (value: unknown, maxLength = 400): string | undefined => {
      if (typeof value === 'string') {
        return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
      }
      if (value === null || value === undefined) {
        return undefined;
      }
      try {
        const serialised = JSON.stringify(value, null, 2);
        return serialised.length > maxLength ? `${serialised.slice(0, maxLength)}...` : serialised;
      } catch {
        return undefined;
      }
    };

    const scrubImageDetails = (payload: Record<string, unknown>): Record<string, unknown> => {
      const cleaned: Record<string, unknown> = { ...payload };
      const raw = (cleaned as { partial_image_b64?: unknown }).partial_image_b64;
      if (typeof raw === 'string') {
        cleaned['partial_image_b64_length'] = raw.length;
      }
      delete (cleaned as { partial_image_b64?: unknown }).partial_image_b64;
      return cleaned;
    };

    const finalizeStream = (overrides: Partial<Message> = {}) => {
      if (streamClosed) return;
      streamClosed = true;
      clearStreamingContext();
      clearStreamingState();
      updateMessage(threadId, assistantMessageId, {
        content: fullContent,
        sources,
        charts,
        extras: extrasPayload,
        toolEvents,
        reasoningText,
        reasoningStream,
        reasoningStreaming: false,
        refusal,
        guardrail: guardrailInfo,
        isStreaming: false,
        ...overrides,
      });
      // Call the onFinalize callback after stream is complete (for queue processing)
      if (onFinalize) {
        // Use setTimeout to ensure state updates are processed first
        setTimeout(onFinalize, 100);
      }
    };

    const updateToolEvent = (callId: string, builder: (prev?: ToolEvent) => ToolEvent) => {
      const existingIndex = toolEvents.findIndex((evt) => evt.id === callId);
      const nextEvent = builder(existingIndex >= 0 ? toolEvents[existingIndex] : undefined);
      toolEvents = existingIndex >= 0
        ? toolEvents.map((evt, idx) => (idx === existingIndex ? nextEvent : evt))
        : [...toolEvents, nextEvent];
      updateMessage(threadId, assistantMessageId, { toolEvents });
      persistState();
    };

    const nextMessageId = streamContext.messageId ?? assistantMessageId;
    const defaultResumeCursor = `${nextMessageId}_0`;

    if (!isResume) {
      streamingStorage.remove(LAST_EVENT_ID_KEY);
      streamingStorage.remove(MESSAGE_ID_KEY);
      const targetSession = streamContext.sessionId ?? threadId;
      if (targetSession) {
        streamingStorage.write(SESSION_ID_KEY, targetSession);
      }
      streamingStorage.write(MESSAGE_ID_KEY, nextMessageId);
      streamingStorage.write(LAST_EVENT_ID_KEY, defaultResumeCursor);
    } else {
      // Keep the previously stored server message id; just ensure session id is present.
      const targetSession = streamContext.sessionId ?? threadId;
      if (targetSession) {
        streamingStorage.write(SESSION_ID_KEY, targetSession);
      }
      if (streamContext.messageId) {
        streamingStorage.write(MESSAGE_ID_KEY, streamContext.messageId);
      }
      if (streamContext.lastEventId) {
        streamingStorage.write(LAST_EVENT_ID_KEY, streamContext.lastEventId);
      }
    }

    if (loadingMessage) {
      extrasPayload = { ...extrasPayload, statusMessage: loadingMessage };
      updateMessage(threadId, assistantMessageId, { extras: extrasPayload });
      persistState();
    }

    const runtimeStreamContext: StreamContextPayload = {
      ...streamContext,
      ...(streamContext.messageId
        ? { messageId: streamContext.messageId }
        : !isResume
          ? { messageId: assistantMessageId }
          : {}),
      ...(streamContext.lastEventId ? { lastEventId: streamContext.lastEventId } : {}),
      ...(isResume ? { isResume: true } : {}),
    };

    persistStreamingContext({
      message: messageText,
      threadId,
      assistantMessageId,
      streamContext: runtimeStreamContext,
    });

    streamingService.startStream(messageText, {
      onMessage: (data) => {
        switch (data.type) {
          case 'content': {
            if (structuredStreaming) {
              break;
            }
            const chunk = (data as any).content ?? '';
            fullContent += chunk;
            updateMessage(threadId, assistantMessageId, { content: fullContent });
            persistState();
            break;
          }
          case 'output_text_delta': {
            structuredStreaming = true;
            const payload = (data as any).event ?? data;
            const delta = typeof payload?.delta === 'string' ? payload.delta : '';
            if (delta) {
              fullContent += delta;
              updateMessage(threadId, assistantMessageId, { content: fullContent });
              persistState();
            }
            break;
          }
          case 'output_text_done': {
            structuredStreaming = true;
            const payload = (data as any).event ?? data;
            const text = typeof payload?.text === 'string' ? payload.text : '';
            if (text) {
              fullContent = text;
              updateMessage(threadId, assistantMessageId, { content: fullContent });
              persistState();
            }
            break;
          }
          case 'sources': {
            sources = Array.isArray((data as any).sources) ? [...(data as any).sources] : [];
            updateMessage(threadId, assistantMessageId, { sources });
            persistState();
            break;
          }
          case 'charts': {
            charts = Array.isArray((data as any).charts) ? [...(data as any).charts] : [];
            updateMessage(threadId, assistantMessageId, { charts });
            persistState();
            break;
          }
          case 'extras': {
            const extras = (data as any).extras;
            if (extras && typeof extras === 'object') {
              extrasPayload = { ...extrasPayload, ...(extras as Record<string, unknown>) };
              updateMessage(threadId, assistantMessageId, { extras: extrasPayload });
              persistState();
            }
            break;
          }
          case 'status': {
            const message = (data as any).message ?? (data as any).status;
            updateStatusExtras(message);
            break;
          }
          case 'output_text_annotation_added': {
            const payload = (data as any).event ?? data;
            const annotations = Array.isArray((extrasPayload.annotations as unknown[]))
              ? [...(extrasPayload.annotations as unknown[])]
              : [];
            annotations.push(payload);
            extrasPayload = { ...extrasPayload, annotations };
            updateMessage(threadId, assistantMessageId, { extras: extrasPayload });
            persistState();
            break;
          }
          case 'reasoning_delta': {
            const payload = (data as any).event ?? data;
            const delta = typeof payload?.delta === 'string' ? payload.delta : '';
            if (delta) {
              reasoningStream.push(delta);
              reasoningText = reasoningStream.join('');
              reasoningStreaming = true;
              updateMessage(threadId, assistantMessageId, {
                reasoningText,
                reasoningStream: [...reasoningStream],
                reasoningStreaming: true,
              });
              persistState();
            }
            break;
          }
          case 'reasoning_done': {
            const payload = (data as any).event ?? data;
            const text = typeof payload?.text === 'string' ? payload.text : reasoningStream.join('');
            reasoningStream = [];
            reasoningText = text;
            reasoningStreaming = false;
            updateMessage(threadId, assistantMessageId, {
              reasoningText,
              reasoningStream,
              reasoningStreaming: false,
            });
            persistState();
            break;
          }
          case 'function_call_arguments_delta':
          case 'response.function_call_arguments.delta': {
            const payload = (data as any).event ?? data;
            const delta = typeof payload?.delta === 'string' ? payload.delta : '';
            const callId = payload?.item_id ?? payload?.call_id ?? payload?.tool_call_id ?? payload?.id ?? `function_call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            updateToolEvent(callId, (prev) => {
              const toolName = payload?.name ?? payload?.tool_name ?? prev?.toolName ?? 'Function Call';
              const tn = (toolName || '').toLowerCase();
              let detectedType: 'function_call' | 'mcp_call' | 'code_interpreter' = 'function_call';
              if (tn.includes('code') || tn.includes('interpreter')) detectedType = 'code_interpreter';
              else if (tn.startsWith('mcp') || tn.includes('mcp')) detectedType = 'mcp_call';
              return {
                id: callId,
                toolType: prev?.toolType ?? detectedType,
                toolName,
                status: 'in_progress',
                arguments: (prev?.arguments ?? '') + delta,
                startTime: prev?.startTime ?? Date.now(),
                details: { ...prev?.details, ...payload },
                result: prev?.result,
                endTime: prev?.endTime,
                error: prev?.error,
              };
            });
            const existing = (extrasPayload.function_call_delta as string | undefined) ?? '';
            extrasPayload = {
              ...extrasPayload,
              function_call_delta: existing + (delta || ''),
            };
            updateMessage(threadId, assistantMessageId, { extras: extrasPayload });
            persistState();
            break;
          }
          case 'function_call_arguments_done':
          case 'response.function_call_arguments.done': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.call_id ?? payload?.tool_call_id ?? payload?.id ?? 'function_call_default';
            const toolName = payload?.name ?? 'Function Call';
            const args = payload?.arguments ?? payload?.delta;
            const argumentsText =
              typeof args === 'string'
                ? args
                : args
                ? JSON.stringify(args, null, 2)
                : undefined;
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: prev?.toolType ?? 'function_call',
              toolName: prev?.toolName ?? toolName,
              status: 'completed',
              arguments: argumentsText ?? prev?.arguments ?? '',
              startTime: prev?.startTime ?? Date.now(),
              endTime: Date.now(),
              error: prev?.error,
              details: { ...prev?.details, ...payload },
            }));
            extrasPayload = {
              ...extrasPayload,
              function_call_arguments: args,
            };
            updateMessage(threadId, assistantMessageId, { extras: extrasPayload });
            persistState();
            break;
          }
          case 'reasoning_summary_part': {
            const payload = (data as any).event ?? data;
            const delta = typeof payload?.part?.text === 'string' ? payload.part.text : (typeof payload?.text === 'string' ? payload.text : '');
            if (delta) {
              reasoningStream.push(delta);
              reasoningText = reasoningStream.join('');
              reasoningStreaming = true;
              updateMessage(threadId, assistantMessageId, {
                reasoningText,
                reasoningStream: [...reasoningStream],
                reasoningStreaming: true,
              });
              persistState();
            }
            break;
          }
          case 'reasoning_summary_done': {
            const payload = (data as any).event ?? data;
            const text = typeof payload?.text === 'string' ? payload.text : reasoningStream.join('');
            reasoningStream = [];
            reasoningText = text;
            reasoningStreaming = false;
            updateMessage(threadId, assistantMessageId, {
              reasoningText,
              reasoningStream,
              reasoningStreaming: false,
            });
            persistState();
            break;
          }
          case 'tool_call_started': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.call_id ?? payload?.tool_call_id ?? payload?.id ?? `tool_${Date.now()}`;
            const toolName = payload?.tool_name ?? payload?.name ?? 'Tool Call';
            const tn = (toolName || '').toLowerCase();

            // Infer tool type from tool name (for custom tools that don't send granular events)
            let toolType: 'function_call' | 'mcp_call' | 'code_interpreter' | 'file_search' | 'web_search' = 'function_call';

            if (tn.includes('code') || tn.includes('interpreter') || tn.includes('python')) {
              toolType = 'code_interpreter';
            } else if (tn.includes('file') && tn.includes('search')) {
              toolType = 'file_search';
            } else if (tn.includes('web') && tn.includes('search')) {
              toolType = 'web_search';
            } else if (tn.includes('search')) {
              // Generic search - could be file or web, default to web
              toolType = 'web_search';
            } else if (tn.startsWith('mcp') || tn.includes('mcp') || tn.includes('fmp') || tn.includes('yahoo') || tn.includes('fred') || tn.includes('sec')) {
              // MCP server calls (FMP, Yahoo Finance, FRED, SEC, etc.)
              toolType = 'mcp_call';
            }

            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: (prev?.toolType && prev.toolType !== 'function_call') ? prev.toolType : toolType,
              toolName,
              status: 'in_progress',
              startTime: prev?.startTime ?? Date.now(),
            }));
            break;
          }
          case 'tool_call_output': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.call_id ?? payload?.id ?? 'tool_call_default';
            const out = payload?.output;
            const resultText = typeof out === 'string' ? out : (out ? JSON.stringify(out, null, 2) : undefined);
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: prev?.toolType ?? 'function_call',
              toolName: prev?.toolName ?? 'Tool Call',
              status: 'completed',
              startTime: prev?.startTime ?? Date.now(),
              endTime: Date.now(),
              result: resultText ?? prev?.result,
              arguments: prev?.arguments,
              error: prev?.error,
              details: { ...prev?.details, ...payload },
            }));
            break;
          }
          case 'agent_updated': {
            const payload = (data as any).event ?? data;
            const agentName = payload?.agent_name;
            const nextExtras = { ...(extrasPayload || {}), agent: agentName };
            extrasPayload = nextExtras;
            updateMessage(threadId, assistantMessageId, { extras: nextExtras });
            persistState();
            break;
          }
          case 'mcp_call_in_progress':
          case 'mcp_call_completed':
          case 'mcp_call_failed':
          case 'mcp_call_arguments_delta':
          case 'response.mcp_call_arguments.delta':
          case 'mcp_call_arguments_done':
          case 'response.mcp_call_arguments.done': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.call_id ?? payload?.tool_call_id ?? payload?.id ?? `mcp_call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            const toolName = payload?.tool_name ?? payload?.name ?? 'MCP Call';
            const delta = typeof payload?.delta === 'string' ? payload.delta : '';
            const args = payload?.arguments;
            const argumentsText =
              typeof args === 'string'
                ? args
                : args
                ? JSON.stringify(args, null, 2)
                : undefined;
            updateToolEvent(callId, (prev) => {
              const baseArguments = prev?.arguments ?? '';
              const combinedArgs = argumentsText ?? (baseArguments + (delta || ''));
              return {
                id: callId,
                toolType: prev?.toolType ?? 'mcp_call',
                toolName,
                status: payload?.type?.includes('failed') ? 'failed' : 'in_progress',
                arguments: combinedArgs,
                startTime: prev?.startTime ?? Date.now(),
                endTime: payload?.type?.includes('done') || payload?.type?.includes('completed') ? Date.now() : prev?.endTime,
                details: { ...prev?.details, ...payload },
                result: prev?.result,
                error: payload?.error ?? prev?.error,
              };
            });
            extrasPayload = {
              ...extrasPayload,
              mcp_call_delta: ((extrasPayload.mcp_call_delta as string | undefined) ?? '') + (delta || ''),
            };
            updateMessage(threadId, assistantMessageId, { extras: extrasPayload });
            persistState();
            break;
          }
          case 'mcp_list_tools_in_progress':
          case 'mcp_list_tools_completed':
          case 'mcp_list_tools_failed': {
            const payload = (data as any).event ?? data;
            const stageType = (data.type as string) ?? '';
            const status =
              stageType.endsWith('failed') ? 'failed' : stageType.endsWith('completed') ? 'completed' : 'in_progress';
            const callId = payload?.item_id ?? payload?.id ?? 'mcp_list_tools';
            const payloadDetails =
              typeof payload === 'object' && payload ? (payload as Record<string, unknown>) : undefined;
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'mcp_call',
              toolName: prev?.toolName ?? 'MCP Tool Discovery',
              status,
              startTime: prev?.startTime ?? Date.now(),
              endTime: status === 'in_progress' ? prev?.endTime : Date.now(),
              arguments: prev?.arguments,
              result: prev?.result,
              error: status === 'failed' ? (payload?.error as string | undefined) ?? prev?.error : prev?.error,
              details: { ...prev?.details, ...(payloadDetails ?? {}), stage: stageType },
            }));
            persistState();
            break;
          }
          case 'custom_tool_call_input_delta': {
            const payload = (data as any).event ?? data;
            const callId =
              payload?.item_id ??
              payload?.call_id ??
              payload?.tool_call_id ??
              payload?.id ??
              `custom_tool_${Date.now()}`;
            const delta = typeof payload?.delta === 'string' ? payload.delta : '';
            const payloadDetails =
              typeof payload === 'object' && payload ? (payload as Record<string, unknown>) : undefined;
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'custom_tool_call',
              toolName: payload?.tool_name ?? payload?.name ?? prev?.toolName ?? 'Custom Tool',
              status: 'in_progress',
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: (prev?.arguments ?? '') + (delta || ''),
              result: prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(payloadDetails ?? {}) },
            }));
            persistState();
            break;
          }
          case 'custom_tool_call_input_done': {
            const payload = (data as any).event ?? data;
            const callId =
              payload?.item_id ??
              payload?.call_id ??
              payload?.tool_call_id ??
              payload?.id ??
              `custom_tool_${Date.now()}`;
            const inputValue = payload?.input ?? payload?.arguments ?? payload?.delta;
            const inputText = summariseValue(inputValue);
            const payloadDetails =
              typeof payload === 'object' && payload ? (payload as Record<string, unknown>) : undefined;
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'custom_tool_call',
              toolName: payload?.tool_name ?? payload?.name ?? prev?.toolName ?? 'Custom Tool',
              status: 'completed',
              startTime: prev?.startTime ?? Date.now(),
              endTime: Date.now(),
              arguments: inputText ?? prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(payloadDetails ?? {}) },
            }));
            persistState();
            break;
          }
          case 'output_item_added':
          case 'output_item_done': {
            const payload = (data as any).event ?? data;
            const itemId = payload?.item_id ?? payload?.id ?? `output_item_${Date.now()}`;
            const status = data.type === 'output_item_done' ? 'completed' : 'in_progress';
            const label =
              payload?.output_item?.type ??
              payload?.item_type ??
              payload?.name ??
              (status === 'completed' ? 'Output Item' : 'Output Item (pending)');
            const resultText =
              status === 'completed'
                ? summariseValue(
                    (payload?.output_item as { content?: unknown } | undefined)?.content ?? payload?.content,
                  )
                : undefined;
            const payloadDetails =
              typeof payload === 'object' && payload ? (payload as Record<string, unknown>) : undefined;
            updateToolEvent(itemId, (prev) => ({
              id: itemId,
              toolType: 'output_item',
              toolName: prev?.toolName ?? label ?? 'Output Item',
              status,
              startTime: prev?.startTime ?? Date.now(),
              endTime: status === 'completed' ? Date.now() : prev?.endTime,
              arguments: prev?.arguments,
              result: resultText ?? prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(payloadDetails ?? {}) },
            }));
            persistState();
            break;
          }
          case 'content_part_added':
          case 'content_part_done': {
            const payload = (data as any).event ?? data;
            const partId = payload?.item_id ?? payload?.id ?? `content_part_${Date.now()}`;
            const status = data.type === 'content_part_done' ? 'completed' : 'in_progress';
            const label = payload?.part?.type ?? payload?.name ?? 'Content Part';
            const resultText =
              status === 'completed'
                ? summariseValue((payload?.part as { text?: unknown } | undefined)?.text ?? payload?.text)
                : undefined;
            const payloadDetails =
              typeof payload === 'object' && payload ? (payload as Record<string, unknown>) : undefined;
            updateToolEvent(partId, (prev) => ({
              id: partId,
              toolType: 'content_part',
              toolName: prev?.toolName ?? label,
              status,
              startTime: prev?.startTime ?? Date.now(),
              endTime: status === 'completed' ? Date.now() : prev?.endTime,
              arguments: prev?.arguments,
              result: resultText ?? prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(payloadDetails ?? {}) },
            }));
            persistState();
            break;
          }
          case 'image_generation_in_progress':
          case 'image_generation_generating': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'image_generation';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'image_generation',
              toolName: prev?.toolName ?? payload?.tool_name ?? 'Image Generation',
              status: 'in_progress',
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: {
                ...prev?.details,
                ...(typeof payload === 'object' && payload
                  ? (payload as Record<string, unknown>)
                  : {}),
              },
            }));
            persistState();
            break;
          }
          case 'image_generation_partial_image': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'image_generation';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'image_generation',
              toolName: prev?.toolName ?? payload?.tool_name ?? 'Image Generation',
              status: 'in_progress',
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: prev?.arguments,
              result: 'Partial image received',
              error: prev?.error,
              details: {
                ...prev?.details,
                ...(typeof payload === 'object' && payload
                  ? scrubImageDetails(payload as Record<string, unknown>)
                  : {}),
              },
            }));
            persistState();
            break;
          }
          case 'image_generation_completed': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'image_generation';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'image_generation',
              toolName: prev?.toolName ?? payload?.tool_name ?? 'Image Generation',
              status: 'completed',
              startTime: prev?.startTime ?? Date.now(),
              endTime: Date.now(),
              arguments: prev?.arguments,
              result: summariseValue(payload?.result ?? payload?.summary) ?? prev?.result ?? 'Image generation complete',
              error: prev?.error,
              details: {
                ...prev?.details,
                ...(typeof payload === 'object' && payload
                  ? scrubImageDetails(payload as Record<string, unknown>)
                  : {}),
              },
            }));
            persistState();
            break;
          }
          // File Search events
          case 'file_search_in_progress':
          case 'file_search.in_progress': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'file_search';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'file_search',
              toolName: prev?.toolName ?? 'File Search',
              status: 'in_progress',
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          case 'file_search_searching':
          case 'file_search.searching': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'file_search';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'file_search',
              toolName: prev?.toolName ?? 'File Search',
              status: 'searching', // ← Granular status
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          case 'file_search_completed':
          case 'file_search.completed': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'file_search';
            const resultText = summariseValue(payload?.result ?? payload?.summary) ?? 'Search complete';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'file_search',
              toolName: prev?.toolName ?? 'File Search',
              status: 'completed',
              startTime: prev?.startTime ?? Date.now(),
              endTime: Date.now(),
              arguments: prev?.arguments,
              result: resultText,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          // Web Search events
          case 'web_search_in_progress':
          case 'web_search.in_progress': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'web_search';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'web_search',
              toolName: prev?.toolName ?? 'Web Search',
              status: 'in_progress',
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          case 'web_search_searching':
          case 'web_search.searching': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'web_search';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'web_search',
              toolName: prev?.toolName ?? 'Web Search',
              status: 'searching', // ← Granular status
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          case 'web_search_completed':
          case 'web_search.completed': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'web_search';
            const resultText = summariseValue(payload?.result ?? payload?.summary) ?? 'Web search complete';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'web_search',
              toolName: prev?.toolName ?? 'Web Search',
              status: 'completed',
              startTime: prev?.startTime ?? Date.now(),
              endTime: Date.now(),
              arguments: prev?.arguments,
              result: resultText,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          // Code Interpreter events with granular statuses
          case 'code_interpreter_in_progress':
          case 'code_interpreter.in_progress': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'code_interpreter';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'code_interpreter',
              toolName: prev?.toolName ?? 'Code Interpreter',
              status: 'in_progress',
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          case 'code_interpreter_interpreting':
          case 'code_interpreter.interpreting': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'code_interpreter';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'code_interpreter',
              toolName: prev?.toolName ?? 'Code Interpreter',
              status: 'interpreting', // ← Granular status
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          case 'code_interpreter_code_delta':
          case 'code_interpreter.code_delta': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'code_interpreter';
            const codeDelta = payload?.code ?? payload?.delta ?? '';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'code_interpreter',
              toolName: prev?.toolName ?? 'Code Interpreter',
              status: 'code_delta', // ← Granular status
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: (prev?.arguments ?? '') + codeDelta,
              result: prev?.result,
              error: prev?.error,
              details: {
                ...prev?.details,
                ...(typeof payload === 'object' && payload ? payload : {}),
                code: (prev?.details?.code ?? '') + codeDelta,
              },
            }));
            persistState();
            break;
          }
          case 'code_interpreter_code_done':
          case 'code_interpreter.code_done': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'code_interpreter';
            const code = payload?.code ?? '';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'code_interpreter',
              toolName: prev?.toolName ?? 'Code Interpreter',
              status: 'code_done', // ← Granular status
              startTime: prev?.startTime ?? Date.now(),
              endTime: prev?.endTime,
              arguments: code || prev?.arguments,
              result: prev?.result,
              error: prev?.error,
              details: {
                ...prev?.details,
                ...(typeof payload === 'object' && payload ? payload : {}),
                code: code || prev?.details?.code,
              },
            }));
            persistState();
            break;
          }
          case 'code_interpreter_completed':
          case 'code_interpreter.completed': {
            const payload = (data as any).event ?? data;
            const callId = payload?.item_id ?? payload?.id ?? 'code_interpreter';
            const resultText = summariseValue(payload?.result ?? payload?.output) ?? 'Execution complete';
            updateToolEvent(callId, (prev) => ({
              id: callId,
              toolType: 'code_interpreter',
              toolName: prev?.toolName ?? 'Code Interpreter',
              status: 'completed',
              startTime: prev?.startTime ?? Date.now(),
              endTime: Date.now(),
              arguments: prev?.arguments,
              result: resultText,
              error: prev?.error,
              details: { ...prev?.details, ...(typeof payload === 'object' && payload ? payload : {}) },
            }));
            persistState();
            break;
          }
          case 'response_created':
          case 'response_queued':
          case 'response_in_progress':
          case 'response_completed':
          case 'response_incomplete':
          case 'response_failed': {
            const payload = (data as any).event ?? data;
            const stage = data.type.replace('response_', '') as ResponseStage;
            const label = responseStageLabels[stage];
            const payloadDetails =
              typeof payload === 'object' && payload ? (payload as Record<string, unknown>) : {};
            const errorText =
              stage === 'failed' || stage === 'incomplete'
                ? typeof (payload as { error?: unknown } | undefined)?.error === 'string'
                  ? (payload as { error?: string }).error
                  : undefined
                : undefined;
            recordResponseLifecycle(stage, payloadDetails, errorText);
            updateStatusExtras(label);
            if (stage === 'failed') {
              const errMsg = errorText ?? 'Response failed';
              finalizeStream({
                error: errMsg,
              });
            }
            break;
          }
          case 'cancelled': {
            extrasPayload = {
              ...extrasPayload,
              status: (data as any).reason ?? 'cancelled',
            };
            finalizeStream({ extras: extrasPayload });
            break;
          }
          case 'done': {
            finalizeStream();
            break;
          }
          case 'error': {
            const errorMessage = (data as any).error ?? 'Streaming error';
            finalizeStream({
              error: typeof errorMessage === 'string' ? errorMessage : 'Streaming error',
            });
            break;
          }
          default:
            break;
        }
      },
      onComplete: () => {
        finalizeStream();
      },
      onError: (error) => {
        finalizeStream({
          error: error instanceof Error ? error.message : 'Streaming error',
        });
      },
    }, runtimeStreamContext);

    persistState();
  }, [clearStreamingContext, clearStreamingState, updateMessage, persistStreamingContext, persistStreamingState, selectedChatPortfolioId, agentMode, selectedModel, deepAnalysisMode]);

  const resumeActiveStream = useCallback(async () => {
    try {
      const contextRaw = streamingStorage.read(CONTEXT_KEY);
      if (!contextRaw) {
        return false;
      }
      const parsed = JSON.parse(contextRaw) as {
        message: string;
        threadId: string;
        assistantMessageId: string;
        streamContext: StreamContextPayload;
        timestamp?: number;
      };

      const { message, threadId, assistantMessageId, streamContext } = parsed;
      if (!message || !threadId || !assistantMessageId) {
        return false;
      }
      const createdAt = typeof parsed.timestamp === 'number' ? parsed.timestamp : 0;
      if (createdAt && Date.now() - createdAt > STREAM_STATE_TTL_MS) {
        clearStreamingContext();
        clearStreamingState();
        return false;
      }

      const store = useChatStore.getState();
      const waitForThread = async (): Promise<Thread | undefined> => {
        const maxAttempts = 10;
        const retryDelayMs = 50;
        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
          const current = useChatStore.getState().threads.find((t) => t.id === threadId);
          if (current) {
            return current;
          }
          if (attempt === 0 && typeof store.loadThreads === 'function') {
            await store.loadThreads();
          } else {
            await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
          }
        }
        return undefined;
      };

      const thread = await waitForThread();
      if (!thread) {
        console.warn('[useChat] resumeActiveStream: missing thread', threadId);
        return false;
      }


      let assistantMessage = thread.messages.find((m) => m.id === assistantMessageId);
      if (!assistantMessage) {
        assistantMessage = {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
          extras: {},
        } as Message;
        addMessage(threadId, assistantMessage);
      } else {
        updateMessage(threadId, assistantMessageId, { isStreaming: true });
      }

      const persistedState = loadStreamingState();
      const hasPersistedState =
        persistedState &&
        persistedState.threadId === threadId &&
        persistedState.messageId === assistantMessageId;
      let normalizedPersisted: {
        content: string;
        sources: any[];
        charts: any[];
        extras: Record<string, unknown>;
        toolEvents: ToolEvent[];
      } | null = null;

      if (hasPersistedState && persistedState?.state) {
        const {
          content = '',
          sources = [],
          charts = [],
          extras = {},
          toolEvents = [],
        } = persistedState.state;

        const normalizedExtras =
          extras && typeof extras === 'object' && !Array.isArray(extras)
            ? (extras as Record<string, unknown>)
            : {};
        const normalizedSources = Array.isArray(sources) ? sources : [];
        const normalizedCharts = Array.isArray(charts) ? charts : [];
        const normalizedToolEvents = Array.isArray(toolEvents) ? toolEvents : [];
        const hasReplayableData =
          content.length > 0 ||
          normalizedSources.length > 0 ||
          normalizedCharts.length > 0 ||
          normalizedToolEvents.length > 0 ||
          Object.keys(normalizedExtras).length > 0;

        if (hasReplayableData) {
          normalizedPersisted = {
            content: typeof content === 'string' ? content : '',
            sources: normalizedSources,
            charts: normalizedCharts,
            extras: normalizedExtras,
            toolEvents: normalizedToolEvents,
          };
          updateMessage(threadId, assistantMessageId, normalizedPersisted);
        }
      }

      const storedLastEventId = streamingStorage.read(LAST_EVENT_ID_KEY);
      console.log('[Resume Debug] storedLastEventId from storage:', storedLastEventId);
      console.log('[Resume Debug] streamContext.lastEventId:', streamContext?.lastEventId);
      const effectiveLastEventId =
        streamContext?.lastEventId ??
        (typeof storedLastEventId === 'string' && storedLastEventId.length > 0
          ? storedLastEventId
          : undefined);
      console.log('[Resume Debug] effectiveLastEventId:', effectiveLastEventId);

      const initialState: StreamingStateSnapshot = {
        content: assistantMessage.content || normalizedPersisted?.content || '',
        extras: assistantMessage.extras || normalizedPersisted?.extras || {},
        toolEvents: assistantMessage.toolEvents || normalizedPersisted?.toolEvents || [],
        reasoningTrace: (assistantMessage as any).reasoning || (hasPersistedState && persistedState?.state.reasoningTrace) || undefined,
        reasoningText: (assistantMessage as any).reasoningText || (hasPersistedState && persistedState?.state.reasoningText) || undefined,
        reasoningStream: Array.isArray((assistantMessage as any).reasoningStream)
          ? [...(assistantMessage as any).reasoningStream]
          : hasPersistedState && persistedState?.state.reasoningStream
            ? [...persistedState.state.reasoningStream]
            : [],
        reasoningStreaming:
          (assistantMessage as any).reasoningStreaming ??
          (hasPersistedState ? persistedState?.state.reasoningStreaming : undefined),
        refusal: (assistantMessage as any).refusal || (hasPersistedState && persistedState?.state.refusal) || undefined,
        guardrail: (assistantMessage as any).guardrail || (hasPersistedState && persistedState?.state.guardrail) || undefined,
        sources: (assistantMessage as any).sources || normalizedPersisted?.sources || undefined,
        charts: (assistantMessage as any).charts || normalizedPersisted?.charts || undefined,
      };

      if (streamContext?.isBlocking) {
        return true;
      }

      const storedMessageId = streamingStorage.read(MESSAGE_ID_KEY);
      const looksLikeServerMessageId =
        typeof (streamContext?.messageId ?? storedMessageId) === 'string' &&
        /^[0-9a-f]{24,}$/i.test(streamContext?.messageId ?? storedMessageId ?? '');

      const matchesCurrentMessage =
        typeof effectiveLastEventId === 'string' &&
        effectiveLastEventId.startsWith(`${assistantMessageId}_`);
      const canResume = Boolean(effectiveLastEventId && matchesCurrentMessage);

      const resumeMessageId =
        (streamContext?.messageId && /^[0-9a-f]{24,}$/i.test(streamContext.messageId)
          ? streamContext.messageId
          : undefined)
        ?? (storedMessageId && /^[0-9a-f]{24,}$/i.test(storedMessageId)
          ? storedMessageId
          : undefined);

      console.log('[Resume Debug] About to call streamAssistantResponse with:', {
        lastEventId: effectiveLastEventId,
        messageId: resumeMessageId,
        isResume: canResume,
      });

      streamAssistantResponse({
        messageText: message,
        threadId,
        assistantMessageId,
        streamContext: {
          agentMode: streamContext?.agentMode ?? (agentMode === 'auto' ? undefined : agentMode),
          portfolioId: streamContext?.portfolioId ?? selectedChatPortfolioId ?? undefined,
          sessionId: streamContext?.sessionId ?? threadId,
          fileIds: streamContext?.fileIds,
          selectedModel: streamContext?.selectedModel ?? selectedModel,
          deepAnalysisMode: streamContext?.deepAnalysisMode ?? deepAnalysisMode,
          ...(resumeMessageId ? { messageId: resumeMessageId } : {}),
          lastEventId: effectiveLastEventId,
        },
        initialState,
        loadingMessage: 'Resuming response...',
        isResume: canResume,
      });

      return true;
    } catch (error) {
      console.warn('[useChat] Failed to resume stream:', error);
      return false;
    }
  }, [addMessage, updateMessage, selectedChatPortfolioId, agentMode, selectedModel, deepAnalysisMode, streamAssistantResponse, loadStreamingState]);

  const sendMessage = useCallback(async (content: string, useStreaming = true, fileIds?: string[], portfolioId?: string | null, attachments?: UploadedFile[]) => {
    if (!content.trim()) return;

    // Auto-create session before first send if missing or invalid (non-UUID)
    const chatStore = useChatStore.getState();
    let threadId = currentThreadId;
    const isUuid = (v: string) => /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(v);

    // Check if thread actually exists in the store (handles stale IDs)
    const threadExists = threadId && chatStore.threads.some(t => t.id === threadId);

    if (!threadId || threadId.startsWith('default-') || !isUuid(threadId) || !threadExists) {
      threadId = await chatStore.createNewThread('New Chat');
    }

    if (!threadId) {
      console.error('[useChat] Failed to create or get thread ID');
      return;
    }

    // Persist session/thread id immediately so streaming always sends a stable id
    try {
      streamingStorage.write(SESSION_ID_KEY, threadId);
      if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
        window.localStorage.setItem('session_id', threadId);
      }
    } catch {
      // best-effort; ignore storage errors
    }

    // Find the selected portfolio details if portfolioId is provided
    const portfolioStore = usePortfolioStore.getState();
    const selectedPortfolio = portfolioId ? portfolioStore.savedPortfolios.find(p => p.id === portfolioId) : undefined;

    // Add user message with attachments and portfolio
    const userMessage = {
      id: Math.random().toString(36).substring(2, 15),
      role: 'user' as const,
      content: content.trim(),
      timestamp: new Date(),
      attachments: attachments || undefined,
      portfolio: selectedPortfolio ? {
        tickers: selectedPortfolio.tickers,
        weights: selectedPortfolio.weights,
        value: selectedPortfolio.value || 1000000, // Default portfolio value
        lastUpdated: new Date(selectedPortfolio.created_at),
        // Aggregate lots into summary to reduce context bloat
        holdings: selectedPortfolio.holdings?.map(h => {
          const lots = h.lots || [];
          if (lots.length === 0) return { ticker: h.ticker };
          const totalQty = lots.reduce((sum, lot) => sum + (lot.quantity || 0), 0);
          const totalCost = lots.reduce((sum, lot) => sum + (lot.quantity || 0) * (lot.purchasePrice || 0), 0);
          const avgCostBasis = totalQty > 0 ? totalCost / totalQty : 0;
          return {
            ticker: h.ticker,
            totalQuantity: Math.round(totalQty * 10000) / 10000,
            avgCostBasis: Math.round(avgCostBasis * 100) / 100,
            lotCount: lots.length,
          };
        }),
      } : undefined,
      portfolioId: portfolioId || undefined,
    };

    addMessage(threadId, userMessage);

    // Create assistant message placeholder
    const assistantMessageId = generateHexId();
    const assistantMessage = {
      id: assistantMessageId,
      role: 'assistant' as const,
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      // Default AIP-like metadata placeholders (filled as data arrives)
      agentType: 'generalist' as const,
      reasoning: undefined,
      extras: {},
    };

    addMessage(threadId, assistantMessage);
    console.log('[useChat] Added assistant placeholder:', assistantMessageId);

    try {
      console.log('[useChat] sendMessage called with portfolioId:', portfolioId, 'selectedChatPortfolioId:', selectedChatPortfolioId);
      if (useStreaming) {
        const streamContext: StreamContextPayload = {
          agentMode: agentMode === 'auto' ? undefined : agentMode,
          portfolioId: portfolioId || undefined,
          sessionId: threadId,
          fileIds: fileIds || undefined,
          selectedModel,
          deepAnalysisMode,
          prioritizedTools: prioritizedTools.length > 0 ? prioritizedTools : undefined,
        };
        console.log('[useChat] streamContext built:', streamContext);

        // Build onFinalize callback to process queue after streaming completes
        const onStreamFinalize = () => {
          const queue = getQueueForThread(threadId);
          if (queue.length > 0) {
            // Process next message from queue after a brief delay
            setTimeout(() => {
              const nextMessage = getNextFromQueue(threadId);
              if (nextMessage) {
                // Re-trigger sendMessage for the queued item
                const portfolioStore = usePortfolioStore.getState();
                const selectedPortfolio = nextMessage.portfolioId 
                  ? portfolioStore.savedPortfolios.find(p => p.id === nextMessage.portfolioId) 
                  : undefined;

                const userMsg = {
                  id: Math.random().toString(36).substring(2, 15),
                  role: 'user' as const,
                  content: nextMessage.content.trim(),
                  timestamp: new Date(),
                  attachments: nextMessage.attachments || undefined,
                  portfolio: selectedPortfolio ? {
                    tickers: selectedPortfolio.tickers,
                    weights: selectedPortfolio.weights,
                    value: selectedPortfolio.value || 1000000,
                    lastUpdated: new Date(selectedPortfolio.created_at),
                    holdings: selectedPortfolio.holdings?.map(h => {
                      const lots = h.lots || [];
                      if (lots.length === 0) return { ticker: h.ticker };
                      const totalQty = lots.reduce((sum, lot) => sum + (lot.quantity || 0), 0);
                      const totalCost = lots.reduce((sum, lot) => sum + (lot.quantity || 0) * (lot.purchasePrice || 0), 0);
                      const avgCostBasis = totalQty > 0 ? totalCost / totalQty : 0;
                      return {
                        ticker: h.ticker,
                        totalQuantity: Math.round(totalQty * 10000) / 10000,
                        avgCostBasis: Math.round(avgCostBasis * 100) / 100,
                        lotCount: lots.length,
                      };
                    }),
                  } : undefined,
                  portfolioId: nextMessage.portfolioId || undefined,
                };

                addMessage(threadId, userMsg);

                const nextAssistantId = generateHexId();
                const nextAssistantMsg = {
                  id: nextAssistantId,
                  role: 'assistant' as const,
                  content: '',
                  timestamp: new Date(),
                  isStreaming: true,
                  agentType: 'generalist' as const,
                  reasoning: undefined,
                  extras: {},
                };

                addMessage(threadId, nextAssistantMsg);
                
                const nextStreamContext: StreamContextPayload = {
                  agentMode: agentMode === 'auto' ? undefined : agentMode,
                  portfolioId: nextMessage.portfolioId || undefined,
                  sessionId: threadId,
                  fileIds: nextMessage.fileIds || undefined,
                  selectedModel,
                  deepAnalysisMode,
                  prioritizedTools: prioritizedTools.length > 0 ? prioritizedTools : undefined,
                };

                // Recursively call with onFinalize to continue processing queue
                streamAssistantResponse({
                  messageText: nextMessage.content,
                  threadId,
                  assistantMessageId: nextAssistantId,
                  streamContext: nextStreamContext,
                  isResume: false,
                  onFinalize: onStreamFinalize,
                });
              }
            }, 200);
          }
        };

        streamAssistantResponse({
          messageText: content,
          threadId,
          assistantMessageId,
          streamContext,
          isResume: false,
          onFinalize: onStreamFinalize,
        });
      } else {
        streamingStorage.write(SESSION_ID_KEY, threadId);
        streamingStorage.write(MESSAGE_ID_KEY, assistantMessageId);
        streamingStorage.remove(LAST_EVENT_ID_KEY);

        const blockingContext: StreamContextPayload = {
          agentMode: agentMode === 'auto' ? undefined : agentMode,
          portfolioId: portfolioId || undefined,
          sessionId: threadId,
          fileIds: fileIds || undefined,
          selectedModel,
          deepAnalysisMode,
          prioritizedTools: prioritizedTools.length > 0 ? prioritizedTools : undefined,
          isBlocking: true,
        };

        updateMessage(threadId, assistantMessageId, {
          extras: { statusMessage: 'Processing...' },
        });

        persistStreamingState({
          threadId,
          messageId: assistantMessageId,
          state: { extras: { statusMessage: 'Processing...' } },
        });

        persistStreamingContext({
          message: content,
          threadId,
          assistantMessageId,
          streamContext: blockingContext,
        });

        setLoading(true, 'Processing...');

        const thread = useChatStore.getState().threads.find((t) => t.id === threadId);
        const history = (thread?.messages || []).slice(-20).map((m) => ({ role: m.role, content: m.content }));
        const response = await chatAPI.sendMessage({
          session_id: threadId,
          message: content,
          agent_mode: agentMode === 'auto' ? undefined : agentMode,
          selected_model: selectedModel,
          portfolio_id: portfolioId || undefined,
          file_ids: fileIds || undefined,
          history,
        });

        updateMessage(threadId, assistantMessageId, {
          content: response.response,
          sources: response.sources,
          charts: response.charts,
          reasoning: response.reasoning,
          extras: {
            metrics: response.metrics,
          },
          isStreaming: false,
        });

        clearStreamingContext();
        clearStreamingState();
        setLoading(false);
      }

      // Update thread title if it's the first message
        const thread = useChatStore.getState().threads.find((t) => t.id === threadId);
        if (thread && thread.messages.length <= 2) {
          const newTitle = (content as string).substring(0, 50) + (content.length > 50 ? '...' : '');
          updateThreadTitle(threadId, newTitle);

          // Persist to backend
          try {
            await chatApiService.updateSession(threadId, newTitle);
          } catch (error) {
            console.error('Failed to update chat title:', error);
            // Title still updated locally, just log error
          }
        }

    } catch (error) {
      const status = (error as any)?.response?.status;

      if (status === 400) {
        // Generic friendly message for all 400 errors
        updateMessage(threadId, assistantMessageId, {
          content: "I'm having trouble processing that request. Could you provide more details or try rephrasing?",
          isStreaming: false,
        });
        console.error('Chat 400 error:', error); // Log for debugging
      } else {
        // Keep existing error handling for other errors
        updateMessage(threadId, assistantMessageId, {
          content: 'Sorry, an error occurred while processing your request.',
          error: error instanceof Error ? error.message : 'Unknown error',
          isStreaming: false,
        });
        toast.error('Failed to send message');
      }

      setLoading(false);
      clearStreamingContext();
      clearStreamingState();
    }
  }, [currentThreadId, agentMode, selectedModel, deepAnalysisMode, addMessage, updateMessage, updateThreadTitle, setLoading, streamAssistantResponse, clearStreamingContext, clearStreamingState, persistStreamingContext, persistStreamingState]);

  const cancelMessage = useCallback(() => {
    // Immediately update UI state BEFORE closing stream
    const store = useChatStore.getState();
    const thread = currentThreadId ? store.threads.find((t) => t.id === currentThreadId) : null;
    const streamingMessage = thread?.messages.find((m) => m.isStreaming);

    // Mark message as cancelled immediately (before network calls)
    if (currentThreadId && streamingMessage) {
      updateMessage(currentThreadId, streamingMessage.id, {
        isStreaming: false,
        extras: {
          ...(streamingMessage.extras ?? {}),
          status: 'cancelled',
          reason: 'user',
        },
      });
    }

    // Now close stream and send cancel requests
    // @ts-expect-error - streamingService.close takes optional cancelled param in base class
    streamingService.close(true);  // Pass true to trigger cancel request to backend
    clearStreamingContext();

    if (currentThreadId) {
      // Fire and forget - don't wait for this
      void chatAPI.cancelStream(currentThreadId);

      const partialContent = streamingMessage?.content;
      const existingUserArtifact = thread?.artifacts?.some((artifact) => {
        if (artifact.type !== 'cancelled') return false;
        if (artifact.data.reason !== 'user') return false;
        const existingPartial = artifact.data.partialContent || '';
        const currentPartial = partialContent || '';
        return existingPartial === currentPartial;
      });

      if (!existingUserArtifact) {
        store.addArtifact(currentThreadId, {
          id: `${currentThreadId}-cancel-${Date.now()}`,
          type: 'cancelled',
          createdAt: new Date(),
          data: {
            reason: 'user',
            partialContent,
          },
        });
      }
    }

    setLoading(false);
    toast.success('Request cancelled');
  }, [currentThreadId, updateMessage, setLoading, clearStreamingContext]);

  // Process the next message in the queue for a given thread
  const processQueue = useCallback(async (threadId: string) => {
    // Prevent re-entry if we're already processing
    if (processingQueueRef.current) {
      return;
    }
    
    // Check if there are any streaming messages still active
    const store = useChatStore.getState();
    const thread = store.threads.find((t) => t.id === threadId);
    const hasStreamingMessage = thread?.messages.some((m) => m.isStreaming);
    
    if (hasStreamingMessage) {
      // Still streaming, don't process queue yet
      return;
    }
    
    // Get the next message from the queue
    const nextMessage = getNextFromQueue(threadId);
    if (!nextMessage) {
      return;
    }
    
    processingQueueRef.current = true;
    
    try {
      // Build the onFinalize callback to continue processing queue
      const onQueueFinalize = () => {
        processingQueueRef.current = false;
        // Check if there are more messages to process
        const remainingQueue = getQueueForThread(threadId);
        if (remainingQueue.length > 0) {
          // Process next in queue after a brief delay
          setTimeout(() => processQueue(threadId), 200);
        }
      };
      
      // Add user message with attachments and portfolio
      const portfolioStore = usePortfolioStore.getState();
      const selectedPortfolio = nextMessage.portfolioId 
        ? portfolioStore.savedPortfolios.find(p => p.id === nextMessage.portfolioId) 
        : undefined;

      const userMessage = {
        id: Math.random().toString(36).substring(2, 15),
        role: 'user' as const,
        content: nextMessage.content.trim(),
        timestamp: new Date(),
        attachments: nextMessage.attachments || undefined,
        portfolio: selectedPortfolio ? {
          tickers: selectedPortfolio.tickers,
          weights: selectedPortfolio.weights,
          value: selectedPortfolio.value || 1000000,
          lastUpdated: new Date(selectedPortfolio.created_at),
          holdings: selectedPortfolio.holdings?.map(h => {
            const lots = h.lots || [];
            if (lots.length === 0) return { ticker: h.ticker };
            const totalQty = lots.reduce((sum, lot) => sum + (lot.quantity || 0), 0);
            const totalCost = lots.reduce((sum, lot) => sum + (lot.quantity || 0) * (lot.purchasePrice || 0), 0);
            const avgCostBasis = totalQty > 0 ? totalCost / totalQty : 0;
            return {
              ticker: h.ticker,
              totalQuantity: Math.round(totalQty * 10000) / 10000,
              avgCostBasis: Math.round(avgCostBasis * 100) / 100,
              lotCount: lots.length,
            };
          }),
        } : undefined,
        portfolioId: nextMessage.portfolioId || undefined,
      };

      addMessage(threadId, userMessage);

      // Create assistant message placeholder
      const assistantMessageId = generateHexId();
      const assistantMessage = {
        id: assistantMessageId,
        role: 'assistant' as const,
        content: '',
        timestamp: new Date(),
        isStreaming: true,
        agentType: 'generalist' as const,
        reasoning: undefined,
        extras: {},
      };

      addMessage(threadId, assistantMessage);
      
      // Start streaming with the onFinalize callback
      const streamContext: StreamContextPayload = {
        agentMode: agentMode === 'auto' ? undefined : agentMode,
        portfolioId: nextMessage.portfolioId || undefined,
        sessionId: threadId,
        fileIds: nextMessage.fileIds || undefined,
        selectedModel,
        deepAnalysisMode,
        prioritizedTools: prioritizedTools.length > 0 ? prioritizedTools : undefined,
      };

      streamAssistantResponse({
        messageText: nextMessage.content,
        threadId,
        assistantMessageId,
        streamContext,
        isResume: false,
        onFinalize: onQueueFinalize,
      });
      
      toast.success('Sending queued message...');
    } catch (error) {
      processingQueueRef.current = false;
      console.error('[useChat] Failed to process queue:', error);
      toast.error('Failed to send queued message');
    }
  }, [agentMode, selectedModel, deepAnalysisMode, prioritizedTools, addMessage, getNextFromQueue, getQueueForThread, streamAssistantResponse]);

  return { sendMessage, cancelMessage, resumeActiveStream, processQueue };
};
