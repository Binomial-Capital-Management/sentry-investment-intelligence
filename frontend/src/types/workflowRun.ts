// Workflow Run TypeScript types for execution results

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type StepStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped';

export interface WorkflowStep {
  id: string;
  node_id: string;
  node_type: 'dataset' | 'agent' | 'output';
  node_label?: string;
  status: StepStatus;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  output?: any;
  error?: string;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  user_id: string;
  status: RunStatus;
  started_at: string;
  finished_at?: string;
  completed_at?: string;  // Backend uses this instead of finished_at
  duration_ms?: number;
  steps: WorkflowStep[];
  summary?: {
    content?: string;
    charts?: any[];
    metrics?: Record<string, any>;
    // Handle nested structure from backend
    summary?: {
      content?: string;
      charts?: any[];
    };
  };
  error?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRunListResponse {
  runs: WorkflowRun[];
  total: number;
}
