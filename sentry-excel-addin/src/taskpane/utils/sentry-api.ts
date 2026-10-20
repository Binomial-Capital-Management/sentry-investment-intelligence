/**
 * HTTP + SSE client for the Sentry backend /v1/excel/* endpoints.
 *
 * Plan endpoint now uses SSE streaming (not hardcoded status).
 * Other endpoints remain REST.
 */

import axios, { AxiosInstance } from "axios";
import { getAuthHeaders } from "../../shared/auth";

const API_BASE = process.env.SENTRY_API_URL || "";

function createClient(): AxiosInstance {
  return axios.create({
    baseURL: `${API_BASE}/v1/excel`,
    timeout: 900_000,
    headers: { "Content-Type": "application/json" },
  });
}

function withAuth(client: AxiosInstance): AxiosInstance {
  client.interceptors.request.use((config) => {
    const headers = getAuthHeaders();
    Object.assign(config.headers, headers);
    return config;
  });
  return client;
}

const client = withAuth(createClient());

// -- Index --

export async function lookupIndex(workbookHash: string) {
  const { data } = await client.get("/index/lookup", {
    params: { workbook_hash: workbookHash },
  });
  return data;
}

export async function indexWorkbook(
  workbookData: Record<string, unknown>,
  workbookHash: string,
  workbookName: string
) {
  const { data } = await client.post("/index", {
    workbook_data: workbookData,
    workbook_hash: workbookHash,
    workbook_name: workbookName,
  });
  return data;
}

export async function diffIndex(workbookId: string, currentHash: string) {
  const { data } = await client.post("/index/diff", {
    workbook_id: workbookId,
    current_hash: currentHash,
  });
  return data;
}

export async function reindexSheet(
  workbookId: string,
  sheetName: string,
  sheetData: Record<string, unknown>
) {
  const { data } = await client.post("/index/reindex-sheet", {
    workbook_id: workbookId,
    sheet_name: sheetName,
    sheet_data: sheetData,
  });
  return data;
}

// -- Search --

export async function searchWorkbook(
  workbookId: string,
  query: string,
  topK?: number
) {
  const { data } = await client.post("/search", {
    workbook_id: workbookId,
    query,
    top_k: topK,
  });
  return data;
}

// -- Plan (SSE streaming) --

export interface SSECallbacks {
  onStatus?: (stage: string, message: string) => void;
  onToolCall?: (tool: string, message: string) => void;
  onToolDone?: (output: string, message: string) => void;
  onThinking?: (text: string) => void;
  onPlan?: (plan: Record<string, unknown>) => void;
  onError?: (message: string, fatal: boolean) => void;
  onDone?: () => void;
}

/**
 * Create a plan via SSE streaming.
 *
 * Uses XMLHttpRequest with onprogress (better compatibility with Office WebView
 * than fetch + ReadableStream). Parses SSE events incrementally.
 *
 * Returns an abort function so the caller can cancel.
 */
