/**
 * Documentation Tab - Central hub for all feature documentation
 * Clean institutional design - Microsoft/Palantir style
 */

import React, { useState, useMemo } from 'react';
import { Search, X, ArrowRight } from 'lucide-react';

// Import the actual guide panel components
import { ChatGuidePanel } from '@/components/Chat/ChatGuidePanel';
import { DashboardGuidePanel } from '@/components/Dashboard/DashboardGuidePanel';
import { PortfolioGuidePanel } from '@/components/Portfolio/PortfolioGuidePanel';
import { TaskGuidePanel } from '@/components/Task/TaskGuidePanel';
import { PostMortemGuidePanel } from '@/components/TaskTracker/PostMortems/PostMortemGuidePanel';
import { MarketplaceGuidePanel } from '@/pages/Marketplace/MarketplaceGuidePanel';

type FeatureId = 'home' | 'chat' | 'dashboard' | 'portfolio' | 'tasks' | 'postmortems' | 'marketplace';

interface FeatureItem {
  id: FeatureId;
  name: string;
  description: string;
  keywords: string[];
}

const features: FeatureItem[] = [
  {
    id: 'chat',
    name: 'Chat',
    description: 'AI agents, language models, tools, and conversation features',
    keywords: ['agent', 'model', 'gpt', 'claude', 'gemini', 'risk', 'dcf', 'valuation', 'search', 'code interpreter', 'tools', 'mcp', 'export', 'pdf', 'portfolio context'],
  },
  {
    id: 'dashboard',
    name: 'Dashboard',
    description: 'Market views, widgets, portfolio overview, and AI screener',
    keywords: ['market', 'crypto', 'earnings', 'ipo', 'screener', 'fear greed', 'ticker', 'widget', 'insight'],
  },
  {
    id: 'portfolio',
    name: 'Portfolio',
    description: 'Holdings management, trading, lot tracking, and broker integration',
    keywords: ['holdings', 'lot', 'trading', 'buy', 'sell', 'ibkr', 'interactive brokers', 'csv', 'import', 'performance', 'twr'],
  },
  {
    id: 'tasks',
    name: 'Tasks',
    description: 'Workflow automation, scheduling, and delivery channels',
    keywords: ['workflow', 'schedule', 'cron', 'email', 'slack', 'teams', 'pdf', 'pptx', 'node', 'canvas', 'deploy'],
  },
  {
    id: 'postmortems',
    name: 'Post Mortems',
    description: 'Trade review, AI analysis, and performance metrics',
    keywords: ['trade', 'review', 'analysis', 'win rate', 'payoff', 'expectancy', 'drawdown', 'thread'],
  },
  {
    id: 'marketplace',
    name: 'Marketplace',
    description: 'Connect AI models, cloud storage, and third-party integrations',
    keywords: ['integration', 'connect', 'oauth', 'api key', 'byok', 'google drive', 'onedrive', 'sharepoint', 'llm'],
  },
];

export const DocsTab: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [openPanel, setOpenPanel] = useState<FeatureId | null>(null);

  const filteredFeatures = useMemo(() => {
    if (!searchQuery.trim()) return features;
    const query = searchQuery.toLowerCase();
    return features.filter(f =>
      f.name.toLowerCase().includes(query) ||
      f.description.toLowerCase().includes(query) ||
      f.keywords.some(k => k.toLowerCase().includes(query)),
    );
  }, [searchQuery]);

  const handleOpenGuide = (featureId: FeatureId) => {
    if (featureId !== 'home') {
      setOpenPanel(featureId);
    }
  };

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="flex-shrink-0 px-8 py-6 border-b border-gray-200">
        <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Documentation</h1>
        <p className="text-sm text-gray-500 mt-1">
          Platform guides and feature reference
        </p>

        {/* Search */}
        <div className="mt-5 relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
            <input
              type="text"
              placeholder="Search documentation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-8 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-400 focus:border-gray-400"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="max-w-4xl">
          {/* Section Header */}
          <div className="mb-6">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              {searchQuery ? `${filteredFeatures.length} result${filteredFeatures.length !== 1 ? 's' : ''}` : 'All Features'}
            </span>
              </div>

          {/* No Results */}
          {searchQuery && filteredFeatures.length === 0 ? (
            <div className="py-16 text-center">
              <p className="text-gray-500">No results for "{searchQuery}"</p>
              <button
                onClick={() => setSearchQuery('')}
                className="mt-2 text-sm text-gray-400 hover:text-gray-600 underline"
              >
                Clear search
              </button>
                     </div>
          ) : (
            /* Feature List */
            <div className="space-y-1">
              {filteredFeatures.map((feature) => (
                <button
                  key={feature.id}
                  onClick={() => handleOpenGuide(feature.id)}
                  className="w-full group flex items-center justify-between py-4 px-4 -mx-4 rounded hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-3">
                      <h3 className="text-base font-medium text-gray-900 group-hover:text-gray-700">
                        {feature.name}
                      </h3>
                     </div>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {feature.description}
                    </p>
                  </div>
                  <ArrowRight
                    size={16}
                    className="flex-shrink-0 ml-4 text-gray-300 group-hover:text-gray-500 group-hover:translate-x-0.5 transition-all"
                  />
                </button>
                ))}
              </div>
          )}

          {/* Quick Topics */}
          {!searchQuery && (
            <div className="mt-10 pt-8 border-t border-gray-100">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                Popular Topics
              </span>
              <div className="mt-4 flex flex-wrap gap-2">
                {[
                  { label: 'AI Agents', panel: 'chat' as FeatureId },
                  { label: 'Language Models', panel: 'chat' as FeatureId },
                  { label: 'IBKR Connection', panel: 'portfolio' as FeatureId },
                  { label: 'Workflow Nodes', panel: 'tasks' as FeatureId },
                  { label: 'Cloud Storage', panel: 'marketplace' as FeatureId },
                  { label: 'API Keys', panel: 'marketplace' as FeatureId },
                ].map((topic, idx) => (
                   <button
                    key={idx}
                    onClick={() => handleOpenGuide(topic.panel)}
                    className="text-sm px-3 py-1.5 border border-gray-200 rounded hover:border-gray-300 hover:bg-gray-50 text-gray-600 transition-colors"
                   >
                    {topic.label}
                   </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Guide Panel Overlays */}
      <ChatGuidePanel
        isOpen={openPanel === 'chat'}
        onClose={() => setOpenPanel(null)}
      />
      <DashboardGuidePanel
        isOpen={openPanel === 'dashboard'}
        onClose={() => setOpenPanel(null)}
      />
      <PortfolioGuidePanel
        isOpen={openPanel === 'portfolio'}
        onClose={() => setOpenPanel(null)}
      />
      <TaskGuidePanel
        isOpen={openPanel === 'tasks'}
        onClose={() => setOpenPanel(null)}
      />
      <PostMortemGuidePanel
        isOpen={openPanel === 'postmortems'}
        onClose={() => setOpenPanel(null)}
      />
      <MarketplaceGuidePanel
        isOpen={openPanel === 'marketplace'}
        onClose={() => setOpenPanel(null)}
      />
    </div>
  );
};

export default DocsTab;
