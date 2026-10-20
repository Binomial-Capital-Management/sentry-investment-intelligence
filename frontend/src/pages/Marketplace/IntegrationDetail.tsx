import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ArrowLeft,
  ExternalLink,
  Settings,
  Check,
  Shield,
  MessageSquare,
  ListTodo,
  BarChart3,
  FileSearch,
  Info,
  RefreshCw,
} from 'lucide-react';
import { Integration } from './IntegrationCard';

// Import existing services for connectors
import googleDriveService from '../../services/googleDrive';
import onedriveService from '../../services/onedrive';
import slackIntegrationApi from '../../services/slackIntegrationApi';
import teamsIntegrationApi from '../../services/teamsIntegrationApi';
import { disconnectIBKR } from '../../services/brokerService';

// Get API URL from environment or default
const getApiUrl = () => {
  return (import.meta as any).env?.VITE_API_BASE ||
         (import.meta as any).env?.VITE_API_BASE_URL ||
         (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');
};

const API_URL = getApiUrl();

// Where integrations can be used
const AVAILABLE_IN_MODULES = [
  { id: 'chat', name: 'Chat', icon: MessageSquare, description: 'Use in conversations' },
  { id: 'tasks', name: 'Tasks', icon: ListTodo, description: 'Automate workflows' },
  { id: 'analysis', name: 'Analysis', icon: BarChart3, description: 'Data insights' },
  { id: 'search', name: 'Search', icon: FileSearch, description: 'Find documents' },
];

// Map integration categories to available modules
const CATEGORY_MODULES: Record<string, string[]> = {
  'Cloud': ['chat', 'tasks', 'search'],
  'Database Services': ['chat', 'analysis'],
  'LLMs': ['chat', 'tasks', 'analysis'],
  'Communicators': ['tasks'],
  'Actions': ['tasks'],
  'Brokerage': ['tasks', 'analysis'],
};

// Map integration IDs to their connection handlers
const CLOUD_INTEGRATION_IDS = ['google_drive', 'onedrive_business', 'onedrive_personal', 'sharepoint'];
const COMMUNICATION_INTEGRATION_IDS = ['slack', 'teams'];
const BROKERAGE_INTEGRATION_IDS = ['ibkr'];

export const IntegrationDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [integration, setIntegration] = useState<Integration | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/api/marketplace/${id}`);
      setIntegration(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch integration details:', err);
      setError('Failed to load integration details.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // Handle OAuth popup flow for cloud connectors (leveraging existing architecture)
  const handleCloudConnect = async (integrationId: string) => {
    setIsConnecting(true);
    try {
      let authUrl: string;
      let popupTitle: string;

      if (integrationId === 'google_drive') {
        const { authorization_url } = await googleDriveService.startAuthorization();
        authUrl = authorization_url;
        popupTitle = 'Google Drive Authorization';
      } else if (['onedrive_business', 'onedrive_personal', 'sharepoint'].includes(integrationId)) {
        const { authorization_url } = await onedriveService.startAuthorization();
        authUrl = authorization_url;
        popupTitle = 'OneDrive Authorization';
      } else {
        throw new Error('Unknown cloud integration');
      }

      // Open OAuth popup (same pattern as IntegrationsTab)
      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        authUrl,
        popupTitle,
        `width=${width},height=${height},left=${left},top=${top}`,
      );

      // Poll for popup close
      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer);
          setIsConnecting(false);
          // Refresh integration status after popup closes
          setTimeout(() => {
            fetchDetail();
            toast.success('Connection updated');
          }, 1000);
        }
      }, 500);

    } catch (error: any) {
      console.error('Failed to start authorization:', error);
      toast.error(error.response?.data?.detail || 'Failed to start authorization');
      setIsConnecting(false);
    }
  };

  const handleCloudDisconnect = async (integrationId: string) => {
    if (!confirm(`Are you sure you want to disconnect ${integration?.name}?`)) return;

    setIsDisconnecting(true);
    try {
      if (integrationId === 'google_drive') {
        await googleDriveService.disconnect();
      } else if (['onedrive_business', 'onedrive_personal', 'sharepoint'].includes(integrationId)) {
        await onedriveService.disconnect();
      }
      toast.success('Disconnected successfully');
      await fetchDetail();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to disconnect');
    } finally {
      setIsDisconnecting(false);
    }
  };

  // Handle OAuth for communication integrations (Slack/Teams)
  const handleCommunicationConnect = async (integrationId: string) => {
    setIsConnecting(true);
    try {
      let authUrl: string;
      let popupTitle: string;

      if (integrationId === 'slack') {
        authUrl = await slackIntegrationApi.getAuthorizeUrl();
        popupTitle = 'Slack Authorization';
      } else if (integrationId === 'teams') {
        authUrl = await teamsIntegrationApi.getAuthorizeUrl();
        popupTitle = 'Microsoft Teams Authorization';
      } else {
        throw new Error('Unknown communication integration');
      }

      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        authUrl,
        popupTitle,
        `width=${width},height=${height},left=${left},top=${top}`,
      );

      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer);
          setIsConnecting(false);
          setTimeout(() => {
            fetchDetail();
            toast.success('Connection updated');
          }, 1000);
        }
      }, 500);

    } catch (error: any) {
      console.error('Failed to start authorization:', error);
      toast.error(error.response?.data?.detail || 'Failed to start authorization');
      setIsConnecting(false);
    }
  };

  const handleCommunicationDisconnect = async (integrationId: string) => {
    if (!confirm(`Are you sure you want to disconnect ${integration?.name}?`)) return;

    setIsDisconnecting(true);
    try {
      if (integrationId === 'slack') {
        const workspaces = await slackIntegrationApi.listWorkspaces();
        for (const ws of workspaces) {
          await slackIntegrationApi.deleteWorkspace(ws.team_id);
        }
      } else if (integrationId === 'teams') {
        const workspaces = await teamsIntegrationApi.listWorkspaces();
        for (const ws of workspaces) {
          await teamsIntegrationApi.deleteWorkspace(ws.tenant_id);
        }
      }
      toast.success('Disconnected successfully');
      await fetchDetail();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to disconnect');
    } finally {
      setIsDisconnecting(false);
    }
  };

  const handleConnect = async () => {
    if (!integration) return;

    // Cloud connectors
    if (CLOUD_INTEGRATION_IDS.includes(integration.id)) {
      await handleCloudConnect(integration.id);
      return;
    }

    // Communication integrations
    if (COMMUNICATION_INTEGRATION_IDS.includes(integration.id)) {
      await handleCommunicationConnect(integration.id);
      return;
    }

    // Brokerage - redirect to settings for IBKR setup (needs Flex Query credentials)
    if (BROKERAGE_INTEGRATION_IDS.includes(integration.id)) {
      toast.info('Please use the Settings > Integrations tab or navigate to Portfolio to set up IBKR');
      return;
    }

    // For other integrations (LLMs, etc.) - placeholder for future implementation
    setIsConnecting(true);
    setTimeout(() => {
      setIsConnecting(false);
      toast.info(`${integration.name} connection flow coming soon`);
    }, 500);
  };

  const handleDisconnect = async () => {
    if (!integration) return;

    // Cloud connectors
    if (CLOUD_INTEGRATION_IDS.includes(integration.id)) {
      await handleCloudDisconnect(integration.id);
      return;
    }

    // Communication integrations
    if (COMMUNICATION_INTEGRATION_IDS.includes(integration.id)) {
      await handleCommunicationDisconnect(integration.id);
      return;
    }

    // Brokerage
    if (BROKERAGE_INTEGRATION_IDS.includes(integration.id)) {
      if (!confirm(`Are you sure you want to disconnect ${integration.name}?`)) return;
      setIsDisconnecting(true);
      try {
        await disconnectIBKR();
        toast.success('Disconnected successfully');
        await fetchDetail();
      } catch (error: any) {
        toast.error(error.response?.data?.detail || 'Failed to disconnect');
      } finally {
        setIsDisconnecting(false);
      }
      return;
    }

    // For other integrations - placeholder
    if (confirm(`Are you sure you want to disconnect ${integration.name}?`)) {
      toast.info('Disconnect flow coming soon');
    }
  };

  const handleRefresh = async () => {
    if (!integration) return;

    // Re-run OAuth to refresh tokens
    if (CLOUD_INTEGRATION_IDS.includes(integration.id)) {
      await handleCloudConnect(integration.id);
    } else if (COMMUNICATION_INTEGRATION_IDS.includes(integration.id)) {
      await handleCommunicationConnect(integration.id);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen bg-[#fafafa]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error || !integration) {
    return (
      <div className="flex flex-col justify-center items-center h-screen bg-[#fafafa]">
        <p className="text-red-600 mb-4">{error || 'Integration not found'}</p>
        <button
          onClick={() => navigate('/marketplace')}
          className="text-[#0051cc] hover:underline font-medium"
        >
          Back to Marketplace
        </button>
      </div>
    );
  }

  const availableModules = CATEGORY_MODULES[integration.category] || ['chat'];
  const supportsReconnect = CLOUD_INTEGRATION_IDS.includes(integration.id) ||
                            COMMUNICATION_INTEGRATION_IDS.includes(integration.id);

  return (
    <div className="min-h-screen bg-[#fafafa] text-[#323130]">
      {/* Professional Header / Breadcrumb */}
      <div className="bg-white border-b border-[#E1DFDD] px-8 py-4 sticky top-0 z-20 shadow-sm">
        <div className="max-w-6xl mx-auto w-full flex items-center gap-3 text-sm">
          <button
            onClick={() => navigate('/marketplace')}
            className="text-[#0051cc] hover:underline font-medium flex items-center gap-1"
          >
            <ArrowLeft size={14} />
            Marketplace
          </button>
          <span className="text-[#605E5C]">/</span>
          <span className="font-semibold text-[#323130]">{integration.name}</span>
        </div>
      </div>

      <div className="max-w-6xl mx-auto p-8">
        {/* Main Content Card */}
        <div className="bg-white rounded-lg border border-[#E1DFDD] shadow-[0_1.6px_3.6px_rgba(0,0,0,0.132)] overflow-hidden">

          {/* Integration Header Area */}
          <div className="p-8 pb-6 border-b border-[#E1DFDD]">
            <div className="flex flex-col md:flex-row md:items-start gap-6">
              {/* Logo */}
              <div className="w-20 h-20 bg-white rounded-lg border border-[#E1DFDD] flex items-center justify-center p-3 shrink-0 shadow-sm">
                {integration.icon_url ? (
                  <img
                    src={integration.icon_url}
                    alt={integration.name}
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                      if (e.currentTarget.parentElement) {
                        e.currentTarget.parentElement.innerText = integration.name.substring(0, 2).toUpperCase();
                        e.currentTarget.parentElement.className = 'w-20 h-20 bg-[#F3F2F1] rounded-lg border border-[#E1DFDD] flex items-center justify-center text-xl font-bold text-[#605E5C]';
                      }
                    }}
                  />
                ) : (
                  <span className="text-2xl font-bold text-[#605E5C]">
                    {integration.name.substring(0, 2).toUpperCase()}
                  </span>
                )}
              </div>

              {/* Title & Description */}
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h1 className="text-2xl font-bold text-[#323130]">{integration.name}</h1>
                  {integration.status === 'connected' && (
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-50 text-xs font-semibold text-emerald-700 uppercase tracking-wide border border-emerald-100 flex items-center gap-1">
                      <Check size={12} strokeWidth={3} />
                      Active
                    </span>
                  )}
                  {integration.status === 'coming_soon' && (
                    <span className="px-2.5 py-0.5 rounded-full bg-[#F3F2F1] text-xs font-semibold text-[#605E5C] uppercase tracking-wide border border-[#E1DFDD]">
                      Coming Soon
                    </span>
                  )}
                </div>
                <p className="text-[#605E5C] text-[15px] leading-relaxed max-w-3xl">
                  {integration.long_description || integration.description}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col gap-3 min-w-[160px] pt-1">
                {integration.status === 'connected' ? (
                  <>
                    {supportsReconnect && (
                      <button
                        onClick={handleRefresh}
                        disabled={isConnecting}
                        className="flex items-center justify-center gap-2 px-4 py-2 bg-white border border-[#E1DFDD] text-[#323130] font-semibold rounded hover:bg-[#F3F2F1] transition-colors shadow-sm text-sm disabled:opacity-50"
                      >
                        <RefreshCw size={16} className={isConnecting ? 'animate-spin' : ''} />
                        {isConnecting ? 'Refreshing...' : 'Reconnect'}
                      </button>
                    )}
                    <button className="flex items-center justify-center gap-2 px-4 py-2 bg-white border border-[#E1DFDD] text-[#323130] font-semibold rounded hover:bg-[#F3F2F1] transition-colors shadow-sm text-sm">
                      <Settings size={16} />
                      Configure
                    </button>
                    <button
                      onClick={handleDisconnect}
                      disabled={isDisconnecting}
                      className="text-xs text-red-600 hover:text-red-700 hover:underline text-center py-1 font-medium disabled:opacity-50"
                    >
                      {isDisconnecting ? 'Disconnecting...' : 'Disconnect Integration'}
                    </button>
                  </>
                ) : integration.status === 'coming_soon' ? (
                  <button
                    disabled
                    className="flex items-center justify-center gap-2 px-4 py-2 bg-[#F3F2F1] text-[#A19F9D] font-semibold rounded cursor-not-allowed text-sm"
                  >
                    Unavailable
                  </button>
                ) : (
                  <button
                    onClick={handleConnect}
                    disabled={isConnecting}
                    className="flex items-center justify-center gap-2 px-4 py-2 bg-[#0051cc] text-white font-semibold rounded hover:bg-[#003d99] transition-colors shadow-sm text-sm disabled:opacity-70"
                  >
                    {isConnecting ? 'Connecting...' : 'Connect'}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Two Column Layout for Details */}
          <div className="grid grid-cols-1 lg:grid-cols-3">
            {/* Main Content Column */}
            <div className="lg:col-span-2 p-8 border-r border-[#E1DFDD]">

              {/* Features */}
              <section className="mb-10">
                <h3 className="text-sm font-bold text-[#323130] uppercase tracking-wider mb-4">Capabilities</h3>
                <div className="space-y-3">
                  {integration.features && integration.features.length > 0 ? (
                    integration.features.map((feature, idx) => (
                      <div key={idx} className="flex items-start gap-3">
                        <div className="mt-1 w-4 h-4 rounded-full bg-emerald-50 flex items-center justify-center shrink-0 border border-emerald-100">
                          <Check size={10} className="text-emerald-700" strokeWidth={3} />
                        </div>
                        <span className="text-[#323130] text-sm leading-relaxed">{feature}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-[#605E5C] italic">No detailed features listed.</p>
                  )}
                </div>
              </section>

              {/* Supported Files */}
              {integration.supported_file_types && integration.supported_file_types.length > 0 && (
                <section className="mb-10">
                  <h3 className="text-sm font-bold text-[#323130] uppercase tracking-wider mb-4">Supported Files</h3>
                  <div className="flex flex-wrap gap-2">
                    {integration.supported_file_types.map((type) => (
                      <span key={type} className="px-2.5 py-1 bg-[#F3F2F1] text-[#605E5C] rounded text-xs font-medium uppercase border border-[#E1DFDD]">
                        .{type}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              {/* Availability Grid */}
              <section>
                <h3 className="text-sm font-bold text-[#323130] uppercase tracking-wider mb-4">Available In</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {AVAILABLE_IN_MODULES.map((module) => {
                    const isAvailable = availableModules.includes(module.id);
                    const Icon = module.icon;
                    return (
                      <div
                        key={module.id}
                        className={`p-3 rounded border flex items-start gap-3 ${
                          isAvailable
                            ? 'bg-white border-[#E1DFDD]'
                            : 'bg-[#F9F9F9] border-transparent opacity-50'
                        }`}
                      >
                        <div className={`p-1.5 rounded ${isAvailable ? 'bg-blue-50 text-[#0051cc]' : 'bg-[#F3F2F1] text-[#A19F9D]'}`}>
                          <Icon size={16} />
                        </div>
                        <div>
                          <div className={`text-sm font-semibold ${isAvailable ? 'text-[#323130]' : 'text-[#A19F9D]'}`}>
                            {module.name}
                          </div>
                          <div className="text-xs text-[#605E5C]">{module.description}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>

            {/* Sidebar Column */}
            <div className="p-8 bg-[#fafafa]">
              <div className="space-y-6">
                {/* Info Box */}
                <div>
                  <h3 className="text-xs font-bold text-[#605E5C] uppercase tracking-wider mb-3">Information</h3>
                  <div className="bg-white rounded border border-[#E1DFDD] p-4 space-y-3 shadow-sm">
                    <div className="flex justify-between text-sm">
                      <span className="text-[#605E5C]">Category</span>
                      <span className="font-medium text-[#323130]">{integration.category}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[#605E5C]">Auth Type</span>
                      <span className="font-medium text-[#323130]">
                         {integration.category === 'Cloud' ? 'OAuth 2.0' :
                          integration.category === 'LLMs' ? 'API Key' :
                          integration.category === 'Brokerage' ? 'OAuth 2.0' : 'Standard'}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[#605E5C]">Version</span>
                      <span className="font-medium text-[#323130]">v1.0.0</span>
                    </div>
                  </div>
                </div>

                {/* Resources */}
                <div>
                  <h3 className="text-xs font-bold text-[#605E5C] uppercase tracking-wider mb-3">Resources</h3>
                  <div className="space-y-2">
                    {integration.docs_url && (
                      <a
                        href={integration.docs_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block p-3 bg-white border border-[#E1DFDD] rounded hover:border-[#0051cc] transition-colors group"
                      >
                        <div className="flex items-center justify-between text-sm font-medium text-[#323130] group-hover:text-[#0051cc]">
                          <span>Documentation</span>
                          <ExternalLink size={14} />
                        </div>
                      </a>
                    )}
                    {integration.setup_guide_url && (
                      <a
                        href={integration.setup_guide_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block p-3 bg-white border border-[#E1DFDD] rounded hover:border-[#0051cc] transition-colors group"
                      >
                        <div className="flex items-center justify-between text-sm font-medium text-[#323130] group-hover:text-[#0051cc]">
                          <span>Setup Guide</span>
                          <ExternalLink size={14} />
                        </div>
                      </a>
                    )}
                    <button className="w-full p-3 bg-white border border-[#E1DFDD] rounded hover:border-[#0051cc] transition-colors group text-left">
                      <div className="flex items-center justify-between text-sm font-medium text-[#323130] group-hover:text-[#0051cc]">
                        <span>Contact Support</span>
                        <Info size={14} />
                      </div>
                    </button>
                  </div>
                </div>

                {/* Security Note */}
                <div className="bg-emerald-50 border border-emerald-100 rounded p-3 flex items-start gap-2">
                  <Shield size={14} className="text-emerald-600 mt-0.5 shrink-0" />
                  <p className="text-xs text-emerald-800 leading-relaxed">
                    <span className="font-semibold">Enterprise Secure:</span> All data transmission is encrypted. Credentials are stored securely.
                  </p>
                </div>

              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
