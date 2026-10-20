import axios from 'axios';
import { getAuthToken } from './authService';
import { API_BASE } from './api';
import type { ImportFilters, TransactionImportPreview } from '../components/PostMortem/types';

export async function fetchTransactionPreview(filters: ImportFilters): Promise<TransactionImportPreview> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  try {
    // Get token from auth service
    const token = await getAuthToken();

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    } else {
      // DEVELOPMENT ONLY: Auto-auth when Clerk is not available
      const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (isDevelopment) {
        const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
        const devUserId = 'dev-local-user';

        if (devSecret) {
          headers['X-Dev-Secret'] = devSecret;
          headers['X-Dev-User-Id'] = devUserId;
        }
      }
    }

    // Attach organization context
    const activeOrgId = localStorage.getItem('activeOrganization');
    if (activeOrgId) {
      headers['X-Organization-ID'] = activeOrgId;
    }
  } catch (error) {
    console.error('[PostMortem API] Error getting token:', error);
  }

  const response = await axios.post(`${API_BASE}/api/postmortem/preview`, {
    portfolio_ids: filters.portfolioIds,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    tickers: filters.tickers,
    source: filters.source,
    min_value: filters.minValue,
  }, { headers });

  return response.data;
}

export async function listThreads(postmortemId: string) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  try {
    const token = await getAuthToken();

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    } else {
      const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (isDevelopment) {
        const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
        const devUserId = 'dev-local-user';

        if (devSecret) {
          headers['X-Dev-Secret'] = devSecret;
          headers['X-Dev-User-Id'] = devUserId;
        }
      }
    }

    const activeOrgId = localStorage.getItem('activeOrganization');
    if (activeOrgId) {
      headers['X-Organization-ID'] = activeOrgId;
    }
  } catch (error) {
    console.error('[PostMortem API] Error getting token:', error);
  }

  const response = await axios.get(`${API_BASE}/api/postmortem/${postmortemId}/threads`, { headers });
  return response.data;
}

export async function deleteThread(threadId: string) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  try {
    const token = await getAuthToken();

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    } else {
      const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (isDevelopment) {
        const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
        const devUserId = 'dev-local-user';

        if (devSecret) {
          headers['X-Dev-Secret'] = devSecret;
          headers['X-Dev-User-Id'] = devUserId;
        }
      }
    }

    const activeOrgId = localStorage.getItem('activeOrganization');
    if (activeOrgId) {
      headers['X-Organization-ID'] = activeOrgId;
    }
  } catch (error) {
    console.error('[PostMortem API] Error getting token:', error);
  }

  const response = await axios.delete(`${API_BASE}/api/postmortem/threads/${threadId}`, { headers });
  return response.data;
}

export async function cancelAnalysis(postmortemId: string, threadId?: string) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  try {
    const token = await getAuthToken();

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    } else {
      const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (isDevelopment) {
        const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
        const devUserId = 'dev-local-user';

        if (devSecret) {
          headers['X-Dev-Secret'] = devSecret;
          headers['X-Dev-User-Id'] = devUserId;
        }
      }
    }

    const activeOrgId = localStorage.getItem('activeOrganization');
    if (activeOrgId) {
      headers['X-Organization-ID'] = activeOrgId;
    }
  } catch (error) {
    console.error('[PostMortem API] Error getting token:', error);
  }

  const url = threadId
    ? `${API_BASE}/api/postmortem/${postmortemId}/analyze/cancel?thread_id=${threadId}`
    : `${API_BASE}/api/postmortem/${postmortemId}/analyze/cancel`;

  const response = await axios.post(url, {}, { headers });
  return response.data;
}
