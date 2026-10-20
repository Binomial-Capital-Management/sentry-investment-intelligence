import axios from 'axios';
import { getAuthToken } from './authService';
import { API_BASE } from './api';

// Create axios instance for user settings API
const userSettingsApi = axios.create({
  baseURL: `${API_BASE}/api/user-settings`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth header to all requests using auth service
userSettingsApi.interceptors.request.use(
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
      console.error('[User Settings API] Error getting token:', error);
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response error handling
userSettingsApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'Unknown error';
    console.error('User Settings API error:', message);
    return Promise.reject(new Error(message));
  },
);

// Export styles types
export interface ExportSettings {
  custom_prompt: string | null;
  theme_id: string | null;
  logo_source: 'themeLogo' | 'custom' | 'none';
  logo_file_id: string | null;
  logo_url: string | null;
  logo_position: string;
  logo_size: string;
  language: string;
  verbosity: 'brief' | 'low' | 'mid' | 'high';
  tone: string;
  audience: string;
}

export interface ExportStyle {
  style_name: string;
  settings: ExportSettings;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

// Export the axios instance for direct use
export { userSettingsApi };

// API methods
export const userSettingsApiService = {
  // List all export styles for the user
  listExportStyles: async (): Promise<ExportStyle[]> => {
    const startTime = Date.now();
    try {
      const response = await userSettingsApi.get('/export-styles');
      const duration = Date.now() - startTime;
      console.log(`[User Settings API] Loaded ${response.data.styles.length} export styles in ${duration}ms`);
      return response.data.styles;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`[User Settings API] Failed to load export styles after ${duration}ms`, error);
      throw error;
    }
  },
};

export default userSettingsApiService;
