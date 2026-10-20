/**
 * Task Guide Panel - Slide-in documentation panel from the right
 * Professional institutional finance design matching ChatGuidePanel style
 */

import React, { useState, useEffect } from 'react';
import {
  X, Play, Calendar, Clock, Mail,
  FileText, Presentation, Save, Square,
  Zap, Upload, MessageSquare, Users,
  CheckCircle2, AlertCircle, Info, Activity,
  Database, Merge, Split, Rocket, BookOpen,
  Brain, Sparkles, BarChart3, LineChart, Code,
  Calculator, Bitcoin, Scale, Target, TrendingUp,
  GitBranch, Workflow, Layers, Send, RefreshCw,
  ChevronRight, ChevronDown,
} from 'lucide-react';

// Import model logos
import gptLogo from '@/assets/model-logos/gpt-logo.png';
import claudeLogo from '@/assets/model-logos/claude-logo.svg.png';
import geminiLogo from '@/assets/model-logos/gemini-logo.png';
import grokLogo from '@/assets/model-logos/grok.png';
import qwenLogo from '@/assets/model-logos/Qwen_logo.svg.png';

interface TaskGuidePanelProps {
  isOpen: boolean;
  onClose: () => void;
  /** Which page context we're on - affects which content is highlighted */
  context?: 'list' | 'builder';
}

type TabId = 'toc' | 'overview' | 'canvas' | 'nodes' | 'schedule' | 'delivery' | 'execution';

// Node types data
const flowControlNodes = [
  { name: 'Start', icon: Play, color: '#22c55e', desc: 'Entry point. Exactly one required. No incoming edges.' },
  { name: 'End', icon: Square, color: '#ef4444', desc: 'Termination. Accepts multiple inputs. No outgoing edges.' },
  { name: 'Merge', icon: Merge, color: '#8b5cf6', desc: 'Accepts multiple inputs. Combines data sources for agent context.' },
  { name: 'Distribute', icon: Split, color: '#6366f1', desc: 'Fans out to multiple outputs. Send to Email, Slack, Teams, etc.' },
];

const inputNodes = [
  { name: 'Portfolio', icon: Database, color: '#3b82f6', desc: 'Select from saved portfolios. Provides holdings context.', logo: null },
  { name: 'File Upload', icon: Upload, color: '#6b7280', desc: 'Attach local files (PDF, XLSX, CSV, images).', logo: null },
  { name: 'OneDrive', icon: null, color: '#0078d4', desc: 'Browse and select files from Microsoft OneDrive.', logo: '/connector-logos/one-drive.png' },
  { name: 'SharePoint', icon: null, color: '#038387', desc: 'Connect to SharePoint document libraries.', logo: '/connector-logos/sharepoint-logo.png' },
  { name: 'Google Drive', icon: null, color: '#4285f4', desc: 'Browse and select files from Google Drive.', logo: '/connector-logos/google-drive.png' },
];

const agentModes = [
  { id: 'auto', name: 'Auto', icon: Brain, color: '#111827', desc: 'Supervisor routes to best agent' },
  { id: 'generalist', name: 'Agentic Search', icon: Sparkles, color: '#3b82f6', desc: 'Web search + market data' },
  { id: 'risk', name: 'Risk Analysis', icon: Zap, color: '#ef4444', desc: 'VaR, Monte Carlo, GEX, short interest' },
  { id: 'filings', name: 'Filing Search', icon: FileText, color: '#f59e0b', desc: 'SEC filings, transcripts' },
  { id: 'multiples', name: 'Comparable Companies', icon: BarChart3, color: '#8b5cf6', desc: 'Peer analysis, multiples' },
  { id: 'charts', name: 'Chart Analysis', icon: LineChart, color: '#06b6d4', desc: 'Technicals, GEX levels, max pain' },
  { id: 'quant', name: 'Quantitative Coding', icon: Code, color: '#ec4899', desc: 'Python + flow signals' },
  { id: 'dcf', name: 'DCF Valuation', icon: Calculator, color: '#059669', desc: 'Discounted cash flow' },
  { id: 'alternatives', name: 'Alternatives Data', icon: Bitcoin, color: '#f59e0b', desc: 'Crypto, FX, commodities' },
  { id: 'institutional', name: 'Institutional Activity', icon: Scale, color: '#8b5cf6', desc: '13F, dark pool, congress' },
  { id: 'prediction_markets', name: 'Prediction Markets', icon: Target, color: '#06b6d4', desc: 'Polymarket, Kalshi' },
  { id: 'funds_products', name: 'Funds & Products', icon: TrendingUp, color: '#10b981', desc: 'ETF, mutual fund, flows' },
  { id: 'structuring', name: 'Structuring', icon: Layers, color: '#6366f1', desc: 'Derivatives + GEX context' },
  { id: 'options', name: 'Options Analysis', icon: TrendingUp, color: '#f97316', desc: 'Flow alerts, Greeks, GEX' },
  { id: 'screener', name: 'Screener', icon: BarChart3, color: '#3b82f6', desc: 'Stocks, options, flow screening' },
];

