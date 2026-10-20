import axios from 'axios';
import type { ChatRequest, ChatResponse, ClassifyResponse } from '@/types';
import { pickContent, pickSources, pickCharts, pickMetrics } from '@utils/alias';
import { getAuthToken } from './authService';

// Environment-driven configuration
// In production, must point to the actual backend URL
// Check both VITE_API_BASE and VITE_API_BASE_URL for compatibility
export const API_BASE = (import.meta as any).env?.VITE_API_BASE ||
  (import.meta as any).env?.VITE_API_BASE_URL ||
  (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');
const API_TIMEOUT_MS: number = Number((import.meta as any).env?.VITE_API_TIMEOUT_MS ?? 600000); // 10 minutes for PDF/PowerPoint generation
const BACKEND_VERSION = (import.meta as any).env?.VITE_BACKEND_VERSION || 'v6';

console.log('API Configuration:', { API_BASE, BACKEND_VERSION });

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_BASE,
  timeout: API_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  async (config) => {
    // Add Clerk authentication token
    try {
      // Get token from auth service (which is updated by AuthProvider)
      const token: string | null = await getAuthToken();

      console.log('[API Interceptor] Token status:', token ? 'Token available' : 'No token');

      // DEVELOPMENT ONLY: Auto-auth when Clerk is not available
      // WARNING: This is insecure and should NEVER be used in production
      const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (!token && isDevelopment) {
        // Auto-use dev authentication in development mode
        const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
        const devUserId = 'dev-local-user';

        // Use dev authentication headers
        if (!config.headers) config.headers = {} as any;
        (config.headers as any)['X-Dev-Secret'] = devSecret;
        (config.headers as any)['X-Dev-User-Id'] = devUserId;

        // Only show warning once per session
        if (!window.sessionStorage.getItem('dev-auth-warned')) {
          console.warn('⚠️ DEV MODE: Using automatic dev authentication');
          window.sessionStorage.setItem('dev-auth-warned', 'true');
        }
      }
      if (token) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error('Failed to attach auth token:', error);
    }

    // Attach session_id if present for v6 continuity
    try {
      const sid = localStorage.getItem('session_id');
      const isUuid = (v: string) =>
        /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(v || '');
      if (sid && isUuid(sid)) {
        if (!config.headers) config.headers = {} as any;
        // Also inject into body when JSON
        if (config.data && typeof config.data === 'object') {
          (config.data as any).session_id = (config.data as any).session_id || sid;
        }
        (config.headers as any)['X-Session-Id'] = sid;
      }
    } catch (error) {
      console.error('Failed to attach session ID:', error);
    }

    // Attach organization context for workspace switching
    try {
      const activeOrgId = localStorage.getItem('activeOrganization');
      if (activeOrgId) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any)['X-Organization-ID'] = activeOrgId;
      }
    } catch (error) {
      console.error('Failed to attach organization ID:', error);
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    // Persist session_id if backend returns it
    try {
      const sid = (response.data && response.data.session_id) || (response.headers && (response.headers['x-session-id'] as string));
      if (sid) localStorage.setItem('session_id', sid);
    } catch (error) {
      console.error('Failed to persist session ID:', error);
    }
    return response;
  },
  (error) => {
    const status = error.response?.status;
    const authEnabled =
      (import.meta as any).env?.VITE_ENABLE_AUTH === 'true' &&
      !!(import.meta as any).env?.VITE_CLERK_PUBLISHABLE_KEY &&
      !!(window as any).Clerk;

    if (status === 401 && authEnabled && !(error.config as any)?._retry) {
      return (async () => {
        try {
          const originalConfig: any = error.config || {};
          originalConfig._retry = true;
          const { getAuthToken } = await import('./authService');
          const token = await Promise.race([
            getAuthToken(),
            new Promise<string | null>((resolve) => setTimeout(() => resolve(null), 2000)),
          ]);
          if (token) {
            originalConfig.headers = originalConfig.headers || {};
            originalConfig.headers.Authorization = `Bearer ${token}`;
            return api(originalConfig);
          }
        } catch (e) {
          console.warn('Retry after 401 failed to get token:', e);
        }
        throw error;
      })();
    }

    // Clear stale org context on 403 (not a member) errors
    if (status === 403) {
      const currentOrgId = localStorage.getItem('activeOrganization');
      const errorDetail = error.response?.data?.detail || '';
      if (currentOrgId && (errorDetail.toLowerCase().includes('member') || errorDetail.toLowerCase().includes('organization'))) {
        console.warn('[API] Clearing stale org context due to 403 org access error');
        localStorage.removeItem('activeOrganization');
      }
    }

    // Normalize error shape
    const data = error.response?.data;
    const firstArrMsg = Array.isArray(data?.errors) && data.errors.length > 0 ? (data.errors[0].msg || data.errors[0].message) : undefined;
    // Handle detail as object (backend returns {detail: {message: "...", errors: []}})
    let message: string;
    if (data?.detail && typeof data.detail === 'object') {
      message = data.detail.message || data.detail.error || 'Unknown error';
    } else {
      message = (data?.detail || data?.message || data?.error || firstArrMsg || error.message || 'Unknown error') as string;
    }
    const normalized = { message, status, raw: data };
    console.error('API error:', normalized);
    return Promise.reject(new Error(message));
  },
);