export function createPlanSSE(
  message: string,
  workbookId: string,
  callbacks: SSECallbacks
): { abort: () => void } {
  const url = `${API_BASE}/v1/excel/plan`;
  const auth = getAuthHeaders();
  const xhr = new XMLHttpRequest();
  let processedLength = 0;
  let buffer = "";

  function parseSSEChunk(chunk: string): void {
    buffer += chunk;
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;

      let eventName = "message";
      let eventData = "";

      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) {
          eventName = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          eventData = line.slice(6);
        }
      }

      if (!eventData) continue;

      try {
        const parsed = JSON.parse(eventData);
        switch (eventName) {
          case "status":
            callbacks.onStatus?.(parsed.stage || "", parsed.message || "");
            break;
          case "tool_call":
            callbacks.onToolCall?.(parsed.tool || "", parsed.message || "");
            break;
          case "tool_done":
            callbacks.onToolDone?.(parsed.output || "", parsed.message || "");
            break;
          case "thinking":
            callbacks.onThinking?.(parsed.text || "");
            break;
          case "plan":
            callbacks.onPlan?.(parsed);
            break;
          case "error":
            callbacks.onError?.(parsed.message || "Unknown error", !!parsed.fatal);
            break;
          case "done":
            callbacks.onDone?.();
            break;
        }
      } catch {
        // Non-JSON — ignore
      }
    }
  }

  xhr.open("POST", url, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  // Apply auth headers
  for (const [key, val] of Object.entries(auth)) {
    if (typeof val === "string") xhr.setRequestHeader(key, val);
  }

  // Incremental parsing as data arrives
  xhr.onprogress = function () {
    const newData = xhr.responseText.slice(processedLength);
    processedLength = xhr.responseText.length;
    if (newData) parseSSEChunk(newData);
  };

  xhr.onload = function () {
    // Parse any remaining data
    const remaining = xhr.responseText.slice(processedLength);
    if (remaining) parseSSEChunk(remaining);
    callbacks.onDone?.();
  };

  xhr.onerror = function () {
    callbacks.onError?.("Network error during plan generation", true);
  };

  xhr.ontimeout = function () {
    callbacks.onError?.("Plan generation timed out", true);
  };

  xhr.timeout = 900_000; // 15 minutes
  xhr.send(JSON.stringify({ message, workbook_id: workbookId }));

  return {
    abort: () => {
      try { xhr.abort(); } catch { /* ignore */ }
    },
  };
}

// ═══════════════════════════════════════════════════════════════════════════════
// Execute (v2 — tool-calling architecture, operations stream one at a time)
// ═══════════════════════════════════════════════════════════════════════════════

export interface ExecuteSSECallbacks {
  /** Tool-first mode: skip RAG context search, agent reads workbook on-demand */
  skipContext?: boolean;
  /** Called when stream starts with message_id and request_id */
  onStart?: (data: { message_id: string; request_id: string }) => void;
  onStatus?: (stage: string, message: string) => void;
  /** Called when agent starts a tool call. Includes structured parameters and call_id if available. */
  onToolCall?: (tool: string, parameters?: Record<string, unknown>, callId?: string) => void;
  /** Called when tool returns. Includes structured result and call_id for correlation. */
  onToolDone?: (output: string, result?: Record<string, unknown>, callId?: string) => void;
  /** Called when a tool actually completes on the server (real-time, before batched tool_done) */
  onToolServerDone?: (tool: string, callId?: string, serverDurationMs?: number) => void;
  onThinking?: (text: string) => void;
  /** Called once per request with the actual model parameters used by the backend */
  onModelParams?: (model: string, params: Record<string, unknown>) => void;
  /** Called during silent thinking to report API milestone phases */
  onThinkingPhase?: (phase: string, elapsedMs: number) => void;
  /** Called for each streamed text token from the agent's final response */
  onToken?: (text: string) => void;
  /** Called for each Excel operation — frontend should execute immediately */
  onOperation?: (op: Record<string, unknown>) => void;
  /** Called when agent generates VBA macro code for the user */
  onVbaCode?: (data: { title: string; code: string; purpose: string; instructions: string; sheets_involved: string[] }) => void;
  /** Called for each API call completion with real token usage from the provider */
  onApiUsage?: (data: { index: number; timestamp: number; input_tokens: number; output_tokens: number; cached_tokens: number; cumulative_input_tokens: number; tokens_per_min: number }) => void;
  /** Called for each Python code delta as the model writes a code_interpreter block */
  onCiCodeDelta?: (delta: string, callId?: string) => void;
  /** Called when code_interpreter transitions from writing to executing */
  onCiInterpreting?: (callId?: string) => void;
  onSummary?: (text: string, count: number) => void;
  onError?: (message: string, fatal: boolean) => void;
  onDone?: () => void;
}

/**
 * Execute a request via the v2 tool-calling agent.
 * Operations stream one at a time for immediate Office.js execution.
 */
