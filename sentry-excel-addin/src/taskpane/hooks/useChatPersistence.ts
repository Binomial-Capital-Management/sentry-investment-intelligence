import { useState, useCallback, useRef, useEffect } from "react";
import {
  AgentMessage,
  AgentStatus,
} from "../../shared/types";
import { getWorkbookHash } from "../utils/workbook-hash";
import {
  lookupIndex,
  listWorkbookChats,
  loadWorkbookChat,
  saveWorkbookChat,
  appendChatMessage,
  deleteWorkbookChat,
  toDbRole,
  PERSISTABLE_ROLES,
} from "../utils/sentry-api";
import { convertDbMessages } from "../utils/chat-helpers";
import { deleteCheckpointsByThread } from "../utils/checkpoint-store";
import type { AgentLoopState } from "./useAgentLoop";

export interface ChatThread {
  id: string;
  title: string | null;
  updated_at: string | null;
  message_count: number;
  model?: string | null;
}

export interface ChatPersistenceConfig {
  messages: AgentMessage[];
  workbookHash: string | null; // raw SentryWorkbookId — chat endpoints expect this, not registry UUID
  threadId: string | null;
  selectedModel: string;
  lastSavedMessageIndex: number;
  status: AgentStatus;
  updateState: (patch: Partial<AgentLoopState>) => void;
}

