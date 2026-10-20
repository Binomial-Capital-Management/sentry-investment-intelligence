export interface TaskDraft {
  nodes: any[];
  edges: any[];
  taskName: string;
  description: string;
  frequency: string;
  cronExpression: string;
  customCronExpression?: string;
  email: string;
  deliveryPreference: string;
  selectedDate?: string;
  timezone?: string;
  tags?: string[];
  selectedDays?: number[];
  dayOfMonth?: number | null;
  updatedAt: number;
}

const STORAGE_KEY = 'task_builder_draft';
const MAX_AGE_MS = 1000 * 60 * 60 * 12; // 12 hours

export function loadTaskDraft(): TaskDraft | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw) as TaskDraft;
    if (!draft?.nodes || !Array.isArray(draft.nodes)) return null;
    if (Date.now() - draft.updatedAt > MAX_AGE_MS) {
      window.localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return draft;
  } catch (error) {
    console.error('Failed to load task draft', error);
    return null;
  }
}

export function saveTaskDraft(draft: Omit<TaskDraft, 'updatedAt'>): void {
  if (typeof window === 'undefined') return;
  try {
    const payload: TaskDraft = { ...draft, updatedAt: Date.now() };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (error) {
    console.error('Failed to save task draft', error);
  }
}

export function clearTaskDraft(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.error('Failed to clear task draft', error);
  }
}