// Models with logos
const models = [
  { id: 'gpt-6-astra', name: 'GPT-6 Astra', logo: gptLogo, provider: 'OpenAI' },
  { id: 'gpt-6.1-sol', name: 'GPT-6.1 Sol', logo: gptLogo, provider: 'OpenAI' },
  { id: 'litellm/anthropic/claude-fable-5-1', name: 'Claude Fable 5.1', logo: claudeLogo, provider: 'Anthropic' },
  { id: 'litellm/anthropic/claude-opus-5-5', name: 'Claude Opus 5.5', logo: claudeLogo, provider: 'Anthropic' },
  { id: 'litellm/anthropic/claude-sonnet-5-5', name: 'Claude Sonnet 5.5', logo: claudeLogo, provider: 'Anthropic' },
  { id: 'litellm/gemini/gemini-4-argon', name: 'Gemini 4 Argon', logo: geminiLogo, provider: 'Google' },
  { id: 'litellm/gemini/gemini-3.8-flash', name: 'Gemini 3.8 Flash', logo: geminiLogo, provider: 'Google' },
  { id: 'litellm/xai/grok-4.7', name: 'Grok 4.7', logo: grokLogo, provider: 'xAI' },
  { id: 'litellm/xai/grok-4.20-0309-non-reasoning', name: 'Grok 4.20 Fast', logo: grokLogo, provider: 'xAI' },
  { id: 'litellm/dashscope/qwen3.8-max', name: 'Qwen 3.8 Max', logo: qwenLogo, provider: 'Alibaba' },
];

const outputFormats = [
  { name: 'PDF Report', icon: FileText, color: '#ef4444', engine: 'Gamma API', desc: 'Professional PDF documents with charts and tables' },
  { name: 'PowerPoint', icon: Presentation, color: '#f97316', engine: 'Gamma API', desc: 'Slide presentations for stakeholder review' },
  { name: 'Workbook', icon: BookOpen, color: '#22c55e', engine: 'Code Interpreter', desc: 'Excel workbooks with data and formulas' },
];

const deliveryChannels = [
  { name: 'Email', icon: Mail, color: '#6b7280', protocol: 'SMTP / SES', desc: 'Attach artifacts, multiple recipients, custom subject', logo: '/connector-logos/email-icon.png' },
  { name: 'Slack', icon: MessageSquare, color: '#611f69', protocol: 'Webhook', desc: 'Post to channel with formatted blocks and file links', logo: '/connector-logos/slack-logo.png' },
  { name: 'Microsoft Teams', icon: Users, color: '#6264a7', protocol: 'Webhook', desc: 'Adaptive Card to Teams channel with attachments', logo: '/connector-logos/teams-logo.png' },
  { name: 'Save to Sentry', icon: Save, color: '#374151', protocol: 'S3 + DB', desc: 'Store with RLS-scoped record, access via History', logo: null },
];

const scheduleFrequencies = [
  { name: 'Once', desc: 'Single execution at specified date/time' },
  { name: 'Daily', desc: 'Every day at specified time' },
  { name: 'Weekdays', desc: 'Monday–Friday at specified time' },
  { name: 'Weekly', desc: 'Select specific days of week' },
  { name: 'Biweekly', desc: 'Every two weeks on selected days' },
  { name: 'Monthly', desc: 'Specific day of month' },
  { name: 'Custom', desc: 'Cron expression (e.g., 0 9 * * 1-5)' },
];

const ITEMS_PER_PAGE = 5;

