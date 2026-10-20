// Simplified Workflow TypeScript types matching backend models

// ===== INPUT NODES =====
export type InputNodeType = 'portfolio' | 'uploaded_file' | 'prompt' | 'external_data';

export interface InputNode {
  id: string;
  type: InputNodeType;
  portfolio_id?: string;
  file_id?: string;
  prompt_text?: string;
  external_source?: 'google_drive' | 'onedrive';  // For external_data type
}

// ===== AGENT NODES =====
export type AgentNodeType =
  | 'generalist'
  | 'risk_specialist'
  | 'document_analyst'
  | 'comparable_companies'
  | 'chart_analyst'
  | 'quant_coding'
  | 'alternatives_coding'
  | 'institutional_activity'
  | 'dcf_agent'
  | 'options_coding'
  | 'prediction_markets';

export interface AgentNode {
  id: string;
  agent_type: AgentNodeType;
  custom_prompt: string;  // Can use {input}, {previous_output}
}

// ===== OUTPUT NODES =====
export type OutputNodeType = 'text' | 'pdf' | 'presentation';

export interface OutputNode {
  id: string;
  type: OutputNodeType;
  title?: string;
  include_charts?: boolean;
}

// ===== SIMPLIFIED WORKFLOW =====
export interface SimplifiedWorkflow {
  input_node: InputNode;
  agent_nodes: AgentNode[];
  output_node: OutputNode;
}

// ===== API MODELS =====
export interface WorkflowCreate {
  name: string;
  description?: string;
  simplified_workflow: SimplifiedWorkflow;
  status?: 'draft' | 'active' | 'archived';
}

export interface WorkflowResponse {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  simplified_workflow: SimplifiedWorkflow | null;
  nodes: any[] | null;  // Legacy format (deprecated)
  edges: any[] | null;  // Legacy format (deprecated)
  configuration: any | null;  // Legacy format (deprecated)
  status: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WorkflowListResponse {
  workflows: WorkflowResponse[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface WorkflowValidationResponse {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  agent_count: number;
  unknown_agents: string[];
}

// ===== WORKFLOW RUNS =====
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

export interface WorkflowRunResponse {
  id: string;
  workflow_id: string;
  user_id: string;
  status: RunStatus;
  input_data: Record<string, any>;
  output_data?: Record<string, any>;
  configuration: Record<string, any>;
  error?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface WorkflowRunStepResponse {
  id: string;
  run_id: string;
  node_id: string;
  node_type: string;
  node_label?: string;
  status: StepStatus;
  input_data: Record<string, any>;
  output_data?: Record<string, any>;
  error_message?: string;
  execution_order: number;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}
