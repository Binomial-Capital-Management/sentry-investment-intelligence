import axios from 'axios';
import { getAuthToken } from './authService';
import { API_BASE } from './api';

// Create axios instance for uploads
const uploadApi = axios.create({
  baseURL: API_BASE,
  // No timeout for uploads - let server handle it
});

// Add auth interceptor using auth service
uploadApi.interceptors.request.use(
  async (config) => {
    try {
      // Get token from auth service (updated by AuthProvider)
      const token = await getAuthToken();

      if (token) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error('[Upload API] Error getting token:', error);
    }
    return config;
  },
  (error) => Promise.reject(error),
);

export interface UploadedFile {
  id: string;
  original_name: string;
  content_type: string;
  size: number;
  created_at: string;
  source?: string;
  drive_file_id?: string;
  drive_mime_type?: string;
}

// File size limits (must match backend)
const MAX_FILE_SIZE = 40 * 1024 * 1024; // 40MB in bytes

function formatFileSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

export const uploadService = {
  /**
   * Upload multiple files
   * Returns array of uploaded file metadata with IDs
   */
  uploadFiles: async (files: File[]): Promise<UploadedFile[]> => {
    // Validate file sizes before uploading
    const oversizedFiles = files.filter(file => file.size > MAX_FILE_SIZE);
    if (oversizedFiles.length > 0) {
      const fileNames = oversizedFiles.map(f => `${f.name} (${formatFileSize(f.size)})`).join(', ');
      throw new Error(
        `File(s) too large: ${fileNames}. Maximum file size is ${formatFileSize(MAX_FILE_SIZE)}.`,
      );
    }

    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await uploadApi.post<{
      status: string;
      files: UploadedFile[];
      count: number;
    }>('/api/uploads/files', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data.files;
  },

  /**
   * Get file metadata
   */
  getFileMetadata: async (fileId: string): Promise<UploadedFile> => {
    const response = await uploadApi.get<UploadedFile>(`/api/uploads/files/${fileId}`);
    return response.data;
  },

  /**
   * Delete a file
   */
  deleteFile: async (fileId: string): Promise<void> => {
    await uploadApi.delete(`/api/uploads/files/${fileId}`);
  },

  /**
   * List user's files
   */
  listFiles: async (limit = 50, offset = 0): Promise<{ files: UploadedFile[]; total: number }> => {
    const response = await uploadApi.get<{
      files: UploadedFile[];
      total: number;
      limit: number;
      offset: number;
    }>('/api/uploads/files', {
      params: { limit, offset },
    });

    return {
      files: response.data.files,
      total: response.data.total,
    };
  },

  downloadFile: async (fileId: string): Promise<File> => {
    const response = await uploadApi.get(`/api/uploads/files/${fileId}/download`, {
      responseType: 'blob',
    });

    const disposition = response.headers['content-disposition'] as string | undefined;
    let filename = 'downloaded-file';
    if (disposition) {
      const match = disposition.match(/filename="?([^";]+)"?/);
      if (match?.[1]) {
        filename = decodeURIComponent(match[1]);
      }
    }

    const type = response.headers['content-type'] as string | undefined;
    return new File([response.data], filename, { type: type || response.data.type || 'application/octet-stream' });
  },
};