export function useChatPersistence(config: ChatPersistenceConfig) {
  const { messages, workbookHash, threadId, selectedModel, lastSavedMessageIndex, status, updateState } = config;

  const [chatThreads, setChatThreads] = useState<ChatThread[]>([]);
  const savingRef = useRef(false);
  const saveUnsavedMessagesRef = useRef<(() => Promise<void>) | null>(null);

  // ─── Refresh thread list helper ───

  const refreshThreads = useCallback(async (wbHashOverride?: string | null) => {
    try {
      const hash = wbHashOverride || workbookHash || undefined;
      // Skip fetch when no workbook hash — avoids returning all chats unfiltered
      const threads = hash ? await listWorkbookChats(hash) : [];
      setChatThreads(threads);
    } catch {
      // non-critical
    }
  }, [workbookHash]);

  // ─── Load a specific thread by ID ───

  const loadThread = useCallback(async (loadThreadId: string) => {
    if (threadId && threadId !== loadThreadId && saveUnsavedMessagesRef.current) {
      await saveUnsavedMessagesRef.current();
    }

    try {
      const rawMessages = await loadWorkbookChat(loadThreadId);
      const loaded = convertDbMessages(rawMessages);

      const threadInfo = chatThreads.find((t) => t.id === loadThreadId);

      updateState({
        threadId: loadThreadId,
        messages: loaded,
        currentPlan: null,
        currentStep: 0,
        status: "idle",
        selectedModel: threadInfo?.model || selectedModel,
        lastSavedMessageIndex: loaded.length - 1,
      });
    } catch (err) {
      console.warn("[useChatPersistence] Failed to load thread:", err);
    }
  }, [chatThreads, threadId, selectedModel, updateState]);

  // ─── Delete a thread ───

  const deleteThread = useCallback(async (deleteThreadId: string) => {
    try {
      await deleteWorkbookChat(deleteThreadId);
      deleteCheckpointsByThread(deleteThreadId).catch(() => {});
      setChatThreads((prev) => prev.filter((t) => t.id !== deleteThreadId));
      if (threadId === deleteThreadId) {
        updateState({
          messages: [],
          threadId: null,
          currentPlan: null,
          currentStep: 0,
          status: "idle",
        });
      }
    } catch (err) {
      console.warn("[useChatPersistence] Failed to delete thread:", err);
    }
  }, [threadId, updateState]);

  // ─── Chat persistence: load on mount ───

  useEffect(() => {
    let cancelled = false;

    async function loadChat() {
      try {
        let hash: string | undefined;

        try {
          hash = await getWorkbookHash();
          const lookup = await lookupIndex(hash);
          if (lookup.indexed && !cancelled) {
            updateState({ workbookId: lookup.workbook_id, workbookHash: hash });
          } else if (!cancelled) {
            updateState({ workbookHash: hash });
          }
        } catch {
          // Workbook hash/index not available — continue without it
        }

        if (cancelled) return;

        // Only fetch threads when a workbook hash is known; otherwise the API
        // returns ALL threads across every workbook (unfiltered).
        const threads = hash ? await listWorkbookChats(hash) : [];
        if (cancelled) return;

        setChatThreads(threads);

        if (threads.length === 0) return;

        const latest = threads[0];
        const rawMessages = await loadWorkbookChat(latest.id);
        if (cancelled) return;

        const loaded = convertDbMessages(rawMessages);

        updateState({
          threadId: latest.id,
          messages: loaded,
          selectedModel: latest.model || selectedModel,
        });
      } catch {
        // Silently fail — first use or DB not available
      }
    }

    loadChat();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Save unsaved messages ───

  const saveUnsavedMessages = useCallback(async () => {
    if (savingRef.current) return;
    savingRef.current = true;

    try {
      if (!workbookHash || messages.length === 0) return;

      const unsavedMessages = messages.slice(lastSavedMessageIndex + 1);
      const toAppend = unsavedMessages
        .filter((m) => PERSISTABLE_ROLES.has(m.role))
        .map((m) => {
          let metadata: Record<string, unknown> | undefined;
          if (m.plan) metadata = { plan: m.plan, planStatus: m.planStatus };
          if (m.vbaCode) metadata = { ...metadata, vbaCode: m.vbaCode };
          if (m.activity) metadata = { ...metadata, activity: m.activity };
          if (m.thinkingSections) metadata = { ...metadata, thinking: m.thinkingSections };
          if (m.thinkingDurationSecs !== undefined) metadata = { ...metadata, thinkingDurationSecs: m.thinkingDurationSecs };
          if (m.checkpointId) metadata = { ...metadata, checkpointId: m.checkpointId };
          return { role: toDbRole(m.role), content: m.content, metadata };
        });

      if (toAppend.length === 0) return;

      if (threadId) {
        for (const msg of toAppend) {
          await appendChatMessage(threadId, msg);
        }
        updateState({ lastSavedMessageIndex: messages.length - 1 });
      } else {
        const allToSave = messages
          .filter((m) => PERSISTABLE_ROLES.has(m.role))
          .map((m) => {
            let metadata: Record<string, unknown> | undefined;
            if (m.plan) metadata = { plan: m.plan, planStatus: m.planStatus };
            if (m.vbaCode) metadata = { ...metadata, vbaCode: m.vbaCode };
            if (m.activity) metadata = { ...metadata, activity: m.activity };
            if (m.thinkingSections) metadata = { ...metadata, thinking: m.thinkingSections };
            if (m.checkpointId) metadata = { ...metadata, checkpointId: m.checkpointId };
            return { role: toDbRole(m.role), content: m.content, metadata };
          });

        if (allToSave.length === 0) return;

        const firstUser = messages.find((m) => m.role === "user");
        const title = firstUser?.content.slice(0, 80) || "Excel chat";

        const saved = await saveWorkbookChat({
          workbook_id: workbookHash!,
          title,
          model: selectedModel,
          messages: allToSave,
        });
        updateState({ threadId: saved.id, lastSavedMessageIndex: messages.length - 1 });
      }

      refreshThreads(workbookHash);
    } catch (err) {
      console.warn("[useChatPersistence] Failed to save messages:", err);
    } finally {
      savingRef.current = false;
    }
  }, [messages, workbookHash, threadId, selectedModel, lastSavedMessageIndex, updateState, refreshThreads]);

  // Keep ref in sync
  useEffect(() => {
    saveUnsavedMessagesRef.current = saveUnsavedMessages;
  }, [saveUnsavedMessages]);

  // Auto-save when a turn completes
  useEffect(() => {
    if (
      workbookHash &&
      messages.length > 0 &&
      (status === "done" || status === "awaiting_approval")
    ) {
      saveUnsavedMessages();
    }
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── New chat ───

  const newChat = useCallback(() => {
    updateState({
      messages: [],
      threadId: null,
      currentPlan: null,
      currentStep: 0,
      status: "idle",
      lastSavedMessageIndex: -1,
    });
    refreshThreads();
  }, [updateState, refreshThreads]);

  return {
    chatThreads,
    loadThread,
    deleteThread,
    newChat,
    refreshThreads,
    saveUnsavedMessages,
    saveUnsavedMessagesRef,
  };
}
