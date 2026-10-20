// Task-related TypeScript interfaces and types

export interface Task {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  frequency: 'once' | 'daily' | 'weekdays' | 'weekly' | 'biweekly' | 'monthly' | 'custom';
  timezone?: string;              // Task timezone (e.g., "America/New_York")
  time?: string;                  // Time string (e.g., "02:30 PM" or "14:30")
  cron_expression?: string;
  days_of_week?: number[];        // 0=Sunday to 6=Saturday for weekly/biweekly
  day_of_month?: number;          // 1-31 for monthly frequency
  start_date?: string;            // ISO8601 date for 'once' frequency
  delivery_preference: 'email' | 'slack' | 'teams' | 'saveToSentry';
  email?: string;
  slack_webhook?: string;
  webhook_url?: string;
  status: 'draft' | 'active' | 'paused' | 'archived';
  canvas_data?: any;
  agent_config?: any;
  metadata?: Record<string, any>;
  next_run_at?: string;
  last_run_at?: string;
  created_at: string;
  updated_at: string;
}

export interface TaskExecution {
  id: string;
  task_id: string;
  user_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  trigger_type: 'scheduled' | 'manual';
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at?: string;
  result?: any;
  error_message?: string;
  execution_time_ms?: number;
  input_snapshot?: any;
  delivery_results?: any;
}

export interface TaskArtifact {
  name?: string;
  path?: string;
  url?: string;
  type?: string;
  category?: string;  // For S3 artifact downloads (e.g., "tasks")
  filename?: string;  // For S3 artifact downloads
  s3_key?: string;    // Full S3 key path
  [key: string]: any;
}

export interface TaskSavedOutput {
  id: string;
  task_run_id: string;
  task_id: string;
  user_id: string;
  output?: any;
  artifacts: TaskArtifact[];
  delivery_metadata: Record<string, any>;
  created_at: string;
}

export interface TaskRunHistoryEntry {
  run: TaskExecution;
  saved_output?: TaskSavedOutput;
}

export interface TaskCreate {
  name: string;
  description?: string;
  frequency: 'once' | 'daily' | 'weekdays' | 'weekly' | 'biweekly' | 'monthly' | 'custom';
  timezone?: string;              // Task timezone (e.g., "America/New_York")
  time?: string;                  // Time string (e.g., "02:30 PM" or "14:30")
  start_date?: string;            // ISO8601 date for 'once' frequency
  days_of_week?: number[];        // 0=Sunday to 6=Saturday for weekly/biweekly
  day_of_month?: number;          // 1-31 for monthly frequency
  cron_expression?: string;       // Cron expression for 'custom' frequency only
  delivery_preference: 'email' | 'slack' | 'teams' | 'saveToSentry';
  email?: string;
  slack_webhook?: string;
  webhook_url?: string;
  canvas_data: any;
  agent_config: any;
  status?: 'draft' | 'active' | 'paused' | 'archived';
}

export interface TaskUpdate extends Partial<TaskCreate> {
  status?: 'draft' | 'active' | 'paused' | 'archived';
}

export interface TaskListResponse {
  tasks: Task[];
}

export interface TaskRunHistoryResponse {
  runs: TaskRunHistoryEntry[];
}
