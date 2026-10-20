/**
 * Core agent loop with three modes:
 *
 *   Agent mode — Index → Plan (auto-executed, no approval gate) → Validate → Re-embed
 *   Plan mode  — Index → Plan (card with Build/Reject) → Build → Validate → Re-embed
 *   Ask mode   — Index → Plan (summary only, no execution)
 *
 * Chat persistence: auto-loads the latest thread for the workbook on mount,
 * auto-saves after each completed interaction.
 *
 * Following NASA Power of 10: bounded loops, no recursion.
 */

import { useState, useCallback, useRef, useEffect, useDeferredValue, useMemo } from "react";
import {
  AgentPlan,
  AgentStatus,
  AgentMessage,
  nextMessageId,
  ValidationResult,
  InteractionMode,
  ActivityItem,
  EditApprovalMode,
  PendingOperation,
  WorkbookCheckpoint,
} from "../../shared/types";
import { getWorkbookHash, getContentHash, getPerSheetHashes } from "../utils/workbook-hash";
import { AsyncBlockingQueue } from "../utils/async-queue";
import {
  lookupIndex,
  indexWorkbook,
  diffIndex,
  reindexSheet,
  executeSSE,
  cancelExecution,
  postApprovalResponse,
  validateStep,
  saveWorkbookChat,
  appendChatMessage,
  listPortfolios,
} from "../utils/sentry-api";
import type { PortfolioSummary } from "../utils/sentry-api";
import {
  writeCells,
  readRange,
  readWorkbookContext,
  readWorkbookBlueprint,
  readSheet,
  createSheet,
  snapshotWorkbook,
  restoreWorkbook,
} from "../utils/excel-actions";

import { friendlyError } from "../utils/friendly-error";
import { resetParseCache, parseThinkingSections } from "../utils/thinking-parser";
import { createActivityGroup, generateToolLabel, updateActivityLabel } from "../utils/activity-helpers";
import { useChatPersistence } from "./useChatPersistence";
import {
  saveCheckpoint as idbSaveCheckpoint,
  loadCheckpoint as idbLoadCheckpoint,
  loadCheckpointsByThread,
  deleteCheckpoint as idbDeleteCheckpoint,
  deleteCheckpointsByThread,
  enforceCheckpointLimits,
} from "../utils/checkpoint-store";
import {
  executeOperation,
  applyPostWriteActions,
  getSheetCount,
  estimateTotalRows,
  TOOL_FIRST_MAX_SHEETS,
  TOOL_FIRST_MAX_ROWS,
} from "../utils/operation-executor";
import { getModelById } from "../../shared/models";

const MAX_STEPS = 20;

/**
 * Extract a human-readable label from the model's thinking text that precedes
 * a code_interpreter call. The model usually explains what it's about to compute.
 */
/**
 * Extract a human-readable label from the model's thinking text.
 * The model structures reasoning as **Bold Title** sections — the last
 * title before a CI call naturally describes the upcoming computation.
 */
