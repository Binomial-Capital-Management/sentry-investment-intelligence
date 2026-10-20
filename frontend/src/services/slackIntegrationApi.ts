import { tasksClient } from './tasksApi';

export interface SlackWorkspace {
  team_id: string;
  team_name?: string;
  connected_at: string;
}

export interface SlackChannel {
  id: string;
  name: string;
  is_private?: boolean;
}

export const slackIntegrationApi = {
  async getAuthorizeUrl(): Promise<string> {
    const response = await tasksClient.get<{ authorization_url: string }>('/api/slack/authorize');
    return response.data.authorization_url;
  },

  async listWorkspaces(): Promise<SlackWorkspace[]> {
    const response = await tasksClient.get<{ workspaces: SlackWorkspace[] }>('/api/slack/workspaces');
    return response.data.workspaces ?? [];
  },

  async deleteWorkspace(teamId: string): Promise<void> {
    await tasksClient.delete(`/api/slack/workspaces/${teamId}`);
  },

  async listChannels(teamId: string): Promise<SlackChannel[]> {
    const response = await tasksClient.get<{ channels: SlackChannel[] }>('/api/slack/channels', {
      params: { team_id: teamId },
    });
    return response.data.channels ?? [];
  },
};

export default slackIntegrationApi;
