// Import type from upload service
import type { UploadedFile } from '@services/upload';

// Model types
export type ModelId =
  | 'gpt-6-astra'
  | 'gpt-6.1-sol'
  | 'gpt-6-luna'
  | 'litellm/anthropic/claude-fable-5-1'
  | 'litellm/anthropic/claude-opus-5-5'
  | 'litellm/anthropic/claude-sonnet-5-5'
  | 'litellm/anthropic/claude-haiku-4-5-20251001'
  | 'litellm/gemini/gemini-4-argon'
  | 'litellm/gemini/gemini-3.8-flash'
  | 'litellm/gemini/gemini-3.5-flash-lite'
  | 'litellm/xai/grok-4.7'
  | 'litellm/xai/grok-4.20-0309-non-reasoning'
  | 'litellm/moonshot/kimi-k3'
  | 'litellm/dashscope/qwen3.8-max'
  | 'litellm/zai/glm-5.3'
  ;

export interface ModelInfo {
  id: ModelId;
  name: string;
  provider: 'OpenAI' | 'Anthropic' | 'Google' | 'DeepSeek' | 'xAI' | 'Perplexity' | 'AWS' | 'Moonshot' | 'Alibaba' | 'Zhipu';
  logo: string;
  available: boolean;
  category: 'fast' | 'versatile' | 'powerful' | 'search';
  description?: string;
  contextLimit?: string;
}

// Message types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: Source[];
  charts?: ChartData[];
  tables?: TableData[];
  isStreaming?: boolean;
  error?: string;
  // Optional structured reasoning trace (v6)
  reasoning?: ReasoningTrace;
  // Agent metadata for V6
  agentType?: 'generalist' | 'risk_specialist' | 'prediction_markets_analyst' | 'orchestrator';
  agentName?: string;
  confidence?: number;
  handoffFrom?: string;
  handoffReason?: string;
  // Loading state for IntelligenceLoader
  loadingPhase?: 'discovery' | 'analysis' | 'calculation' | 'synthesis';
  loadingProgress?: number;
  loadingSubtask?: string;
  // Preserve any additional backend-provided fields
  extras?: Record<string, unknown>;
  reasoningStream?: string[];
  reasoningText?: string;
  toolEvents?: ToolEvent[];
  refusal?: RefusalDetail | null;
  guardrail?: GuardrailHit | null;
  reasoningStreaming?: boolean;
  // File attachments
  attachments?: UploadedFile[];
  // Portfolio context (for user messages)
  portfolio?: Portfolio;
  portfolioId?: string;
}

export interface ChatArtifact {
  id: string;
  type: 'cancelled';
  createdAt: Date;
  data: {
    reason: 'user' | 'backend' | 'disconnect' | 'send_now';
    partialContent?: string;
  };
}

export interface ToolEvent {
  id: string;
  toolType:
    | 'function_call'
    | 'mcp_call'
    | 'code_interpreter'
    | 'custom_tool_call'
    | 'response'
    | 'output_item'
    | 'content_part'
    | 'image_generation'
    | 'file_search'
    | 'web_search'
    | 'reasoning';
  toolName: string;
  // Granular statuses from OpenAI Responses API
  status:
    | 'in_progress'
    | 'completed'
    | 'failed'
    | 'searching'       // file_search.searching, web_search.searching
    | 'interpreting'    // code_interpreter.interpreting
    | 'generating'      // image_generation.generating
    | 'arguments_delta' // function_call/mcp_call arguments streaming
    | 'arguments_done'  // function_call/mcp_call arguments complete
    | 'code_delta'      // code_interpreter code streaming
    | 'code_done';      // code_interpreter code complete
  startTime: number;
  endTime?: number;
  arguments?: string;
  result?: string;
  error?: string;
  details?: Record<string, unknown>;
  progress?: number; // 0-100 percentage
  messageIndex?: number; // Index of the assistant message that triggered this tool call
}

export interface RefusalDetail {
  text: string;
}

export interface GuardrailHit {
  type: string;
  message: string;
}