export const TaskGuidePanel: React.FC<TaskGuidePanelProps> = ({
  isOpen,
  onClose,
  context = 'list',
}) => {
  const [activeTab, setActiveTab] = useState<TabId>('toc');
  const [visible, setVisible] = useState(false);

  // Pagination states
  const [agentPage, setAgentPage] = useState(1);
  const [modelPage, setModelPage] = useState(1);
  const [schedulePage, setSchedulePage] = useState(1);

  // Sub-navigation states
  const [nodesSection, setNodesSection] = useState<'flow' | 'input' | 'agent' | 'output' | 'delivery'>('flow');
  const [canvasSection, setCanvasSection] = useState<'editor' | 'rules' | 'sidebar' | 'header'>('editor');
  const [executionSection, setExecutionSection] = useState<'lifecycle' | 'status' | 'history' | 'validation' | 'api'>('lifecycle');

  // Animate in
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => setVisible(true), 10);
    } else {
      setVisible(false);
    }
  }, [isOpen]);

  // Reset pagination when switching tabs
  useEffect(() => {
    setAgentPage(1);
    setModelPage(1);
    setSchedulePage(1);
  }, [activeTab, nodesSection]);

  if (!isOpen) return null;

  const tabs: { id: TabId; label: string }[] = [
    { id: 'toc', label: 'Contents' },
    { id: 'overview', label: 'Overview' },
    { id: 'canvas', label: 'Canvas' },
    { id: 'nodes', label: 'Nodes' },
    { id: 'schedule', label: 'Schedule' },
    { id: 'delivery', label: 'Delivery' },
    { id: 'execution', label: 'Execution' },
  ];

  return (
    <>
      {/* Non-blocking side panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-xl bg-white shadow-2xl flex flex-col z-40 transition-transform duration-300 ease-out ${visible ? 'translate-x-0' : 'translate-x-full'}`}
        style={{ borderLeft: '1px solid #e5e7eb' }}
      >
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Tasks Documentation</h2>
              <p className="text-sm text-gray-500 mt-0.5">Workflow automation, scheduling, and delivery</p>
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
                  onClick={() => setActiveTab('canvas')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  2. Canvas Editor
                </button>
                <button
                  onClick={() => setActiveTab('nodes')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  3. Node Types
                </button>
                <button
                  onClick={() => setActiveTab('schedule')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  4. Scheduling
                </button>
                <button
                  onClick={() => setActiveTab('delivery')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  5. Delivery Channels
                </button>
                <button
                  onClick={() => setActiveTab('execution')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  6. Execution & History
                </button>
              </div>
            </div>
          )}

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="h-full bg-white overflow-y-auto">
              <div className="max-w-3xl mx-auto px-8 py-8">

                {/* Header */}
                <div className="mb-8 pb-4 border-b border-gray-200">
                  <h1 className="text-xl font-bold text-gray-900 mb-2">Task Automation</h1>
                  <p className="text-sm text-gray-600">
                    Visual workflow builder for scheduling AI agents to run automated analysis, generate reports, and deliver insights on a recurring basis.
                  </p>
                </div>

                {/* Core Capabilities */}
                <section className="mb-10">
                  <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-4">Core Capabilities</h2>
                  <ul className="space-y-4 text-sm text-gray-700">
                    <li className="flex flex-col gap-1">
                      <div className="font-semibold text-gray-900">Visual Workflow Builder</div>
                      <div className="text-gray-600 leading-relaxed">
                        Drag-and-drop canvas using ReactFlow. Connect nodes to define data flow from inputs through agents to outputs and delivery channels.
                      </div>
                    </li>
                    <li className="flex flex-col gap-1">
                      <div className="font-semibold text-gray-900">Specialized AI Agents</div>
                      <div className="text-gray-600 leading-relaxed">
                        Access 13 specialist agents: Risk, DCF, Comps, Filings, Charts, Quant, Alternatives, Institutional, Prediction Markets, Funds, and Structuring.
                      </div>
                    </li>
                    <li className="flex flex-col gap-1">
                      <div className="font-semibold text-gray-900">Flexible Scheduling</div>
                      <div className="text-gray-600 leading-relaxed">
                        APScheduler-powered execution with daily, weekly, monthly, weekday-only, or custom cron expressions. Timezone-aware scheduling.
                      </div>
                    </li>
                    <li className="flex flex-col gap-1">
                      <div className="font-semibold text-gray-900">Multi-Channel Delivery</div>
                      <div className="text-gray-600 leading-relaxed">
                        Automatic delivery via Email, Slack, Microsoft Teams, or save directly to Sentry. Generate PDF, PowerPoint, or Excel workbooks.
                      </div>
                    </li>
                  </ul>
                </section>

                {/* Quick Start */}
                <section className="mb-10">
                  <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-4">Quick Start</h2>
                  <div className="border rounded-md border-gray-200 divide-y divide-gray-200">
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-semibold bg-gray-100 px-2 py-1 rounded">1</span>
                        <span className="text-sm font-semibold text-gray-900">Create Task</span>
                      </div>
                      <p className="text-sm text-gray-600">Click "Create Task" to open the canvas builder.</p>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-semibold bg-gray-100 px-2 py-1 rounded">2</span>
                        <span className="text-sm font-semibold text-gray-900">Add Nodes</span>
                      </div>
                      <p className="text-sm text-gray-600">Add input nodes (Portfolio, File) and connect to an Agent node.</p>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-semibold bg-gray-100 px-2 py-1 rounded">3</span>
                        <span className="text-sm font-semibold text-gray-900">Configure Output</span>
                      </div>
                      <p className="text-sm text-gray-600">Add output format (PDF, PPT) and delivery channel (Email, Slack).</p>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-semibold bg-gray-100 px-2 py-1 rounded">4</span>
                        <span className="text-sm font-semibold text-gray-900">Deploy</span>
                      </div>
                      <p className="text-sm text-gray-600">Configure schedule in sidebar and click Deploy.</p>
                    </div>
                  </div>
                </section>

                {/* Infrastructure */}
                <section>
                  <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-4">Infrastructure</h2>
                  <div className="overflow-x-auto">
                    <table className="min-w-full border border-gray-200 text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Component</th>
                          <th className="px-4 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Technology</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        <tr>
                          <td className="px-4 py-2 font-medium text-gray-900">Canvas Editor</td>
                          <td className="px-4 py-2 text-gray-600">ReactFlow</td>
                        </tr>
                        <tr>
                          <td className="px-4 py-2 font-medium text-gray-900">Scheduler</td>
                          <td className="px-4 py-2 text-gray-600">APScheduler (AsyncIOScheduler)</td>
                        </tr>
                        <tr>
                          <td className="px-4 py-2 font-medium text-gray-900">Document Generation</td>
                          <td className="px-4 py-2 text-gray-600">Gamma API (PDF, PPTX)</td>
                        </tr>
                        <tr>
                          <td className="px-4 py-2 font-medium text-gray-900">Workbook Generation</td>
                          <td className="px-4 py-2 text-gray-600">OpenAI Code Interpreter</td>
                        </tr>
                        <tr>
                          <td className="px-4 py-2 font-medium text-gray-900">Artifact Storage</td>
                          <td className="px-4 py-2 text-gray-600">S3 + PostgreSQL (RLS)</td>
                        </tr>
                        <tr>
                          <td className="px-4 py-2 font-medium text-gray-900">Data Sources</td>
                          <td className="px-4 py-2 text-gray-600">FMP, Polygon, FRED, SEC, Unusual Whales</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </section>

              </div>
            </div>
          )}

          {/* Canvas Tab */}
          {activeTab === 'canvas' && (
            <div className="p-6">
              {/* Sub-navigation */}
              <div className="flex flex-wrap gap-2 mb-6 pb-4 border-b border-gray-200">
                {(['editor', 'rules', 'sidebar', 'header'] as const).map(section => (
                  <button
                    key={section}
                    onClick={() => setCanvasSection(section)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                      canvasSection === section
                        ? 'bg-gray-900 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {section === 'editor' && 'Editor'}
                    {section === 'rules' && 'Workflow Rules'}
                    {section === 'sidebar' && 'Sidebar'}
                    {section === 'header' && 'Header Actions'}
                  </button>
                ))}
              </div>

              <div className="space-y-4">
                {canvasSection === 'editor' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">ReactFlow Canvas</h2>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Interactive node-based editor. Drag nodes from sidebar, connect handles, configure each node's properties in the right panel.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Pan & Zoom:</strong> Scroll to zoom, drag canvas to pan</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Selection Mode:</strong> Toggle to select multiple nodes</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Connect Nodes:</strong> Drag from source handle to target</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Delete:</strong> Select node + Delete key</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {canvasSection === 'rules' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Workflow Rules (DAG)</h2>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Tasks must form a valid Directed Acyclic Graph (DAG). The validator checks these rules before deployment.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <CheckCircle2 size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                          <span>Exactly one <code className="bg-gray-100 px-1 rounded text-xs">Start</code> node required</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <CheckCircle2 size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                          <span>At least one <code className="bg-gray-100 px-1 rounded text-xs">End</code> node required</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <CheckCircle2 size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                          <span>No cycles allowed (acyclic graph)</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <CheckCircle2 size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                          <span>All paths must reach an End node</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <Info size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                          <span><code className="bg-gray-100 px-1 rounded text-xs">Merge</code> and <code className="bg-gray-100 px-1 rounded text-xs">End</code> accept multiple inputs</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <Info size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                          <span><code className="bg-gray-100 px-1 rounded text-xs">Distribute</code> fans out to multiple outputs</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {canvasSection === 'sidebar' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Left Sidebar</h2>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Collapsible panels for task configuration and node palette.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Settings:</strong> Task name, description</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Schedule:</strong> Frequency, time, timezone</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Delivery:</strong> Channel configuration</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Inputs:</strong> Portfolio, file upload nodes</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Agents:</strong> AI specialist nodes</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span><strong>Outputs:</strong> PDF, PPT, Workbook nodes</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {canvasSection === 'header' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Header Actions</h2>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <div className="space-y-3">
                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">TABS</div>
                          <p className="text-sm text-gray-700">Switch between <strong>Task</strong> (canvas editor) and <strong>History</strong> (run history).</p>
                        </div>

                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">SAVE</div>
                          <p className="text-sm text-gray-700">Save as draft without deploying. Preserves current canvas state.</p>
                        </div>

                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">VALIDATE</div>
                          <p className="text-sm text-gray-700">Check workflow for errors before deploying. Shows errors, warnings, and info.</p>
                        </div>

                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">TEST</div>
                          <p className="text-sm text-gray-700">Run task immediately (manual trigger) without waiting for schedule.</p>
                        </div>

                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">DEPLOY</div>
                          <p className="text-sm text-gray-700">Activate task to run on schedule. Registers job with APScheduler.</p>
                        </div>

                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">AI ASSISTANT</div>
                          <p className="text-sm text-gray-700">Click sparkle icon to describe what you want. AI suggests workflow changes.</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Nodes Tab */}
          {activeTab === 'nodes' && (
            <div className="p-6">
              {/* Sub-navigation */}
              <div className="flex flex-wrap gap-2 mb-6 pb-4 border-b border-gray-200">
                {(['flow', 'input', 'agent', 'output', 'delivery'] as const).map(section => (
                  <button
                    key={section}
                    onClick={() => setNodesSection(section)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                      nodesSection === section
                        ? 'bg-gray-900 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {section === 'flow' && 'Flow Control'}
                    {section === 'input' && 'Data Inputs'}
                    {section === 'agent' && 'Agent'}
                    {section === 'output' && 'Output Formats'}
                    {section === 'delivery' && 'Delivery'}
                  </button>
                ))}
              </div>

              <div className="space-y-4">
                {nodesSection === 'flow' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Flow Control Nodes</h2>
                    <div className="space-y-2">
                      {flowControlNodes.map((node, idx) => {
                        const Icon = node.icon;
                        return (
                          <div key={idx} className="flex items-start gap-3 p-3 bg-white rounded border border-gray-200">
                            <Icon
                              size={16}
                              style={{
                                color: node.color,
                                transform: (node.name === 'Merge' || node.name === 'Distribute') ? 'rotate(90deg)' : undefined,
                              }}
                              className="flex-shrink-0 mt-0.5"
                            />
                            <div>
                              <div className="font-medium text-sm text-gray-900">{node.name}</div>
                              <div className="text-xs text-gray-600 mt-0.5">{node.desc}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Flow Control Config */}
                    <div className="mt-4 bg-gray-50 border border-gray-200 rounded p-4">
                      <div className="text-xs font-semibold text-gray-700 mb-2">NODE CONFIGURATION</div>
                      <p className="text-sm text-gray-600">
                        Start and End nodes have no configuration. Merge and Distribute nodes allow setting a custom label.
                      </p>
                    </div>
                  </div>
                )}

                {nodesSection === 'input' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Data Input Nodes</h2>
                    <div className="space-y-2">
                      {inputNodes.map((node, idx) => {
                        const Icon = node.icon;
                        return (
                          <div key={idx} className="flex items-start gap-3 p-3 bg-white rounded border border-gray-200">
                            {node.logo ? (
                              <img src={node.logo} alt={node.name} className="w-5 h-5 object-contain flex-shrink-0" />
                            ) : Icon ? (
                              <Icon size={16} style={{ color: node.color }} className="flex-shrink-0 mt-0.5" />
                            ) : null}
                            <div>
                              <div className="font-medium text-sm text-gray-900">{node.name}</div>
                              <div className="text-xs text-gray-600 mt-0.5">{node.desc}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Input Node Configs */}
                    <div className="mt-4 space-y-3">
                      <div className="bg-gray-50 border border-gray-200 rounded p-4">
                        <div className="text-xs font-semibold text-gray-700 mb-2">PORTFOLIO NODE</div>
                        <p className="text-sm text-gray-600 mb-2">Select from your saved portfolios. Provides holdings data to agents.</p>
                        <div className="text-xs text-gray-500">Config: Portfolio dropdown selection</div>
                      </div>
                      <div className="bg-gray-50 border border-gray-200 rounded p-4">
                        <div className="text-xs font-semibold text-gray-700 mb-2">FILE UPLOAD NODE</div>
                        <p className="text-sm text-gray-600 mb-2">Upload local files for analysis. Supports PDF, XLSX, CSV, images.</p>
                        <div className="text-xs text-gray-500">Config: File picker, supports multiple files</div>
                      </div>
                      <div className="bg-gray-50 border border-gray-200 rounded p-4">
                        <div className="text-xs font-semibold text-gray-700 mb-2">CLOUD STORAGE NODES</div>
                        <p className="text-sm text-gray-600 mb-2">OAuth integration with OneDrive, SharePoint, Google Drive.</p>
                        <div className="text-xs text-gray-500">Config: Native file picker with folder navigation</div>
                      </div>
                    </div>
                  </div>
                )}

                {nodesSection === 'agent' && (() => {
                  const totalAgentPages = Math.ceil(agentModes.length / ITEMS_PER_PAGE);
                  const startAgentIdx = (agentPage - 1) * ITEMS_PER_PAGE;
                  const displayAgents = agentModes.slice(startAgentIdx, startAgentIdx + ITEMS_PER_PAGE);

                  const totalModelPages = Math.ceil(models.length / ITEMS_PER_PAGE);
                  const startModelIdx = (modelPage - 1) * ITEMS_PER_PAGE;
                  const displayModels = models.slice(startModelIdx, startModelIdx + ITEMS_PER_PAGE);

                  return (
                    <div>
                      <h2 className="text-lg font-bold text-gray-900 mb-2">Agent Node Configuration</h2>
                      <p className="text-sm text-gray-600 mb-4">
                        Core analysis node. Configure specialist mode, model, reasoning level, tools, MCP servers, and custom instructions.
                      </p>

                      {/* Agent Modes */}
                      <div className="mb-6">
                        <div className="text-xs font-semibold text-gray-700 mb-2">SPECIALIST MODES ({agentModes.length})</div>
                        <div className="space-y-2 mb-3">
                          {displayAgents.map((agent, idx) => {
                            const Icon = agent.icon;
                            return (
                              <div key={idx} className="flex items-center gap-3 p-2.5 bg-white rounded border border-gray-200">
                                <Icon size={14} style={{ color: agent.color }} />
                                <div className="flex-1 min-w-0">
                                  <span className="font-medium text-sm text-gray-900">{agent.name}</span>
                                  <span className="text-xs text-gray-500 ml-2">{agent.desc}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        {totalAgentPages > 1 && (
                          <div className="flex items-center justify-between pt-2 border-t border-gray-200">
                            <button
                              onClick={() => setAgentPage(p => Math.max(1, p - 1))}
                              disabled={agentPage === 1}
                              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              ← Previous
                            </button>
                            <span className="text-xs text-gray-500">Page {agentPage} of {totalAgentPages}</span>
                            <button
                              onClick={() => setAgentPage(p => Math.min(totalAgentPages, p + 1))}
                              disabled={agentPage === totalAgentPages}
                              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              Next →
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Models */}
                      <div className="mb-6">
                        <div className="text-xs font-semibold text-gray-700 mb-2">MODEL SELECTION ({models.length})</div>
                        <div className="space-y-2 mb-3">
                          {displayModels.map((model, idx) => (
                            <div key={idx} className="flex items-center gap-3 p-2.5 bg-white rounded border border-gray-200">
                              <img src={model.logo} alt={model.name} className="w-5 h-5 object-contain" />
                              <div className="flex-1 min-w-0">
                                <span className="font-medium text-sm text-gray-900">{model.name}</span>
                                <span className="text-xs text-gray-400 ml-2">{model.provider}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                        {totalModelPages > 1 && (
                          <div className="flex items-center justify-between pt-2 border-t border-gray-200">
                            <button
                              onClick={() => setModelPage(p => Math.max(1, p - 1))}
                              disabled={modelPage === 1}
                              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              ← Previous
                            </button>
                            <span className="text-xs text-gray-500">Page {modelPage} of {totalModelPages}</span>
                            <button
                              onClick={() => setModelPage(p => Math.min(totalModelPages, p + 1))}
                              disabled={modelPage === totalModelPages}
                              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              Next →
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Config Options */}
                      <div className="bg-gray-50 border border-gray-200 rounded p-4">
                        <div className="text-xs font-semibold text-gray-700 mb-3">ADDITIONAL CONFIGURATION</div>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-600">Reasoning Level</span>
                            <span className="text-gray-900 text-xs">Low | Medium | High</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Response Length</span>
                            <span className="text-gray-900 text-xs">Short | Medium | Long</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Tools</span>
                            <span className="text-gray-900 text-xs">Multi-select checkboxes</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">MCP Servers</span>
                            <span className="text-gray-900 text-xs">Multi-select checkboxes</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Instructions</span>
                            <span className="text-gray-900 text-xs">Custom prompt textarea</span>
                          </div>
                        </div>
                        <div className="mt-3 pt-3 border-t border-gray-300 text-xs text-gray-500">
                          <strong>Note:</strong> Code Interpreter only available with OpenAI GPT models.
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {nodesSection === 'output' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Output Format Nodes</h2>
                    <div className="space-y-3">
                      {outputFormats.map((format, idx) => {
                        const Icon = format.icon;
                        return (
                          <div key={idx} className="bg-white border border-gray-200 rounded-lg p-4">
                            <div className="flex items-center gap-2 mb-2">
                              <Icon size={16} style={{ color: format.color }} />
                              <span className="font-semibold text-sm text-gray-900">{format.name}</span>
                              <span className="text-xs text-gray-400">·</span>
                              <span className="text-xs text-gray-500">{format.engine}</span>
                            </div>
                            <p className="text-sm text-gray-600">{format.desc}</p>
                          </div>
                        );
                      })}
                    </div>

                    {/* Output Config */}
                    <div className="mt-4 bg-gray-50 border border-gray-200 rounded p-4">
                      <div className="text-xs font-semibold text-gray-700 mb-2">OUTPUT CONFIGURATION</div>
                      <div className="space-y-2 text-sm text-gray-600">
                        <div><strong>Export Style:</strong> Select from user-defined styles in Settings</div>
                        <div><strong>File Naming:</strong> Automatic based on task name and timestamp</div>
                        <div><strong>Custom Instructions:</strong> Additional formatting instructions</div>
                      </div>
                    </div>
                  </div>
                )}

                {nodesSection === 'delivery' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Delivery Channel Nodes</h2>
                    <div className="space-y-3">
                      {deliveryChannels.map((channel, idx) => {
                        const Icon = channel.icon;
                        return (
                          <div key={idx} className="bg-white border border-gray-200 rounded-lg p-4">
                            <div className="flex items-center gap-2 mb-2">
                              {channel.logo ? (
                                <img src={channel.logo} alt={channel.name} className="w-5 h-5 object-contain" />
                              ) : (
                                <Icon size={16} style={{ color: channel.color }} />
                              )}
                              <span className="font-semibold text-sm text-gray-900">{channel.name}</span>
                              <span className="text-xs text-gray-400">·</span>
                              <span className="text-xs text-gray-500">{channel.protocol}</span>
                            </div>
                            <p className="text-sm text-gray-600">{channel.desc}</p>
                          </div>
                        );
                      })}
                    </div>

                    {/* Delivery Configs */}
                    <div className="mt-4 space-y-3">
                      <div className="bg-gray-50 border border-gray-200 rounded p-4">
                        <div className="text-xs font-semibold text-gray-700 mb-2">EMAIL CONFIGURATION</div>
                        <div className="text-sm text-gray-600 space-y-1">
                          <div>• Select from saved email lists</div>
                          <div>• Custom subject line with placeholders</div>
                          <div>• Optional message body</div>
                        </div>
                      </div>
                      <div className="bg-gray-50 border border-gray-200 rounded p-4">
                        <div className="text-xs font-semibold text-gray-700 mb-2">SLACK CONFIGURATION</div>
                        <div className="text-sm text-gray-600 space-y-1">
                          <div>• Select workspace (OAuth connected)</div>
                          <div>• Select channel from workspace</div>
                          <div>• Optional custom message</div>
                        </div>
                      </div>
                      <div className="bg-gray-50 border border-gray-200 rounded p-4">
                        <div className="text-xs font-semibold text-gray-700 mb-2">TEAMS CONFIGURATION</div>
                        <div className="text-sm text-gray-600 space-y-1">
                          <div>• Select team and channel</div>
                          <div>• Uses incoming webhook connector</div>
                          <div>• Adaptive Card formatting</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Schedule Tab */}
          {activeTab === 'schedule' && (() => {
            const totalPages = Math.ceil(scheduleFrequencies.length / ITEMS_PER_PAGE);
            const startIdx = (schedulePage - 1) * ITEMS_PER_PAGE;
            const displaySchedules = scheduleFrequencies.slice(startIdx, startIdx + ITEMS_PER_PAGE);

            return (
              <div className="p-6 space-y-5">
                <div className="pb-3 border-b border-gray-200">
                  <h3 className="text-base font-semibold text-gray-900 mb-1">Schedule Configuration</h3>
                  <p className="text-sm text-gray-600">
                    Configure when and how often your task runs. All times are timezone-aware.
                  </p>
                </div>

                {/* Frequency Options */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-gray-700">FREQUENCY PRESETS</div>
                  {displaySchedules.map((freq, idx) => (
                    <div key={idx} className="flex items-start gap-3 p-3 bg-white rounded border border-gray-200">
                      <div className="flex-1">
                        <div className="font-medium text-sm text-gray-900">{freq.name}</div>
                        <div className="text-xs text-gray-600 mt-0.5">{freq.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between pt-2 border-t border-gray-200">
                    <button
                      onClick={() => setSchedulePage(p => Math.max(1, p - 1))}
                      disabled={schedulePage === 1}
                      className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      ← Previous
                    </button>
                    <span className="text-xs text-gray-500">
                      Page {schedulePage} of {totalPages}
                    </span>
                    <button
                      onClick={() => setSchedulePage(p => Math.min(totalPages, p + 1))}
                      disabled={schedulePage === totalPages}
                      className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      Next →
                    </button>
                  </div>
                )}

                {/* Timezone */}
                <div className="bg-gray-50 border border-gray-200 rounded p-4">
                  <div className="text-xs font-semibold text-gray-700 mb-2">TIMEZONE HANDLING</div>
                  <p className="text-sm text-gray-700 mb-2">
                    All times configured in user's selected timezone. Stored and executed in UTC.
                  </p>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="px-2 py-1 bg-white rounded border border-gray-300">America/New_York</span>
                    <span className="px-2 py-1 bg-white rounded border border-gray-300">Europe/London</span>
                    <span className="px-2 py-1 bg-white rounded border border-gray-300">Asia/Tokyo</span>
                  </div>
                </div>

                {/* Scheduler Engine */}
                <div className="bg-gray-50 border border-gray-200 rounded p-4">
                  <div className="text-xs font-semibold text-gray-700 mb-2">APSCHEDULER ENGINE</div>
                  <p className="text-sm text-gray-700">
                    Backend uses <code className="bg-gray-200 px-1 rounded text-xs">AsyncIOScheduler</code> to manage job registration. Jobs are persisted and survive server restarts.
                  </p>
                </div>
              </div>
            );
          })()}

          {/* Delivery Tab */}
          {activeTab === 'delivery' && (
            <div className="p-6 space-y-5">
              <div className="pb-3 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-900 mb-1">Delivery Configuration</h3>
                <p className="text-sm text-gray-600">
                  Configure how generated artifacts are delivered to recipients.
                </p>
              </div>

              <div className="space-y-3">
                {deliveryChannels.map((channel, idx) => {
                  const Icon = channel.icon;
                  return (
                    <div key={idx} className="bg-white border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-2">
                        {channel.logo ? (
                          <img src={channel.logo} alt={channel.name} className="w-5 h-5 object-contain" />
                        ) : (
                          <Icon size={16} style={{ color: channel.color }} />
                        )}
                        <span className="font-semibold text-sm text-gray-900">{channel.name}</span>
                        <span className="text-xs text-gray-400">·</span>
                        <span className="text-xs text-gray-500">{channel.protocol}</span>
                      </div>
                      <p className="text-sm text-gray-600">{channel.desc}</p>
                    </div>
                  );
                })}
              </div>

              <div className="bg-gray-50 border border-gray-200 rounded p-4">
                <div className="text-xs font-semibold text-gray-700 mb-2">INTEGRATION SETUP</div>
                <p className="text-sm text-gray-700">
                  Slack and Teams require OAuth connection in Settings → Integrations. Email uses configured SMTP or AWS SES.
                </p>
              </div>
            </div>
          )}

          {/* Execution Tab */}
          {activeTab === 'execution' && (
            <div className="p-6">
              {/* Sub-navigation */}
              <div className="flex flex-wrap gap-2 mb-6 pb-4 border-b border-gray-200">
                {(['lifecycle', 'status', 'history', 'validation', 'api'] as const).map(section => (
                  <button
                    key={section}
                    onClick={() => setExecutionSection(section)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                      executionSection === section
                        ? 'bg-gray-900 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {section === 'lifecycle' && 'Lifecycle'}
                    {section === 'status' && 'Status'}
                    {section === 'history' && 'History'}
                    {section === 'validation' && 'Validation'}
                    {section === 'api' && 'API'}
                  </button>
                ))}
              </div>

              <div className="space-y-4">
                {executionSection === 'lifecycle' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Task Lifecycle</h2>
                    <div className="bg-white border border-gray-200 rounded-lg p-5">
                      <div className="space-y-3">
                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">1. TRIGGER</div>
                          <p className="text-sm text-gray-600">Scheduler fires or manual trigger via API</p>
                        </div>
                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">2. PARSE CANVAS</div>
                          <p className="text-sm text-gray-600">TaskParser converts JSON to TaskDefinition</p>
                        </div>
                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">3. HYDRATE INPUTS</div>
                          <p className="text-sm text-gray-600">Fetch portfolio, files via data_fetchers</p>
                        </div>
                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">4. EXECUTE AGENTS</div>
                          <p className="text-sm text-gray-600">Orchestrator runs configured agent mode</p>
                        </div>
                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">5. GENERATE OUTPUTS</div>
                          <p className="text-sm text-gray-600">PDF/PPT via Gamma, Workbook via Code Interpreter</p>
                        </div>
                        <div className="border-l-4 border-gray-300 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">6. DELIVER</div>
                          <p className="text-sm text-gray-600">Send via configured channels</p>
                        </div>
                        <div className="border-l-4 border-green-400 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">7. COMPLETE</div>
                          <p className="text-sm text-gray-600">Update run status, calculate next_run_at</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {executionSection === 'status' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Task Status</h2>
                    <div className="space-y-2">
                      <div className="flex items-center gap-3 p-3 bg-white rounded border border-gray-200">
                        <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                        <div className="flex-1">
                          <span className="font-medium text-sm text-gray-900">Draft</span>
                          <span className="text-xs text-gray-500 ml-2">Not scheduled</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 p-3 bg-white rounded border border-gray-200">
                        <div className="w-2 h-2 rounded-full bg-green-500"></div>
                        <div className="flex-1">
                          <span className="font-medium text-sm text-gray-900">Active</span>
                          <span className="text-xs text-gray-500 ml-2">Running on schedule</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 p-3 bg-white rounded border border-gray-200">
                        <div className="w-2 h-2 rounded-full bg-amber-500"></div>
                        <div className="flex-1">
                          <span className="font-medium text-sm text-gray-900">Paused</span>
                          <span className="text-xs text-gray-500 ml-2">Temporarily stopped</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 p-3 bg-white rounded border border-gray-200">
                        <div className="w-2 h-2 rounded-full bg-gray-300"></div>
                        <div className="flex-1">
                          <span className="font-medium text-sm text-gray-900">Archived</span>
                          <span className="text-xs text-gray-500 ml-2">Permanently disabled</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {executionSection === 'history' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">History Tab</h2>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Switch to the History tab in the header to view all past executions.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5 flex-shrink-0"></div>
                          <span><strong>Successful Runs:</strong> View output, download artifacts (PDF, PPT, Workbook)</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <div className="w-2 h-2 rounded-full bg-red-500 mt-1.5 flex-shrink-0"></div>
                          <span><strong>Failed Runs:</strong> View error messages for debugging</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 flex-shrink-0 animate-pulse"></div>
                          <span><strong>Running:</strong> Currently executing, polls for completion</span>
                        </div>
                      </div>

                      <div className="bg-gray-50 border border-gray-200 rounded p-3 text-xs text-gray-700">
                        <strong>Database Tables:</strong> task_runs, task_saved_outputs
                      </div>
                    </div>
                  </div>
                )}

                {executionSection === 'validation' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Validation</h2>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Click Validate in header to check workflow before deploying.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <AlertCircle size={14} className="text-red-500 mt-0.5 flex-shrink-0" />
                          <span><strong>Errors:</strong> Must fix before deploy</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <AlertCircle size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                          <span><strong>Warnings:</strong> Recommended to fix</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <Info size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                          <span><strong>Info:</strong> Suggestions for improvement</span>
                        </div>
                      </div>

                      <div className="bg-gray-50 border border-gray-200 rounded p-3 text-xs text-gray-700">
                        <strong>Backend:</strong> CanvasValidator in core/tasks/validator.py
                      </div>
                    </div>
                  </div>
                )}

                {executionSection === 'api' && (
                  <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">API Endpoints</h2>
                    <div className="overflow-x-auto">
                      <table className="min-w-full border border-gray-200 text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Method</th>
                            <th className="px-3 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Endpoint</th>
                            <th className="px-3 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Description</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 font-mono text-xs">
                          <tr>
                            <td className="px-3 py-2 text-green-600">GET</td>
                            <td className="px-3 py-2 text-gray-700">/api/tasks</td>
                            <td className="px-3 py-2 text-gray-500 font-sans">List tasks</td>
                          </tr>
                          <tr>
                            <td className="px-3 py-2 text-blue-600">POST</td>
                            <td className="px-3 py-2 text-gray-700">/api/tasks</td>
                            <td className="px-3 py-2 text-gray-500 font-sans">Create task</td>
                          </tr>
                          <tr>
                            <td className="px-3 py-2 text-amber-600">PUT</td>
                            <td className="px-3 py-2 text-gray-700">/api/tasks/:id</td>
                            <td className="px-3 py-2 text-gray-500 font-sans">Update task</td>
                          </tr>
                          <tr>
                            <td className="px-3 py-2 text-blue-600">POST</td>
                            <td className="px-3 py-2 text-gray-700">/api/tasks/:id/toggle</td>
                            <td className="px-3 py-2 text-gray-500 font-sans">Toggle status</td>
                          </tr>
                          <tr>
                            <td className="px-3 py-2 text-blue-600">POST</td>
                            <td className="px-3 py-2 text-gray-700">/api/tasks/:id/trigger</td>
                            <td className="px-3 py-2 text-gray-500 font-sans">Manual run</td>
                          </tr>
                          <tr>
                            <td className="px-3 py-2 text-blue-600">POST</td>
                            <td className="px-3 py-2 text-gray-700">/api/tasks/validate</td>
                            <td className="px-3 py-2 text-gray-500 font-sans">Validate canvas</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

// Also export a simple trigger hook
export const useTaskGuide = () => {
  const [isOpen, setIsOpen] = useState(false);
  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    toggle: () => setIsOpen(prev => !prev),
  };
};

export default TaskGuidePanel;