export function executeSSE(
  message: string,
  workbookId: string,
  callbacks: ExecuteSSECallbacks,
  blueprint?: Record<string, unknown>,
  model?: string,
  portfolioId?: string,
  fileIds?: string[],
  bloomberg?: boolean,
  threadId?: string,
  selection?: Record<string, unknown>,
  editApprovalMode?: string,
): { abort: () => void } {
  const url = `${API_BASE}/v1/excel/execute`;
  const auth = getAuthHeaders();
  const xhr = new XMLHttpRequest();
  let processedLength = 0;
  let buffer = "";

  let _doneFired = false;  // guard against double onDone (SSE "done" event + xhr.onload)

  function parseSSEChunk(chunk: string): void {
    buffer += chunk;
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;

      let eventName = "message";
      let eventData = "";

      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) {
          eventName = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          eventData = line.slice(6);
        }
      }

      if (!eventData) continue;

      try {
        const parsed = JSON.parse(eventData);
        switch (eventName) {
          case "start":
            callbacks.onStart?.({
              message_id: parsed.message_id || "",
              request_id: parsed.request_id || "",
            });
            break;
          case "status":
            callbacks.onStatus?.(parsed.stage || "", parsed.message || "");
            break;
          case "tool_call":
            callbacks.onToolCall?.(parsed.tool || "tool", parsed.parameters, parsed.call_id);
            break;
          case "tool_done":
            callbacks.onToolDone?.(parsed.output || "", parsed.result, parsed.call_id);
            break;
          case "tool_server_done":
            callbacks.onToolServerDone?.(parsed.tool || "", parsed.call_id, parsed.server_duration_ms);
            break;
          case "model_params":
            callbacks.onModelParams?.(parsed.model || "", parsed.params || {});
            break;
          case "thinking":
            callbacks.onThinking?.(parsed.text || "");
            break;
          case "token":
            callbacks.onToken?.(parsed.text || "");
            break;
          case "operation":
            callbacks.onOperation?.(parsed);
            break;
          case "vba_code":
            callbacks.onVbaCode?.({
              title: parsed.title || "",
              code: parsed.code || "",
              purpose: parsed.purpose || "",
              instructions: parsed.instructions || "",
              sheets_involved: parsed.sheets_involved || [],
            });
            break;
          case "api_usage":
            callbacks.onApiUsage?.(parsed);
            break;
          case "ci_code_delta":
            callbacks.onCiCodeDelta?.(parsed.delta || "", parsed.call_id);
            break;
          case "ci_interpreting":
            callbacks.onCiInterpreting?.(parsed.call_id);
            break;
          case "summary":
            callbacks.onSummary?.(parsed.text || "", parsed.count || 0);
            break;
          case "error":
            callbacks.onError?.(parsed.message || "Unknown error", !!parsed.fatal);
            break;
          case "done":
            if (!_doneFired) { _doneFired = true; callbacks.onDone?.(); }
            break;
        }
      } catch {
        // Non-JSON — ignore
      }
    }
  }

  xhr.open("POST", url, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  for (const [key, val] of Object.entries(auth)) {
    if (typeof val === "string") xhr.setRequestHeader(key, val);
  }

  xhr.onprogress = function () {
    const newData = xhr.responseText.slice(processedLength);
    processedLength = xhr.responseText.length;
    if (newData) parseSSEChunk(newData);
  };

  xhr.onload = function () {
    const remaining = xhr.responseText.slice(processedLength);
    if (remaining) parseSSEChunk(remaining);
    // Only fire onDone if not already fired by SSE "done" event
    if (!_doneFired) { _doneFired = true; callbacks.onDone?.(); }
  };

  xhr.onerror = function () {
    callbacks.onError?.("Network error during execution", true);
  };

  xhr.timeout = 0; // no timeout — agent may wait indefinitely for user permission
  xhr.send(JSON.stringify({
    message,
    workbook_id: workbookId,
    thread_id: threadId || undefined,
    blueprint,
    model: model || undefined,
    portfolio_id: portfolioId || undefined,
    file_ids: fileIds && fileIds.length > 0 ? fileIds : undefined,
    bloomberg: bloomberg || false,
    skip_context: callbacks.skipContext || false,
    selection: selection || undefined,
    edit_approval_mode: editApprovalMode || "accept",
  }));

  return {
    abort: () => {
      try { xhr.abort(); } catch { /* ignore */ }
    },
  };
}

