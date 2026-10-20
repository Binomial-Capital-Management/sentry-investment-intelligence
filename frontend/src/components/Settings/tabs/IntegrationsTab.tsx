import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ExternalLink, RefreshCw } from 'lucide-react';
import onedriveService, { OneDriveStatus } from '../../../services/onedrive';
import googleDriveService, { DriveStatus } from '../../../services/googleDrive';
import slackIntegrationApi, { SlackWorkspace } from '../../../services/slackIntegrationApi';
import teamsIntegrationApi, { TeamsWorkspace } from '../../../services/teamsIntegrationApi';
import { getIBKRStatus, disconnectIBKR, BrokerConnectionStatus } from '../../../services/brokerService';

type SubTab = 'connectors' | 'ai-models';

const IntegrationsTab = () => {
  const navigate = useNavigate();
  const [subTab, setSubTab] = useState<SubTab>('connectors');
  const [oneDriveStatus, setOneDriveStatus] = useState<OneDriveStatus | null>(null);
  const [googleDriveStatus, setGoogleDriveStatus] = useState<DriveStatus | null>(null);
  const [slackWorkspaces, setSlackWorkspaces] = useState<SlackWorkspace[]>([]);
  const [teamsWorkspaces, setTeamsWorkspaces] = useState<TeamsWorkspace[]>([]);
  const [ibkrStatus, setIbkrStatus] = useState<BrokerConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchStatuses = async () => {
    try {
      // Fetch each status individually with proper error logging
      let oneDrive: OneDriveStatus = { enabled: false, connected: false };
      let googleDrive: DriveStatus = { enabled: false, connected: false };
      let slack: SlackWorkspace[] = [];
      let teams: TeamsWorkspace[] = [];
      let ibkr: BrokerConnectionStatus = { connected: false, broker_type: 'ibkr', status: 'not_connected' };

      try {
        oneDrive = await onedriveService.getStatus();
        console.log('[IntegrationsTab] OneDrive status:', oneDrive);
      } catch (e) {
        console.error('[IntegrationsTab] OneDrive status error:', e);
      }

      try {
        googleDrive = await googleDriveService.getStatus();
        console.log('[IntegrationsTab] Google Drive status:', googleDrive);
      } catch (e) {
        console.error('[IntegrationsTab] Google Drive status error:', e);
      }

      try {
        slack = await slackIntegrationApi.listWorkspaces();
        console.log('[IntegrationsTab] Slack workspaces:', slack);
      } catch (e) {
        console.error('[IntegrationsTab] Slack status error:', e);
      }

      try {
        teams = await teamsIntegrationApi.listWorkspaces();
        console.log('[IntegrationsTab] Teams workspaces:', teams);
      } catch (e) {
        console.error('[IntegrationsTab] Teams status error:', e);
      }

      try {
        ibkr = await getIBKRStatus();
        console.log('[IntegrationsTab] IBKR status:', ibkr);
      } catch (e) {
        console.error('[IntegrationsTab] IBKR status error:', e);
      }

      setOneDriveStatus(oneDrive);
      setGoogleDriveStatus(googleDrive);
      setSlackWorkspaces(slack);
      setTeamsWorkspaces(teams);
      setIbkrStatus(ibkr);
    } catch (error) {
      console.error('Failed to fetch integration statuses:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatuses();
  }, []);

  // ===== ONEDRIVE HANDLERS (EXISTING - UNCHANGED) =====
  const handleOneDriveConnect = async () => {
    setActionLoading('onedrive');
    try {
      const { authorization_url } = await onedriveService.startAuthorization();

      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        authorization_url,
        'OneDrive Authorization',
        `width=${width},height=${height},left=${left},top=${top}`,
      );

      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer);
          setActionLoading(null);
          setTimeout(() => fetchStatuses(), 1000);
        }
      }, 500);
    } catch (error: any) {
      console.error('Failed to start authorization:', error);
      toast.error(error.response?.data?.detail || 'Failed to start authorization');
      setActionLoading(null);
    }
  };

  const handleOneDriveDisconnect = async () => {
    if (!confirm('Disconnect OneDrive?')) return;

    setActionLoading('onedrive');
    try {
      await onedriveService.disconnect();
      toast.success('Disconnected');
      await fetchStatuses();
    } catch (error: any) {
      toast.error('Failed to disconnect');
    } finally {
      setActionLoading(null);
    }
  };

  // ===== GOOGLE DRIVE HANDLERS (EXISTING - UNCHANGED) =====
  const handleGoogleDriveConnect = async () => {
    setActionLoading('googledrive');
    try {
      const { authorization_url } = await googleDriveService.startAuthorization();

      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        authorization_url,
        'Google Drive Authorization',
        `width=${width},height=${height},left=${left},top=${top}`,
      );

      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer);
          setActionLoading(null);
          setTimeout(() => fetchStatuses(), 1000);
        }
      }, 500);
    } catch (error: any) {
      console.error('Failed to start authorization:', error);
      toast.error(error.response?.data?.detail || 'Failed to start authorization');
      setActionLoading(null);
    }
  };

  const handleGoogleDriveDisconnect = async () => {
    if (!confirm('Disconnect Google Drive?')) return;

    setActionLoading('googledrive');
    try {
      await googleDriveService.disconnect();
      toast.success('Disconnected');
      await fetchStatuses();
    } catch (error: any) {
      toast.error('Failed to disconnect');
    } finally {
      setActionLoading(null);
    }
  };

  // ===== SLACK HANDLERS =====
  const handleSlackConnect = async () => {
    setActionLoading('slack');
    try {
      const authorization_url = await slackIntegrationApi.getAuthorizeUrl();

      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        authorization_url,
        'Slack Authorization',
        `width=${width},height=${height},left=${left},top=${top}`,
      );

      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer);
          setActionLoading(null);
          setTimeout(() => fetchStatuses(), 1000);
        }
      }, 500);
    } catch (error: any) {
      console.error('Failed to start Slack authorization:', error);
      toast.error(error.response?.data?.detail || 'Failed to start authorization');
      setActionLoading(null);
    }
  };

  const handleSlackDisconnect = async () => {
    if (!confirm('Disconnect all Slack workspaces?')) return;

    setActionLoading('slack');
    try {
      for (const ws of slackWorkspaces) {
        await slackIntegrationApi.deleteWorkspace(ws.team_id);
      }
      toast.success('Disconnected');
      await fetchStatuses();
    } catch (error: any) {
      toast.error('Failed to disconnect');
    } finally {
      setActionLoading(null);
    }
  };

  // ===== TEAMS HANDLERS =====
  const handleTeamsConnect = async () => {
    setActionLoading('teams');
    try {
      const authorization_url = await teamsIntegrationApi.getAuthorizeUrl();

      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        authorization_url,
        'Microsoft Teams Authorization',
        `width=${width},height=${height},left=${left},top=${top}`,
      );

      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer);
          setActionLoading(null);
          setTimeout(() => fetchStatuses(), 1000);
        }
      }, 500);
    } catch (error: any) {
      console.error('Failed to start Teams authorization:', error);
      toast.error(error.response?.data?.detail || 'Failed to start authorization');
      setActionLoading(null);
    }
  };

  const handleTeamsDisconnect = async () => {
    if (!confirm('Disconnect all Teams workspaces?')) return;

    setActionLoading('teams');
    try {
      for (const ws of teamsWorkspaces) {
        await teamsIntegrationApi.deleteWorkspace(ws.tenant_id);
      }
      toast.success('Disconnected');
      await fetchStatuses();
    } catch (error: any) {
      toast.error('Failed to disconnect');
    } finally {
      setActionLoading(null);
    }
  };

  // ===== IBKR HANDLERS =====
  const handleIBKRConnect = () => {
    // Navigate to marketplace for IBKR setup (requires Flex Query credentials)
    navigate('/marketplace/ibkr');
  };

  const handleIBKRDisconnect = async () => {
    if (!confirm('Disconnect Interactive Brokers?')) return;

    setActionLoading('ibkr');
    try {
      await disconnectIBKR();
      toast.success('Disconnected');
      await fetchStatuses();
    } catch (error: any) {
      toast.error('Failed to disconnect');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return <div className="text-gray-500 text-sm">Loading...</div>;
  }

  // Cloud Storage integrations
  const cloudIntegrations = [
    {
      id: 'onedrive-personal',
      name: 'OneDrive Personal',
      description: 'Microsoft consumer account',
      logo: '/connector-logos/one-drive.png',
      connected: oneDriveStatus?.connected || false,
      email: oneDriveStatus?.credential?.drive_email,
      onConnect: handleOneDriveConnect,
      onDisconnect: handleOneDriveDisconnect,
      onRefresh: handleOneDriveConnect,
    },
    {
      id: 'onedrive-business',
      name: 'OneDrive Business',
      description: 'Work or school account',
      logo: '/connector-logos/one-drive.png',
      connected: oneDriveStatus?.connected || false,
      email: oneDriveStatus?.credential?.drive_email,
      onConnect: handleOneDriveConnect,
      onDisconnect: handleOneDriveDisconnect,
      onRefresh: handleOneDriveConnect,
    },
    {
      id: 'sharepoint',
      name: 'SharePoint',
      description: 'Team sites & libraries',
      logo: '/connector-logos/sharepoint-logo.png',
      connected: oneDriveStatus?.connected || false,
      email: oneDriveStatus?.credential?.drive_email,
      onConnect: handleOneDriveConnect,
      onDisconnect: handleOneDriveDisconnect,
      onRefresh: handleOneDriveConnect,
    },
    {
      id: 'googledrive',
      name: 'Google Drive',
      description: 'Personal & Team Drives',
      logo: '/connector-logos/google-drive.png',
      connected: googleDriveStatus?.connected || false,
      email: googleDriveStatus?.credential?.drive_email,
      onConnect: handleGoogleDriveConnect,
      onDisconnect: handleGoogleDriveDisconnect,
      onRefresh: handleGoogleDriveConnect,
    },
  ];

  // Communication integrations
  const communicationIntegrations = [
    {
      id: 'slack',
      name: 'Slack',
      description: 'Workspace messaging',
      logo: '/connector-logos/slack-logo.png',
      connected: slackWorkspaces.length > 0,
      email: slackWorkspaces.map(w => w.team_name || w.team_id).join(', ') || undefined,
      onConnect: handleSlackConnect,
      onDisconnect: handleSlackDisconnect,
      onRefresh: handleSlackConnect,
    },
    {
      id: 'teams',
      name: 'Microsoft Teams',
      description: 'Team collaboration',
      logo: '/connector-logos/teams-logo.png',
      connected: teamsWorkspaces.length > 0,
      email: teamsWorkspaces.map(w => w.tenant_name || w.tenant_id).join(', ') || undefined,
      onConnect: handleTeamsConnect,
      onDisconnect: handleTeamsDisconnect,
      onRefresh: handleTeamsConnect,
    },
  ];

  // Brokerage integrations
  const brokerageIntegrations = [
    {
      id: 'ibkr',
      name: 'Interactive Brokers',
      description: 'Portfolio sync & trading',
      logo: '/connector-logos/ibkr-logo.png',
      connected: ibkrStatus?.connected || false,
      email: ibkrStatus?.last_sync_at ? `Last sync: ${new Date(ibkrStatus.last_sync_at).toLocaleDateString()}` : undefined,
      onConnect: handleIBKRConnect,
      onDisconnect: handleIBKRDisconnect,
      onRefresh: handleIBKRConnect,
      hasError: ibkrStatus?.status === 'error',
      errorMessage: ibkrStatus?.error_message,
    },
  ];

  // AI Models - all platform-provided, always connected
  const aiModels = [
    { id: 'gpt-6-astra', name: 'GPT-6 Astra', description: 'Most capable OpenAI model', logo: '/assets/model-logos/gpt-logo.png' },
    { id: 'claude-fable', name: 'Claude Fable 5.1', description: 'Highest capability', logo: '/assets/model-logos/claude-logo.svg.png' },
    { id: 'claude-opus', name: 'Claude Opus 5.5', description: 'Frontier reasoning', logo: '/assets/model-logos/claude-logo.svg.png' },
    { id: 'claude-sonnet', name: 'Claude Sonnet 5.5', description: 'Balanced performance', logo: '/assets/model-logos/claude-logo.svg.png' },
    { id: 'gemini-argon', name: 'Gemini 4 Argon', description: 'Multimodal reasoning', logo: '/assets/model-logos/gemini-logo.png' },
    { id: 'gemini-flash', name: 'Gemini 3.8 Flash', description: 'Fast tool use and streaming', logo: '/assets/model-logos/gemini-logo.png' },
    { id: 'qwen-max', name: 'Qwen 3.8 Max', description: 'Agentic reasoning', logo: '/assets/model-logos/Qwen_logo.svg.png' },
    { id: 'deepseek-chat', name: 'DeepSeek Chat', description: 'Financial analysis', logo: '/assets/model-logos/deepseek.png' },
    { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner', description: 'Chain-of-thought', logo: '/assets/model-logos/deepseek.png' },
    { id: 'grok-reasoning', name: 'Grok 4.7', description: 'Deep reasoning', logo: '/assets/model-logos/grok.png' },
    { id: 'grok-fast', name: 'Grok 4.20 Fast', description: 'High-speed responses', logo: '/assets/model-logos/grok.png' },
    { id: 'perplexity', name: 'Perplexity Sonar Pro', description: 'Web search with citations', logo: '/assets/model-logos/perplexity-logo.png' },
  ];

  const renderIntegrationCards = (integrations: typeof cloudIntegrations, title: string, description: string) => (
    <div className="mb-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 mb-3">{description}</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
        {integrations.map((integration) => (
          <div
            key={integration.id}
            className="bg-white rounded-lg border border-gray-100 p-3 hover:border-gray-200 hover:shadow-sm transition-all relative"
          >
            {integration.connected && (
              <button
                onClick={integration.onRefresh}
                disabled={!!actionLoading}
                className="absolute top-2 right-2 flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <RefreshCw className="w-2.5 h-2.5" />
                Refresh
              </button>
            )}
            <div className="flex items-center gap-2 mb-2">
              <img
                src={integration.logo}
                alt={integration.name}
                className="w-5 h-5 object-contain flex-shrink-0"
              />
              <span
                className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  (integration as any).hasError
                    ? 'bg-red-500'
                    : integration.connected
                      ? 'bg-green-500'
                      : 'bg-gray-300'
                }`}
                title={integration.connected ? ((integration as any).hasError ? 'Error' : 'Connected') : 'Not connected'}
              />
            </div>
            <div className="text-xs font-medium text-gray-900 truncate mb-0.5">{integration.name}</div>
            <div className="text-[10px] text-gray-400 truncate mb-2">{integration.email || integration.description}</div>
            <div className="flex gap-1">
              {integration.connected ? (
                <button
                  onClick={integration.onDisconnect}
                  disabled={!!actionLoading}
                  className="flex-1 px-2 py-1 text-[10px] font-medium text-red-600 bg-red-50 rounded hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Disconnect
                </button>
              ) : (
                <button
                  onClick={integration.onConnect}
                  disabled={!!actionLoading}
                  className="flex-1 px-2 py-1 text-[10px] font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {actionLoading === integration.id ? '...' : 'Connect'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Integrations</h2>
          <p className="text-sm text-gray-500">Connect external services to your workspace</p>
        </div>
        <button
          onClick={() => navigate('/marketplace')}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
        >
          <ExternalLink className="w-4 h-4" />
          Browse Marketplace
        </button>
      </div>

      {/* Sub-tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        <button
          onClick={() => setSubTab('connectors')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            subTab === 'connectors'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          Connectors
        </button>
        <button
          onClick={() => setSubTab('ai-models')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            subTab === 'ai-models'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          AI Models
        </button>
      </div>

      {subTab === 'connectors' && (
        <>
          {renderIntegrationCards(cloudIntegrations, 'Cloud Storage', 'Connect your cloud storage providers')}
          {renderIntegrationCards(communicationIntegrations, 'Communication', 'Send notifications and collaborate')}
          {renderIntegrationCards(brokerageIntegrations, 'Brokerage', 'Sync portfolio and trading data')}
        </>
      )}

      {subTab === 'ai-models' && (
        <div>
          <p className="text-sm text-gray-500 mb-4">Platform-provided language models available for all users</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
            {aiModels.map((model) => (
              <div
                key={model.id}
                className="bg-white rounded-lg border border-gray-100 p-3 hover:border-gray-200 hover:shadow-sm transition-all"
              >
                <div className="flex items-center gap-2 mb-2">
                  <img
                    src={model.logo}
                    alt={model.name}
                    className="w-5 h-5 object-contain flex-shrink-0"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" title="Active" />
                </div>
                <div className="text-xs font-medium text-gray-900 truncate">{model.name}</div>
                <div className="text-[10px] text-gray-400 truncate">{model.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default IntegrationsTab;
