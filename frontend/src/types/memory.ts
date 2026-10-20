// Memory Notebook Types

export type MemorySection = 'entities' | 'decisions' | 'preferences' | 'context' | 'general';
export type MemoryReferenceType = 'text' | 'message_excerpt' | 'file' | 'portfolio' | 'chart' | 'table' | 'dataset' | 'web' | 'sec_filing' | 'transcript';
export type MemorySource = 'user' | 'ai' | 'tool';

export interface MemoryNote {
  id: string;
  session_id: string;
  user_id: string;
  org_id?: string;
  section: MemorySection;
  content: string;
  summary?: string;
  reference_type: MemoryReferenceType;
  reference_id?: string;
  reference_metadata?: Record<string, unknown>;
  source: MemorySource;
  priority: number;
  is_chunked?: boolean;  // True if indexed for semantic retrieval
  created_at: string;
  updated_at: string;
}

export interface MemoryNoteCreate {
  content: string;
  section?: MemorySection;
  priority?: number;
  reference_type?: MemoryReferenceType;
  reference_id?: string;
  reference_metadata?: Record<string, unknown>;
}

export interface MemoryNoteUpdate {
  content?: string;
  section?: MemorySection;
  priority?: number;
  summary?: string;
}

export interface MemoryNotebook {
  session_id: string;
  notes: MemoryNote[];
  total_count: number;
  sections: MemorySection[];
}

export interface ContextTokenStats {
  // Provider info
  provider: string;
  model: string;
  context_limit: number;
  // Token breakdown
  memory_notebook_tokens: number;
  compaction_summary_tokens: number;
  message_history_tokens: number;
  system_prompt_tokens: number;
  // Computed
  total_used: number;
  remaining: number;
  usage_percent: number;
  pressure_level: 'low' | 'medium' | 'high' | 'critical';
}

// Section display config - professional styling without emojis
export const SECTION_CONFIG: Record<MemorySection, { label: string; color: string; bg: string }> = {
  entities: { label: 'Entities', color: '#0078D4', bg: '#EFF6FC' },
  decisions: { label: 'Decisions', color: '#107C10', bg: '#DFF6DD' },
  preferences: { label: 'Preferences', color: '#5C2D91', bg: '#F3E5FF' },
  context: { label: 'Context', color: '#D83B01', bg: '#FED9CC' },
  general: { label: 'General', color: '#605E5C', bg: '#F3F2F1' },
};