/**
 * Cancel an active Excel agent execution.
 * Called when the user clicks the stop button.
 */
export async function cancelExecution(requestId: string): Promise<{ status: string }> {
  const auth = getAuthHeaders();
  const response = await fetch(`${API_BASE}/v1/excel/execute/cancel/${requestId}`, {
    method: "POST",
    headers: { ...auth, "Content-Type": "application/json" },
  });
  return response.json();
}

/**
 * Send read response back to backend during active execution.
 * Called by the frontend after reading a range requested by excel_read_range tool.
 */
export async function postReadResponse(
  requestId: string,
  readId: string,
  response: {
    success: boolean;
    data?: unknown; // Generic data: read_range returns {values, formulas}, discovery tools return different shapes
    error?: string;
  }
): Promise<{ status: string }> {
  const auth = getAuthHeaders();
  const res = await fetch(`${API_BASE}/v1/excel/execute/${requestId}/read-response`, {
    method: "POST",
    headers: { ...auth, "Content-Type": "application/json" },
    body: JSON.stringify({
      read_id: readId,
      ...response,
    }),
  });
  return res.json();
}

/**
 * Send approval/denial back to backend for a write operation.
 * Called when the user clicks Allow/Deny on the PermissionDialog.
 */
export async function postApprovalResponse(
  requestId: string,
  approvalId: string,
  approved: boolean,
): Promise<{ status: string }> {
  const auth = getAuthHeaders();
  const res = await fetch(`${API_BASE}/v1/excel/execute/${requestId}/approval-response`, {
    method: "POST",
    headers: { ...auth, "Content-Type": "application/json" },
    body: JSON.stringify({ approval_id: approvalId, approved }),
  });
  return res.json();
}

/**
 * Legacy REST createPlan — kept for non-streaming fallback.
 */
export async function createPlan(message: string, workbookId: string) {
  const { data } = await client.post("/plan", {
    message,
    workbook_id: workbookId,
  });
  return data;
}

export async function supplementPlan(
  workbookId: string,
  message: string,
  supplementalData: Record<string, unknown>
) {
  const { data } = await client.post("/plan/supplement", {
    workbook_id: workbookId,
    message,
    data: supplementalData,
  });
  return data;
}

// -- Validate --

export async function validateStep(
  step: Record<string, unknown>,
  actual: Record<string, unknown>,
  workbookId: string,
  attempt: number
) {
  const { data } = await client.post("/validate", {
    step,
    actual,
    workbook_id: workbookId,
    attempt,
  });
  return data;
}

// =============================================================================
// Workbook Chat CRUD (separate from main chats)
// =============================================================================

export interface ChatThreadSummary {
  id: string;
  workbook_id: string;
  title: string | null;
  model: string | null;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
}

