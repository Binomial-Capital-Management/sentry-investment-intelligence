import api from './api';

export interface OneDriveFile {
  id: string;
  name: string;
  mimeType?: string;
  modifiedTime?: string;
  size?: number;
  driveId?: string;
  webUrl?: string;
  isFolder?: boolean;
}

export interface OneDriveStatus {
  enabled: boolean;
  connected: boolean;
  credential?: {
    id: string;
    drive_user_id: string;
    drive_email?: string | null;
    updated_at: string;
  };
}

export interface OneDriveListResponse {
  files: OneDriveFile[];
  next_page_token?: string | null;
}

export interface OneDriveImportResponse {
  status: string;
  file: {
    id: string;
    original_name: string;
    content_type: string;
    size: number;
    created_at: string;
    source?: string;
    onedrive_item_id?: string;
    onedrive_drive_id?: string;
  };
}

export interface OneDriveDownloadResponse {
  blob: Blob;
  filename: string;
  contentType: string;
  driveMimeType?: string;
}

export interface OneDrivePickerTokenResponse {
  access_token: string;
  expires_in?: number;
  expires_at?: string;
  tenant_id?: string;
  picker_origin?: string;
  picker_url?: string;
  scope?: string;
  drive?: {
    id?: string;
    sharepoint_site_id?: string;
    sharepoint_list_id?: string;
    sharepoint_web_id?: string;
  };
}

const onedriveService = {
  async getStatus(): Promise<OneDriveStatus> {
    const response = await api.get('/api/integrations/onedrive/status');
    return response.data;
  },

  async startAuthorization(): Promise<{ authorization_url: string; state: string }> {
    const response = await api.post('/api/integrations/onedrive/authorize');
    return response.data;
  },

  async listFiles(params?: { query?: string; pageToken?: string; pageSize?: number }): Promise<OneDriveListResponse> {
    const response = await api.get('/api/integrations/onedrive/files', {
      params: {
        query: params?.query,
        page_token: params?.pageToken,
        page_size: params?.pageSize,
      },
    });
    return response.data;
  },

  async importFile(fileId: string): Promise<OneDriveImportResponse> {
    const response = await api.post('/api/integrations/onedrive/import', { file_id: fileId });
    return response.data;
  },

  async downloadFile(fileId: string): Promise<OneDriveDownloadResponse> {
    const response = await api.get(`/api/integrations/onedrive/files/${fileId}/download`, {
      responseType: 'blob',
    });

    const disposition = response.headers['content-disposition'] as string | undefined;
    let filename: string | undefined;

    if (disposition) {
      const match = disposition.match(/filename="?([^";]+)"?/);
      if (match?.[1]) {
        filename = decodeURIComponent(match[1]);
      }
    }

    return {
      blob: response.data,
      filename: filename || 'onedrive-file',
      contentType: response.headers['content-type'] as string,
      driveMimeType: response.headers['x-onedrive-mime-type'] as string | undefined,
    };
  },

  async disconnect(): Promise<void> {
    await api.post('/api/integrations/onedrive/disconnect');
  },

  async getPickerToken(accountType?: 'personal' | 'business' | 'sharepoint'): Promise<OneDrivePickerTokenResponse> {
    const response = await api.get('/api/integrations/onedrive/picker/token', {
      params: accountType ? { account_type: accountType } : undefined,
    });
    return response.data;
  },
};

export default onedriveService;
