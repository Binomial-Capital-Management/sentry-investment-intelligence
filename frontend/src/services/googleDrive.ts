import api from './api';

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime?: string;
  size?: string;
  iconLink?: string;
  webViewLink?: string;
}

export interface DriveStatus {
  enabled: boolean;
  connected: boolean;
  credential?: {
    id: string;
    drive_user_id: string;
    drive_email: string;
    updated_at: string;
  };
}

export interface DriveListResponse {
  files: DriveFile[];
  next_page_token?: string | null;
}

export interface DriveImportResponse {
  status: string;
  file: {
    id: string;
    original_name: string;
    content_type: string;
    size: number;
    created_at: string;
    source?: string;
    drive_file_id?: string;
    drive_mime_type?: string;
  };
}

export interface DriveDownloadResponse {
  blob: Blob;
  filename: string;
  contentType: string;
  driveMimeType?: string;
}

const googleDriveService = {
  async getStatus(): Promise<DriveStatus> {
    const response = await api.get('/api/integrations/google-drive/status');
    return response.data;
  },

  async listFiles(params?: { query?: string; pageToken?: string; pageSize?: number }): Promise<DriveListResponse> {
    const response = await api.get('/api/integrations/google-drive/files', {
      params: {
        query: params?.query,
        page_token: params?.pageToken,
        page_size: params?.pageSize,
      },
    });
    return response.data;
  },

  async importFile(fileId: string, exportMimeType?: string): Promise<DriveImportResponse> {
    const response = await api.post('/api/integrations/google-drive/import', {
      file_id: fileId,
      export_mime_type: exportMimeType,
    });
    return response.data;
  },

  async downloadFile(fileId: string, exportMimeType?: string): Promise<DriveDownloadResponse> {
    const response = await api.get(`/api/integrations/google-drive/files/${fileId}/download`, {
      params: {
        export_mime_type: exportMimeType,
      },
      responseType: 'blob',
    });

    const disposition = response.headers['content-disposition'] as string | undefined;
    let filename = response.headers['x-filename'] as string | undefined;

    if (!filename && disposition) {
      const match = disposition.match(/filename="?([^";]+)"?/);
      if (match?.[1]) {
        filename = decodeURIComponent(match[1]);
      }
    }

    return {
      blob: response.data,
      filename: filename || 'drive-file',
      contentType: response.headers['content-type'] as string,
      driveMimeType: response.headers['x-drive-mime-type'] as string | undefined,
    };
  },

  async startAuthorization(): Promise<{ authorization_url: string; state: string }> {
    const response = await api.post('/api/integrations/google-drive/authorize');
    return response.data;
  },

  async disconnect(): Promise<void> {
    await api.post('/api/integrations/google-drive/disconnect');
  },
};

export default googleDriveService;