export interface ChatMessageOut {
  id: string;
  role: string;
  content: string;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

/** List chat threads, optionally filtered by workbook. */
export async function listWorkbookChats(
  workbookId?: string
): Promise<ChatThreadSummary[]> {
  const params: Record<string, string> = {};
  if (workbookId) params.workbook_id = workbookId;
  const { data } = await client.get("/chats", { params });
  return data;
}

/** Load all messages for a thread. */
export async function loadWorkbookChat(
  threadId: string
): Promise<ChatMessageOut[]> {
  const { data } = await client.get(`/chats/${threadId}/messages`);
  return data;
}

/** Save an entire chat (creates new thread + bulk messages). */
export async function saveWorkbookChat(payload: {
  workbook_id: string;
  title?: string;
  model?: string;
  messages: { role: string; content: string; metadata?: Record<string, unknown> }[];
}): Promise<ChatThreadSummary> {
  const { data } = await client.post("/chats", payload);
  return data;
}

/** Append a single message to an existing thread. */
export async function appendChatMessage(
  threadId: string,
  message: { role: string; content: string; metadata?: Record<string, unknown> }
): Promise<ChatMessageOut> {
  const { data } = await client.post(`/chats/${threadId}/messages`, message);
  return data;
}

/** Delete a single chat thread. */
export async function deleteWorkbookChat(threadId: string): Promise<void> {
  await client.delete(`/chats/${threadId}`);
}

/** Bulk delete multiple chat threads. */
export async function bulkDeleteWorkbookChats(
  threadIds: string[]
): Promise<{ deleted_count: number }> {
  const { data } = await client.post("/chats/bulk-delete", {
    thread_ids: threadIds,
  });
  return data;
}

// =============================================================================
// File Upload (reuses main app upload endpoint)
// =============================================================================

const uploadClient = axios.create({
  baseURL: `${API_BASE}/api/uploads`,
  timeout: 120_000,
});

export interface UploadedFile {
  file_id: string;
  filename: string;
  size: number;
  mime_type: string;
}

/** Upload a file to the backend. Returns file metadata. */
export async function uploadFile(file: File): Promise<UploadedFile> {
  const formData = new FormData();
  formData.append("files", file);
  const auth = getAuthHeaders();
  const { data } = await uploadClient.post("/files", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
      ...auth,
    },
  });
  // Backend returns { files: [{id, original_name, content_type, size}] }
  const files = data.files || data;
  const raw = Array.isArray(files) ? files[0] : files;
  return {
    file_id: raw.id || raw.file_id,
    filename: raw.original_name || raw.filename,
    size: raw.size ?? 0,
    mime_type: raw.content_type || raw.mime_type || "",
  };
}

// =============================================================================
// Portfolios (reuses main app portfolio API)
// =============================================================================

const portfolioClient = axios.create({
  baseURL: `${API_BASE}/api/portfolios`,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

export interface PortfolioSummary {
  id: string;
  name: string;
  tickers: string[];
  weights: number[];
  value: number;
  is_default: boolean;
  created_at: string;
}

/** List all portfolios for the current user. */
export async function listPortfolios(): Promise<PortfolioSummary[]> {
  const auth = getAuthHeaders();
  const { data } = await portfolioClient.get("", { headers: auth });
  return data;
}

// =============================================================================
// Memory Notebook (reuses main app memory API)
// =============================================================================

const memoryClient = axios.create({
  baseURL: `${API_BASE}/api/memory`,
  timeout: 30_000,
});

export interface MemoryNote {
  id: string;
  section: string;
  content: string;
  priority: number;
  source: string;
  created_at: string;
}

/** Get all notes for a session. */
export async function getMemoryNotes(
  sessionId: string,
  section?: string
): Promise<MemoryNote[]> {
  const auth = getAuthHeaders();
  const params: Record<string, string> = {};
  if (section) params.section = section;
  const { data } = await memoryClient.get(`/${sessionId}`, { headers: auth, params });
  return data.notes || [];
}

/** Create a memory note. */
export async function createMemoryNote(
  sessionId: string,
  content: string,
  section: string = "general",
  priority: number = 5
): Promise<MemoryNote> {
  const auth = getAuthHeaders();
  const { data } = await memoryClient.post(`/${sessionId}`, {
    content,
    section,
    priority,
    source: "user",
  }, { headers: auth });
  return data;
}

/** Delete a memory note. */
export async function deleteMemoryNote(
  sessionId: string,
  noteId: string
): Promise<void> {
  const auth = getAuthHeaders();
  await memoryClient.delete(`/${sessionId}/notes/${noteId}`, { headers: auth });
}

// ─── Chat Role Helpers ─────────────────────────────────────────────────────────

import type { AgentMessage } from "../../shared/types";

/** Roles we persist (skip transient "system" status messages) */
export const PERSISTABLE_ROLES = new Set(["user", "agent", "plan", "vba_code", "activity", "thinking"]);

/** Map frontend role → DB role (DB constraint: user, assistant, system, plan) */
export function toDbRole(role: string): string {
  if (role === "agent" || role === "vba_code" || role === "activity" || role === "thinking") return "assistant";
  return role;
}

/** Map DB role → frontend role */
export function fromDbRole(role: string): AgentMessage["role"] {
  return (role === "assistant" ? "agent" : role) as AgentMessage["role"];
}
