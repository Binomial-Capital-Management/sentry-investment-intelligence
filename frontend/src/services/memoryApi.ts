import axios from 'axios';
import { getAuthToken } from './authService';
import { API_BASE } from './api';
import type { MemoryNote, MemoryNoteCreate, MemoryNoteUpdate, MemoryNotebook, ContextTokenStats } from '@/types/memory';

// Create axios instance for memory API
const memoryApi = axios.create({
  baseURL: `${API_BASE}/api/memory`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth header to all requests
memoryApi.interceptors.request.use(
  async (config) => {
    try {
      const token = await getAuthToken();
      
      const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (!token && isDevelopment) {
        const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
        const devUserId = 'dev-local-user';
        if (!config.headers) config.headers = {} as any;
        (config.headers as any)['X-Dev-Secret'] = devSecret;
        (config.headers as any)['X-Dev-User-Id'] = devUserId;
      }
      if (token) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error('[Memory API] Error getting token:', error);
    }

    // Attach organization context
    try {
      const activeOrgId = localStorage.getItem('activeOrganization');
      if (activeOrgId) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any)['X-Organization-ID'] = activeOrgId;
      }
    } catch (error) {
      console.error('[Memory API] Failed to attach organization ID:', error);
    }

    return config;
  },
  (error) => Promise.reject(error),
);

/**
 * Memory Notebook API Service
 */
