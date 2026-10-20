import { tasksClient } from './tasksApi';

export interface TeamsWorkspace {
  tenant_id: string;
  tenant_name?: string;
  connected_at: string;
  connected_user_email?: string;
}

export interface TeamsTeam {
  id: string;
  display_name?: string;
}

export interface TeamsChannel {
  id: string;
  display_name?: string;
  membership_type?: string;
}

export const teamsIntegrationApi = {
  async getAuthorizeUrl(): Promise<string> {
    const response = await tasksClient.get<{ authorization_url: string }>('/api/teams/authorize');
    return response.data.authorization_url;
  },

  async listWorkspaces(): Promise<TeamsWorkspace[]> {
    const response = await tasksClient.get<{ workspaces: TeamsWorkspace[] }>('/api/teams/workspaces');
    return response.data.workspaces ?? [];
  },

  async deleteWorkspace(tenantId: string): Promise<void> {
    await tasksClient.delete(`/api/teams/workspaces/${tenantId}`);
  },

  async listTeams(tenantId: string): Promise<TeamsTeam[]> {
    const response = await tasksClient.get<{ teams: TeamsTeam[] }>('/api/teams/teams', {
      params: { tenant_id: tenantId },
    });
    return response.data.teams ?? [];
  },

  async listChannels(tenantId: string, teamId: string): Promise<TeamsChannel[]> {
    const response = await tasksClient.get<{ channels: TeamsChannel[] }>('/api/teams/channels', {
      params: { tenant_id: tenantId, team_id: teamId },
    });
    return response.data.channels ?? [];
  },
};

export default teamsIntegrationApi;
