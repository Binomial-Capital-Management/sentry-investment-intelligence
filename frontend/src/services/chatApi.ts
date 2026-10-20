import axios from 'axios';
import { getAuthToken } from './authService';
import { chatAPI, API_BASE } from './api';

// Create axios instance for chat API
const chatApi = axios.create({
  baseURL: `${API_BASE}/api/chats`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth header to all requests using auth service
chatApi.interceptors.request.use(
  async (config) => {
    try {
      // Get token from auth service (updated by AuthProvider)
      const token = await getAuthToken();

      console.log('[Chat API Interceptor] Token status:', token ? 'Token available' : 'No token');

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
        if (!window.sessionStorage.getItem('chat-dev-auth-warned')) {
          console.warn('⚠️ CHAT API DEV MODE: Using automatic dev authentication');
          window.sessionStorage.setItem('chat-dev-auth-warned', 'true');
        }
      }
      if (token) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error('[Chat API] Error getting token:', error);
    }

    // Attach session_id if present for v6 continuity (same as api.ts)
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
      console.error('[Chat API] Failed to attach organization ID:', error);
    }

    return config;
  },
  (error) => Promise.reject(error),
);

// Response error handling
chatApi.interceptors.response.use(
  (response) => {
    // Persist session_id if backend returns it (same as api.ts)
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
            return chatApi(originalConfig);
          }
        } catch (e) {
          console.warn('Retry after 401 failed to get token:', e);
        }
        throw error;
      })();
    }

    const message = error.response?.data?.detail || error.message || 'Unknown error';
    console.error('Chat API error:', message);
    return Promise.reject(new Error(message));
  },
);

// Chat session types
export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  portfolio_id?: string;
}

export interface ChatMessageResponse {
  response: string;
  sources?: any;
  charts?: any;
  metrics?: any;
  timestamp: string;
  session_id: string;
  message_id: string;
}

// API methods
export const chatApiService = {
  // List all chat sessions for the user
  listSessions: async (): Promise<ChatSession[]> => {
    const response = await chatApi.get('');
    return response.data;
  },

  // Create a new chat session
  createSession: async (title?: string): Promise<ChatSession> => {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    try {
      const response = await chatApi.post('', { title: title || 'New Chat' });
      return response.data;
    } catch (err) {
      if (isLocal) {
        // Fallback: create a local session client-side (development only)
        const id = `web_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;
        const now = new Date().toISOString();
        return { id, title: title || 'New Chat', created_at: now, updated_at: now };
      }
      // In production, throw the error to surface backend issues
      throw err;
    }
  },

  // Update a chat session (e.g., title)
  updateSession: async (sessionId: string, title: string): Promise<ChatSession> => {
    const response = await chatApi.patch(`/${sessionId}`, { title });
    return response.data;
  },

  // Delete a chat session
  deleteSession: async (sessionId: string): Promise<void> => {
    await chatApi.delete(`/${sessionId}`);
  },

  // Bulk delete multiple chat sessions
  bulkDeleteSessions: async (sessionIds: string[]): Promise<{ deleted_count: number }> => {
    const response = await chatApi.post('/bulk-delete', { session_ids: sessionIds });
    return response.data;
  },

  // Get messages for a session (from SQLite store)
  getMessages: async (sessionId: string): Promise<{ messages: any[] }> => {
    const response = await chatApi.get(`/${sessionId}/messages`);
    return response.data;
  },

  // Send a message to a session
  sendMessage: async (
    sessionId: string,
    message: string,
    portfolioId?: string,
    agentMode?: string,
  ): Promise<ChatMessageResponse> => {
    try {
      const response = await chatApi.post(`/${sessionId}/messages`, {
        message,
        portfolio_id: portfolioId,
        agent_mode: agentMode,
      });
      return response.data;
    } catch {
      // Fallback to v6 chat endpoint directly
      const v6 = await chatAPI.sendMessage({
        message,
        agent_mode: agentMode,
        portfolio_id: portfolioId,
        history: [],
        session_id: sessionId,
      } as any);
      return {
        response: v6.response,
        sources: v6.sources,
        charts: v6.charts,
        metrics: (v6 as any).metrics,
        timestamp: new Date().toISOString(),
        session_id: v6.session_id || sessionId,
        message_id: (v6 as any).message_id || Math.random().toString(36).slice(2),
      } as any;
    }
  },
};

export default chatApiService;