function extractCiLabelFromThinking(thinking: string): string | null {
  if (!thinking || thinking.length < 15) return null;

  // Strategy 1: Last **bold title** in thinking text (~90% of cases)
  const boldPattern = /\*\*([^*]+)\*\*/g;
  let lastTitle: string | null = null;
  let match;
  while ((match = boldPattern.exec(thinking)) !== null) {
    lastTitle = match[1].trim();
  }
  if (lastTitle && lastTitle.length >= 8 && lastTitle.length <= 60) {
    return lastTitle;
  }

  // Strategy 2: Plain title — short line without terminal punctuation before a paragraph break
  const blocks = thinking.split(/\n{2,}/);
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i].trim();
    if (block.length >= 8 && block.length <= 60 && !block.includes("\n") && !/[.!?]$/.test(block)) {
      return block.charAt(0).toUpperCase() + block.slice(1);
    }
  }

  // Strategy 3: First sentence (topic sentence) — NOT the last (often meta-commentary)
  const sentences = thinking.split(/[.!?\n]/).map(s => s.trim()).filter(s => s.length > 12);
  if (sentences.length === 0) return null;
  let label = sentences[0];
  label = label.replace(/^(I'll |I will |I need to |I'm going to |Let me |Let's |Now I'll |Now I need to |Now let me |I should |I can |I want to |I could |Maybe I |Perhaps I |I think I |I might |I plan to |I'm planning to |I'm considering |I'm thinking of )/i, "");
  label = label.charAt(0).toUpperCase() + label.slice(1);
  if (label.length > 55) label = label.slice(0, 52) + "...";
  if (label.length < 8) return null;
  return label;
}

function describeOperation(op: Record<string, unknown>): string {
  const action = op.action as string;
  const sheet = op.sheet as string | undefined;
  switch (action) {
    case "write_cells":
      return `write to ${sheet || "sheet"}`;
    case "create_sheet":
      return `create sheet "${op.name}"`;
    case "rename_sheet":
      return `rename sheet "${op.old_name}" → "${op.new_name}"`;
    case "delete_sheet":
      return `delete sheet "${op.name}"`;
    case "clear_range":
      return `clear ${sheet ? sheet + "!" : ""}${op.range}`;
    case "copy_range": {
      const destLabel = op.dest_end_cell
        ? `${op.dest_start_cell}:${op.dest_end_cell}`
        : op.dest_start_cell;
      return `copy ${op.source_sheet}!${op.source_range} → ${op.dest_sheet}!${destLabel}`;
    }
    case "insert_rows":
    case "structure_insert":
      return `insert ${op.count || 1} row(s) in ${sheet}`;
    case "delete_rows":
    case "structure_delete":
      return `delete ${op.count || 1} row(s) in ${sheet}`;
    case "create_chart":
      return `create chart "${op.title || "Untitled"}" in ${sheet}`;
    case "create_table":
      return `create table in ${sheet}`;
    case "sort_range":
      return `sort range in ${sheet}`;
    case "create_scenario_table":
      return `create scenario table in ${sheet}`;
    case "tool_approval_request":
      return (op.description as string) || "perform batch operation";
    default:
      return `${action.replace(/_/g, " ")}${sheet ? ` in ${sheet}` : ""}`;
  }
}

export interface AgentLoopState {
  status: AgentStatus;
  messages: AgentMessage[];
  currentPlan: AgentPlan | null;
  currentStep: number;
  workbookId: string | null;
  workbookHash: string | null; // raw SentryWorkbookId — used for chat save/list (distinct from workbookId which is registry UUID)
  selectedModel: string;
  mode: InteractionMode;
  threadId: string | null;
  lastSavedMessageIndex: number; // -1 means nothing saved yet
  editApprovalMode: EditApprovalMode;
  pendingOperation: PendingOperation | null;
  /** Actual model parameters returned by the backend for the last request */
  lastModelParams: { model: string; params: Record<string, unknown> } | null;
}

/** Snapshot of cell ranges before execution for undo */
interface UndoSnapshot {
  planIndex: number;
  sheets: Record<string, Record<string, unknown>>;
}

export function useAgentLoop() {
  const [state, setState] = useState<AgentLoopState>({
    status: "idle",
    messages: [],
    currentPlan: null,
    currentStep: 0,
    workbookId: null,
    workbookHash: null,
    selectedModel: "gpt-6.1-sol",
    mode: "agent",
    threadId: null,
    lastSavedMessageIndex: -1,
    editApprovalMode: "ask",
    pendingOperation: null,
    lastModelParams: null,
  });

  const undoRef = useRef<UndoSnapshot | null>(null);
  const checkpointsRef = useRef<WorkbookCheckpoint[]>([]);
  const MAX_CHECKPOINTS = 5;
  const sheetHashesRef = useRef<Record<string, string>>({}); // per-sheet content hashes
  const pendingOpsRef = useRef<Record<string, unknown>[]>([]); // plan mode: collected operations
  const streamingMsgIdxRef = useRef(-1); // index of in-progress streaming agent message
  const streamingTextRef = useRef(""); // accumulated text for that message
  const abortRef = useRef<(() => void) | null>(null); // abort function for current SSE stream
  const abortedRef = useRef(false); // flag to signal early termination of execution loop
  const requestIdRef = useRef<string | null>(null); // request_id for explicit cancellation

  // Approval gate: resolver for the PermissionDialog promise.
  // autoApproveRef tracks "Always Allow" within the current run — remaining ops
  // still arrive with approval_id but should be auto-approved locally.
  const approvalResolverRef = useRef<((approved: boolean) => void) | null>(null);
  const autoApproveRef = useRef(false);
  const permissionLogRef = useRef<{ timestamp: number; approvalId: string; description: string; decision: "allow_once" | "always_allow" | "deny" }[]>([]);

  // Status phase tracking (for dev export)
  const statusPhasesRef = useRef<{ status: string; startedAt: number; durationMs?: number }[]>([]);

  // Per-API-call token usage tracking (for dev export)
  const apiUsageRef = useRef<{ index: number; timestamp: number; input_tokens: number; output_tokens: number; cached_tokens: number; cumulative_input_tokens: number; tokens_per_min: number }[]>([]);

  // Activity grouping refs
  const activityMsgIdxRef = useRef(-1); // index of current activity message
  const lastToolCallTimeRef = useRef(0); // timestamp of last tool call for grouping
  
  // Tool call correlation map: call_id → { tool, label } for rich permission dialog labels
  const toolCallMapRef = useRef<Map<string, { tool: string; label: string }>>(new Map());
  
  // Thinking sections - deferred parsing for performance
  // Raw text accumulates fast in ref, state update is batched/throttled
  const thinkingMsgIdxRef = useRef(-1); // index of current thinking message
  const thinkingTextRef = useRef(""); // accumulated thinking text (fast accumulation)
  const silentThinkStartRef = useRef(0); // when silent thinking began (all tools done)
  const respondingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null); // detect token absence → thinking
  const [thinkingRawText, setThinkingRawText] = useState(""); // triggers deferred parsing
  const thinkingUpdateScheduledRef = useRef(false); // throttle state updates
  const thinkingRafRef = useRef<number>(0); // rAF handle for cleanup

  useEffect(() => {
    return () => cancelAnimationFrame(thinkingRafRef.current);
  }, []);

  // Deferred parsing - React will prioritize urgent updates over this
  const deferredThinkingText = useDeferredValue(thinkingRawText);
  const parsedThinkingSections = useMemo(
    () => parseThinkingSections(deferredThinkingText),
    [deferredThinkingText]
  );

  // ─── Chat persistence ───

  const updateState = useCallback(
    (patch: Partial<AgentLoopState>) => setState((prev) => ({ ...prev, ...patch })),
    []
  );

  const persistence = useChatPersistence({
    messages: state.messages,
    workbookHash: state.workbookHash,
    threadId: state.threadId,
    selectedModel: state.selectedModel,
    lastSavedMessageIndex: state.lastSavedMessageIndex,
    status: state.status,
    updateState,
  });

  // ─── Hydrate checkpoints from IndexedDB when thread changes ───

  useEffect(() => {
    if (!state.threadId) {
      checkpointsRef.current = [];
      return;
    }
    const tid = state.threadId;
    loadCheckpointsByThread(tid)
      .then((stored) => {
        if (stored.length > 0) {
          checkpointsRef.current = stored.map((cp) => ({
            messageId: cp.messageId,
            timestamp: cp.timestamp,
            sheetNames: cp.sheetNames,
            sheets: cp.sheets,
            namedRanges: cp.namedRanges,
          }));

          // Patch checkpointId on loaded messages that match stored checkpoints.
          // After reload, message IDs are regenerated and metadata roundtrip may
          // not preserve checkpointId — so we reconcile via timestamp proximity.
          setState((prev) => {
            const userMsgs = prev.messages.filter((m) => m.role === "user");
            let patched = false;
            const updated = prev.messages.map((m) => {
              if (m.role !== "user" || m.checkpointId) return m;
              // Find a checkpoint whose timestamp is within 5 s of this message
              const match = stored.find(
                (cp) =>
                  Math.abs(cp.timestamp - m.timestamp) < 5000 &&
                  !userMsgs.some((u) => u.checkpointId === cp.messageId && u !== m)
              );
              if (match) {
                patched = true;
                return { ...m, checkpointId: match.messageId };
              }
              return m;
            });
            return patched ? { ...prev, messages: updated } : prev;
          });
        } else if (checkpointsRef.current.length > 0) {
          // First message — threadId just became available, flush in-memory to IDB
          Promise.all(
            checkpointsRef.current.map((cp) =>
              idbSaveCheckpoint({
                ...cp,
                threadId: tid,
                sizeEstimate: JSON.stringify(cp.sheets).length,
              })
            )
          ).catch(() => {});
        }
      })
      .catch(() => {
        checkpointsRef.current = [];
      });
  }, [state.threadId]);

  // Portfolio context
  const [portfolios, setPortfolios] = useState<PortfolioSummary[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  // File attachments (declared early so runAgent can reference them)
  const [attachedFiles, setAttachedFiles] = useState<{ file_id: string; filename: string; thumbnailUrl?: string }[]>([]);

  // Bloomberg toggle
  const [bloombergEnabled, setBloombergEnabled] = useState(false);

  // ─── Helpers ───

  const addMessage = useCallback(
    (role: AgentMessage["role"], content: string, extra?: Partial<AgentMessage>) => {
      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          { id: nextMessageId(), role, content, timestamp: Date.now(), ...extra },
        ],
      }));
    },
    []
  );

  const updateMessage = useCallback(
    (index: number, patch: Partial<AgentMessage>) => {
      setState((prev) => {
        const msgs = [...prev.messages];
        if (index >= 0 && index < msgs.length) {
          msgs[index] = { ...msgs[index], ...patch };
        }
        return { ...prev, messages: msgs };
      });
    },
    []
  );

  const setStatus = useCallback((status: AgentStatus) => {
    // Track status phase transitions for dev export (deduplicate same-status calls)
    const phases = statusPhasesRef.current;
    if (phases.length === 0 || phases[phases.length - 1].status !== status) {
      const now = Date.now();
      if (phases.length > 0) {
        const prev = phases[phases.length - 1];
        if (prev.durationMs == null) prev.durationMs = now - prev.startedAt;
      }
      phases.push({ status, startedAt: now });
    }

    setState((prev) => ({ ...prev, status }));
  }, []);

  const setModel = useCallback((model: string) => {
    setState((prev) => ({ ...prev, selectedModel: model }));
  }, []);

  const setMode = useCallback((mode: InteractionMode) => {
    setState((prev) => ({ ...prev, mode }));
  }, []);

  const setEditApprovalMode = useCallback((editApprovalMode: EditApprovalMode) => {
    setState((prev) => ({ ...prev, editApprovalMode }));
  }, []);

  const setPendingOperation = useCallback((pendingOperation: PendingOperation | null) => {
    setState((prev) => ({ ...prev, pendingOperation }));
  }, []);

  // ─── Permission Dialog Helpers ───

  const tagLastActivityPermission = useCallback((decision: ActivityItem["permission"]) => {
    setState((prev) => {
      const msgs = [...prev.messages];
      const idx = activityMsgIdxRef.current;
      if (idx >= 0 && idx < msgs.length && msgs[idx].activity) {
        const activity = { ...msgs[idx].activity! };
        const items = [...activity.items];
        const last = items.length - 1;
        if (last >= 0) {
          items[last] = { ...items[last], permission: decision };
          activity.items = items;
          msgs[idx] = { ...msgs[idx], activity };
        }
      }
      return { ...prev, messages: msgs };
    });
  }, []);

  const allowOnce = useCallback(async () => {
    const pending = state.pendingOperation;
    if (!pending) return;
    permissionLogRef.current.push({ timestamp: Date.now(), approvalId: pending.id, description: pending.description, decision: "allow_once" });
    tagLastActivityPermission("allow_once");
    setPendingOperation(null);
    approvalResolverRef.current = null;
    try {
      await pending.execute();
    } catch (err) {
      console.error("[useAgentLoop] allowOnce operation failed:", err);
    }
  }, [state.pendingOperation, setPendingOperation, tagLastActivityPermission]);

  const alwaysAllow = useCallback(async () => {
    const pending = state.pendingOperation;
    if (!pending) return;
    permissionLogRef.current.push({ timestamp: Date.now(), approvalId: pending.id, description: pending.description, decision: "always_allow" });
    tagLastActivityPermission("always_allow");
    setPendingOperation(null);
    approvalResolverRef.current = null;
    autoApproveRef.current = true;
    try {
      await pending.execute();
    } catch (err) {
      console.error("[useAgentLoop] alwaysAllow operation failed:", err);
    }
  }, [state.pendingOperation, setPendingOperation, tagLastActivityPermission]);

  const denyOperation = useCallback(() => {
    const pending = state.pendingOperation;
    if (pending) {
      permissionLogRef.current.push({ timestamp: Date.now(), approvalId: pending.id, description: pending.description, decision: "deny" });
      tagLastActivityPermission("deny");
    }
    setPendingOperation(null);
    if (approvalResolverRef.current) {
      approvalResolverRef.current(false);
      approvalResolverRef.current = null;
    }
    addMessage("system", "Operation denied by user.");
  }, [state.pendingOperation, setPendingOperation, addMessage, tagLastActivityPermission]);

  // ─── Activity Grouping Helpers ───

  const addOrUpdateActivity = useCallback((
    tool: string,
    status: ActivityItem["status"] = "running",
    preview?: string,
    parameters?: Record<string, unknown>,
    callId?: string,
    labelOverride?: string
  ) => {
    // Interleave: when a tool call happens, close the current thinking message
    // so next thinking text creates a new message (appears after this activity)
    if (thinkingMsgIdxRef.current >= 0) {
      thinkingMsgIdxRef.current = -1;
      thinkingTextRef.current = "";
    }
    
    // Interleave: also close the current streaming agent message so subsequent
    // tokens create a new message that appears AFTER this activity
    if (streamingMsgIdxRef.current >= 0) {
      streamingMsgIdxRef.current = -1;
      streamingTextRef.current = "";
    }
    
    const now = Date.now();
    const GROUPING_WINDOW = 5000; // 5 seconds - group tool calls within this window
    
    setState((prev) => {
      const msgs = [...prev.messages];
      const currentIdx = activityMsgIdxRef.current;
      const timeSinceLastTool = now - lastToolCallTimeRef.current;
      
      // Check if we should append to existing activity or create new one
      if (
        currentIdx >= 0 && 
        currentIdx < msgs.length && 
        msgs[currentIdx].role === "activity" &&
        msgs[currentIdx].activity?.status === "running" &&
        timeSinceLastTool < GROUPING_WINDOW
      ) {
        // Append to existing activity group
        const activity = { ...msgs[currentIdx].activity! };
        activity.items = [...activity.items, {
          tool,
          label: labelOverride || generateToolLabel(tool, parameters),
          status,
          preview,
          parameters,
          callId,
          startedAt: now,
        }];
        activity.label = updateActivityLabel(activity);
        msgs[currentIdx] = { ...msgs[currentIdx], activity };
      } else {
        // Create new activity group
        const newActivity = createActivityGroup(tool, parameters);
        if (labelOverride) newActivity.items[0].label = labelOverride;
        if (preview) newActivity.items[0].preview = preview;
        if (parameters) newActivity.items[0].parameters = parameters;
        if (callId) newActivity.items[0].callId = callId;
        const newIdx = msgs.length;
        activityMsgIdxRef.current = newIdx;
        msgs.push({
          id: nextMessageId(),
          role: "activity",
          content: "",
          timestamp: now,
          activity: newActivity,
        });
      }
      
      lastToolCallTimeRef.current = now;
      return { ...prev, messages: msgs };
    });
  }, []);

  const updateLastActivityItem = useCallback((
    status: ActivityItem["status"],
    preview?: string,
    result?: Record<string, unknown>,
    callId?: string,
    serverDurationMs?: number
  ) => {
    setState((prev) => {
      const msgs = [...prev.messages];
      const now = Date.now();

      // If callId provided, search ALL activity messages for matching item
      // This handles out-of-order completion when approvals delay some tools
      if (callId) {
        for (let msgIdx = msgs.length - 1; msgIdx >= 0; msgIdx--) {
          const msg = msgs[msgIdx];
          if (msg.role !== "activity" || !msg.activity) continue;

          const activity = { ...msg.activity };
          const items = [...activity.items];
          const matchIdx = items.findIndex(i => i.callId === callId);

          if (matchIdx >= 0) {
            const matched = items[matchIdx];
            // Don't let "done" overwrite "error" (race: onToolDone arriving after operation failure)
            if (matched.status === "error" && status === "done") {
              return prev;
            }
            items[matchIdx] = {
              ...matched,
              status,
              ...(preview ? { preview } : {}),
              ...(result ? { result } : {}),
              completedAt: now,
              durationMs: serverDurationMs ?? matched.durationMs ?? (matched.startedAt ? now - matched.startedAt : undefined),
            };
            activity.items = items;

            // Check if all items are done
            const allDone = items.every(i => i.status === "done" || i.status === "error");
            if (allDone) {
              activity.status = "done";
              activity.label = updateActivityLabel(activity);
              activity.completedAt = now;
              activity.durationMs = activity.startedAt ? now - activity.startedAt : undefined;
            }

            msgs[msgIdx] = { ...msgs[msgIdx], activity };
            return { ...prev, messages: msgs };
          }
        }
      }

      // Fallback: FIFO matching on current activity group (backward compatibility)
      const currentIdx = activityMsgIdxRef.current;
      if (currentIdx >= 0 && currentIdx < msgs.length && msgs[currentIdx].activity) {
        const activity = { ...msgs[currentIdx].activity! };
        const items = [...activity.items];

        // Find the FIRST running item (FIFO order)
        const pendingIdx = items.findIndex(i => i.status === "running");
        if (pendingIdx >= 0) {
          const matched = items[pendingIdx];
          // Don't let "done" overwrite "error" (race: onToolDone arriving after operation failure)
          if (matched.status === "error" && status === "done") {
            return prev;
          }
          items[pendingIdx] = {
            ...matched,
            status,
            ...(preview ? { preview } : {}),
            ...(result ? { result } : {}),
            completedAt: now,
            durationMs: serverDurationMs ?? matched.durationMs ?? (matched.startedAt ? now - matched.startedAt : undefined),
          };
        } else if (result) {
          // Safety net: tool_done arrived after tool_server_done already marked item "done".
          // Attach result to the most recent done item that lacks one.
          for (let i = items.length - 1; i >= 0; i--) {
            if (items[i].status === "done" && !items[i].result) {
              items[i] = { ...items[i], result };
              break;
            }
          }
        }
        activity.items = items;

        // Check if all items are done
        const allDone = items.every(i => i.status === "done" || i.status === "error");
        if (allDone) {
          activity.status = "done";
          activity.label = updateActivityLabel(activity);
          activity.completedAt = now;
          activity.durationMs = activity.startedAt ? now - activity.startedAt : undefined;
        }

        msgs[currentIdx] = { ...msgs[currentIdx], activity };
      }

      return { ...prev, messages: msgs };
    });
  }, []);

  const appendCiCodeToActivity = useCallback((callId: string | undefined, delta: string) => {
    if (!callId || !delta) return;
    setState((prev) => {
      const msgs = [...prev.messages];
      for (let msgIdx = msgs.length - 1; msgIdx >= 0; msgIdx--) {
        const msg = msgs[msgIdx];
        if (msg.role !== "activity" || !msg.activity) continue;
        const items = msg.activity.items;
        const matchIdx = items.findIndex(i => i.callId === callId);
        if (matchIdx < 0) continue;
        const updatedItems = [...items];
        const item = updatedItems[matchIdx];
        const newCode = (item.code ?? "") + delta;
        // Extract label from first comment line (fallback if thinking text didn't provide one)
        let newLabel = item.label;
        if (item.tool === "code_interpreter" && (item.label === "Execute Python code" || item.label === "Run calculation")) {
          const commentMatch = newCode.match(/^[ \t]*#[ \t]*(.+)/m);
          if (commentMatch) {
            const raw = commentMatch[1].trim();
            // Capitalize first letter, truncate long comments
            newLabel = raw.charAt(0).toUpperCase() + raw.slice(1);
            if (newLabel.length > 60) newLabel = newLabel.slice(0, 57) + "...";
          }
        }
        updatedItems[matchIdx] = { ...item, code: newCode, label: newLabel };
        msgs[msgIdx] = { ...msg, activity: { ...msg.activity, items: updatedItems } };
        return { ...prev, messages: msgs };
      }
      return prev;
    });
  }, []);

  const finalizeCurrentActivity = useCallback(() => {
    setState((prev) => {
      const msgs = [...prev.messages];
      const currentIdx = activityMsgIdxRef.current;
      const now = Date.now();

      if (currentIdx >= 0 && currentIdx < msgs.length && msgs[currentIdx].activity) {
        const activity = { ...msgs[currentIdx].activity! };
        activity.status = "done";
        activity.items = activity.items.map(item => ({
          ...item,
          status: item.status === "running" ? "done" : item.status,
          ...(!item.completedAt ? {
            completedAt: now,
            durationMs: item.startedAt ? now - item.startedAt : undefined,
          } : {}),
        }));
        activity.label = updateActivityLabel(activity);
        activity.completedAt = now;
        activity.durationMs = activity.startedAt ? now - activity.startedAt : undefined;
        msgs[currentIdx] = { ...msgs[currentIdx], activity };
      }

      return { ...prev, messages: msgs };
    });
    activityMsgIdxRef.current = -1;
  }, []);

  // ─── Thinking Section Helpers (optimized with deferred parsing) ───

  const addOrUpdateThinking = useCallback((text: string) => {
    // Fast path: just accumulate text in ref
    thinkingTextRef.current += text;
    
    // Throttle state updates to reduce re-renders
    // Schedule update if not already scheduled (batches rapid tokens)
    if (!thinkingUpdateScheduledRef.current) {
      thinkingUpdateScheduledRef.current = true;
      
      thinkingRafRef.current = requestAnimationFrame(() => {
        thinkingUpdateScheduledRef.current = false;
        const accumulated = thinkingTextRef.current;
        setThinkingRawText(accumulated);
      });
    }
  }, []);

  // Sync parsed thinking sections to messages when deferred parsing completes
  useEffect(() => {
    if (parsedThinkingSections.length === 0) return;
    
    setState((prev) => {
      const msgs = [...prev.messages];
      const currentIdx = thinkingMsgIdxRef.current;
      
      if (currentIdx >= 0 && currentIdx < msgs.length && msgs[currentIdx].role === "thinking") {
        // Update existing thinking message, preserving collapsed state
        const existingSections = msgs[currentIdx].thinkingSections || [];
        const mergedSections = parsedThinkingSections.map((newSection, idx) => {
          const existing = existingSections[idx];
          if (existing) {
            return { ...newSection, collapsed: existing.collapsed };
          }
          return newSection;
        });
        msgs[currentIdx] = {
          ...msgs[currentIdx],
          content: deferredThinkingText,
          thinkingSections: mergedSections,
        };
      } else {
        // Create new thinking message (use silent thinking start if available)
        const newIdx = msgs.length;
        thinkingMsgIdxRef.current = newIdx;
        const ts = silentThinkStartRef.current || Date.now();
        silentThinkStartRef.current = 0;
        msgs.push({
          id: nextMessageId(),
          role: "thinking",
          content: deferredThinkingText,
          timestamp: ts,
          thinkingSections: parsedThinkingSections,
        });
      }
      
      return { ...prev, messages: msgs };
    });
  }, [parsedThinkingSections]);

  const toggleThinkingSection = useCallback((msgIdx: number, sectionIdx: number) => {
    setState((prev) => {
      const msgs = [...prev.messages];
      if (msgIdx >= 0 && msgIdx < msgs.length && msgs[msgIdx].thinkingSections) {
        const sections = [...msgs[msgIdx].thinkingSections!];
        if (sectionIdx >= 0 && sectionIdx < sections.length) {
          sections[sectionIdx] = {
            ...sections[sectionIdx],
            collapsed: !sections[sectionIdx].collapsed,
          };
          msgs[msgIdx] = { ...msgs[msgIdx], thinkingSections: sections };
        }
      }
      return { ...prev, messages: msgs };
    });
  }, []);

  const toggleActivityCollapsed = useCallback((msgIdx: number) => {
    setState((prev) => {
      const msgs = [...prev.messages];
      if (msgIdx >= 0 && msgIdx < msgs.length && msgs[msgIdx].activity) {
        const activity = { ...msgs[msgIdx].activity! };
        activity.collapsed = !activity.collapsed;
        msgs[msgIdx] = { ...msgs[msgIdx], activity };
      }
      return { ...prev, messages: msgs };
    });
  }, []);

  const resetActivityAndThinkingRefs = useCallback(() => {
    activityMsgIdxRef.current = -1;
    lastToolCallTimeRef.current = 0;
    thinkingMsgIdxRef.current = -1;
    thinkingTextRef.current = "";
    silentThinkStartRef.current = 0;
    if (respondingTimeoutRef.current) { clearTimeout(respondingTimeoutRef.current); respondingTimeoutRef.current = null; }
    cancelAnimationFrame(thinkingRafRef.current);
    thinkingUpdateScheduledRef.current = false;
    setThinkingRawText("");
    resetParseCache(); // Clear incremental parse cache
  }, []);

  // ─── Stop agent ───

  const stopAgent = useCallback(() => {
    abortedRef.current = true;

    // Unblock any pending approval dialog so the executor loop can exit
    if (approvalResolverRef.current) {
      approvalResolverRef.current(false);
      approvalResolverRef.current = null;
    }

    // Call explicit cancel endpoint (primary mechanism)
    if (requestIdRef.current) {
      cancelExecution(requestIdRef.current).catch(() => {
        // Ignore errors - best effort cancellation
      });
      requestIdRef.current = null;
    }

    // Also abort the XHR stream (fallback mechanism)
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }

    // Save any unsaved messages before stopping (fire-and-forget to avoid blocking UI)
    if (persistence.saveUnsavedMessagesRef.current) {
      persistence.saveUnsavedMessagesRef.current();
    }

    setState((prev) => ({
      ...prev,
      status: "idle",
      currentStep: 0,
    }));
  }, [addMessage]);

  // ─── Portfolio helpers ───

  const refreshPortfolios = useCallback(async () => {
    try {
      const list = await listPortfolios();
      setPortfolios(list);
      // Auto-select default if none selected
      if (!selectedPortfolioId && list.length > 0) {
        const dflt = list.find((p) => p.is_default);
        if (dflt) setSelectedPortfolioId(dflt.id);
      }
    } catch {
      // Non-critical — portfolios may not be set up
    }
  }, [selectedPortfolioId]);

  const selectPortfolio = useCallback((id: string | null) => {
    setSelectedPortfolioId(id);
  }, []);

  // Load portfolios on mount
  useEffect(() => {
    refreshPortfolios();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Execute a plan (shared by both modes) ───

  const executePlan = useCallback(
    async (plan: AgentPlan, planMsgIndex: number | null) => {
      const workbookId = plan.workbook_id;

      if (planMsgIndex !== null) {
        updateMessage(planMsgIndex, { planStatus: "building" });
      }
      setStatus("writing_excel");

      try {
        // Snapshot for undo
        const snapshot: UndoSnapshot = { planIndex: planMsgIndex ?? -1, sheets: {} };
        const stepLimit = Math.min(plan.steps.length, MAX_STEPS);

        for (let si = 0; si < stepLimit; si++) {
          const step = plan.steps[si];
          const key = `${step.sheet}::${step.target_range}`;
          if (!snapshot.sheets[key]) {
            try {
              const data = await readRange(step.target_range, step.sheet);
              snapshot.sheets[key] = data as Record<string, unknown>;
            } catch {
              // Range may not exist yet
            }
          }
        }
        undoRef.current = snapshot;

        // Execute steps
        const changedSheets = new Set<string>();

        for (let si = 0; si < stepLimit; si++) {
          const step = plan.steps[si];
          setState((prev) => ({ ...prev, currentStep: si }));
          addMessage("system", `Step ${si + 1}/${stepLimit}: ${step.description}`);

          if (step.create_sheet) {
            await createSheet(step.sheet);
          }

          // Write cells — auto-fix handles dimension mismatches now
          let writeOk = false;
          try {
            await writeCells(step.operations, step.sheet);
            writeOk = true;
            changedSheets.add(step.sheet);
          } catch (writeErr) {
            const msg = friendlyError(writeErr);
            if (msg) addMessage("system", `Step ${si + 1} write issue: ${msg}`);

            // One retry with LLM-corrected operations
            try {
              setStatus("validating");
              const actual = await readRange(step.target_range, step.sheet).catch(() => ({
                values: [] as unknown[][],
                formulas: [] as unknown[][],
              }));
              const validation: ValidationResult = await validateStep(
                step as unknown as Record<string, unknown>,
                actual as unknown as Record<string, unknown>,
                workbookId,
                0
              );
              if (validation.corrected_operations) {
                addMessage("system", `Retrying step ${si + 1}: ${validation.reason}`);
                await writeCells(validation.corrected_operations, step.sheet);
                writeOk = true;
                changedSheets.add(step.sheet);
              }
            } catch {
              // Retry also failed — move on
            }

            if (!writeOk) {
              addMessage("system", `Step ${si + 1} failed — continuing to next step.`);
            }
          }

          // ─── Post-write actions (only if write succeeded) ───
          if (writeOk) {
            await applyPostWriteActions(step, addMessage);
          }

          setStatus("writing_excel");
        }

        // Re-index changed sheets + update local hashes
        setStatus("re_indexing");
        for (const sheetName of changedSheets) {
          const sheetData = await readSheet(sheetName);
          if (sheetData) {
            await reindexSheet(workbookId, sheetName, sheetData);
          }
        }
        // Refresh per-sheet hashes so next run knows current state
        const updatedHashes = await getPerSheetHashes();
        sheetHashesRef.current = updatedHashes;

        if (planMsgIndex !== null) {
          updateMessage(planMsgIndex, { planStatus: "built" });
        }
        setStatus("done");

        const stepCount = plan.steps?.length || 0;
        addMessage("agent", `Done — ${stepCount} step${stepCount !== 1 ? "s" : ""} executed.`);
      } catch (err) {
        setStatus("error");
        if (planMsgIndex !== null) {
          updateMessage(planMsgIndex, { planStatus: "pending" });
        }
        const msg = friendlyError(err);
        if (msg) addMessage("system", msg);
      }
    },
    [addMessage, updateMessage, setStatus]
  );

  // ─── Build plan (called from plan card "Build" button) ───

  const buildPlan = useCallback(
    async (planMsgIndex: number) => {
      const ops = pendingOpsRef.current;

      // If we have collected operations from v2 flow, replay them
      if (ops.length > 0) {
        setStatus("writing_excel");
        updateMessage(planMsgIndex, { planStatus: "building" });

        const changedSheets = new Set<string>();
        let successCount = 0;
        let failCount = 0;
        const failedActions: string[] = [];

        for (const op of ops) {
          try {
            // Note: requestId is null here since buildPlan runs after streaming ends
            // read_range operations won't work in deferred mode (they're blocking)
            await executeOperation(op, changedSheets, null);
            successCount++;
          } catch (err) {
            failCount++;
            const action = op.action as string;
            if (action && !failedActions.includes(action)) {
              failedActions.push(action);
            }
            const msg = friendlyError(err);
            if (msg) addMessage("system", msg);
          }
        }

        pendingOpsRef.current = [];

        // Re-index changed sheets
        const updatedHashes = await getPerSheetHashes();
        sheetHashesRef.current = updatedHashes;

        updateMessage(planMsgIndex, { planStatus: "built" });
        let summaryMsg = `Done — ${successCount} of ${ops.length} operations executed.`;
        if (failCount > 0) {
          summaryMsg += ` (${failCount} failed: ${failedActions.join(", ")})`;
        }
        addMessage("agent", summaryMsg);
        setStatus("done");
        return;
      }

      // Legacy fallback: execute plan steps
      const plan = state.messages[planMsgIndex]?.plan;
      if (!plan) return;
      await executePlan(plan, planMsgIndex);
    },
    [state.messages, executePlan, addMessage, updateMessage, setStatus]
  );

  // ─── Undo ───

  const undoPlan = useCallback(
    async (planMsgIndex: number) => {
      const snap = undoRef.current;
      if (!snap || snap.planIndex !== planMsgIndex) {
        addMessage("system", "No undo data available for this plan.");
        return;
      }

      setStatus("writing_excel");
      addMessage("system", "Undoing changes...");

      try {
        for (const [key, data] of Object.entries(snap.sheets)) {
          const [sheet, range] = key.split("::");
          if (data && range && sheet) {
            const values = (data as Record<string, unknown>).values;
            if (values) {
              await writeCells([{ range, values: values as (string | number | null)[][] }]);
            }
          }
        }

        updateMessage(planMsgIndex, { planStatus: "undone" });
        undoRef.current = null;
        addMessage("system", "Undo complete.");
        setStatus("done");
      } catch (err) {
        const msg = friendlyError(err);
        addMessage("system", msg || "Undo failed.");
        setStatus("error");
      }
    },
    [addMessage, updateMessage, setStatus]
  );

  // ─── Restore Checkpoint ───

  const restoreCheckpoint = useCallback(
    async (messageId: string) => {
      // Try in-memory first, then fall back to IndexedDB
      let checkpoint: WorkbookCheckpoint | undefined = checkpointsRef.current.find(
        (cp) => cp.messageId === messageId
      );
      if (!checkpoint) {
        try {
          const stored = await idbLoadCheckpoint(messageId);
          if (stored) {
            checkpoint = {
              messageId: stored.messageId,
              timestamp: stored.timestamp,
              sheetNames: stored.sheetNames,
              sheets: stored.sheets,
              namedRanges: stored.namedRanges,
            };
          }
        } catch {
          // IndexedDB read failed — fall through to "not available"
        }
      }
      if (!checkpoint) {
        addMessage("system", "No checkpoint data available.");
        return;
      }
      setStatus("writing_excel");

      try {
        await restoreWorkbook(checkpoint);

        setState((prev) => {
          // Match by checkpointId first (survives reload), fall back to message id
          let msgIdx = prev.messages.findIndex((m) => m.checkpointId === messageId);
          if (msgIdx < 0) msgIdx = prev.messages.findIndex((m) => m.id === messageId);
          if (msgIdx < 0) return prev;
          return {
            ...prev,
            messages: prev.messages.slice(0, msgIdx),
            currentPlan: null,
            currentStep: 0,
            status: "done" as AgentStatus,
            pendingOperation: null,
          };
        });

        // Discard this + later checkpoints (in-memory)
        const cpIdx = checkpointsRef.current.findIndex((cp) => cp.messageId === messageId);
        if (cpIdx >= 0) checkpointsRef.current = checkpointsRef.current.slice(0, cpIdx);
        undoRef.current = null;
        sheetHashesRef.current = {}; // Force re-index on next run

        // Discard this + later checkpoints (IndexedDB)
        if (state.threadId) {
          loadCheckpointsByThread(state.threadId)
            .then((all) => {
              const toDelete = all.filter((cp) => cp.timestamp >= checkpoint!.timestamp);
              return Promise.all(toDelete.map((cp) => idbDeleteCheckpoint(cp.messageId)));
            })
            .catch(() => {});
        }
      } catch (err) {
        const msg = friendlyError(err);
        addMessage("system", msg || "Restore failed.");
        setStatus("error");
      }
    },
    [addMessage, setStatus, state.threadId]
  );

  // ─── Reject ───

  const rejectPlan = useCallback(
    (planMsgIndex: number) => {
      updateMessage(planMsgIndex, { planStatus: "rejected" });
      setStatus("idle");
      addMessage("system", "Plan rejected.");
    },
    [updateMessage, setStatus, addMessage]
  );

  // ─── Clean plan summary ───

  function cleanSummary(raw: string): string {
    let summary = raw || "Execution plan ready";
    if (summary.trim().startsWith("{")) {
      try {
        const inner = JSON.parse(summary);
        summary = inner.summary || summary;
      } catch {
        summary = summary.slice(0, 200);
      }
    }
    return summary;
  }

  // ─── Main entry: index → plan → (show card | auto-execute | answer) ───

  const runAgent = useCallback(
    async (userMessage: string, selection?: Record<string, unknown>) => {
      const userMsgId = nextMessageId();
      // Snapshot file IDs before clearing (they're needed for the SSE request)
      const sentFileIds = attachedFiles.length > 0 ? attachedFiles.map((f) => f.file_id) : undefined;

      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          { id: userMsgId, role: "user" as const, content: userMessage, timestamp: Date.now(), checkpointId: userMsgId },
        ],
      }));
      setStatus("preparing");

      // Clear attached files after send (revoke thumbnail URLs to free memory)
      setAttachedFiles((prev) => {
        for (const f of prev) {
          if (f.thumbnailUrl) URL.revokeObjectURL(f.thumbnailUrl);
        }
        return [];
      });

      // ── Capture workbook checkpoint (non-fatal) ──
      try {
        const snap = await snapshotWorkbook();
        const cps = checkpointsRef.current;
        if (cps.length >= MAX_CHECKPOINTS) cps.shift();
        const cpTimestamp = Date.now();
        cps.push({
          messageId: userMsgId,
          timestamp: cpTimestamp,
          sheetNames: snap.sheetNames,
          sheets: snap.sheets,
          namedRanges: snap.namedRanges,
        });

        // Persist to IndexedDB (non-fatal, fire-and-forget)
        if (state.threadId) {
          idbSaveCheckpoint({
            messageId: userMsgId,
            threadId: state.threadId,
            timestamp: cpTimestamp,
            sheetNames: snap.sheetNames,
            sheets: snap.sheets,
            namedRanges: snap.namedRanges,
            sizeEstimate: JSON.stringify(snap.sheets).length,
          })
            .then(() => enforceCheckpointLimits(state.threadId!, MAX_CHECKPOINTS))
            .catch((err) => console.warn("[useAgentLoop] IDB checkpoint save failed:", err));
        }
      } catch (snapErr) {
        console.warn("[useAgentLoop] Checkpoint capture failed:", snapErr);
        setState((prev) => {
          const msgs = [...prev.messages];
          const idx = msgs.findIndex((m) => m.id === userMsgId);
          if (idx >= 0) msgs[idx] = { ...msgs[idx], checkpointId: undefined };
          return { ...prev, messages: msgs };
        });
      }

      try {
        // ─── Tool-First vs RAG Path Decision ───
        // Quick size check to decide between tool-first (agent reads on-demand)
        // and RAG path (index → search → inject context)
        const sheetCount = await getSheetCount();
        const estimatedRows = await estimateTotalRows();
        const useToolFirst = sheetCount <= TOOL_FIRST_MAX_SHEETS && estimatedRows <= TOOL_FIRST_MAX_ROWS;

        // Get workbook hash (needed for both paths)
        const workbookHash = await getWorkbookHash();
        let workbookId: string;

        if (useToolFirst) {
          // ════════════════════════════════════════════════════════════════════════
          // TOOL-FIRST PATH: Skip indexing, agent reads workbook on-demand via tools
          // ════════════════════════════════════════════════════════════════════════
          console.log(`[useAgentLoop] Tool-first path: ${sheetCount} sheets, ~${estimatedRows} rows`);
          
          // Use hash as workbook ID (no DB lookup needed for tool-first)
          // But first check if we have an existing workbook_id to maintain thread association
          const lookup = await lookupIndex(workbookHash);
          workbookId = lookup.indexed ? lookup.workbook_id : workbookHash;

          setState((prev) => ({ ...prev, workbookId, workbookHash }));
        } else {
          // ════════════════════════════════════════════════════════════════════════
          // RAG PATH: Full indexing for large workbooks
          // ════════════════════════════════════════════════════════════════════════
          console.log(`[useAgentLoop] RAG path: ${sheetCount} sheets, ~${estimatedRows} rows`);
          
          setStatus("indexing");
          const lookup = await lookupIndex(workbookHash);

          // Get current per-sheet hashes (cheap — samples first rows only)
          const currentHashes = await getPerSheetHashes();

          if (!lookup.indexed) {
            // First time: full index
            const context = await readWorkbookContext();
            const result = await indexWorkbook(
              { sheets: context },
              workbookHash,
              "Workbook"
            );
            workbookId = result.workbook_id;
            sheetHashesRef.current = currentHashes;
          } else {
            workbookId = lookup.workbook_id;

            // Diff per-sheet: only re-index sheets whose hash changed
            const prevHashes = sheetHashesRef.current;
            const changedSheets: string[] = [];

            for (const [name, hash] of Object.entries(currentHashes)) {
              if (prevHashes[name] !== hash) {
                changedSheets.push(name);
              }
            }
            // Also check for deleted sheets (in prev but not in current)
            // — those are handled by the backend when it can't find them

            if (changedSheets.length > 0) {
              // Only read and re-embed changed sheets
              for (const sheetName of changedSheets) {
                try {
                  const sheetData = await readSheet(sheetName);
                  if (sheetData) {
                    await reindexSheet(workbookId, sheetName, sheetData);
                  }
                } catch {
                  // Sheet might have been deleted — skip
                }
              }
            }
            // If no prev hashes stored (first run after load), do a backend diff as fallback
            if (Object.keys(prevHashes).length === 0) {
              const contentHash = await getContentHash();
              const diff = await diffIndex(workbookId, contentHash);
              if (diff.stale) {
                const context = await readWorkbookContext();
                for (const sheetName of Object.keys(context)) {
                  await reindexSheet(workbookId, sheetName, context[sheetName]);
                }
              }
            }

            sheetHashesRef.current = currentHashes;
          }

          setState((prev) => ({ ...prev, workbookId, workbookHash }));

        }

        // Save user message immediately for resilience (shared by both paths)
        // Chat endpoints expect workbook_hash, not workbook_registry.id
        try {
          if (!state.threadId) {
            const saved = await saveWorkbookChat({
              workbook_id: workbookHash,
              title: userMessage.slice(0, 80),
              model: state.selectedModel,
              messages: [{ role: "user", content: userMessage }],
            });
            setState((prev) => ({ ...prev, threadId: saved.id, lastSavedMessageIndex: 0 }));
            persistence.refreshThreads(workbookHash);
          } else {
            await appendChatMessage(state.threadId, { role: "user", content: userMessage });
            setState((prev) => ({ ...prev, lastSavedMessageIndex: prev.messages.length - 1 }));
          }
        } catch (saveErr) {
          console.warn("[useAgentLoop] Failed to save user message:", saveErr);
        }

        // Track whether we're using tool-first for this execution
        const skipContext = useToolFirst;

        // 2. EXECUTE (mode-dependent)
        if (state.mode === "agent" || state.mode === "ask") {
          // ── v2: Incremental tool-calling via /execute ──
          // Operations execute LIVE in Excel as the agent streams them.

          const blueprint = await readWorkbookBlueprint();

          const changedSheets = new Set<string>();
          const DONE = Symbol("DONE");
          type QItem = Record<string, unknown> | typeof DONE;
          const opQueue = new AsyncBlockingQueue<QItem>();
          let summaryResult = { summary: "Done.", count: 0 };
          let sseError: Error | null = null;

          // Reset streaming state for this run
          streamingMsgIdxRef.current = -1;
          streamingTextRef.current = "";
          resetActivityAndThinkingRefs();
          let vbaEmitted = false;
          let activeToolCallCount = 0;

          // Start SSE — operations enqueue synchronously (safe from onprogress)
          abortedRef.current = false;
          autoApproveRef.current = false;
          permissionLogRef.current = [];
          requestIdRef.current = null;
          toolCallMapRef.current.clear(); // Clear tool call map for new run
          const { abort } = executeSSE(userMessage, workbookId, {
            skipContext, // Tool-first mode: skip RAG search
            onStart: (data) => {
              // Store request_id for explicit cancellation
              requestIdRef.current = data.request_id;
            },
            onStatus: (_stage: string, _message: string) => {
              // Status messages not displayed in chat (cleaner UI)
            },
            onToolCall: (tool, parameters, callId) => {
              if (respondingTimeoutRef.current) { clearTimeout(respondingTimeoutRef.current); respondingTimeoutRef.current = null; }
              activeToolCallCount++;
              setStatus("executing");
              // For CI calls, extract a label from the model's thinking text (about to be cleared)
              let ciLabelOverride: string | undefined;
              if (tool === "code_interpreter" && thinkingTextRef.current.length > 10) {
                ciLabelOverride = extractCiLabelFromThinking(thinkingTextRef.current) ?? undefined;
              }
              addOrUpdateActivity(tool, "running", undefined, parameters, callId, ciLabelOverride);
              // Store tool info for correlation with operations
              if (callId) {
                toolCallMapRef.current.set(callId, { tool, label: ciLabelOverride || generateToolLabel(tool, parameters) });
              }
            },
            onToolDone: (output, result, callId) => {
              activeToolCallCount = Math.max(0, activeToolCallCount - 1);
              if (activeToolCallCount === 0) {
                setStatus("thinking");
                silentThinkStartRef.current = Date.now();
              }
              updateLastActivityItem("done", output ? output.slice(0, 2500) : undefined, result, callId);
            },
            onToolServerDone: (_tool, callId, serverDurationMs) => {
              updateLastActivityItem("done", undefined, undefined, callId, serverDurationMs);
            },
            onCiCodeDelta: (delta, callId) => {
              appendCiCodeToActivity(callId, delta);
            },
            onThinking: (text) => {
              if (respondingTimeoutRef.current) { clearTimeout(respondingTimeoutRef.current); respondingTimeoutRef.current = null; }
              if (vbaEmitted) return;
              setStatus("thinking");
              addOrUpdateThinking(text);
            },
            onToken: (text) => {
              if (activeToolCallCount === 0) setStatus("responding");

              // Detect token absence: if no new token for 3s, model moved to tool generation
              if (respondingTimeoutRef.current) clearTimeout(respondingTimeoutRef.current);
              respondingTimeoutRef.current = setTimeout(() => {
                if (activeToolCallCount === 0) {
                  setStatus("thinking");
                  silentThinkStartRef.current = Date.now();
                }
                respondingTimeoutRef.current = null;
              }, 3000);

              // Stamp final duration on thinking message when first response token arrives
              const thinkingIdx = thinkingMsgIdxRef.current;
              if (thinkingIdx >= 0) {
                setState((prev) => {
                  const msgs = [...prev.messages];
                  const thinkingMsg = msgs[thinkingIdx];
                  if (thinkingMsg?.role === "thinking" && thinkingMsg.thinkingDurationSecs === undefined) {
                    msgs[thinkingIdx] = {
                      ...thinkingMsg,
                      thinkingDurationSecs: Math.round((Date.now() - thinkingMsg.timestamp) / 1000),
                    };
                    return { ...prev, messages: msgs };
                  }
                  return prev;
                });
              }

              streamingTextRef.current += text;
              if (vbaEmitted) return;
              const accumulated = streamingTextRef.current;

              if (streamingMsgIdxRef.current === -1) {
                streamingMsgIdxRef.current = -2;
                setState((prev) => {
                  const idx = prev.messages.length;
                  streamingMsgIdxRef.current = idx;
                  return { ...prev, messages: [...prev.messages, { id: nextMessageId(), role: "agent", content: accumulated, timestamp: Date.now() }] };
                });
              } else if (streamingMsgIdxRef.current >= 0) {
                const idx = streamingMsgIdxRef.current;
                setState((prev) => {
                  if (idx >= prev.messages.length) return prev;
                  const msgs = [...prev.messages];
                  msgs[idx] = { ...msgs[idx], content: accumulated };
                  return { ...prev, messages: msgs };
                });
              }
            },
            onOperation: (op) => {
              opQueue.enqueue(op);
            },
            onVbaCode: (data) => {
              vbaEmitted = true;
              setState((prev) => {
                const msgs = streamingMsgIdxRef.current >= 0
                  ? prev.messages.filter((_, i) => i !== streamingMsgIdxRef.current)
                  : [...prev.messages];
                streamingMsgIdxRef.current = -1;
                return {
                  ...prev,
                  messages: [...msgs, {
                    id: nextMessageId(),
                    role: "vba_code" as const,
                    content: data.purpose,
                    timestamp: Date.now(),
                    vbaCode: data,
                  }],
                };
              });
            },
            onApiUsage: (data) => {
              apiUsageRef.current.push(data);
            },
            onSummary: (text, count) => {
              if (respondingTimeoutRef.current) { clearTimeout(respondingTimeoutRef.current); respondingTimeoutRef.current = null; }
              summaryResult = { summary: text, count };
              // Update streaming message with final authoritative text
              if (streamingMsgIdxRef.current !== -1 && text) {
                setState((prev) => {
                  const msgs = [...prev.messages];
                  const idx = streamingMsgIdxRef.current;
                  if (idx >= 0 && idx < msgs.length) {
                    msgs[idx] = { ...msgs[idx], content: text };
                  }
                  return { ...prev, messages: msgs };
                });
              }
            },
            onError: (message, fatal) => {
              const friendly = friendlyError(message);
              if (friendly) addMessage("system", friendly);
              if (fatal) {
                sseError = new Error(message);
                opQueue.enqueue(DONE);
              }
            },
            onModelParams: (model, params) => {
              setState((prev) => ({ ...prev, lastModelParams: { model, params } }));
            },
            onDone: () => {
              opQueue.enqueue(DONE);
            },
          },
            blueprint as unknown as Record<string, unknown>,
            state.selectedModel,
            selectedPortfolioId || undefined,
            sentFileIds,
            bloombergEnabled,
            state.threadId || undefined,
            selection,
            state.editApprovalMode,
          );
          abortRef.current = abort; // store abort function for stop button

          // Executor: runs concurrently with SSE, awaits one op at a time
          let opsExecuted = 0;
          let opsFailed = 0;
          let opsDenied = 0;
          const failedActions: string[] = [];
          while (true) {
            if (abortedRef.current) break;
            const item = await opQueue.dequeue();
            if (item === DONE) break;
            const op = item as Record<string, unknown>;
            const action = op.action as string;

            // ── Backend-aware approval gate ──
            // If the op has an approval_id, the backend is blocked waiting for our response.
            const approvalId = op.approval_id as string | undefined;

            if (approvalId) {
              let approved: boolean;

              if (autoApproveRef.current) {
                approved = true;
                tagLastActivityPermission("auto_approved");
              } else {
                setStatus("awaiting_approval");
                
                // Look up rich label from correlated tool call
                const callId = op.call_id as string | undefined;
                const toolInfo = callId ? toolCallMapRef.current.get(callId) : undefined;
                
                approved = await new Promise<boolean>((resolve) => {
                  approvalResolverRef.current = resolve;
                  setPendingOperation({
                    id: approvalId,
                    description: describeOperation(op),
                    toolName: action === "tool_approval_request" ? undefined : toolInfo?.tool,
                    toolLabel: action === "tool_approval_request" ? undefined : toolInfo?.label,
                    execute: async () => { resolve(true); },
                  });
                });
                approvalResolverRef.current = null;
                setStatus("writing_excel");
              }

              // Unblock the backend with the user's decision
              if (requestIdRef.current) {
                postApprovalResponse(requestIdRef.current, approvalId, approved).catch((err) =>
                  console.warn("Failed to post approval response:", err),
                );
              }

              if (!approved) {
                opsDenied++;
                continue;
              }

              // Synthetic approval-only op — don't pass to executeOperation
              if (action === "tool_approval_request") continue;
            }

            try {
              setStatus("writing_excel");
              await executeOperation(op, changedSheets, requestIdRef.current);
              opsExecuted++;
            } catch (err) {
              opsFailed++;
              if (action && !failedActions.includes(action)) {
                failedActions.push(action);
              }
              const msg = friendlyError(err);
              if (msg) {
                const callId = op.call_id as string | undefined;
                if (callId) {
                  updateLastActivityItem("error", undefined, { error: msg }, callId);
                } else {
                  addMessage("system", msg);
                }
              }
            }
          }

          if (sseError) throw sseError;

          // Finalize any open activity groups
          finalizeCurrentActivity();

          // Build an accurate summary based on actual execution results
          let executionNote = "";
          if (opsFailed > 0) {
            executionNote = ` (${opsFailed} operation${opsFailed !== 1 ? "s" : ""} failed: ${failedActions.join(", ")})`;
          }

          const result = summaryResult.count > 0
            ? { ...summaryResult, summary: summaryResult.summary }
            : { summary: `Done — ${opsExecuted} operations executed${executionNote}.`, count: opsExecuted };

          // Re-index changed sheets
          const updatedHashes = await getPerSheetHashes();
          sheetHashesRef.current = updatedHashes;

          const streamingIdx = streamingMsgIdxRef.current; // -1 = none, -2 = pending, >=0 = real index
          // Prefer the locally-accumulated streaming text — it's the full untruncated content.
          // Fall back to result.summary only when no streaming happened.
          const streamedText = streamingTextRef.current.trim();
          let finalText = streamedText
            || result.summary
            || (state.mode === "ask" ? "Analysis complete." : `Done — ${result.count} operations executed.`);
          
          // Append execution feedback if there were failures
          if (opsFailed > 0 && finalText && !finalText.includes("failed")) {
            finalText += `\n\n(Note: ${opsFailed} of ${opsExecuted + opsFailed} Excel operations failed to execute.)`;
          }

          setState((prev) => {
            // Remove transient system messages (keep those with persist: true)
            const msgs = prev.messages.filter((m) => m.role !== "system" || m.persist);
            if (vbaEmitted) {
              // VBA card already serves as the response — just clean up system msgs
              return { ...prev, messages: msgs };
            }
            if (streamingIdx >= 0) {
              const sysBeforeStreaming = prev.messages.slice(0, streamingIdx).filter((m) => m.role === "system" && !m.persist).length;
              const adjustedIdx = streamingIdx - sysBeforeStreaming;
              if (adjustedIdx >= 0 && adjustedIdx < msgs.length && msgs[adjustedIdx].role === "agent") {
                msgs[adjustedIdx] = { ...msgs[adjustedIdx], content: finalText };
                return { ...prev, messages: msgs };
              }
            }
            return { ...prev, messages: [...msgs, { id: nextMessageId(), role: "agent", content: finalText, timestamp: Date.now() }] };
          });
          setStatus("done");

        } else {
          // ── Plan mode: use /execute but COLLECT operations for approval ──
          setStatus("planning");

          const blueprint = await readWorkbookBlueprint();
          const collectedOps: Record<string, unknown>[] = [];

          // Reset streaming and activity state for this run
          streamingMsgIdxRef.current = -1;
          streamingTextRef.current = "";
          resetActivityAndThinkingRefs();

          abortedRef.current = false;
          requestIdRef.current = null; // Reset request ID
          toolCallMapRef.current.clear(); // Clear tool call map for new run
          const result = await new Promise<{ summary: string; count: number }>((resolve, reject) => {
            const { abort } = executeSSE(userMessage, workbookId, {
              onStart: (data) => {
                // Store request_id for explicit cancellation
                requestIdRef.current = data.request_id;
              },
              onStatus: (_stage: string, _message: string) => {
                // Status messages not displayed in chat (cleaner UI)
              },
              onToolCall: (tool, parameters, callId) => {
                addOrUpdateActivity(tool, "running", undefined, parameters, callId);
                // Store tool info for correlation with operations
                if (callId) {
                  toolCallMapRef.current.set(callId, { tool, label: generateToolLabel(tool, parameters) });
                }
              },
              onToolDone: (output, result, callId) => {
                updateLastActivityItem("done", output ? output.slice(0, 2500) : undefined, result, callId);
              },
              onCiCodeDelta: (delta, callId) => {
                appendCiCodeToActivity(callId, delta);
              },
              onThinking: (text) => {
                addOrUpdateThinking(text);
              },
              onOperation: async (op) => {
                // COLLECT instead of executing — save for approval
                collectedOps.push(op);
              },
              onVbaCode: (data) => {
                setState((prev) => ({
                  ...prev,
                  messages: [...prev.messages, {
                    id: nextMessageId(),
                    role: "vba_code" as const,
                    content: data.purpose,
                    timestamp: Date.now(),
                    vbaCode: data,
                  }],
                }));
              },
              onApiUsage: (data) => {
                apiUsageRef.current.push(data);
              },
              onSummary: (text, count) => {
                resolve({ summary: text, count });
              },
              onError: (message, fatal) => {
                const friendly = friendlyError(message);
                if (friendly) addMessage("system", friendly);
                if (fatal) reject(new Error(message));
              },
              onDone: () => {
                resolve({ summary: "Plan ready.", count: collectedOps.length });
              },
            },
              blueprint as unknown as Record<string, unknown>,
              state.selectedModel,
              selectedPortfolioId || undefined,
              sentFileIds,
              bloombergEnabled,
              state.threadId || undefined,
              selection,
              state.editApprovalMode,
            );
            abortRef.current = abort; // store abort function for stop button
          });

          // Finalize any open activity groups
          finalizeCurrentActivity();

          // Store collected operations in the pending plan ref
          pendingOpsRef.current = collectedOps;

          // Build a summary of what the plan will do
          const opSummary = collectedOps
            .filter((op) => op.action === "write_cells" || op.action === "create_sheet" || op.action === "create_chart")
            .map((op) => {
              if (op.action === "create_sheet") return `Create sheet "${op.name}"`;
              if (op.action === "create_chart") return `Create ${op.chart_type || "column"} chart: "${op.title}"`;
              return `Write to ${op.sheet}`;
            })
            .slice(0, 10);

          const planText = result.summary || `${collectedOps.length} operations planned:\n${opSummary.join("\n")}`;

          // Clear transient system messages before showing plan (keep those with persist: true)
          setState((prev) => ({
            ...prev,
            messages: prev.messages.filter((m) => m.role !== "system" || m.persist),
          }));

          // Show plan card with approval buttons
          addMessage("plan", planText, {
            plan: {
              summary: planText,
              steps: collectedOps.map((op, i) => ({
                step_number: i + 1,
                description: `${op.action}: ${op.sheet || op.name || ""}`,
                sheet: (op.sheet || op.name || "") as string,
                operations: [],
                target_range: "",
              })),
              data_requests: [],
              workbook_id: workbookId,
            },
            planStatus: "pending",
          });
          setStatus("awaiting_approval");
        }
      } catch (err) {
        // Clear transient system messages before showing error (keep those with persist: true)
        setState((prev) => ({
          ...prev,
          messages: prev.messages.filter((m) => m.role !== "system" || m.persist),
        }));
        if (state.status !== "error") setStatus("error");
        const msg = friendlyError(err);
        if (msg) addMessage("agent", msg);
      }
    },
    [addMessage, setStatus, state.mode, state.status, state.selectedModel, state.threadId, state.editApprovalMode, executePlan, selectedPortfolioId, attachedFiles, bloombergEnabled, addOrUpdateActivity, updateLastActivityItem, finalizeCurrentActivity, addOrUpdateThinking, resetActivityAndThinkingRefs, setPendingOperation, tagLastActivityPermission]
  );

  // ─── Smart send: detect "build it" for pending plans ───

  const smartSend = useCallback(
    async (userMessage: string, selection?: Record<string, unknown>) => {
      const lower = userMessage.trim().toLowerCase();
      const buildTriggers = [
        "build", "build it", "go", "go ahead", "yes", "do it",
        "execute", "run it", "proceed", "ok", "sure", "approve",
        "let's go", "lets go", "start", "confirm",
      ];

      if (state.status === "awaiting_approval") {
        const pendingIndex = state.messages.findIndex(
          (m) => m.role === "plan" && m.planStatus === "pending"
        );
        if (pendingIndex >= 0 && buildTriggers.includes(lower)) {
          addMessage("user", userMessage);
          await buildPlan(pendingIndex);
          return;
        }
      }

      await runAgent(userMessage, selection);
    },
    [state.status, state.messages, addMessage, buildPlan, runAgent]
  );

  // ─── Edit Message ───

  const editMessage = useCallback(
    async (messageIndex: number, newContent: string, revert: boolean) => {
      const msg = state.messages[messageIndex];
      if (!msg || msg.role !== "user") return;

      if (revert && msg.checkpointId) {
        await restoreCheckpoint(msg.checkpointId);
      } else {
        setState((prev) => ({
          ...prev,
          messages: prev.messages.slice(0, messageIndex),
          currentPlan: null,
          currentStep: 0,
          status: "done" as AgentStatus,
          pendingOperation: null,
        }));
      }

      setTimeout(() => runAgent(newContent), 50);
    },
    [state.messages, restoreCheckpoint, runAgent]
  );

  // ─── File attachments ───

  const handleFileUpload = useCallback(async (file: File) => {
    try {
      const { uploadFile } = await import("../utils/sentry-api");
      const result = await uploadFile(file);
      if (result) {
        let thumbnailUrl: string | undefined;
        if (file.type.startsWith("image/")) {
          thumbnailUrl = URL.createObjectURL(file);
        }
        const entry = { file_id: result.file_id, filename: result.filename, thumbnailUrl };
        setAttachedFiles((prev) => [...prev, entry]);
        return entry;
      }
    } catch (err) {
      const msg = friendlyError(err);
      addMessage("system", msg || "File upload failed.");
    }
    return null;
  }, [addMessage]);

  const removeAttachedFile = useCallback((fileId: string) => {
    setAttachedFiles((prev) => {
      const removed = prev.find((f) => f.file_id === fileId);
      if (removed?.thumbnailUrl) URL.revokeObjectURL(removed.thumbnailUrl);
      return prev.filter((f) => f.file_id !== fileId);
    });
  }, []);

  // ─── Dev Export: Full conversation state for AI debugging ───

  const exportConversation = useCallback(() => {
    // Build performance summary from activity items
    const allItems: { tool: string; durationMs?: number }[] = [];
    for (const msg of state.messages) {
      if (msg.role === "activity" && msg.activity) {
        for (const item of msg.activity.items) {
          allItems.push({ tool: item.tool, durationMs: item.durationMs });
        }
      }
    }
    const timedItems = allItems.filter(i => i.durationMs != null) as { tool: string; durationMs: number }[];
    const byTool: Record<string, { count: number; totalMs: number; avgMs: number }> = {};
    for (const { tool, durationMs } of timedItems) {
      if (!byTool[tool]) byTool[tool] = { count: 0, totalMs: 0, avgMs: 0 };
      byTool[tool].count++;
      byTool[tool].totalMs += durationMs;
    }
    for (const entry of Object.values(byTool)) {
      entry.avgMs = Math.round(entry.totalMs / entry.count);
    }
    const totalDurationMs = timedItems.reduce((sum, i) => sum + i.durationMs, 0);
    const slowest = timedItems.length > 0
      ? timedItems.reduce((a, b) => a.durationMs >= b.durationMs ? a : b)
      : undefined;

    const exportData = {
      export_version: "2.1",
      exported_at: new Date().toISOString(),
      performance: {
        total_tool_calls: allItems.length,
        timed_tool_calls: timedItems.length,
        total_duration_ms: totalDurationMs,
        avg_duration_ms: timedItems.length > 0 ? Math.round(totalDurationMs / timedItems.length) : 0,
        slowest_tool: slowest ? { tool: slowest.tool, durationMs: slowest.durationMs } : null,
        by_tool: byTool,
        token_summary: (() => {
          const calls = apiUsageRef.current;
          if (calls.length === 0) return null;
          const lastCall = calls[calls.length - 1];
          return {
            total_api_calls: calls.length,
            total_input_tokens: lastCall.cumulative_input_tokens,
            total_output_tokens: calls.reduce((s, c) => s + c.output_tokens, 0),
            peak_input_tokens_per_call: Math.max(...calls.map(c => c.input_tokens)),
            peak_tokens_per_min: Math.max(...calls.map(c => c.tokens_per_min)),
            avg_input_tokens_per_call: Math.round(lastCall.cumulative_input_tokens / calls.length),
          };
        })(),
      },
      session: {
        thread_id: state.threadId,
        workbook_id: state.workbookId,
        model: (() => {
          const info = getModelById(state.selectedModel);
          return {
            id: info.id,
            name: info.name,
            provider: info.provider,
            category: info.category,
            context_limit: info.contextLimit,
            ...(state.lastModelParams ? { params: state.lastModelParams.params } : {}),
          };
        })(),
        mode: state.mode,
        status: state.status,
        edit_approval_mode: state.editApprovalMode,
        current_step: state.currentStep,
        current_plan: state.currentPlan,
        attached_files: attachedFiles.map((f) => ({ file_id: f.file_id, filename: f.filename })),
        selected_portfolio_id: selectedPortfolioId,
        bloomberg_enabled: bloombergEnabled,
      },
      messages: (() => {
        // Map chat messages
        const chatMessages: Record<string, unknown>[] = state.messages.map((msg) => {
          const base: Record<string, unknown> = {
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp,
          };

          if (msg.role === "activity" && msg.activity) {
            base.activity_id = msg.activity.id;
            base.label = msg.activity.label;
            base.status = msg.activity.status;
            base.startedAt = msg.activity.startedAt;
            base.completedAt = msg.activity.completedAt;
            base.durationMs = msg.activity.durationMs;
            base.items = msg.activity.items.map((item) => ({
              tool: item.tool,
              label: item.label,
              status: item.status,
              preview: item.preview,
              parameters: item.parameters,
              result: item.result,
              permission: item.permission,
              startedAt: item.startedAt,
              completedAt: item.completedAt,
              durationMs: item.durationMs,
            }));
          }

          if (msg.role === "thinking") {
            if (msg.thinkingDurationSecs !== undefined) {
              base.thinkingDurationSecs = msg.thinkingDurationSecs;
            }
            if (msg.thinkingSections && msg.thinkingSections.length > 0) {
              base.thinking = msg.thinkingSections.map((s) => ({
                title: s.title,
                content: s.content,
              }));
            }
          }

          if (msg.role === "plan" && msg.plan) {
            base.planStatus = msg.planStatus;
            base.plan = msg.plan;
          }

          if (msg.role === "vba_code" && msg.vbaCode) {
            base.vbaCode = msg.vbaCode;
          }

          if (msg.persist) {
            base.persist = true;
          }

          if (msg.error) {
            base.error = msg.error;
          }

          return base;
        });

        // Merge status phase entries into the timeline
        const phaseEntries: Record<string, unknown>[] = statusPhasesRef.current.map((p) => ({
          role: "status_phase",
          status: p.status,
          startedAt: p.startedAt,
          durationMs: p.durationMs,
          timestamp: p.startedAt,
        }));

        // Merge per-API-call token usage entries into the timeline
        const apiUsageEntries: Record<string, unknown>[] = apiUsageRef.current.map((u) => ({
          role: "api_usage",
          index: u.index,
          input_tokens: u.input_tokens,
          output_tokens: u.output_tokens,
          cached_tokens: u.cached_tokens,
          cumulative_input_tokens: u.cumulative_input_tokens,
          tokens_per_min: u.tokens_per_min,
          timestamp: u.timestamp,
        }));

        return [...chatMessages, ...phaseEntries, ...apiUsageEntries].sort(
          (a, b) => ((a.timestamp as number) || 0) - ((b.timestamp as number) || 0)
        );
      })(),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sentry-conversation-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [state, attachedFiles, selectedPortfolioId, bloombergEnabled]);

  const wrappedNewChat = useCallback(() => {
    if (approvalResolverRef.current) {
      approvalResolverRef.current(false);
      approvalResolverRef.current = null;
    }
    setPendingOperation(null);
    statusPhasesRef.current = [];
    apiUsageRef.current = [];
    checkpointsRef.current = [];
    persistence.newChat();
  }, [setPendingOperation, persistence.newChat]);

  return {
    ...state,
    runAgent: smartSend,
    buildPlan,
    undoPlan,
    restoreCheckpoint,
    editMessage,
    rejectPlan,
    setModel,
    setMode,
    setEditApprovalMode,
    setPendingOperation,
    allowOnce,
    alwaysAllow,
    denyOperation,
    stopAgent,
    newChat: wrappedNewChat,
    chatThreads: persistence.chatThreads,
    loadThread: persistence.loadThread,
    deleteThread: persistence.deleteThread,
    refreshThreads: persistence.refreshThreads,
    attachedFiles,
    onFileUpload: handleFileUpload,
    onRemoveFile: removeAttachedFile,
    portfolios,
    selectedPortfolioId,
    selectPortfolio,
    refreshPortfolios,
    bloombergEnabled,
    setBloombergEnabled,
    toggleActivityCollapsed,
    toggleThinkingSection,
    exportConversation,
  };
}
