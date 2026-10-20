import { tasksClient } from './tasksApi';

export interface EmailList {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  recipients: string[];
  created_at: string;
  updated_at: string;
}

export interface EmailListCreate {
  name: string;
  description?: string;
  recipients: string[];
}

export interface EmailListUpdate {
  name?: string;
  description?: string;
  recipients?: string[];
}

export const emailListsApi = {
  /**
   * List all email lists for the current user
   */
  async list(): Promise<EmailList[]> {
    const response = await tasksClient.get<EmailList[]>('/api/email-lists');
    return response.data;
  },

  /**
   * Get a specific email list by ID
   */
  async get(id: string): Promise<EmailList> {
    const response = await tasksClient.get<EmailList>(`/api/email-lists/${id}`);
    return response.data;
  },

  /**
   * Create a new email list
   */
  async create(data: EmailListCreate): Promise<EmailList> {
    const response = await tasksClient.post<EmailList>('/api/email-lists', data);
    return response.data;
  },

  /**
   * Update an existing email list
   */
  async update(id: string, data: EmailListUpdate): Promise<EmailList> {
    const response = await tasksClient.put<EmailList>(`/api/email-lists/${id}`, data);
    return response.data;
  },

  /**
   * Delete an email list
   */
  async delete(id: string): Promise<void> {
    await tasksClient.delete(`/api/email-lists/${id}`);
  },
};

export default emailListsApi;