// API methods
export const chatAPI = {
  sendMessage: async (data: ChatRequest): Promise<ChatResponse> => {
    // Be tolerant to field name variations
    // Use V6 endpoint if available (it properly handles conversation history)
    const endpoint = (import.meta as any).env?.VITE_USE_V6 === 'true' || BACKEND_VERSION === 'v6' ? '/v6/chat' : '/chat';
    const response = await api.post(endpoint, data);
    const d: unknown = response.data || {};
    return {
      response: pickContent(d),
      sources: pickSources(d),
      charts: pickCharts(d),
      metrics: pickMetrics(d),
      error: (d as any)?.error,
      session_id: (d as any)?.session_id,
      reasoning: (d as any)?.reasoning,
      version: (d as any)?.version || BACKEND_VERSION,
    };
  },
  transform: async (payload: { operation?: string; message_id?: string; session_id?: string; options?: any }): Promise<ChatResponse> => {
    const endpoint = (import.meta as any).env?.VITE_USE_V6 === 'true' || BACKEND_VERSION === 'v6' ? '/v6/transform' : '/transform';
    const response = await api.post(endpoint, payload);
    return response.data as ChatResponse;
  },

  classifyIntent: async (message: string): Promise<ClassifyResponse> => {
    const endpoint = (import.meta as any).env?.VITE_USE_V6 === 'true' || BACKEND_VERSION === 'v6' ? '/v6/classify' : '/classify';
    const response = await api.post<any>(endpoint, { message });
    const d = response.data || {};
    // Support v6 classify { type } or legacy shape
    if (typeof d.type === 'string') {
      const intent = d.type === 'calculation' ? 'calculation' : d.type === 'search' ? 'information' : 'simple';
      return { needs_calculation: d.type === 'calculation', intent, confidence: 0.9 };
    }
    return {
      needs_calculation: !!d.needs_calculation,
      intent: d.intent || 'information',
      confidence: typeof d.confidence === 'number' ? d.confidence : 0.9,
    };
  },

  exportAnalysis: async (format: string, threadId?: string) => {
    const endpoint = (import.meta as any).env?.VITE_USE_V6 === 'true' || BACKEND_VERSION === 'v6' ? '/v6/export' : '/export';
    const response = await api.post(endpoint,
      { format, thread_id: threadId },
      { responseType: 'blob' },
    );
    return response.data;
  },
  exportPdf: async (payload: any, exportType: string = 'free', styleName?: string): Promise<Blob> => {
    const endpoint = '/v6/export/pdf';
    const params = new URLSearchParams({ export_type: exportType });
    if (styleName) {
      params.append('style_name', styleName);
    }
    const response = await api.post(`${endpoint}?${params}`, payload, {
      responseType: 'blob',
      timeout: 600000, // 10 minutes for Gamma PDF generation
    });
    return response.data as Blob;
  },
  exportPowerpoint: async (payload: any, exportType: string = 'gamma_pptx', styleName?: string): Promise<Blob> => {
    const endpoint = '/v6/export/pdf';  // Same endpoint, different export_type
    const params = new URLSearchParams({ export_type: exportType });
    if (styleName) {
      params.append('style_name', styleName);
    }
    const response = await api.post(`${endpoint}?${params}`, payload, {
      responseType: 'blob',
      timeout: 600000, // 10 minutes for Gamma PPTX generation
    });
    return response.data as Blob;
  },
  exportWorkbook: async (payload: any): Promise<Blob> => {
    const endpoint = '/v6/export/workbook';
    const response = await api.post(endpoint, payload, {
      responseType: 'blob',
      timeout: 600000, // 10 minutes (consistent with PDF/PowerPoint)
    });
    return response.data as Blob;
  },
  cancelStream: async (sessionId: string): Promise<void> => {
    if (!sessionId) return;
    try {
      const params = new URLSearchParams({ session_id: sessionId });
      const token = await getAuthToken();
      const headers: Record<string, string> = {};
      
      // Use headers for auth (not query params) to avoid logging tokens
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      } else {
        const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
        const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (isLocal && devSecret) {
          headers['X-Dev-Secret'] = devSecret;
          headers['X-Dev-User-Id'] = 'dev-local-user';
        }
      }
      
      await fetch(`${API_BASE}/v6/chat/cancel?${params.toString()}`, {
        method: 'POST',
        headers: Object.keys(headers).length ? headers : undefined,
        keepalive: true,
      });
    } catch (error) {
      console.warn('[chatAPI] Failed to cancel stream:', error);
    }
  },
};

// Workflow API methods
export const workflowApi = {
  create: async (data: any) => {
    const response = await api.post('/api/workflows', data);
    return response.data;
  },
  list: async (minimal = true) => {
    const response = await api.get(`/api/workflows?minimal=${minimal}`);
    return response.data;
  },
  get: async (id: string) => {
    const response = await api.get(`/api/workflows/${id}`);
    return response.data;
  },
  update: async (id: string, data: any) => {
    const response = await api.put(`/api/workflows/${id}`, data);
    return response.data;
  },
  delete: async (id: string) => {
    const response = await api.delete(`/api/workflows/${id}`);
    return response.data;
  },
  validate: async (data: any) => {
    const response = await api.post('/api/workflows/validate', data);
    return response.data;
  },
  validateExisting: async (id: string) => {
    const response = await api.post(`/api/workflows/${id}/validate`);
    return response.data;
  },
  run: async (id: string) => {
    const response = await api.post(`/api/workflows/${id}/run`);
    return response.data;
  },
  getRunStatus: async (runId: string) => {
    const response = await api.get(`/api/workflows/workflow-runs/${runId}`);
    return response.data;
  },
  // PR3b: Run history methods
  listRuns: async (workflowId: string, limit = 20) => {
    const response = await api.get(`/api/workflows/${workflowId}/runs?limit=${limit}`);
    return response.data;
  },
  rerun: async (workflowId: string) => {
    const response = await api.post(`/api/workflows/${workflowId}/run`);
    return response.data;
  },
  deleteRun: async (runId: string) => {
    const response = await api.delete(`/api/workflows/workflow-runs/${runId}`);
    return response.data;
  },
};

export default api;
