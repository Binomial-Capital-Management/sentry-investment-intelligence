/**
 * Marketplace Guide Panel - Compact slide-in documentation
 */

import React, { useState, useEffect } from 'react';
import {
  X, Cloud, Database, Bot, MessageSquare, Zap, TrendingUp,
  Search, Settings, Check, Shield, Key, RefreshCw, Link2,
  FileText, BarChart3, ListTodo, FileSearch, Plug,
} from 'lucide-react';

import gptLogo from '@/assets/model-logos/gpt-logo.png';
import claudeLogo from '@/assets/model-logos/claude-logo.svg.png';
import geminiLogo from '@/assets/model-logos/gemini-logo.png';
import perplexityLogo from '@/assets/model-logos/perplexity-logo.png';
import grokLogo from '@/assets/model-logos/grok.png';

interface MarketplaceGuidePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabId = 'toc' | 'overview' | 'categories' | 'connecting' | 'llms' | 'cloud' | 'detail';

const categories = [
  { id: 'cloud', name: 'Cloud Storage', icon: Cloud, count: 6, desc: 'GDrive, OneDrive, SharePoint, AWS, GCS' },
  { id: 'database', name: 'Databases', icon: Database, count: 4, desc: 'PostgreSQL, Snowflake, Databricks, Oracle' },
  { id: 'llm', name: 'AI Models', icon: Bot, count: 14, desc: 'GPT, Claude, Gemini, DeepSeek, Grok' },
  { id: 'communicator', name: 'Communication', icon: MessageSquare, count: 3, desc: 'Slack, Teams, Email' },
  { id: 'action', name: 'Actions', icon: Zap, count: 2, desc: 'Zapier, SendGrid' },
  { id: 'brokerage', name: 'Brokerage', icon: TrendingUp, count: 3, desc: 'IBKR, Robinhood, Schwab' },
];

const llmModels = [
  { name: 'GPT-6 Astra', logo: gptLogo, context: '1M', provider: 'OpenAI' },
  { name: 'Claude Fable 5.1', logo: claudeLogo, context: '1M', provider: 'Anthropic' },
  { name: 'Claude Opus 5.5', logo: claudeLogo, context: '1M', provider: 'Anthropic' },
  { name: 'GPT-6.1 Sol', logo: gptLogo, context: '1M', provider: 'OpenAI' },
  { name: 'GPT-6 Luna', logo: gptLogo, context: '1M', provider: 'OpenAI' },
  { name: 'Claude Sonnet 5.5', logo: claudeLogo, context: '1M', provider: 'Anthropic' },
  { name: 'Claude Haiku 4.5', logo: claudeLogo, context: '200K', provider: 'Anthropic' },
  { name: 'Gemini 4 Argon', logo: geminiLogo, context: '1M', provider: 'Google' },
  { name: 'Gemini 3.8 Flash', logo: geminiLogo, context: '1M', provider: 'Google' },
  { name: 'Grok 4.7', logo: grokLogo, context: '500K', provider: 'xAI' },
  { name: 'Grok 4.20 Fast', logo: grokLogo, context: '1M', provider: 'xAI' },
  { name: 'Perplexity Sonar', logo: perplexityLogo, context: '128K', provider: 'Perplexity' },
];

const cloudIntegrations = [
  { name: 'Google Drive', logo: '/connector-logos/google-drive.png', auth: 'OAuth', status: 'Available' },
  { name: 'OneDrive Business', logo: '/connector-logos/one-drive.png', auth: 'OAuth', status: 'Available' },
  { name: 'OneDrive Personal', logo: '/connector-logos/one-drive.png', auth: 'OAuth', status: 'Available' },
  { name: 'SharePoint', logo: '/connector-logos/sharepoint-logo.png', auth: 'OAuth', status: 'Available' },
  { name: 'AWS S3', logo: '/connector-logos/aws.png', auth: 'IAM', status: 'Soon' },
  { name: 'Google Cloud', logo: '/connector-logos/google-cloud.png', auth: 'Service Acct', status: 'Soon' },
];

