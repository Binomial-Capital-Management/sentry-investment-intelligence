/**
 * Post Mortem Guide Panel - Slide-in documentation panel from the right
 * Professional institutional finance design matching ChatGuidePanel style
 */

import React, { useState, useEffect } from 'react';
import {
  X, Activity, MessageSquare, Plus, Trash2, Pencil, Search,
  Settings, ArrowLeft, Check, TrendingUp, TrendingDown, BarChart3,
  FileText, Presentation, Sheet, Copy, Globe, Upload, Cloud,
  Database, ChevronRight, ChevronDown, Folder, Calendar, Clock,
  Target, Percent, DollarSign, Scale, Sparkles, Brain, Code,
  Terminal, Server, Wrench, Filter, ChevronLeft, Loader2,
} from 'lucide-react';

// Import model logos
import gptLogo from '@/assets/model-logos/gpt-logo.png';
import claudeLogo from '@/assets/model-logos/claude-logo.svg.png';
import geminiLogo from '@/assets/model-logos/gemini-logo.png';
import grokLogo from '@/assets/model-logos/grok.png';

interface PostMortemGuidePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabId = 'toc' | 'overview' | 'creating' | 'detail' | 'analysis' | 'metrics' | 'exports';

// MCP Servers used by PostMortemAgent
const mcpServers = [
  { name: 'FMPMarketDataServer', purpose: 'Stock quotes, historical data, financials, technical indicators' },
  { name: 'FMPAlternativesServer', purpose: 'ETF/fund context, sector benchmarks, commodity data' },
  { name: 'PolygonOptionsFuturesServer', purpose: 'Options chains, Greeks, IV surfaces, contract snapshots' },
  { name: 'FMPTradeFlowServer', purpose: 'ETF holdings, institutional ownership, flow data' },
  { name: 'EconomicDataServer', purpose: 'FRED macro indicators for regime context (on request)' },
];

// Tools available to PostMortemAgent
const agentTools = [
  { name: 'CodeInterpreterTool', desc: 'Python sandbox for multi-trade stats, expectancy, drawdown series, distribution plots, regressions' },
  { name: 'read_file_content', desc: 'Load uploaded trade logs, journals, and fill data' },
  { name: 'search_file_chunks_tool', desc: 'Semantic search across uploaded notes and briefs' },
  { name: 'web_search', desc: 'Internet research (only when explicitly requested and MCP data insufficient)' },
];

// Model categories
const modelCategories = [
  {
    name: 'Reasoning',
    models: [
      { name: 'GPT-6 Astra', logo: gptLogo, context: '1M' },
      { name: 'Claude Fable 5.1', logo: claudeLogo, context: '1M' },
      { name: 'Claude Opus 5.5', logo: claudeLogo, context: '1M' },
      { name: 'Gemini 4 Argon', logo: geminiLogo, context: '1M' },
      { name: 'Grok 4.7', logo: grokLogo, context: '500K' },
    ],
  },
  {
    name: 'Standard',
    models: [
      { name: 'GPT-6.1 Sol', logo: gptLogo, context: '1M' },
      { name: 'Claude Sonnet 5.5', logo: claudeLogo, context: '1M' },
      { name: 'Gemini 3.8 Flash', logo: geminiLogo, context: '1M' },
    ],
  },
  {
    name: 'Fast',
    models: [
      { name: 'GPT-6 Luna', logo: gptLogo, context: '1M' },
      { name: 'Claude Haiku 4.5', logo: claudeLogo, context: '200K' },
      { name: 'Grok 4.20 Fast', logo: grokLogo, context: '1M' },
    ],
  },
];

// Metrics definitions
const metricsInfo = [
  { name: 'Total P&L', desc: 'Sum of realized gains/losses across all SELL transactions in the post-mortem', icon: DollarSign },
  { name: 'Win Rate', desc: 'Percentage of profitable trades (wins / total closed trades)', icon: Target },
  { name: 'Payoff Ratio', desc: 'Average winning trade / Average losing trade. Higher is better', icon: Scale },
  { name: 'Expectancy', desc: '(Win Rate × Avg Win) - (Loss Rate × Avg Loss). Expected value per trade', icon: TrendingUp },
  { name: 'Max Drawdown', desc: 'Largest peak-to-trough decline in cumulative P&L', icon: TrendingDown },
];

