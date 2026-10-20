import axios from 'axios';
import { getAuthToken } from './authService';
import { API_BASE } from './api';

// Create axios instance for organization API
const organizationApi = axios.create({
  baseURL: `${API_BASE}/api/organizations`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth header and organization context to all requests
organizationApi.interceptors.request.use(
  async (config) => {
    try {
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
      console.error('[Organization API] Error getting token:', error);
    }

    // Attach organization context for workspace switching
    try {
      const activeOrgId = localStorage.getItem('activeOrganization');
      if (activeOrgId) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any)['X-Organization-ID'] = activeOrgId;
      }
    } catch (error) {
      console.error('[Organization API] Error attaching organization ID:', error);
    }

    return config;
  },
  (error) => Promise.reject(error),
);

// Response error handling
organizationApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const message = error.response?.data?.detail || error.message || 'Unknown error';

    // Clear stale org context on 403 (not a member) or 404 (org not found)
    if (status === 403 || status === 404) {
      const currentOrgId = localStorage.getItem('activeOrganization');
      if (currentOrgId && message.toLowerCase().includes('member')) {
        console.warn('[Organization API] Clearing stale org context due to access error');
        localStorage.removeItem('activeOrganization');
      }
    }

    console.error('Organization API error:', message);
    return Promise.reject(new Error(message));
  },
);

// Organization types
export interface Organization {
  id: string;
  name: string;
  slug: string;
  usage_credits: number;
  created_at: string;
  creator_id?: string | null;  // User ID of org creator (null if creator was deleted)
}

export interface OrganizationMember {
  user_id: string;
  email: string | null;
  name: string | null;
  role: string;
  joined_at: string;
}

export interface CreateOrganizationRequest {
  name: string;
  slug: string;
  industry?: string;
  id?: string;
}

export interface UpdateOrganizationRequest {
  name?: string;
  industry?: string;
}

export interface AddMemberRequest {
  user_id: string;
  role: 'org:admin' | 'org:member';
}

export interface UpdateMemberRoleRequest {
  role: 'org:admin' | 'org:member';
}

export interface InviteMemberRequest {
  email: string;
  role: 'org:admin' | 'org:member';
}

export interface Invitation {
  id: string;
  email_address: string;
  role: string;
  status: string;
  created_at: string;
}

// Organization API service
export const organizationApiService = {
  // Get all organizations for current user
  async getMyOrganizations(): Promise<Organization[]> {
    const response = await organizationApi.get('/my-organizations');
    return response.data;
  },

  // Get organization by ID
  async getOrganization(orgId: string): Promise<Organization> {
    const response = await organizationApi.get(`/${orgId}`);
    return response.data;
  },

  // Create new organization
  async createOrganization(data: CreateOrganizationRequest): Promise<Organization> {
    const response = await organizationApi.post('', data);
    return response.data;
  },

  // Update organization
  async updateOrganization(orgId: string, data: UpdateOrganizationRequest): Promise<{ success: boolean; message: string }> {
    const response = await organizationApi.put(`/${orgId}`, data);
    return response.data;
  },

  // Delete organization
  async deleteOrganization(orgId: string): Promise<{ success: boolean; message: string }> {
    const response = await organizationApi.delete(`/${orgId}`);
    return response.data;
  },

  // Get organization members
  async getMembers(orgId: string): Promise<OrganizationMember[]> {
    const response = await organizationApi.get(`/${orgId}/members`);
    return response.data;
  },

  // Add member to organization
  async addMember(orgId: string, data: AddMemberRequest): Promise<{ success: boolean; message: string }> {
    const response = await organizationApi.post(`/${orgId}/members`, data);
    return response.data;
  },

  // Remove member from organization
  async removeMember(orgId: string, userId: string): Promise<{ success: boolean; message: string }> {
    const response = await organizationApi.delete(`/${orgId}/members/${userId}`);
    return response.data;
  },

  // Check if slug is available
  async checkSlugAvailability(slug: string): Promise<{ available: boolean; slug: string; message?: string }> {
    const response = await organizationApi.get(`/check-slug/${slug}`);
    return response.data;
  },

  // Update member role
  async updateMemberRole(orgId: string, userId: string, data: UpdateMemberRoleRequest): Promise<OrganizationMember> {
    const response = await organizationApi.put(`/${orgId}/members/${userId}/role`, data);
    return response.data;
  },

  // Leave organization (self-removal)
  async leaveOrganization(orgId: string): Promise<{ success: boolean; message: string }> {
    const response = await organizationApi.post(`/${orgId}/leave`);
    return response.data;
  },

  // Invite member by email
  async inviteMember(orgId: string, data: InviteMemberRequest): Promise<Invitation> {
    const response = await organizationApi.post(`/${orgId}/invite`, data);
    return response.data;
  },

  // List invitations
  async listInvitations(orgId: string, status?: string): Promise<Invitation[]> {
    const params = status ? { status } : {};
    const response = await organizationApi.get(`/${orgId}/invitations`, { params });
    return response.data;
  },

  // Revoke invitation
  async revokeInvitation(orgId: string, invitationId: string): Promise<{ success: boolean; message: string }> {
    const response = await organizationApi.delete(`/${orgId}/invitations/${invitationId}`);
    return response.data;
  },

  // Resend invitation
  async resendInvitation(orgId: string, invitationId: string): Promise<Invitation> {
    const response = await organizationApi.post(`/${orgId}/invitations/${invitationId}/resend`);
    return response.data;
  },
};