export const MarketplaceGuidePanel: React.FC<MarketplaceGuidePanelProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabId>('toc');
  const [llmPage, setLlmPage] = useState(1);
  const [cloudPage, setCloudPage] = useState(1);
  const [connectSection, setConnectSection] = useState<'oauth' | 'apikey' | 'status'>('oauth');

  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (isOpen) setTimeout(() => setVisible(true), 10);
    else setVisible(false);
  }, [isOpen]);

  if (!isOpen) return null;

  const tabs: { id: TabId; label: string }[] = [
    { id: 'toc', label: 'Contents' },
    { id: 'overview', label: 'Overview' },
    { id: 'categories', label: 'Categories' },
    { id: 'connecting', label: 'Connect' },
    { id: 'llms', label: 'AI Models' },
    { id: 'cloud', label: 'Cloud' },
    { id: 'detail', label: 'Detail' },
  ];

  return (
    <div
      className={`fixed top-0 right-0 h-full w-full max-w-xl bg-white shadow-2xl flex flex-col z-40 transition-transform duration-300 ${visible ? 'translate-x-0' : 'translate-x-full'}`}
      style={{ borderLeft: '1px solid #e5e7eb' }}
    >
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Marketplace Guide</h2>
            <p className="text-xs text-gray-500">Connect tools, AI models & services</p>
          </div>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg">
            <X size={18} />
          </button>
        </div>
        <div className="flex gap-0 overflow-x-auto mt-3 border-b border-gray-200 -mb-px">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 ${
                activeTab === tab.id ? 'border-gray-900 text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* TOC */}
        {activeTab === 'toc' && (
          <div className="p-4">
            <h1 className="text-lg font-bold text-gray-900 mb-3">Table of Contents</h1>
            <div className="space-y-0.5">
              {[
                { tab: 'overview', label: '1. Overview' },
                { tab: 'categories', label: '2. Categories' },
                { tab: 'connecting', label: '3. Connecting' },
                { tab: 'llms', label: '4. AI Models (BYOK)' },
                { tab: 'cloud', label: '5. Cloud Storage' },
                { tab: 'detail', label: '6. Detail View' },
              ].map(item => (
                <button key={item.tab} onClick={() => setActiveTab(item.tab as TabId)} className="w-full text-left px-2 py-1.5 text-sm text-blue-600 hover:underline">
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Overview */}
        {activeTab === 'overview' && (
          <div className="p-4 space-y-4">
            <div className="pb-3 border-b border-gray-200">
              <h1 className="text-base font-bold text-gray-900">Marketplace</h1>
              <p className="text-xs text-gray-600 mt-1">Connect external tools, AI models, cloud storage, and services.</p>
            </div>

            <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
              <h3 className="text-xs font-semibold text-gray-900 mb-2">Key Features</h3>
              <ul className="space-y-1 text-xs text-gray-700">
                <li>• <strong>BYOK:</strong> Use your own API keys for AI models</li>
                <li>• <strong>OAuth:</strong> Securely connect cloud storage</li>
                <li>• <strong>Categories:</strong> Cloud, Database, AI, Communication</li>
                <li>• <strong>Status:</strong> Connected, Disconnected, Coming Soon</li>
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-gray-900">Page Layout</h3>
              <div className="grid grid-cols-3 gap-2">
                <div className="p-2 bg-white border border-gray-200 rounded text-center">
                  <Search size={14} className="mx-auto text-gray-500 mb-1" />
                  <span className="text-xs text-gray-600">Search</span>
                </div>
                <div className="p-2 bg-white border border-gray-200 rounded text-center">
                  <Plug size={14} className="mx-auto text-gray-500 mb-1" />
                  <span className="text-xs text-gray-600">Tabs</span>
                </div>
                <div className="p-2 bg-white border border-gray-200 rounded text-center">
                  <FileText size={14} className="mx-auto text-gray-500 mb-1" />
                  <span className="text-xs text-gray-600">Cards</span>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-xs font-semibold text-gray-900 mb-2">Status Badges</h3>
              <div className="flex gap-2">
                <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-xs font-medium text-emerald-700 border border-emerald-100 flex items-center gap-1">
                  <Check size={10} /> Active
                </span>
                <span className="px-2 py-0.5 rounded-full bg-gray-100 text-xs font-medium text-gray-600">Disconnected</span>
                <span className="px-2 py-0.5 rounded-full bg-gray-100 text-xs font-medium text-gray-500">Soon</span>
              </div>
            </div>
          </div>
        )}

        {/* Categories */}
        {activeTab === 'categories' && (
          <div className="p-4 space-y-3">
            <h2 className="text-base font-bold text-gray-900">Categories</h2>
            <div className="space-y-2">
              {categories.map((cat) => {
                const Icon = cat.icon;
                return (
                  <div key={cat.id} className="p-2.5 bg-white border border-gray-200 rounded-lg flex items-center gap-2.5">
                    <div className="p-1.5 bg-blue-50 rounded">
                      <Icon size={14} className="text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-sm text-gray-900">{cat.name}</span>
                        <span className="text-xs text-gray-400">{cat.count}</span>
                      </div>
                      <p className="text-xs text-gray-500 truncate">{cat.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
              <h3 className="text-xs font-semibold text-gray-900 mb-2">Available In</h3>
              <div className="grid grid-cols-2 gap-1.5 text-xs">
                <div className="flex items-center gap-1.5"><MessageSquare size={12} className="text-gray-400" /> Chat</div>
                <div className="flex items-center gap-1.5"><ListTodo size={12} className="text-gray-400" /> Tasks</div>
                <div className="flex items-center gap-1.5"><BarChart3 size={12} className="text-gray-400" /> Analysis</div>
                <div className="flex items-center gap-1.5"><FileSearch size={12} className="text-gray-400" /> Search</div>
              </div>
            </div>
          </div>
        )}

        {/* Connecting */}
        {activeTab === 'connecting' && (
          <div className="p-4 space-y-3">
            <div className="flex gap-1.5 pb-3 border-b border-gray-200">
              {(['oauth', 'apikey', 'status'] as const).map(sec => (
                <button
                  key={sec}
                  onClick={() => setConnectSection(sec)}
                  className={`px-2.5 py-1 text-xs font-medium rounded ${
                    connectSection === sec ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {sec === 'oauth' ? 'OAuth' : sec === 'apikey' ? 'API Keys' : 'Status'}
                </button>
              ))}
            </div>

            {connectSection === 'oauth' && (
              <div className="space-y-2">
                <h2 className="text-sm font-bold text-gray-900">OAuth 2.0 Flow</h2>
                <p className="text-xs text-gray-600">Cloud storage uses OAuth for secure authentication.</p>
                <div className="space-y-1.5">
                  {['Click Connect', 'Popup opens', 'Authorize access', 'Connected!'].map((step, i) => (
                    <div key={i} className="flex items-center gap-2 p-2 bg-white border border-gray-200 rounded">
                      <span className="w-5 h-5 rounded-full bg-blue-100 text-xs font-bold text-blue-600 flex items-center justify-center">{i+1}</span>
                      <span className="text-xs text-gray-700">{step}</span>
                    </div>
                  ))}
                </div>
                <div className="p-2 bg-emerald-50 border border-emerald-200 rounded flex items-center gap-2">
                  <Shield size={12} className="text-emerald-600" />
                  <p className="text-xs text-emerald-800">Tokens encrypted. Sentry never sees your password.</p>
                </div>
              </div>
            )}

            {connectSection === 'apikey' && (
              <div className="space-y-2">
                <h2 className="text-sm font-bold text-gray-900">API Keys (BYOK)</h2>
                <div className="p-2.5 bg-white border border-gray-200 rounded">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Key size={12} className="text-gray-500" />
                    <span className="text-xs font-semibold text-gray-900">Get API Key</span>
                  </div>
                  <div className="space-y-0.5 text-xs">
                    <div className="flex items-center gap-1.5">
                      <img src={gptLogo} alt="" className="w-3.5 h-3.5" />
                      <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">OpenAI</a>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <img src={claudeLogo} alt="" className="w-3.5 h-3.5" />
                      <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Anthropic</a>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <img src={geminiLogo} alt="" className="w-3.5 h-3.5" />
                      <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Google</a>
                    </div>
                  </div>
                </div>
                <div className="p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                  Keys encrypted. Usage billed by provider.
                </div>
              </div>
            )}

            {connectSection === 'status' && (
              <div className="space-y-2">
                <h2 className="text-sm font-bold text-gray-900">Managing Status</h2>
                {[
                  { icon: RefreshCw, label: 'Reconnect', desc: 'Refresh expired tokens' },
                  { icon: Settings, label: 'Configure', desc: 'Adjust settings' },
                  { icon: Link2, label: 'Disconnect', desc: 'Remove integration', red: true },
                ].map((item, i) => (
                  <div key={i} className="p-2.5 bg-white border border-gray-200 rounded flex items-center gap-2">
                    <item.icon size={14} className={item.red ? 'text-red-500' : 'text-gray-500'} />
                    <div>
                      <span className="text-xs font-medium text-gray-900">{item.label}</span>
                      <span className="text-xs text-gray-500 ml-1.5">{item.desc}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* AI Models */}
        {activeTab === 'llms' && (
          <div className="p-4 space-y-3">
            <div className="pb-2 border-b border-gray-200">
              <h2 className="text-base font-bold text-gray-900">AI Models (BYOK)</h2>
              <p className="text-xs text-gray-600">Bring Your Own Key for premium models.</p>
            </div>

            {(() => {
              const totalPages = Math.ceil(llmModels.length / 7);
              const startIdx = (llmPage - 1) * 7;
              const displayModels = llmModels.slice(startIdx, startIdx + 7);

              return (
                <>
                  <div className="space-y-1.5">
                    {displayModels.map((model, idx) => (
                      <div key={idx} className="p-2 bg-white border border-gray-200 rounded flex items-center gap-2">
                        <img src={model.logo} alt="" className="w-6 h-6 object-contain" />
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-medium text-gray-900">{model.name}</span>
                          <span className="text-xs text-gray-400 ml-1.5">{model.context}</span>
                        </div>
                        <span className="text-xs text-gray-400">{model.provider}</span>
                      </div>
                    ))}
                  </div>
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between pt-2 text-xs">
                      <button onClick={() => setLlmPage(p => Math.max(1, p - 1))} disabled={llmPage === 1} className="text-gray-500 hover:text-gray-700 disabled:text-gray-300">Prev</button>
                      <span className="text-gray-400">{llmPage}/{totalPages}</span>
                      <button onClick={() => setLlmPage(p => Math.min(totalPages, p + 1))} disabled={llmPage === totalPages} className="text-gray-500 hover:text-gray-700 disabled:text-gray-300">Next</button>
                    </div>
                  )}
                </>
              );
            })()}

            <div className="p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800">
              <strong>Tip:</strong> Reasoning models for complex tasks, fast models for quick responses.
            </div>
          </div>
        )}

        {/* Cloud */}
        {activeTab === 'cloud' && (
          <div className="p-4 space-y-3">
            <div className="pb-2 border-b border-gray-200">
              <h2 className="text-base font-bold text-gray-900">Cloud Storage</h2>
              <p className="text-xs text-gray-600">Connect to access and analyze documents.</p>
            </div>

            {(() => {
              const totalPages = Math.ceil(cloudIntegrations.length / 4);
              const startIdx = (cloudPage - 1) * 4;
              const displayIntegrations = cloudIntegrations.slice(startIdx, startIdx + 4);

              return (
                <>
                  <div className="space-y-2">
                    {displayIntegrations.map((int, idx) => (
                      <div key={idx} className="p-2.5 bg-white border border-gray-200 rounded flex items-center gap-2.5">
                        <img src={int.logo} alt="" className="w-7 h-7 object-contain" />
                        <div className="flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-medium text-gray-900">{int.name}</span>
                            <span className={`text-xs px-1.5 py-0.5 rounded ${int.status === 'Available' ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                              {int.status}
                            </span>
                          </div>
                          <span className="text-xs text-gray-400">{int.auth}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between pt-2 text-xs">
                      <button onClick={() => setCloudPage(p => Math.max(1, p - 1))} disabled={cloudPage === 1} className="text-gray-500 hover:text-gray-700 disabled:text-gray-300">Prev</button>
                      <span className="text-gray-400">{cloudPage}/{totalPages}</span>
                      <button onClick={() => setCloudPage(p => Math.min(totalPages, p + 1))} disabled={cloudPage === totalPages} className="text-gray-500 hover:text-gray-700 disabled:text-gray-300">Next</button>
                    </div>
                  )}
                </>
              );
            })()}

            <div className="bg-gray-50 rounded p-2.5 border border-gray-200">
              <h3 className="text-xs font-semibold text-gray-900 mb-1.5">Supported Files</h3>
              <div className="flex flex-wrap gap-1.5">
                {['docx', 'xlsx', 'pptx', 'pdf', 'txt', 'csv'].map(type => (
                  <span key={type} className="text-xs text-gray-500 bg-white px-1.5 py-0.5 rounded border border-gray-200 uppercase">.{type}</span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Detail View */}
        {activeTab === 'detail' && (
          <div className="p-4 space-y-3">
            <h2 className="text-base font-bold text-gray-900">Detail View</h2>
            <p className="text-xs text-gray-600">Click any card to view integration details.</p>

            <div className="space-y-2">
              {[
                { title: 'Header', items: ['Logo & name', 'Status badge', 'Connect/Disconnect'] },
                { title: 'Capabilities', items: ['Feature list with checkmarks'] },
                { title: 'Supported Files', items: ['File type badges (docx, pdf, etc.)'] },
                { title: 'Available In', items: ['Chat, Tasks, Analysis, Search'] },
                { title: 'Sidebar', items: ['Category, auth type, docs, support'] },
              ].map((section, i) => (
                <div key={i} className="p-2.5 bg-white border border-gray-200 rounded">
                  <h3 className="text-xs font-semibold text-gray-900 mb-1">{section.title}</h3>
                  <ul className="text-xs text-gray-600 space-y-0.5">
                    {section.items.map((item, j) => <li key={j}>• {item}</li>)}
                  </ul>
                </div>
              ))}
            </div>

            <div className="p-2 bg-emerald-50 border border-emerald-200 rounded flex items-center gap-2">
              <Shield size={12} className="text-emerald-600" />
              <p className="text-xs text-emerald-800">All data encrypted. AES-256 credential storage.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MarketplaceGuidePanel;