export const PostMortemGuidePanel: React.FC<PostMortemGuidePanelProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabId>('toc');
  const [serverPage, setServerPage] = useState(1);
  const [toolsPage, setToolsPage] = useState(1);
  const [modelsPage, setModelsPage] = useState(1);
  const [creatingSection, setCreatingSection] = useState<'select' | 'filters' | 'preview'>('select');
  const [detailSection, setDetailSection] = useState<'header' | 'metrics' | 'table' | 'actions'>('header');
  const [analysisSection, setAnalysisSection] = useState<'chat' | 'threads' | 'context' | 'tools'>('chat');
  const ITEMS_PER_PAGE = 4;

  // Animate in
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => setVisible(true), 10);
    } else {
      setVisible(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const tabs: { id: TabId; label: string }[] = [
    { id: 'toc', label: 'Contents' },
    { id: 'overview', label: 'Overview' },
    { id: 'creating', label: 'Creating' },
    { id: 'detail', label: 'Detail View' },
    { id: 'analysis', label: 'Analysis' },
    { id: 'metrics', label: 'Metrics' },
    { id: 'exports', label: 'Exports' },
  ];

  return (
    <div
      className={`fixed top-0 right-0 h-full w-full max-w-xl bg-white shadow-2xl flex flex-col z-40 transition-transform duration-300 ease-out ${visible ? 'translate-x-0' : 'translate-x-full'}`}
      style={{ borderLeft: '1px solid #e5e7eb' }}
    >
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Post Mortem Documentation</h2>
            <p className="text-sm text-gray-500 mt-0.5">Trade review, analysis, and pattern detection</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mt-4">
          <div className="flex gap-0 overflow-x-auto no-scrollbar">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-xs font-medium transition-all whitespace-nowrap border-b-2 ${
                  activeTab === tab.id
                    ? 'border-gray-900 text-gray-900'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* TOC Tab */}
        {activeTab === 'toc' && (
          <div className="p-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">Table of Contents</h1>

            <div className="space-y-1">
              <button
                onClick={() => setActiveTab('overview')}
                className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
              >
                1. Overview
              </button>
              <button
                onClick={() => setActiveTab('creating')}
                className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
              >
                2. Creating Post Mortems
              </button>
              <button
                onClick={() => setActiveTab('detail')}
                className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
              >
                3. Detail View
              </button>
              <button
                onClick={() => setActiveTab('analysis')}
                className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
              >
                4. AI Analysis
              </button>
              <button
                onClick={() => setActiveTab('metrics')}
                className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
              >
                5. Metrics Reference
              </button>
              <button
                onClick={() => setActiveTab('exports')}
                className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
              >
                6. Exports
              </button>
            </div>
          </div>
        )}

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="p-6 space-y-6">
            <div className="pb-4 border-b border-gray-200">
              <h1 className="text-xl font-bold text-gray-900 mb-2">Post Mortems</h1>
              <p className="text-sm text-gray-600">
                Review completed trades, identify patterns, and improve your trading process through AI-powered analysis.
              </p>
            </div>

            <section>
              <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-4">What is a Post Mortem?</h2>
              <p className="text-sm text-gray-700 leading-relaxed mb-4">
                A Post Mortem is a structured review of completed trades from your portfolios. By grouping
                related transactions together, you can analyze trading decisions, identify behavioral
                patterns, and extract actionable lessons to improve future performance.
              </p>

              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">Key Features</h3>
                <ul className="space-y-2 text-sm text-gray-700">
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span><strong>Transaction Selection:</strong> Select SELL trades from any portfolio to review</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span><strong>AI Analysis:</strong> Specialized agent for trade reconstruction and pattern detection</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span><strong>Metrics Dashboard:</strong> Win rate, P&L, payoff ratio, and more</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span><strong>Multiple Threads:</strong> Maintain separate conversation threads per post-mortem</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span><strong>Export Options:</strong> Generate PDF, PowerPoint, or Excel reports</span>
                  </li>
                </ul>
              </div>
            </section>

            <section>
              <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-4">Workflow</h2>
              <div className="space-y-3">
                <div className="flex items-start gap-3 p-3 bg-white border border-gray-200 rounded-lg">
                  <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-600">1</div>
                  <div>
                    <div className="font-medium text-sm text-gray-900">Create Post Mortem</div>
                    <div className="text-xs text-gray-600">Select completed trades from your portfolios</div>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-white border border-gray-200 rounded-lg">
                  <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-600">2</div>
                  <div>
                    <div className="font-medium text-sm text-gray-900">Review Metrics</div>
                    <div className="text-xs text-gray-600">View summary statistics and individual trades</div>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-white border border-gray-200 rounded-lg">
                  <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-600">3</div>
                  <div>
                    <div className="font-medium text-sm text-gray-900">Analyze with AI</div>
                    <div className="text-xs text-gray-600">Get patterns, rules, and improvement experiments</div>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-white border border-gray-200 rounded-lg">
                  <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-600">4</div>
                  <div>
                    <div className="font-medium text-sm text-gray-900">Export & Share</div>
                    <div className="text-xs text-gray-600">Generate reports in PDF, PPTX, or Excel format</div>
                  </div>
                </div>
              </div>
            </section>
          </div>
        )}

        {/* Creating Tab */}
        {activeTab === 'creating' && (
          <div className="p-6 space-y-5">
            {/* Sub-navigation */}
            <div className="flex flex-wrap gap-2 pb-4 border-b border-gray-200">
              <button
                onClick={() => setCreatingSection('select')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  creatingSection === 'select'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Selection Modal
              </button>
              <button
                onClick={() => setCreatingSection('filters')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  creatingSection === 'filters'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Filters
              </button>
              <button
                onClick={() => setCreatingSection('preview')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  creatingSection === 'preview'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Preview & Save
              </button>
            </div>

            {creatingSection === 'select' && (
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <h2 className="text-lg font-bold text-gray-900">Transaction Selection Modal</h2>
                  <button
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg shadow-sm"
                    style={{ backgroundColor: '#0051cc', color: 'white' }}
                  >
                    <Plus className="h-4 w-4" />
                    Create Post Mortem
                  </button>
                </div>

                <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                  <p className="text-sm text-gray-700">
                    Click "Create Post Mortem" to open the transaction selection modal. This modal allows you
                    to browse and select completed trades from all your portfolios.
                  </p>

                  <div className="space-y-2.5 text-sm text-gray-700">
                    <div className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>Portfolio Filter:</strong> Select specific portfolios or view all</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>Transaction Types:</strong> SELL transactions show realized P&L</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>Multi-select:</strong> Check individual trades or select all</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span><strong>Search:</strong> Filter by ticker symbol</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {creatingSection === 'filters' && (
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <h2 className="text-lg font-bold text-gray-900">Available Filters</h2>
                  <Filter className="w-5 h-5 text-gray-500" />
                </div>

                <div className="space-y-3">
                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Folder size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Portfolio</h3>
                    </div>
                    <p className="text-sm text-gray-600">Filter by one or more portfolios. Select "All" to include transactions from every portfolio.</p>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Calendar size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Date Range</h3>
                    </div>
                    <p className="text-sm text-gray-600">Filter transactions by date range (from/to). Useful for reviewing specific time periods.</p>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Search size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Ticker</h3>
                    </div>
                    <p className="text-sm text-gray-600">Search for specific ticker symbols. Supports partial matching.</p>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Database size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Source</h3>
                    </div>
                    <p className="text-sm text-gray-600">Filter by transaction source: All, Manual, or IBKR (Interactive Brokers sync).</p>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <DollarSign size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Minimum Value</h3>
                    </div>
                    <p className="text-sm text-gray-600">Filter out small transactions by setting a minimum trade value.</p>
                  </div>
                </div>
              </div>
            )}

            {creatingSection === 'preview' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">Preview & Save</h2>

                <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                  <p className="text-sm text-gray-700">
                    Before saving, review the preview metrics for your selected transactions.
                  </p>

                  <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">Preview Metrics</h3>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="p-2 bg-white rounded border border-gray-200">
                        <div className="text-xs text-gray-500">Total P&L</div>
                        <div className="font-bold text-green-600">+$X,XXX</div>
                      </div>
                      <div className="p-2 bg-white rounded border border-gray-200">
                        <div className="text-xs text-gray-500">Win Rate</div>
                        <div className="font-bold text-gray-900">XX%</div>
                      </div>
                      <div className="p-2 bg-white rounded border border-gray-200">
                        <div className="text-xs text-gray-500">Avg Win</div>
                        <div className="font-bold text-green-600">+$XXX</div>
                      </div>
                      <div className="p-2 bg-white rounded border border-gray-200">
                        <div className="text-xs text-gray-500">Avg Loss</div>
                        <div className="font-bold text-red-600">-$XXX</div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <Sparkles size={16} className="text-blue-600" />
                    <p className="text-xs text-gray-700">
                      Once saved, you can analyze the post-mortem with AI to identify patterns and get improvement recommendations.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Detail View Tab */}
        {activeTab === 'detail' && (
          <div className="p-6 space-y-5">
            {/* Sub-navigation */}
            <div className="flex flex-wrap gap-2 pb-4 border-b border-gray-200">
              <button
                onClick={() => setDetailSection('header')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  detailSection === 'header'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Header
              </button>
              <button
                onClick={() => setDetailSection('metrics')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  detailSection === 'metrics'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Summary Cards
              </button>
              <button
                onClick={() => setDetailSection('table')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  detailSection === 'table'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Transactions Table
              </button>
              <button
                onClick={() => setDetailSection('actions')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  detailSection === 'actions'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Actions
              </button>
            </div>

            {detailSection === 'header' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">Header Section</h2>

                <div className="space-y-3">
                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <ArrowLeft size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Back Button</h3>
                    </div>
                    <p className="text-sm text-gray-600">Navigate back to the post-mortems list.</p>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Pencil size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Editable Title</h3>
                    </div>
                    <p className="text-sm text-gray-600">Click the pencil icon to rename your post-mortem. Press Enter to save, Escape to cancel.</p>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Metadata</h3>
                    </div>
                    <p className="text-sm text-gray-600">Shows trade count and creation date below the title.</p>
                  </div>
                </div>
              </div>
            )}

            {detailSection === 'metrics' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">Summary Metric Cards</h2>
                <p className="text-sm text-gray-600">Five summary cards display key performance metrics:</p>

                <div className="grid grid-cols-1 gap-3">
                  {metricsInfo.slice(0, 4).map((metric, idx) => {
                    const Icon = metric.icon;
                    return (
                      <div key={idx} className="p-4 bg-white border border-gray-200 rounded-lg">
                        <div className="flex items-center gap-2 mb-1">
                          <Icon size={16} className="text-gray-600" />
                          <h3 className="font-semibold text-sm text-gray-900">{metric.name}</h3>
                        </div>
                        <p className="text-sm text-gray-600">{metric.desc}</p>
                      </div>
                    );
                  })}
                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-1">
                      <Percent size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Win Rate</h3>
                    </div>
                    <p className="text-sm text-gray-600">Displayed with a visual progress bar indicator.</p>
                  </div>
                </div>
              </div>
            )}

            {detailSection === 'table' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">Transactions Table</h2>

                <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                  <p className="text-sm text-gray-700">
                    The transactions table shows all trades included in this post-mortem with the following columns:
                  </p>

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm border-collapse">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-semibold text-gray-700">Column</th>
                          <th className="px-3 py-2 text-left text-xs font-semibold text-gray-700">Description</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        <tr><td className="px-3 py-2 font-medium">Portfolio</td><td className="px-3 py-2 text-gray-600">Source portfolio name</td></tr>
                        <tr><td className="px-3 py-2 font-medium">Date</td><td className="px-3 py-2 text-gray-600">Transaction date</td></tr>
                        <tr><td className="px-3 py-2 font-medium">Ticker</td><td className="px-3 py-2 text-gray-600">Stock/ETF symbol</td></tr>
                        <tr><td className="px-3 py-2 font-medium">Type</td><td className="px-3 py-2 text-gray-600">BUY or SELL badge</td></tr>
                        <tr><td className="px-3 py-2 font-medium">Qty</td><td className="px-3 py-2 text-gray-600">Number of shares</td></tr>
                        <tr><td className="px-3 py-2 font-medium">Price</td><td className="px-3 py-2 text-gray-600">Execution price</td></tr>
                        <tr><td className="px-3 py-2 font-medium">Value</td><td className="px-3 py-2 text-gray-600">Total transaction value</td></tr>
                        <tr><td className="px-3 py-2 font-medium">Realized</td><td className="px-3 py-2 text-gray-600">P&L for SELL trades (green/red)</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {detailSection === 'actions' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">Action Buttons</h2>

                <div className="space-y-3">
                  <div className="p-4 bg-white border border-gray-200 rounded-lg flex items-start gap-3">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-red-50 border border-red-200 rounded text-sm">
                      <Trash2 size={14} className="text-red-600" />
                      <span className="text-red-700 font-medium">Delete</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-gray-700">Permanently delete this post-mortem and all associated chat threads.</p>
                    </div>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg flex items-start gap-3">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-300 rounded text-sm">
                      <Settings size={14} className="text-gray-600" />
                      <span className="text-gray-700 font-medium">Manage Trades</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-gray-700">Add or remove transactions from this post-mortem.</p>
                    </div>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg flex items-start gap-3">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded text-sm" style={{ backgroundColor: '#0051cc', color: 'white' }}>
                      <MessageSquare size={14} />
                      <span className="font-medium">Analyze Trades</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-gray-700">Open the AI analysis panel to get insights on your trades.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Analysis Tab */}
        {activeTab === 'analysis' && (
          <div className="p-6 space-y-5">
            {/* Sub-navigation */}
            <div className="flex flex-wrap gap-2 pb-4 border-b border-gray-200">
              <button
                onClick={() => setAnalysisSection('chat')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  analysisSection === 'chat'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Chat Panel
              </button>
              <button
                onClick={() => setAnalysisSection('threads')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  analysisSection === 'threads'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Threads
              </button>
              <button
                onClick={() => setAnalysisSection('context')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  analysisSection === 'context'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Context Controls
              </button>
              <button
                onClick={() => setAnalysisSection('tools')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  analysisSection === 'tools'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Agent Tools
              </button>
            </div>

            {analysisSection === 'chat' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">AI Analysis Chat Panel</h2>

                <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                  <p className="text-sm text-gray-700">
                    The analysis panel is a resizable sidebar that provides conversational AI analysis
                    of your trades using the specialized Post-Mortem Agent.
                  </p>

                  {/* Panel Header Controls */}
                  <div className="border-l-4 border-gray-300 pl-3">
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">Header Controls</h3>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                        <MessageSquare size={12} className="text-gray-500" />
                        <span>Thread Selector</span>
                      </div>
                      <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                        <Plus size={12} className="text-gray-500" />
                        <span>New Thread</span>
                      </div>
                      <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                        <Sparkles size={12} className="text-gray-500" />
                        <span>Help Guide</span>
                      </div>
                      <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                        <X size={12} className="text-gray-500" />
                        <span>Close Panel</span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="border-l-4 border-blue-500 pl-3">
                      <h3 className="text-sm font-semibold text-gray-900">Resizable Panel</h3>
                      <p className="text-xs text-gray-600 mt-1">Drag the left edge to resize. Range: 300px to 90% of screen width. Double-click to maximize/restore.</p>
                    </div>

                    <div className="border-l-4 border-blue-500 pl-3">
                      <h3 className="text-sm font-semibold text-gray-900">Streaming Responses</h3>
                      <p className="text-xs text-gray-600 mt-1">See reasoning, tool calls, and content as they stream in real-time with typing indicators.</p>
                    </div>

                    <div className="border-l-4 border-blue-500 pl-3">
                      <h3 className="text-sm font-semibold text-gray-900">Markdown Rendering</h3>
                      <p className="text-xs text-gray-600 mt-1">Responses render with syntax highlighting, tables, code blocks, and formatted text.</p>
                    </div>

                    <div className="border-l-4 border-blue-500 pl-3">
                      <h3 className="text-sm font-semibold text-gray-900">Cancel Analysis</h3>
                      <p className="text-xs text-gray-600 mt-1">Click the stop button to cancel a running analysis mid-stream.</p>
                    </div>
                  </div>
                </div>

                {/* Input Area */}
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Input Area</h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                      <Database size={12} className="text-blue-500" />
                      <span className="flex-1">Transaction selector - choose trades for context</span>
                      <span className="text-gray-400 bg-gray-200 px-1.5 rounded">badge</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                      <Upload size={12} className="text-gray-500" />
                      <span>Upload files (drag & drop supported)</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                      <Cloud size={12} className="text-gray-500" />
                      <span>Cloud storage (GDrive, OneDrive, SharePoint)</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                      <Globe size={12} className="text-gray-500" />
                      <span>Web search toggle (when MCP data insufficient)</span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">Press Enter to send, Shift+Enter for new line</p>
                </div>

                {/* Message Actions */}
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Message Actions</h3>
                  <p className="text-xs text-gray-600 mb-2">Hover over any AI response to reveal export options:</p>
                  <div className="flex flex-wrap gap-2">
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-100 rounded text-xs">
                      <Copy size={12} /> Copy
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-100 rounded text-xs">
                      <FileText size={12} /> PDF
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-100 rounded text-xs">
                      <Presentation size={12} /> PPTX
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-100 rounded text-xs">
                      <Sheet size={12} /> Workbook
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-100 rounded text-xs">
                      <Pencil size={12} /> Style
                    </div>
                  </div>
                </div>

                {/* Agent Description */}
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Brain size={18} className="text-blue-600" />
                    <h3 className="font-semibold text-sm text-gray-900">Post-Mortem Analyst</h3>
                  </div>
                  <p className="text-xs text-gray-600 mb-3">
                    Specialized agent for forensic trade analysis with a senior risk reviewer mindset.
                    Focuses on process over outcome and patterns over one-offs.
                  </p>
                  <div className="text-xs text-gray-700">
                    <strong>Core Objectives:</strong>
                    <ul className="mt-1 space-y-0.5 ml-4 list-disc">
                      <li>Reconstruct trades: timing, sizing, execution quality</li>
                      <li>Quantify outcomes: PnL, payoff ratio, hit rate, drawdowns</li>
                      <li>Detect patterns: timing bias, vol/regime sensitivity, discipline</li>
                      <li>Deliver 3-7 actionable rules with thresholds</li>
                      <li>Define 2-3 experiments to validate improvements</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {analysisSection === 'threads' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">Conversation Threads</h2>

                <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                  <p className="text-sm text-gray-700">
                    Each post-mortem can have multiple conversation threads, allowing you to explore
                    different aspects of your trades separately.
                  </p>

                  <div className="space-y-3">
                    <div className="p-3 bg-gray-50 rounded-lg flex items-center gap-3">
                      <MessageSquare size={16} className="text-gray-600" />
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-gray-900">Thread Selector</h3>
                        <p className="text-xs text-gray-600">Click the chat icon in the header to switch between threads.</p>
                      </div>
                    </div>

                    <div className="p-3 bg-gray-50 rounded-lg flex items-center gap-3">
                      <Plus size={16} className="text-gray-600" />
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-gray-900">New Thread</h3>
                        <p className="text-xs text-gray-600">Click the + button to start a fresh conversation.</p>
                      </div>
                    </div>

                    <div className="p-3 bg-gray-50 rounded-lg flex items-center gap-3">
                      <Trash2 size={16} className="text-gray-600" />
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-gray-900">Delete Thread</h3>
                        <p className="text-xs text-gray-600">Hover over a thread in the menu to reveal the delete button.</p>
                      </div>
                    </div>
                  </div>

                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-gray-700">
                    <strong>Tip:</strong> Use separate threads for different analysis angles—one for timing patterns,
                    another for sizing issues, etc.
                  </div>
                </div>
              </div>
            )}

            {analysisSection === 'context' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">Context Controls</h2>

                <div className="space-y-3">
                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Database size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Transaction Selector</h3>
                    </div>
                    <p className="text-sm text-gray-600">Select which transactions to include in the analysis context. A badge shows the count.</p>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Globe size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Web Search</h3>
                    </div>
                    <p className="text-sm text-gray-600">Toggle to force web search for news and external context (only when MCP data is insufficient).</p>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Cloud size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">Cloud Storage</h3>
                    </div>
                    <p className="text-sm text-gray-600">Attach files from Google Drive, OneDrive, or SharePoint for additional context.</p>
                    <div className="flex gap-2 mt-2">
                      <img src="/connector-logos/google-drive.png" alt="Google Drive" className="w-5 h-5 object-contain" />
                      <img src="/connector-logos/one-drive.png" alt="OneDrive" className="w-5 h-5 object-contain" />
                      <img src="/connector-logos/sharepoint-logo.png" alt="SharePoint" className="w-5 h-5 object-contain" />
                    </div>
                  </div>

                  <div className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Upload size={16} className="text-gray-600" />
                      <h3 className="font-semibold text-sm text-gray-900">File Upload</h3>
                    </div>
                    <p className="text-sm text-gray-600">Upload trade logs, journals, or notes. Supports PDF, CSV, Excel, images. Drag and drop supported.</p>
                  </div>
                </div>
              </div>
            )}

            {analysisSection === 'tools' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-gray-900">Agent Tools & Data Sources</h2>

                {/* MCP Servers */}
                <div className="bg-white rounded-lg border border-gray-200 p-4">
                  <h3 className="text-xs font-bold text-gray-900 mb-3 uppercase tracking-wide">
                    MCP Data Servers ({mcpServers.length})
                  </h3>

                  {(() => {
                    const totalPages = Math.ceil(mcpServers.length / ITEMS_PER_PAGE);
                    const startIdx = (serverPage - 1) * ITEMS_PER_PAGE;
                    const paginatedServers = mcpServers.slice(startIdx, startIdx + ITEMS_PER_PAGE);

                    return (
                      <>
                        <div className="space-y-2">
                          {paginatedServers.map((server, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-sm">
                              <Server size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                              <div>
                                <div className="font-medium text-gray-900">{server.name}</div>
                                <div className="text-gray-600 text-xs">{server.purpose}</div>
                              </div>
                            </div>
                          ))}
                        </div>

                        {totalPages > 1 && (
                          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
                            <button
                              onClick={() => setServerPage(p => Math.max(1, p - 1))}
                              disabled={serverPage === 1}
                              className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                            >
                              Previous
                            </button>
                            <span className="text-xs text-gray-500">
                              Page {serverPage} of {totalPages}
                            </span>
                            <button
                              onClick={() => setServerPage(p => Math.min(totalPages, p + 1))}
                              disabled={serverPage === totalPages}
                              className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                            >
                              Next
                            </button>
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>

                {/* Tools */}
                <div className="bg-white rounded-lg border border-gray-200 p-4">
                  <h3 className="text-xs font-bold text-gray-900 mb-3 uppercase tracking-wide">
                    Available Tools ({agentTools.length})
                  </h3>

                  <div className="space-y-2">
                    {agentTools.map((tool, idx) => (
                      <div key={idx} className="flex items-start gap-2 text-sm">
                        <Wrench size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                        <div>
                          <code className="font-medium text-gray-900 text-xs">{tool.name}</code>
                          <div className="text-gray-600 text-xs">{tool.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Metrics Tab */}
        {activeTab === 'metrics' && (
          <div className="p-6 space-y-5">
            <div className="pb-4 border-b border-gray-200">
              <h2 className="text-lg font-bold text-gray-900">Metrics Reference</h2>
              <p className="text-sm text-gray-600 mt-1">
                Understanding the performance metrics used in post-mortem analysis.
              </p>
            </div>

            <div className="space-y-4">
              {metricsInfo.map((metric, idx) => {
                const Icon = metric.icon;
                return (
                  <div key={idx} className="p-4 bg-white border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Icon size={18} className="text-blue-600" />
                      <h3 className="font-semibold text-gray-900">{metric.name}</h3>
                    </div>
                    <p className="text-sm text-gray-700">{metric.desc}</p>
                  </div>
                );
              })}
            </div>

            {/* Formulas */}
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h3 className="text-xs font-bold text-gray-900 mb-3 uppercase tracking-wide">Formulas</h3>
              <div className="space-y-3 text-sm">
                <div>
                  <code className="text-xs font-mono bg-gray-200 px-2 py-1 rounded">Hit Rate = Wins / Total Trades</code>
                </div>
                <div>
                  <code className="text-xs font-mono bg-gray-200 px-2 py-1 rounded">Payoff Ratio = Avg Win / Avg Loss</code>
                </div>
                <div>
                  <code className="text-xs font-mono bg-gray-200 px-2 py-1 rounded">Expectancy = (Hit Rate × Avg Win) - (Loss Rate × Avg Loss)</code>
                </div>
              </div>
            </div>

            {/* Note */}
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-gray-700">
              <strong>Note:</strong> Metrics are calculated from SELL transactions only, as they represent
              realized P&L. BUY transactions are included for context but don't contribute to win/loss calculations.
            </div>
          </div>
        )}

        {/* Exports Tab */}
        {activeTab === 'exports' && (
          <div className="p-6 space-y-5">
            <div className="pb-4 border-b border-gray-200">
              <h2 className="text-lg font-bold text-gray-900">Export Options</h2>
              <p className="text-sm text-gray-600 mt-1">
                Export AI analysis to various formats for sharing and documentation.
              </p>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-white border border-gray-200 rounded-lg flex items-start gap-4">
                <div className="p-2 border border-gray-300 rounded">
                  <Copy size={16} className="text-gray-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-sm text-gray-900">Copy to Clipboard</h3>
                  <p className="text-sm text-gray-600 mt-1">Copy the message content as plain text for pasting anywhere.</p>
                </div>
              </div>

              <div className="p-4 bg-white border border-gray-200 rounded-lg flex items-start gap-4">
                <div className="p-2 border border-gray-300 rounded">
                  <FileText size={16} className="text-gray-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-sm text-gray-900">PDF Export (Gamma)</h3>
                  <p className="text-sm text-gray-600 mt-1">Generate a professionally formatted PDF document via Gamma API. Includes all analysis content with custom styling.</p>
                  <p className="text-xs text-gray-500 mt-2">Processing time: ~30-60 seconds</p>
                </div>
              </div>

              <div className="p-4 bg-white border border-gray-200 rounded-lg flex items-start gap-4">
                <div className="p-2 border border-gray-300 rounded">
                  <Presentation size={16} className="text-gray-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-sm text-gray-900">PowerPoint Export (Gamma)</h3>
                  <p className="text-sm text-gray-600 mt-1">Create a presentation-ready PPTX file. AI structures content into slides with headers and bullet points.</p>
                  <p className="text-xs text-gray-500 mt-2">Processing time: ~30-60 seconds</p>
                </div>
              </div>

              <div className="p-4 bg-white border border-gray-200 rounded-lg flex items-start gap-4">
                <div className="p-2 border border-gray-300 rounded">
                  <Sheet size={16} className="text-gray-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-sm text-gray-900">Excel/CSV Workbook</h3>
                  <p className="text-sm text-gray-600 mt-1">Export data tables and metrics as a ZIP archive containing Excel and CSV files.</p>
                  <p className="text-xs text-gray-500 mt-2">Processing time: ~30-60 seconds</p>
                </div>
              </div>

              <div className="p-4 bg-white border border-gray-200 rounded-lg flex items-start gap-4">
                <div className="p-2 border border-gray-300 rounded">
                  <Pencil size={16} className="text-gray-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-sm text-gray-900">Style Selector</h3>
                  <p className="text-sm text-gray-600 mt-1">Choose a custom export style (logo, theme, tone) configured in Settings. Applies to PDF and PowerPoint exports.</p>
                </div>
              </div>
            </div>

            {/* Models info */}
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h3 className="text-xs font-bold text-gray-900 mb-3 uppercase tracking-wide">Available Models</h3>

              {(() => {
                const allModels = modelCategories.flatMap(cat =>
                  cat.models.map(m => ({ ...m, category: cat.name })),
                );
                const totalPages = Math.ceil(allModels.length / 6);
                const startIdx = (modelsPage - 1) * 6;
                const displayModels = allModels.slice(startIdx, startIdx + 6);

                return (
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      {displayModels.map((model, idx) => (
                        <div key={idx} className="flex items-center gap-2 p-2 bg-white rounded border border-gray-200">
                          <img src={model.logo} alt="" className="w-4 h-4 object-contain" />
                          <span className="text-xs font-medium text-gray-900 truncate">{model.name}</span>
                        </div>
                      ))}
                    </div>

                    {totalPages > 1 && (
                      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
                        <button
                          onClick={() => setModelsPage(p => Math.max(1, p - 1))}
                          disabled={modelsPage === 1}
                          className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                        >
                          Previous
                        </button>
                        <span className="text-xs text-gray-500">
                          Page {modelsPage} of {totalPages}
                        </span>
                        <button
                          onClick={() => setModelsPage(p => Math.min(totalPages, p + 1))}
                          disabled={modelsPage === totalPages}
                          className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                        >
                          Next
                        </button>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PostMortemGuidePanel;