export interface Source {
  id: number;
  title: string;
  url: string;
  snippet?: string;
}

export interface ChartData {
  id: string;
  data?: any; // Plotly data format (optional for backward compat)
  layout?: any; // Plotly layout format (optional for backward compat)
  plotly?: {
    data: any; // Plotly data format (v6 backend format)
    layout: any; // Plotly layout format (v6 backend format)
  };
  config?: any; // Plotly config
  // Additional metadata for ChartFrame
  title?: string;
  subtitle?: string;
  alt_text?: string;
  metadata?: any;
  kpis?: Array<{
    label: string;
    value: number | string;
    change?: number;
    trend?: 'up' | 'down' | 'neutral';
  }>;
}

// Table data interface
export interface TableData {
  id?: string;
  title: string;
  headers: string[];
  rows: (string | number)[][];
  caption?: string;
  metadata?: any;
}

// Optional reasoning trace (v6 agents)
export interface ReasoningTraceStep {
  name: string;
  durationMs?: number;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  error?: string;
}

export interface ReasoningTrace {
  steps: ReasoningTraceStep[];
  handoffs?: Array<{ from: string; to: string; reason?: string }>;
  totalDurationMs?: number;
}

// Portfolio types
export interface Portfolio {
  tickers: string[];
  weights?: number[];
  value: number;
  lastUpdated: Date;
}

// Risk metrics are flexible in v6; do not hardcode keys
export type RiskMetrics = Record<string, number> & {
  // Common, optional well-known keys for type-ahead (non-breaking)
  var_95?: number;
  var_99?: number;
  cvar_95?: number;
  cvar_99?: number;
  volatility?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
};

// API types
export interface ChatRequest {
  message: string;
  portfolio?: Portfolio;
  stream?: boolean;
  // V6 session continuity
  session_id?: string;
  // Agent routing
  agent_mode?: string;
  // Portfolio selection
  portfolio_id?: string;
  // File attachments
  file_ids?: string[];
  // Model selection
  selected_model?: string;
  // Prioritized tools for forced usage
  prioritized_tools?: string[];
  // Optional short history to support reformat/convert intents without full context
  history?: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
}

export interface ChatResponse {
  response: string;
  sources?: Source[];
  charts?: ChartData[];
  metrics?: RiskMetrics;
  error?: string;
  // v6 extras
  session_id?: string;
  reasoning?: ReasoningTrace;
  version?: string;
}

export interface ClassifyResponse {
  needs_calculation: boolean;
  intent: string;
  confidence: number;
}

// UI State types
export interface UIState {
  isLoading: boolean;
  loadingMessage: string;
  activeModal: 'portfolio' | 'reports' | 'export' | 'history' | 'bookmarks' | 'settings' | null;
  activeTab: 'binomial' | 'sources';
  sidebarExpanded: boolean;
  backendVersion?: 'v5' | 'v6' | 'unknown';
  healthStatus?: 'healthy' | 'degraded' | 'down';
}

// Agent mode type
export type AgentMode = 'auto' | 'generalist' | 'risk' | 'web' | 'market' | 'filings' | 'multiples' | 'charts' | 'quant' | 'structuring' | 'dcf' | 'options' | 'alternatives' | 'institutional' | 'prediction_markets' | 'funds_products' | 'private_markets';

// Thread types
export interface Thread {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  selectedModel?: ModelId;
  agentMode?: AgentMode;
  artifacts?: ChatArtifact[];
  hasLoadedMessages?: boolean;
}

export interface StreamingContext {
  agentMode?: AgentMode;
  portfolioId?: string;
  sessionId?: string;
  fileIds?: string[];
  selectedModel?: ModelId;
  deepAnalysisMode?: boolean;
  prioritizedTools?: string[];
  isResume?: boolean;
  messageId?: string;
  isBlocking?: boolean;
}

// Re-export memory types
export type {
  MemoryNote,
  MemoryNoteCreate,
  MemoryNoteUpdate,
  MemoryNotebook,
  ContextTokenStats,
  MemorySection,
  MemoryReferenceType,
  MemorySource,
} from './memory';
