import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { IntegrationCard, Integration } from './IntegrationCard';
import MarketplaceGuidePanel from './MarketplaceGuidePanel';
import WorkspaceIndicator from '@/components/Common/WorkspaceIndicator';
import { Search, Filter, Cloud, Database, Bot, MessageSquare, Zap, TrendingUp, HelpCircle } from 'lucide-react';

// Get API URL from environment or default
const getApiUrl = () => {
  return (import.meta as any).env?.VITE_API_BASE ||
         (import.meta as any).env?.VITE_API_BASE_URL ||
         (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');
};

const API_URL = getApiUrl();

const TABS = [
  { id: 'all', label: 'All Apps' },
  { id: 'Cloud', label: 'Cloud', icon: Cloud },
  { id: 'Database Services', label: 'Databases', icon: Database },
  { id: 'LLMs', label: 'AI Models', icon: Bot },
  { id: 'Communicators', label: 'Communication', icon: MessageSquare },
  { id: 'Actions', label: 'Actions', icon: Zap },
  { id: 'Brokerage', label: 'Brokerage', icon: TrendingUp },
];

export const MarketplacePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('all');
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [guideOpen, setGuideOpen] = useState(false);

  useEffect(() => {
    const fetchIntegrations = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/api/marketplace/list`);
        setIntegrations(response.data.integrations);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch marketplace integrations:', err);
        setError('Failed to load integrations. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchIntegrations();
  }, []);

  const filteredIntegrations = integrations.filter(i => {
    const matchesTab = activeTab === 'all' || i.category === activeTab;
    const matchesSearch = i.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          i.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  return (
    <div className="flex flex-col h-full bg-[#fafafa]">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-6 sticky top-0 z-10">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Marketplace</h1>
            <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
              <span>Connect tools and services</span>
              <span className="text-gray-300">•</span>
              <WorkspaceIndicator size="sm" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setGuideOpen(true)}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all"
              title="Open Marketplace Guide"
            >
              <HelpCircle className="w-5 h-5" />
            </button>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search apps..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all w-64"
              />
            </div>
          </div>
        </div>

        {/* Minimal Text-Only Filter Tabs (Simplified from Pills) */}
        <div className="flex items-center gap-1 flex-wrap border-b border-transparent">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex items-center gap-2 px-3 py-2 text-sm font-medium
                transition-all duration-200 border-b-2 -mb-[1px]
                ${
                  activeTab === tab.id
                    ? 'border-[#0051cc] text-[#0051cc]'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-t-md'
                }
              `}
            >
              {tab.icon && (
                <tab.icon
                  size={15}
                  className={`flex-shrink-0 ${
                    activeTab === tab.id ? 'text-[#0051cc]' : 'text-gray-400 group-hover:text-gray-600'
                  }`}
                />
              )}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm flex items-center justify-center">
            {error}
          </div>
        ) : (
          <div className="max-w-[1600px] mx-auto">
            {filteredIntegrations.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {filteredIntegrations.map((integration) => (
                  <IntegrationCard key={integration.id} integration={integration} />
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-96 bg-white rounded-2xl border border-gray-200 border-dashed">
                <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-4">
                  <Filter className="w-8 h-8 text-gray-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900">No integrations found</h3>
                <p className="text-gray-500 text-sm mt-2 max-w-sm text-center">
                  We couldn't find any integrations matching your current filters. Try adjusting your search or category.
                </p>
                <button
                  onClick={() => { setActiveTab('all'); setSearchQuery(''); }}
                  className="mt-6 px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors"
                >
                  Clear all filters
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Marketplace Guide Panel */}
      <MarketplaceGuidePanel
        isOpen={guideOpen}
        onClose={() => setGuideOpen(false)}
      />
    </div>
  );
};
