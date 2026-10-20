import axios from 'axios';
import { getAuthToken } from './authService';
import { API_BASE } from './api';

// Create axios instance for insights API
const insightsApi = axios.create({
  baseURL: `${API_BASE}/api/insights`,
  timeout: 300000,  // 5 minutes for agent generation
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth header to all requests using auth service
insightsApi.interceptors.request.use(
  async (config) => {
    try {
      // Get token from auth service (updated by AuthProvider)
      const token = await getAuthToken();

      if (token) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any).Authorization = `Bearer ${token}`;
      } else {
        // DEVELOPMENT ONLY: Auto-auth when Clerk is not available
        const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (isDevelopment) {
          const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
          const devUserId = 'dev-local-user';

          if (!config.headers) config.headers = {} as any;
          (config.headers as any)['X-Dev-Secret'] = devSecret;
          (config.headers as any)['X-Dev-User-Id'] = devUserId;
        }
      }
    } catch (error) {
      console.error('[Insights API] Error getting token:', error);
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response error handling
insightsApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'Unknown error';
    console.error('Insights API error:', message);
    return Promise.reject(new Error(message));
  },
);

// Type definitions matching backend models

export type PageType = 'markets' | 'crypto' | 'macro';

export interface InsightContent {
  text: string;
  data?: Record<string, any>;
  source?: string;
}

export interface Insight {
  id: string;
  user_id: string;
  page_type: PageType;
  title: string;
  content: InsightContent;
  priority: number;  // 1-10 (higher = more important)
  is_read: boolean;
  metadata?: Record<string, any>;
  generated_at: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export interface InsightListResponse {
  insights: Insight[];
  total: number;
  page_type?: PageType;
}

export interface InsightGenerateRequest {
  page_type?: PageType;
  region?: string;
  force_regenerate?: boolean;
}

export interface InsightUpdate {
  is_read?: boolean;
  priority?: number;
}

export interface InsightGenerateResponse {
  status: string;
  user_id: string;
  insights_created: number;
  generated_at?: string;
  errors?: string[];
}

// API Methods

/**
 * Get user's insights with optional filtering
 */
export const getInsights = async (
  pageType?: PageType,
  region?: string,
  unreadOnly: boolean = false,
  limit: number = 6,
): Promise<InsightListResponse> => {
  const params = new URLSearchParams();
  if (pageType) params.append('page_type', pageType);
  if (region) params.append('region', region);
  if (unreadOnly) params.append('unread_only', 'true');
  params.append('limit', limit.toString());

  const response = await insightsApi.get<InsightListResponse>(`?${params.toString()}`);
  return response.data;
};

/**
 * Trigger on-demand insight generation for current user
 */
export const generateInsights = async (
  request: InsightGenerateRequest = {},
): Promise<InsightGenerateResponse> => {
  const response = await insightsApi.post<InsightGenerateResponse>('/generate', request);
  return response.data;
};

/**
 * Mark insight as read
 */
export const markInsightAsRead = async (insightId: string): Promise<Insight> => {
  const response = await insightsApi.patch<Insight>(`/${insightId}`, {
    is_read: true,
  });
  return response.data;
};

/**
 * Update insight (e.g., change priority or read status)
 */
export const updateInsight = async (
  insightId: string,
  updates: InsightUpdate,
): Promise<Insight> => {
  const response = await insightsApi.patch<Insight>(`/${insightId}`, updates);
  return response.data;
};

/**
 * Delete a specific insight
 */
export const deleteInsight = async (insightId: string): Promise<void> => {
  await insightsApi.delete(`/${insightId}`);
};

/**
 * Cleanup expired insights (older than 24 hours)
 */
export const cleanupExpiredInsights = async (): Promise<{ status: string; deleted_count: number }> => {
  const response = await insightsApi.delete<{ status: string; deleted_count: number }>('/cleanup/expired');
  return response.data;
};

export default insightsApi;