const memoryApiService = {
  /**
   * Get all memory notes for a session
   */
  async getNotes(sessionId: string): Promise<MemoryNotebook> {
    const response = await memoryApi.get<MemoryNotebook>(`/${sessionId}`);
    return response.data;
  },

  /**
   * Create a new memory note
   */
  async createNote(sessionId: string, payload: MemoryNoteCreate): Promise<MemoryNote> {
    const response = await memoryApi.post<MemoryNote>(`/${sessionId}`, {
      ...payload,
      session_id: sessionId,
    });
    return response.data;
  },

  /**
   * Update an existing memory note
   */
  async updateNote(sessionId: string, noteId: string, payload: MemoryNoteUpdate): Promise<MemoryNote> {
    const response = await memoryApi.patch<MemoryNote>(`/${sessionId}/notes/${noteId}`, payload);
    return response.data;
  },

  /**
   * Delete a memory note
   */
  async deleteNote(sessionId: string, noteId: string): Promise<void> {
    await memoryApi.delete(`/${sessionId}/notes/${noteId}`);
  },

  /**
   * Clear all notes for a session
   */
  async clearNotes(sessionId: string): Promise<void> {
    await memoryApi.delete(`/${sessionId}`);
  },

  /**
   * Get token stats for a session
   */
  async getTokenStats(sessionId: string, modelName: string = 'gpt-6.1-sol'): Promise<ContextTokenStats> {
    const response = await memoryApi.get<ContextTokenStats>(`/${sessionId}/stats`, {
      params: { model: modelName },
    });
    return response.data;
  },

  /**
   * Pin a message excerpt to memory
   */
  async pinMessageExcerpt(
    sessionId: string,
    messageId: string,
    excerptStart: number,
    excerptEnd: number,
    section: string = 'context',
  ): Promise<MemoryNote> {
    const response = await memoryApi.post<MemoryNote>(`/${sessionId}/excerpt`, {
      message_id: messageId,
      excerpt_start: excerptStart,
      excerpt_end: excerptEnd,
      section,
    });
    return response.data;
  },

  /**
   * Pin an uploaded file to memory with full content extraction.
   * 
   * For PDFs:
   * - Auto-detects page count to choose extraction method
   * - Long PDFs (4+ pages) use text extraction (full document)
   * - Short PDFs (1-3 pages) use Vision (higher quality)
   * - Override with extractionMode='text' for long documents
   * 
   * @param sessionId - Chat session ID
   * @param fileId - Uploaded file ID
   * @param options - Optional extraction settings
   * @param options.extractionMode - 'text' forces full text extraction, 'vision' forces GPT-5 Vision
   * @param options.index - Whether to chunk and index for semantic retrieval (default: true)
   */
  async pinFileToMemory(
    sessionId: string,
    fileId: string,
    options?: {
      extractionMode?: 'text' | 'vision';
      index?: boolean;
    }
  ): Promise<MemoryNote> {
    const response = await memoryApi.post<MemoryNote>(`/${sessionId}/pin-file`, {
      file_id: fileId,
      extraction_mode: options?.extractionMode,
      index: options?.index ?? true,
    });
    return response.data;
  },

  /**
   * Pin a cloud file (Google Drive or OneDrive) to memory with full content extraction.
   * 
   * This method imports the file from the cloud provider, extracts its content,
   * and creates a memory note that will be available for context in the chat.
   * 
   * @param sessionId - Chat session ID
   * @param source - Cloud provider: 'google_drive' or 'onedrive'
   * @param cloudFileId - File ID from the cloud provider
   * @param options - Optional extraction settings
   * @param options.extractionMode - 'text' forces full text extraction, 'vision' forces GPT-5 Vision
   * @param options.index - Whether to chunk and index for semantic retrieval (default: true)
   */
  async pinCloudFileToMemory(
    sessionId: string,
    source: 'google_drive' | 'onedrive',
    cloudFileId: string,
    options?: {
      extractionMode?: 'text' | 'vision';
      index?: boolean;
    }
  ): Promise<MemoryNote> {
    const response = await memoryApi.post<MemoryNote>(`/${sessionId}/pin-cloud-file`, {
      source,
      cloud_file_id: cloudFileId,
      extraction_mode: options?.extractionMode,
      index: options?.index ?? true,
    });
    return response.data;
  },

  /**
   * Pin an SEC filing to memory with full content extraction and indexing.
   * 
   * Fetches the SEC filing content, extracts text, chunks it, and embeds
   * for semantic retrieval at query time. This is the proper way to add
   * SEC filings since they're too long for direct context injection.
   * 
   * @param sessionId - Chat session ID
   * @param filing - SEC filing details
   * @param options.index - Whether to chunk and index for semantic retrieval (default: true)
   */
  async pinSECFilingToMemory(
    sessionId: string,
    filing: {
      link: string;
      title: string;
      formType?: string;
      filingDate?: string;
      cik?: string;
      accessionNumber?: string;
      ticker?: string;
    },
    options?: {
      index?: boolean;
    }
  ): Promise<MemoryNote> {
    const response = await memoryApi.post<MemoryNote>(`/${sessionId}/pin-sec-filing`, {
      link: filing.link,
      title: filing.title,
      form_type: filing.formType,
      filing_date: filing.filingDate,
      cik: filing.cik,
      accession_number: filing.accessionNumber,
      ticker: filing.ticker,
      index: options?.index ?? true,
    });
    return response.data;
  },

  async pin13FFilingToMemory(
    sessionId: string,
    filing: {
      title: string;
      institutionName: string;
      cik: string;
      year: number;
      quarter: number;
      totalValue: number;
      holdingsCount: number;
      holdings: Array<{
        symbol: string;
        securityName: string;
        shares: number;
        value: number;
        weight: number;
      }>;
      secLink?: string;
    },
    options?: {
      index?: boolean;
    }
  ): Promise<MemoryNote> {
    const response = await memoryApi.post<MemoryNote>(`/${sessionId}/pin-13f-filing`, {
      title: filing.title,
      institution_name: filing.institutionName,
      cik: filing.cik,
      year: filing.year,
      quarter: filing.quarter,
      total_value: filing.totalValue,
      holdings_count: filing.holdingsCount,
      holdings: filing.holdings,
      sec_link: filing.secLink,
      index: options?.index ?? true,
    });
    return response.data;
  },

  async pinTranscriptToMemory(
    sessionId: string,
    transcript: {
      ticker: string;
      year: number;
      quarter: number;
      title?: string;
    },
    options?: {
      index?: boolean;
    }
  ): Promise<MemoryNote> {
    const response = await memoryApi.post<MemoryNote>(`/${sessionId}/pin-transcript`, {
      ticker: transcript.ticker,
      year: transcript.year,
      quarter: transcript.quarter,
      title: transcript.title,
      index: options?.index ?? true,
    });
    return response.data;
  },
};

export default memoryApiService;

