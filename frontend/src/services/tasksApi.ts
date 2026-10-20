import axios from 'axios';
import type {
  Task,
  TaskCreate,
  TaskUpdate,
  TaskListResponse,
  TaskExecution,
  TaskRunHistoryEntry,
  TaskRunHistoryResponse,
} from '@/types/tasks';
import { getAuthToken } from './authService';

import { API_BASE } from './api';

// Create axios instance for tasks API
export const tasksClient = axios.create({
  baseURL: API_BASE || undefined,
  timeout: 900000, // 15 minutes max for long-running tasks
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth
tasksClient.interceptors.request.use(
  async (config) => {
    // Get token from auth service (same as main api client)
    const token = await getAuthToken();

    if (token) {
      if (!config.headers) config.headers = {} as any;
      (config.headers as any).Authorization = `Bearer ${token}`;
    }

    // Development mode fallback
    const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (!token && isDevelopment) {
      const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
      const devUserId = 'dev-local-user';

      if (!config.headers) config.headers = {} as any;
      (config.headers as any)['X-Dev-Secret'] = devSecret;
      (config.headers as any)['X-Dev-User-Id'] = devUserId;
    }

    // Attach organization context for workspace switching
    try {
      const activeOrgId = localStorage.getItem('activeOrganization');
      if (activeOrgId) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any)['X-Organization-ID'] = activeOrgId;
      }
    } catch (error) {
      console.error('[Tasks API] Failed to attach organization ID:', error);
    }

    return config;
  },
  (error) => Promise.reject(error),
);

export const tasksApi = {
  /**
   * List all tasks for the current user
   */
  list: async (): Promise<Task[]> => {
    const response = await tasksClient.get<TaskListResponse>('/api/tasks');
    return response.data.tasks || [];
  },

  /**
   * Get a specific task by ID
   */
  get: async (taskId: string): Promise<Task> => {
    const response = await tasksClient.get<Task>(`/api/tasks/${taskId}`);
    return response.data;
  },

  /**
   * Create a new task
   */
  create: async (data: TaskCreate): Promise<Task> => {
    const response = await tasksClient.post<Task>('/api/tasks', data);
    return response.data;
  },

  /**
   * Update an existing task
   */
  update: async (taskId: string, data: TaskUpdate): Promise<Task> => {
    const response = await tasksClient.put<Task>(`/api/tasks/${taskId}`, data);
    return response.data;
  },

  /**
   * Delete a task
   */
  delete: async (taskId: string): Promise<void> => {
    await tasksClient.delete(`/api/tasks/${taskId}`);
  },

  /**
   * Toggle task status (active <-> paused)
   */
  toggle: async (taskId: string): Promise<Task> => {
    const response = await tasksClient.post<Task>(`/api/tasks/${taskId}/toggle`);
    return response.data;
  },

  /**
   * Manually trigger a task execution
   */
  trigger: async (taskId: string): Promise<TaskExecution> => {
    const response = await tasksClient.post<TaskExecution>(`/api/tasks/${taskId}/trigger`);
    return response.data;
  },

  /**
   * Get execution history for a task
   */
  getExecutions: async (taskId: string, limit: number = 50): Promise<TaskRunHistoryEntry[]> => {
    const response = await tasksClient.get<TaskRunHistoryResponse>(
      `/api/tasks/${taskId}/runs`,
      { params: { limit } },
    );
    return response.data.runs || [];
  },

  /**
   * Alias for getExecutions - Get run history for a task
   */
  getRuns: async (taskId: string, limit: number = 50): Promise<TaskRunHistoryEntry[]> => {
    return tasksApi.getExecutions(taskId, limit);
  },

  /**
   * Validate task canvas structure
   */
  validate: async (canvasData: any): Promise<any> => {
    const response = await tasksClient.post('/api/tasks/validate', {
      canvas_data: canvasData,
    });
    return response.data;
  },

  /**
   * Task assistant chat
   */
  assistant: async (message: string, context: any): Promise<any> => {
    const response = await tasksClient.post('/api/tasks/assistant', {
      message,
      context,
    });
    return response.data;
  },
};

export default tasksApi;
