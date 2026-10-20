import { Node } from 'reactflow';
import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { portfolioApiService, type PortfolioData } from '@/services/portfolioApi';
import {
  Trash2, Brain, Sparkles, Zap, FileText, BarChart3, LineChart,
  Code, Calculator, Bitcoin, Scale, Target, TrendingUp, ChevronDown,
  Upload, Link, X,
} from 'lucide-react';
import { OneDriveNativePicker } from '@/components/KnowledgeGraph/OneDriveNativePicker';
import { GoogleDriveNativePicker } from '@/components/KnowledgeGraph/GoogleDriveNativePicker';
import toast from 'react-hot-toast';
import { slackIntegrationApi, type SlackWorkspace, type SlackChannel } from '@/services/slackIntegrationApi';
import { teamsIntegrationApi, type TeamsWorkspace, type TeamsTeam, type TeamsChannel } from '@/services/teamsIntegrationApi';
import { emailListsApi, type EmailList } from '@/services/emailListsApi';
import { uploadService, type UploadedFile } from '@/services/upload';
import { userSettingsApiService, type ExportStyle } from '@/services/userSettingsApi';

// Import logos
import gptLogo from '@/assets/model-logos/gpt-logo.png';
import claudeLogo from '@/assets/model-logos/claude-logo.svg.png';
import geminiLogo from '@/assets/model-logos/gemini-logo.png';
import grokLogo from '@/assets/model-logos/grok.png';
import kimiLogo from '@/assets/model-logos/Kimi-logo-2025.png';
import qwenLogo from '@/assets/model-logos/Qwen_logo.svg.png';
import glmLogo from '@/assets/model-logos/Z.ai_(company_logo).svg.png';

// Agent modes from AgentModeSelector
const agentModes = [
  { id: 'auto', name: 'Auto', icon: Brain, color: '#111827' },
  { id: 'generalist', name: 'Agentic Search', icon: Sparkles, color: '#3b82f6' },
  { id: 'risk', name: 'Risk Analysis', icon: Zap, color: '#ef4444' },
  { id: 'filings', name: 'Filing Search', icon: FileText, color: '#f59e0b' },
  { id: 'multiples', name: 'Comparable Companies', icon: BarChart3, color: '#8b5cf6' },
  { id: 'charts', name: 'Chart Analysis', icon: LineChart, color: '#06b6d4' },
  { id: 'quant', name: 'Quantitative Coding', icon: Code, color: '#ec4899' },
  { id: 'dcf', name: 'DCF Valuation', icon: Calculator, color: '#059669' },
  { id: 'alternatives', name: 'Alternatives Data', icon: Bitcoin, color: '#f59e0b' },
  { id: 'institutional', name: 'Institutional Activity', icon: Scale, color: '#8b5cf6' },
  { id: 'prediction_markets', name: 'Prediction Markets', icon: Target, color: '#06b6d4' },
  { id: 'funds_products', name: 'Funds & Products', icon: TrendingUp, color: '#10b981' },
  { id: 'structuring', name: 'Structuring', icon: Zap, color: '#111827' },
];

// Models from models.ts - all models
const models = [
  { id: 'gpt-6-astra', name: 'GPT-6 Astra', logo: gptLogo },
  { id: 'gpt-6.1-sol', name: 'GPT-6.1 Sol', logo: gptLogo },
  { id: 'gpt-6-luna', name: 'GPT-6 Luna', logo: gptLogo },
  { id: 'litellm/anthropic/claude-fable-5-1', name: 'Claude Fable 5.1', logo: claudeLogo },
  { id: 'litellm/anthropic/claude-opus-5-5', name: 'Claude Opus 5.5', logo: claudeLogo },
  { id: 'litellm/anthropic/claude-sonnet-5-5', name: 'Claude Sonnet 5.5', logo: claudeLogo },
  { id: 'litellm/anthropic/claude-haiku-4-5-20251001', name: 'Claude Haiku 4.5', logo: claudeLogo },
  { id: 'litellm/gemini/gemini-4-argon', name: 'Gemini 4 Argon', logo: geminiLogo },
  { id: 'litellm/gemini/gemini-3.8-flash', name: 'Gemini 3.8 Flash', logo: geminiLogo },
  { id: 'litellm/gemini/gemini-3.5-flash-lite', name: 'Gemini 3.5 Flash Lite', logo: geminiLogo },
  { id: 'litellm/xai/grok-4.7', name: 'Grok 4.7', logo: grokLogo },
  { id: 'litellm/xai/grok-4.20-0309-non-reasoning', name: 'Grok 4.20 Fast', logo: grokLogo },
  { id: 'litellm/moonshot/kimi-k3', name: 'Kimi K3', logo: kimiLogo },
  { id: 'litellm/dashscope/qwen3.8-max', name: 'Qwen 3.8 Max', logo: qwenLogo },
  { id: 'litellm/zai/glm-5.3', name: 'GLM-5.3', logo: glmLogo },
];

interface NodeConfigPanelProps {
  selectedNode: Node | null;
  onUpdateNode: (nodeId: string, data: any) => void;
  onDeleteNode: (nodeId: string) => void;
  onClose: () => void;
}

export function NodeConfigPanel({ selectedNode, onUpdateNode, onDeleteNode }: NodeConfigPanelProps) {
  if (!selectedNode) {
    return null;
  }

  // Get node-specific subtitle
  const getSubtitle = (type: string) => {
    const subtitles: Record<string, string> = {
      start: 'Define the workflow inputs',
      end: 'Choose the workflow output',
      agent: 'Call the model with your instructions and tools',
      merge: 'Combine multiple data sources',
      distribute: 'Send to multiple delivery channels',
      portfolio: 'Select portfolio data source',
      graph: 'Configure chart or graph output',
      fileUpload: 'Configure file upload settings',
      oneDrive: 'Connect to OneDrive storage',
      googleDrive: 'Connect to Google Drive storage',
      pdfReport: 'Configure PDF report generation',
      pptPresentation: 'Configure PowerPoint presentation',
      workbook: 'Configure Excel workbook output',
      email: 'Configure email delivery',
      slack: 'Configure Slack message',
      teams: 'Configure Microsoft Teams message',
    };
    return subtitles[type] || 'Configure this node';
  };

  const renderConfig = () => {
    switch (selectedNode.type) {
      case 'start':
        return <StartConfig />;
      case 'end':
        return <EndConfig />;
      case 'agent':
        return (
          <AgentConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'portfolio':
        return (
          <PortfolioConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'fileUpload':
        return (
          <FileUploadConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'oneDrive':
        return (
          <OneDriveConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'sharepoint':
        return (
          <SharePointConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'googleDrive':
        return (
          <GoogleDriveConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'pdfReport':
        return (
          <PDFReportConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'pptPresentation':
        return (
          <PPTConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'workbook':
        return (
          <WorkbookConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'email':
        return (
          <EmailConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'slack':
        return (
          <SlackConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'teams':
        return (
          <TeamsConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'saveToSentry':
        return <SaveToSentryConfig />;
      case 'merge':
        return (
          <MergeConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      case 'distribute':
        return (
          <DistributeConfig
            node={selectedNode}
            onUpdate={(data: any) => onUpdateNode(selectedNode.id, data)}
          />
        );
      default:
        return (
          <div style={{ padding: '24px', color: '#8A8886', fontSize: '14px' }}>
            Configuration coming soon...
          </div>
        );
    }
  };

  return (
    <div style={{
      width: '300px',
      background: '#FFFFFF',
      borderRadius: '12px',
      overflow: 'visible',
      display: 'flex',
      flexDirection: 'column',
      maxHeight: '100%',
      border: '1px solid #EDEBE9',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
      }}>
        <div style={{ flex: 1 }}>
          <div style={{
            fontSize: '16px',
            fontWeight: '600',
            color: '#1F1F1F',
            marginBottom: '4px',
          }}>
            {selectedNode.data?.label || selectedNode.type}
          </div>
          <div style={{
            fontSize: '12px',
            color: '#8A8886',
            fontWeight: '400',
          }}>
            {getSubtitle(selectedNode.type)}
          </div>
        </div>
        {/* Delete Button */}
        <button
          onClick={() => onDeleteNode(selectedNode.id)}
          title="Delete"
          style={{
            padding: '8px',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#EDEBE9'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          <Trash2 size={18} color="#605E5C" />
        </button>
      </div>

      {/* Config Content */}
      <div style={{ flex: 1, overflow: 'visible' }}>
        {renderConfig()}
      </div>
    </div>
  );
}

// Start Configuration Component
function StartConfig() {
  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {/* Description label */}
      <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600' }}>
        Description
      </label>
      {/* Description - locked/read-only */}
      <div style={{
        padding: '12px',
        background: '#F5F5F5',
        borderRadius: '6px',
        fontSize: '12px',
        color: '#605E5C',
        lineHeight: '1.5',
      }}>
        This is the default initialization node that marks the beginning of your workflow.
      </div>
    </div>
  );
}

// End Configuration Component
function EndConfig() {
  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {/* Description label */}
      <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600' }}>
        Description
      </label>
      {/* Description - locked/read-only */}
      <div style={{
        padding: '12px',
        background: '#F5F5F5',
        borderRadius: '6px',
        fontSize: '12px',
        color: '#605E5C',
        lineHeight: '1.5',
      }}>
        This is the terminal node that marks the completion of your workflow.
      </div>
    </div>
  );
}

// Agent Configuration Component
function AgentConfig({ node, onUpdate }: any) {
  const [showAgentDropdown, setShowAgentDropdown] = useState(false);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [showReasoningDropdown, setShowReasoningDropdown] = useState(false);
  const [showLengthDropdown, setShowLengthDropdown] = useState(false);

  const selectedAgent = agentModes.find(a => a.id === (node.data?.agent || 'auto')) || agentModes[0];
  const selectedModel = models.find(m => m.id === (node.data?.model || 'gpt-6.1-sol')) || models[0];
  const AgentIcon = selectedAgent.icon;

  const reasoningOptions = [
    { value: 'low', label: 'Low' },
    { value: 'medium', label: 'Medium' },
    { value: 'high', label: 'High' },
  ];

  const lengthOptions = [
    { value: 'short', label: 'Short' },
    { value: 'medium', label: 'Medium' },
    { value: 'long', label: 'Long' },
  ];

  const selectedReasoning = reasoningOptions.find(r => r.value === (node.data?.reasoning || 'low')) || reasoningOptions[0];
  const selectedLength = lengthOptions.find(l => l.value === (node.data?.responseLength || 'medium')) || lengthOptions[1];

  // Tools mapping by agent
  const agentToolsMap: Record<string, string[]> = {
    auto: ['All tools available'],
    generalist: [
      'web_search',
      'read_file_content',
      'search_file_chunks_tool',
      'drive_list_files',
      'drive_get_file_preview',
      'market_chart_build_tool',
      'get_latest_news',
      'get_news_by_symbol',
      'get_latest_alternatives_news',
      'get_alternatives_news_by_symbol',
      'CodeInterpreterTool',
      'auto',
    ],
    risk: [
      'calculate_var',
      'run_monte_carlo',
      'optimize_portfolio',
      'analyze_barra_factors',
      'create_hedge_portfolio',
      'compute_optimal_hedge_path',
      'get_latest_news',
      'get_news_by_symbol',
      'analyze_fft_trends',
      'calculate_rolling_correlation',
      'calculate_implied_correlation',
      'price_correlation_swap',
      'stress_test_correlation',
      'analyze_correlation_matrix',
      'analyze_graph_theory_risk',
      'analyze_systemic_risk_score',
      'detect_squeeze_setup',
      'calculate_delta_exposure',
      'calculate_gamma_exposure',
      'calculate_vega_exposure',
      'calculate_cross_greeks',
      'calculate_theta_decay',
      'construct_dynamic_hedge',
      'analyze_pca_eigen_portfolios',
      'model_volatility_surface',
      'analyze_dealer_gamma_regime',
      'analyze_vanna_charm_flow',
      'analyze_iv_rv_vs_peers',
      'analyze_gex_levels',
      'scan_nope_divergences',
      'analyze_herding_regime',
      'analyze_instanton_crash',
      'list_user_portfolios',
      'get_portfolio',
      'set_active_portfolio',
      'get_active_portfolio',
      'web_search',
      'CodeInterpreterTool',
      'auto',
    ],
    structuring: [
      'CodeInterpreterTool',
      'read_file_content',
      'search_file_chunks_tool',
      'price_interest_rate_swap',
      'price_swaption',
      'price_credit_default_swap',
      'price_variance_swap',
      'price_dispersion_trade',
      'price_exotic_derivatives',
      'price_equity_options',
      'model_volatility_surface',
      'calculate_delta_exposure',
      'calculate_gamma_exposure',
      'calculate_vega_exposure',
      'calculate_cross_greeks',
      'analyze_dealer_gamma_regime',
      'web_search',
      'auto',
    ],
    filings: [
      'sec_index_filing',
      'sec_search_filings',
      'sec_get_filing',
      'read_file_content',
      'search_file_chunks_tool',
      'drive_list_files',
      'drive_get_file_preview',
      'get_latest_news',
      'get_news_by_symbol',
      'web_search',
      'CodeInterpreterTool',
      'auto',
    ],
    multiples: [
      'analyze_comparable_companies',
      'get_latest_news',
      'get_news_by_symbol',
      'web_search',
      'CodeInterpreterTool',
      'auto',
    ],
    charts: [
      'read_file_content',
      'get_latest_news',
      'get_news_by_symbol',
      'web_search',
      'CodeInterpreterTool',
      'auto',
    ],
    quant: [
      'CodeInterpreterTool',
      'read_file_content',
      'search_file_chunks_tool',
      'forecast_arima',
      'forecast_arimax_macro',
      'analyze_recession_field',
      'analyze_herding_regime',
      'analyze_pca_eigen_portfolios',
      'analyze_feature_importance',
      'identify_cointegrated_pairs',
      'calculate_hedge_ratio',
      'compute_optimal_hedge_path',
      'generate_mean_reversion_signals',
      'price_correlation_swap',
      'analyze_correlation_matrix',
      'analyze_graph_theory_risk',
      'analyze_systemic_risk_score',
      'detect_squeeze_setup',
      'calculate_delta_exposure',
      'calculate_gamma_exposure',
      'calculate_vega_exposure',
      'calculate_cross_greeks',
      'calculate_theta_decay',
      'construct_dynamic_hedge',
      'price_equity_options',
      'model_volatility_surface',
      'analyze_dealer_gamma_regime',
      'analyze_vanna_charm_flow',
      'analyze_iv_rv_vs_peers',
      'analyze_gex_levels',
      'detect_signal_confluence',
      'scan_universe_confluence',
      'analyze_earnings_patterns',
      'scan_nope_divergences',
      'analyze_sector_rotation_flow',
      'analyze_instanton_crash',
      'analyze_portfolio_geodesic_distance',
      'get_latest_news',
      'get_news_by_symbol',
      'get_latest_alternatives_news',
      'get_alternatives_news_by_symbol',
      'web_search',
      'auto',
    ],
    dcf: [
      'gather_dcf_data_sources',
      'analyze_three_stage_dcf',
      'analyze_two_stage_dcf',
      'analyze_stable_stage_dcf',
      'analyze_reverse_dcf',
      'analyze_epv',
      'analyze_monte_carlo_dcf',
      'dcf_sensitivity_analysis',
      'read_file_content',
      'search_file_chunks_tool',
      'get_latest_news',
      'get_news_by_symbol',
      'web_search',
      'CodeInterpreterTool',
      'auto',
    ],
    alternatives: [
      'CodeInterpreterTool',
      'read_file_content',
      'search_file_chunks_tool',
      'analyze_crypto_equity_beta_regime',
      'analyze_commodity_ratio',
      'screen_forex_carry_trades',
      'analyze_commodity_seasonality',
      'screen_commodity_momentum',
      'get_latest_news',
      'get_news_by_symbol',
      'get_latest_alternatives_news',
      'get_alternatives_news_by_symbol',
      'web_search',
      'auto',
    ],
    institutional: [
      'CodeInterpreterTool',
      'read_file_content',
      'search_file_chunks_tool',
      'web_search',
      'auto',
    ],
    prediction_markets: [
      'discover_polymarket_tags',
      'get_polymarket_markets_by_tag',
      'discover_polymarket_market_fields',
      'search_polymarket_markets',
      'get_polymarket_quotes',
      'get_polymarket_price_history',
      'CodeInterpreterTool',
      'read_file_content',
      'search_file_chunks_tool',
      'web_search',
      'auto',
    ],
    funds_products: [
      'CodeInterpreterTool',
      'read_file_content',
      'search_file_chunks_tool',
      'forecast_tearsheet_returns',
      'forecast_tearsheet_with_macro',
      'compare_fund_returns',
      'get_latest_news',
      'get_news_by_symbol',
      'web_search',
      'auto',
    ],
  };

  // Get base tools for the agent
  const availableTools = [...(agentToolsMap[selectedAgent.id] || [])];

  // Add code_interpreter only for OpenAI GPT models for specific agents
  const isGPT5Model = selectedModel.id.startsWith('gpt-');
  const gpt5Agents = ['generalist', 'risk', 'multiples', 'charts', 'quant', 'dcf', 'alternatives', 'institutional', 'prediction_markets', 'funds_products', 'structuring'];
  if (gpt5Agents.includes(selectedAgent.id) && isGPT5Model) {
    availableTools.push('code_interpreter');
  }

  const selectedTools = node.data?.tools || ['auto'];

  const toggleTool = (tool: string) => {
    const newTools = selectedTools.includes(tool)
      ? selectedTools.filter((t: string) => t !== tool)
      : [...selectedTools, tool];
    onUpdate({ ...node.data, tools: newTools });
  };

  // MCP Servers mapping by agent
  const agentMCPServersMap: Record<string, string[]> = {
    auto: ['All MCP servers available'],
    generalist: ['market_data', 'economic_data', 'auto'],
    risk: ['yahoo_finance', 'economic_data', 'unusualwhales', 'auto'],
    filings: ['fmp_documents', 'sec_filings', 'auto'],
    multiples: ['market_data', 'auto'],
    charts: ['market_data', 'auto'],
    quant: ['market_data', 'economic_data', 'alternatives_data', 'unusualwhales', 'auto'],
    dcf: ['market_data', 'economic_data', 'advanced_valuation', 'auto'],
    alternatives: ['polygon_crypto_fx', 'alternatives_data', 'economic_data', 'auto'],
    institutional: ['trade_flow', 'unusualwhales', 'auto'],
    prediction_markets: ['market_data', 'polymarket', 'prediction_markets', 'auto'],
    funds_products: ['market_data', 'alternatives_data', 'economic_data', 'auto'],
    structuring: ['market_data', 'trade_flow', 'economic_data', 'unusualwhales', 'auto'],
  };

  const availableMCPServers = agentMCPServersMap[selectedAgent.id] || [];
  const selectedMCPServers = node.data?.mcpServers || ['auto'];

  const toggleMCPServer = (server: string) => {
    const newServers = selectedMCPServers.includes(server)
      ? selectedMCPServers.filter((s: string) => s !== server)
      : [...selectedMCPServers, server];
    onUpdate({ ...node.data, mcpServers: newServers });
  };

  const [showToolsDropdown, setShowToolsDropdown] = useState(false);
  const [showMCPServersDropdown, setShowMCPServersDropdown] = useState(false);

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Select Agent Dropdown */}
      <div style={{ position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Select Agent
        </label>
        <button
          onClick={() => setShowAgentDropdown(!showAgentDropdown)}
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: '#FFFFFF',
            color: '#1F1F1F',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AgentIcon size={16} style={{ color: selectedAgent.color }} />
            <span>{selectedAgent.name}</span>
          </div>
          <ChevronDown size={14} />
        </button>

        {showAgentDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: '4px',
            maxHeight: '200px',
            overflowY: 'auto',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
          }}>
            {agentModes.map((agent) => {
              const Icon = agent.icon;
              return (
                <div
                  key={agent.id}
                  onClick={() => {
                    onUpdate({ ...node.data, agent: agent.id });
                    setShowAgentDropdown(false);
                  }}
                  style={{
                    padding: '8px 10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '12px',
                    background: agent.id === selectedAgent.id ? '#F5F5F5' : 'transparent',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                  onMouseLeave={(e) => e.currentTarget.style.background = agent.id === selectedAgent.id ? '#F5F5F5' : 'transparent'}
                >
                  <Icon size={14} style={{ color: agent.color }} />
                  <span>{agent.name}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Model Section */}
      <div style={{ position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Model
        </label>
        <button
          onClick={() => setShowModelDropdown(!showModelDropdown)}
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: '#FFFFFF',
            color: '#1F1F1F',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src={selectedModel.logo} alt={selectedModel.name} style={{ width: '16px', height: '16px', borderRadius: '3px' }} />
            <span>{selectedModel.name}</span>
          </div>
          <ChevronDown size={14} />
        </button>

        {showModelDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: '4px',
            maxHeight: '200px',
            overflowY: 'auto',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
          }}>
            {models.map((model) => (
              <div
                key={model.id}
                onClick={() => {
                  onUpdate({ ...node.data, model: model.id });
                  setShowModelDropdown(false);
                }}
                style={{
                  padding: '8px 10px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '12px',
                  background: model.id === selectedModel.id ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = model.id === selectedModel.id ? '#F5F5F5' : 'transparent'}
              >
                <img src={model.logo} alt={model.name} style={{ width: '16px', height: '16px', borderRadius: '3px' }} />
                <span>{model.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Reasoning Level - inline */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Reasoning level
        </label>
        <button
          onClick={() => setShowReasoningDropdown(!showReasoningDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedReasoning.label}
          <ChevronDown size={12} />
        </button>

        {showReasoningDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '120px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {reasoningOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, reasoning: option.value });
                  setShowReasoningDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedReasoning.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedReasoning.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedReasoning.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Response Length - inline */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Response length
        </label>
        <button
          onClick={() => setShowLengthDropdown(!showLengthDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedLength.label}
          <ChevronDown size={12} />
        </button>

        {showLengthDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '120px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {lengthOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, responseLength: option.value });
                  setShowLengthDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedLength.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedLength.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedLength.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tools Section */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Tools
        </label>

        {/* Multi-select dropdown button */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowToolsDropdown(!showToolsDropdown)}
            style={{
              width: '100%',
              padding: '8px 10px',
              fontSize: '12px',
              border: '1px solid #EDEBE9',
              borderRadius: '6px',
              background: '#FFFFFF',
              color: '#1F1F1F',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              textAlign: 'left',
            }}
          >
            <span style={{ color: '#8A8886' }}>
              {selectedTools.length === 0 ? 'Select tools...' : `${selectedTools.length} tool${selectedTools.length !== 1 ? 's' : ''} selected`}
            </span>
            <ChevronDown size={14} />
          </button>

          {showToolsDropdown && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: '4px',
              maxHeight: '200px',
              overflowY: 'auto',
              overflowX: 'hidden',
              background: '#FFFFFF',
              border: '1px solid #EDEBE9',
              borderRadius: '6px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              zIndex: 10,
            }}>
              {availableTools.map((tool) => (
                <div
                  key={tool}
                  onClick={() => toggleTool(tool)}
                  style={{
                    padding: '8px 10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '12px',
                    background: 'transparent',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <input
                    type="checkbox"
                    checked={selectedTools.includes(tool)}
                    readOnly
                    style={{
                      width: '14px',
                      height: '14px',
                      cursor: 'pointer',
                      accentColor: '#2196F3',
                    }}
                  />
                  <span>{tool}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Selected tools display area (chips) */}
        {selectedTools.length > 0 && (
          <div style={{
            marginTop: '8px',
            padding: '12px',
            background: '#F5F5F5',
            borderRadius: '6px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '6px',
          }}>
            {selectedTools.map((tool: string) => (
              <div
                key={tool}
                style={{
                  padding: '4px 8px',
                  background: '#FFFFFF',
                  border: '1px solid #EDEBE9',
                  borderRadius: '4px',
                  fontSize: '11px',
                  color: '#605E5C',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span>{tool}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleTool(tool);
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '0',
                    display: 'flex',
                    alignItems: 'center',
                    color: '#8A8886',
                    fontSize: '14px',
                    lineHeight: '1',
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* MCP Servers Section */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          MCP Servers
        </label>

        {/* Multi-select dropdown button */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowMCPServersDropdown(!showMCPServersDropdown)}
            style={{
              width: '100%',
              padding: '8px 10px',
              fontSize: '12px',
              border: '1px solid #EDEBE9',
              borderRadius: '6px',
              background: '#FFFFFF',
              color: '#1F1F1F',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              textAlign: 'left',
            }}
          >
            <span style={{ color: '#8A8886' }}>
              {selectedMCPServers.length === 0 ? 'Select MCP servers...' : `${selectedMCPServers.length} server${selectedMCPServers.length !== 1 ? 's' : ''} selected`}
            </span>
            <ChevronDown size={14} />
          </button>

          {showMCPServersDropdown && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: '4px',
              maxHeight: '200px',
              overflowY: 'auto',
              overflowX: 'hidden',
              background: '#FFFFFF',
              border: '1px solid #EDEBE9',
              borderRadius: '6px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              zIndex: 10,
            }}>
              {availableMCPServers.map((server) => (
                <div
                  key={server}
                  onClick={() => toggleMCPServer(server)}
                  style={{
                    padding: '8px 10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '12px',
                    background: 'transparent',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <input
                    type="checkbox"
                    checked={selectedMCPServers.includes(server)}
                    readOnly
                    style={{
                      width: '14px',
                      height: '14px',
                      cursor: 'pointer',
                      accentColor: '#2196F3',
                    }}
                  />
                  <span>{server}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Selected MCP servers display area (chips) */}
        {selectedMCPServers.length > 0 && (
          <div style={{
            marginTop: '8px',
            padding: '12px',
            background: '#F5F5F5',
            borderRadius: '6px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '6px',
          }}>
            {selectedMCPServers.map((server: string) => (
              <div
                key={server}
                style={{
                  padding: '4px 8px',
                  background: '#FFFFFF',
                  border: '1px solid #EDEBE9',
                  borderRadius: '4px',
                  fontSize: '11px',
                  color: '#605E5C',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span>{server}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleMCPServer(server);
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '0',
                    display: 'flex',
                    alignItems: 'center',
                    color: '#8A8886',
                    fontSize: '14px',
                    lineHeight: '1',
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Instructions */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Instructions
        </label>
        <textarea
          value={node.data?.instructions || ''}
          onChange={(e) => onUpdate({ ...node.data, instructions: e.target.value })}
          placeholder="Write your prompt here..."
          rows={4}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>
    </div>
  );
}

// Portfolio Configuration Component
function PortfolioConfig({ node, onUpdate }: any) {
  const [portfolios, setPortfolios] = useState<PortfolioData[]>([]);
  const [loading, setLoading] = useState(true);
  const [showPortfolioDropdown, setShowPortfolioDropdown] = useState(false);

  // Fetch portfolios on mount
  useEffect(() => {
    const loadPortfolios = async () => {
      try {
        const data = await portfolioApiService.listPortfolios();
        setPortfolios(data);
      } catch (error) {
        console.error('Failed to load portfolios:', error);
      } finally {
        setLoading(false);
      }
    };
    loadPortfolios();
  }, []);

  const selectedPortfolioId = node.data?.portfolioId;
  const selectedPortfolio = portfolios.find(p => p.id === selectedPortfolioId);

  // Default name to portfolio name if not set
  const displayName = node.data?.name || selectedPortfolio?.name || '';

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Select Portfolio Dropdown */}
      <div style={{ position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Select Portfolio
        </label>
        <button
          onClick={() => setShowPortfolioDropdown(!showPortfolioDropdown)}
          disabled={loading}
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: '#FFFFFF',
            color: '#1F1F1F',
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            opacity: loading ? 0.6 : 1,
          }}
        >
          <span>{loading ? 'Loading portfolios...' : (selectedPortfolio?.name || 'Select a portfolio')}</span>
          <ChevronDown size={14} />
        </button>

        {showPortfolioDropdown && !loading && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: '4px',
            maxHeight: '200px',
            overflowY: 'auto',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
          }}>
            {portfolios.length === 0 ? (
              <div style={{ padding: '12px', fontSize: '12px', color: '#8A8886', textAlign: 'center' }}>
                No portfolios found
              </div>
            ) : (
              portfolios.map((portfolio) => (
                <div
                  key={portfolio.id}
                  onClick={() => {
                    onUpdate({
                      ...node.data,
                      portfolioId: portfolio.id,
                      name: portfolio.name, // Auto-set name to portfolio name
                    });
                    setShowPortfolioDropdown(false);
                  }}
                  style={{
                    padding: '8px 10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '12px',
                    background: portfolio.id === selectedPortfolioId ? '#F5F5F5' : 'transparent',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                  onMouseLeave={(e) => e.currentTarget.style.background = portfolio.id === selectedPortfolioId ? '#F5F5F5' : 'transparent'}
                >
                  <div>
                    <div>{portfolio.name}</div>
                    <div style={{ fontSize: '10px', color: '#8A8886', marginTop: '2px' }}>
                      {portfolio.tickers.length} assets
                    </div>
                  </div>
                  {portfolio.is_default && (
                    <span style={{ fontSize: '10px', color: '#2196F3', fontWeight: '600' }}>DEFAULT</span>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Name Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Name (Optional)
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => onUpdate({ ...node.data, name: e.target.value })}
          placeholder="Enter custom name"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            background: '#FFFFFF',
            color: '#1F1F1F',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = '#0078D4'}
          onBlur={(e) => e.currentTarget.style.borderColor = '#EDEBE9'}
        />
      </div>

      {/* Description Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Description (Optional)
        </label>
        <textarea
          value={node.data?.description || ''}
          onChange={(e) => onUpdate({ ...node.data, description: e.target.value })}
          placeholder="Add a description..."
          rows={4}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>
    </div>
  );
}

// File Upload Configuration Component
function FileUploadConfig({ node, onUpdate }: any) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(
    node.data?.fileId ? {
      id: node.data.fileId,
      original_name: node.data.fileName || '',
      size: node.data.fileSize || 0,
      content_type: node.data.fileType || '',
    } as UploadedFile : null,
  );

  // Display name defaults to uploaded file name if available
  const displayName = node.data?.name || '';
  const fileName = node.data?.fileName || '';

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      // Upload file to backend (same as Chat does)
      const [uploaded] = await uploadService.uploadFiles([file]);
      setUploadedFile(uploaded);

      // Update node with BOTH file name AND file ID
      onUpdate({
        ...node.data,
        fileName: uploaded.original_name,
        fileId: uploaded.id, // NEW: Store backend file ID
        name: uploaded.original_name, // Auto-set name to file name
        fileSize: uploaded.size,
        fileType: uploaded.content_type,
      });

      toast.success('File uploaded successfully');
    } catch (err) {
      console.error('Upload failed:', err);
      toast.error('Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const handleFileUploadClick = () => {
    if (!uploading) {
      fileInputRef.current?.click();
    }
  };

  const handleRemoveFile = async () => {
    if (uploadedFile?.id) {
      try {
        await uploadService.deleteFile(uploadedFile.id);
        toast.success('File removed');
      } catch (err) {
        console.warn('Failed to delete file:', err);
        // Don't show error to user - file might already be deleted
      }
    }
    setUploadedFile(null);
    onUpdate({
      ...node.data,
      fileName: null,
      fileId: null,
      name: '',
      fileSize: null,
      fileType: null,
    });
  };

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* File Upload Area */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Upload File
        </label>
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          disabled={uploading}
        />
        <button
          onClick={handleFileUploadClick}
          disabled={uploading}
          style={{
            width: '100%',
            padding: '32px 16px',
            fontSize: '12px',
            border: '2px dashed #EDEBE9',
            borderRadius: '6px',
            background: uploading ? '#F5F5F5' : '#FAFAFA',
            color: uploading ? '#A19F9D' : '#605E5C',
            cursor: uploading ? 'not-allowed' : 'pointer',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '8px',
            transition: 'all 0.2s',
            opacity: uploading ? 0.6 : 1,
          }}
          onMouseEnter={(e) => {
            if (!uploading) {
              e.currentTarget.style.borderColor = '#0078D4';
              e.currentTarget.style.background = '#F3F9FF';
            }
          }}
          onMouseLeave={(e) => {
            if (!uploading) {
              e.currentTarget.style.borderColor = '#EDEBE9';
              e.currentTarget.style.background = '#FAFAFA';
            }
          }}
        >
          <Upload size={20} style={{ color: uploading ? '#A19F9D' : '#FF9800' }} />
          <div style={{ textAlign: 'center' }}>
            {uploading ? (
              <>
                <div style={{ fontWeight: '600', color: '#1F1F1F', marginBottom: '4px' }}>Uploading...</div>
                <div style={{ fontSize: '11px', color: '#8A8886' }}>Please wait</div>
              </>
            ) : fileName ? (
              <>
                <div style={{ fontWeight: '600', color: '#1F1F1F', marginBottom: '4px' }}>{fileName}</div>
                <div style={{ fontSize: '11px', color: '#8A8886' }}>Click to change file</div>
              </>
            ) : (
              <>
                <div style={{ fontWeight: '600', color: '#1F1F1F' }}>Click to upload</div>
                <div style={{ fontSize: '11px', color: '#8A8886' }}>or drag and drop</div>
              </>
            )}
          </div>
        </button>

        {/* Remove File Button */}
        {uploadedFile && !uploading && (
          <button
            onClick={handleRemoveFile}
            style={{
              marginTop: '8px',
              width: '100%',
              padding: '8px',
              fontSize: '12px',
              border: '1px solid #E1DFDD',
              borderRadius: '6px',
              background: '#FFFFFF',
              color: '#A4262C',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#FFF4F4';
              e.currentTarget.style.borderColor = '#A4262C';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#FFFFFF';
              e.currentTarget.style.borderColor = '#E1DFDD';
            }}
          >
            <Trash2 size={14} />
            Remove File
          </button>
        )}
      </div>

      {/* Name Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Name (Optional)
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => onUpdate({ ...node.data, name: e.target.value })}
          placeholder="Enter custom name"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            background: '#FFFFFF',
            color: '#1F1F1F',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = '#0078D4'}
          onBlur={(e) => e.currentTarget.style.borderColor = '#EDEBE9'}
        />
      </div>

      {/* Description Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Description (Optional)
        </label>
        <textarea
          value={node.data?.description || ''}
          onChange={(e) => onUpdate({ ...node.data, description: e.target.value })}
          placeholder="Add a description..."
          rows={4}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>
    </div>
  );
}


// OneDrive Configuration Component
function OneDriveConfig({ node, onUpdate }: any) {
  const [showAccountTypeDropdown, setShowAccountTypeDropdown] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(
    node.data?.fileId ? {
      id: node.data.fileId,
      original_name: node.data.connectedFile || '',
      size: node.data.fileSize || 0,
      content_type: node.data.fileType || '',
    } as UploadedFile : null,
  );

  const accountTypeOptions = [
    { value: 'personal', label: 'Personal' },
    { value: 'business', label: 'Business' },
  ];

  const selectedAccountType = accountTypeOptions.find(a => a.value === (node.data?.accountType || 'personal')) || accountTypeOptions[0];
  const displayName = node.data?.name || '';

  const handleFileSelect = async (file: File) => {
    setShowPicker(false);
    setUploading(true);

    try {
      // Upload OneDrive file to backend storage (same as Chat)
      const [uploaded] = await uploadService.uploadFiles([file]);
      setUploadedFile(uploaded);

      // Update node with BOTH file name AND file ID
      onUpdate({
        ...node.data,
        connectedFile: uploaded.original_name,
        fileId: uploaded.id, // NEW: Store backend file ID
        name: uploaded.original_name,
        fileSize: uploaded.size,
        fileType: uploaded.content_type,
      });

      toast.success('OneDrive file uploaded successfully');
    } catch (err) {
      console.error('Upload failed:', err);
      toast.error('Failed to upload OneDrive file');
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveFile = async () => {
    if (uploadedFile?.id) {
      try {
        await uploadService.deleteFile(uploadedFile.id);
        toast.success('File removed');
      } catch (err) {
        console.warn('Failed to delete file:', err);
      }
    }
    setUploadedFile(null);
    onUpdate({
      ...node.data,
      connectedFile: null,
      fileId: null,
      name: '',
      fileSize: null,
      fileType: null,
    });
  };

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Account Type - inline */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Account type
        </label>
        <button
          onClick={() => setShowAccountTypeDropdown(!showAccountTypeDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedAccountType.label}
          <ChevronDown size={12} />
        </button>

        {showAccountTypeDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '120px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {accountTypeOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, accountType: option.value });
                  setShowAccountTypeDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedAccountType.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedAccountType.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedAccountType.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Connect Button */}
      <div>
        <button
          onClick={() => setShowPicker(true)}
          disabled={uploading}
          style={{
            width: '100%',
            padding: '10px 16px',
            fontSize: '13px',
            fontWeight: '500',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: uploading ? '#F5F5F5' : '#FAFAFA',
            color: uploading ? '#A19F9D' : '#1F1F1F',
            cursor: uploading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            transition: 'all 0.2s',
            opacity: uploading ? 0.6 : 1,
          }}
          onMouseEnter={(e) => {
            if (!uploading) {
              e.currentTarget.style.background = '#F5F5F5';
              e.currentTarget.style.borderColor = '#0078D4';
            }
          }}
          onMouseLeave={(e) => {
            if (!uploading) {
              e.currentTarget.style.background = '#FAFAFA';
              e.currentTarget.style.borderColor = '#EDEBE9';
            }
          }}
        >
          <Link size={16} style={{ color: uploading ? '#A19F9D' : '#0078D4' }} />
          {uploading ? 'Uploading...' : node.data?.connectedFile ? `Connected: ${node.data.connectedFile}` : 'Connect to OneDrive'}
        </button>

        {/* Remove File Button */}
        {uploadedFile && !uploading && (
          <button
            onClick={handleRemoveFile}
            style={{
              marginTop: '8px',
              width: '100%',
              padding: '8px',
              fontSize: '12px',
              border: '1px solid #E1DFDD',
              borderRadius: '6px',
              background: '#FFFFFF',
              color: '#A4262C',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#FFF4F4';
              e.currentTarget.style.borderColor = '#A4262C';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#FFFFFF';
              e.currentTarget.style.borderColor = '#E1DFDD';
            }}
          >
            <Trash2 size={14} />
            Remove File
          </button>
        )}
      </div>

      {/* OneDrive Picker Modal */}
      {showPicker && (
        <OneDriveNativePicker
          accountType={selectedAccountType.value as 'personal' | 'business' | 'sharepoint'}
          allowAllFileTypes={true}
          onSelect={handleFileSelect}
          onClose={() => setShowPicker(false)}
        />
      )}

      {/* Name Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Name (Optional)
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => onUpdate({ ...node.data, name: e.target.value })}
          placeholder="Enter custom name"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            background: '#FFFFFF',
            color: '#1F1F1F',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = '#0078D4'}
          onBlur={(e) => e.currentTarget.style.borderColor = '#EDEBE9'}
        />
      </div>

      {/* Description Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Description (Optional)
        </label>
        <textarea
          value={node.data?.description || ''}
          onChange={(e) => onUpdate({ ...node.data, description: e.target.value })}
          placeholder="Add a description..."
          rows={4}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>
    </div>
  );
}

// SharePoint Configuration Component
function SharePointConfig({ node, onUpdate }: any) {
  const [showPicker, setShowPicker] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(
    node.data?.fileId ? {
      id: node.data.fileId,
      original_name: node.data.connectedFile || '',
      size: node.data.fileSize || 0,
      content_type: node.data.fileType || '',
    } as UploadedFile : null,
  );

  const displayName = node.data?.name || '';

  const handleFileSelect = async (file: File) => {
    setShowPicker(false);
    setUploading(true);

    try {
      // Upload SharePoint file to backend storage (same as Chat)
      const [uploaded] = await uploadService.uploadFiles([file]);
      setUploadedFile(uploaded);

      // Update node with BOTH file name AND file ID
      onUpdate({
        ...node.data,
        connectedFile: uploaded.original_name,
        fileId: uploaded.id, // NEW: Store backend file ID
        name: uploaded.original_name,
        fileSize: uploaded.size,
        fileType: uploaded.content_type,
      });

      toast.success('SharePoint file uploaded successfully');
    } catch (err) {
      console.error('Upload failed:', err);
      toast.error('Failed to upload SharePoint file');
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveFile = async () => {
    if (uploadedFile?.id) {
      try {
        await uploadService.deleteFile(uploadedFile.id);
        toast.success('File removed');
      } catch (err) {
        console.warn('Failed to delete file:', err);
      }
    }
    setUploadedFile(null);
    onUpdate({
      ...node.data,
      connectedFile: null,
      fileId: null,
      name: '',
      fileSize: null,
      fileType: null,
    });
  };

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Connect Button */}
      <div>
        <button
          onClick={() => setShowPicker(true)}
          disabled={uploading}
          style={{
            width: '100%',
            padding: '10px 16px',
            fontSize: '13px',
            fontWeight: '500',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: uploading ? '#F5F5F5' : '#036C70',
            color: uploading ? '#A19F9D' : '#FFFFFF',
            cursor: uploading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
          }}
          onMouseEnter={(e) => {
            if (!uploading) {
              e.currentTarget.style.background = '#025a5d';
            }
          }}
          onMouseLeave={(e) => {
            if (!uploading) {
              e.currentTarget.style.background = '#036C70';
            }
          }}
        >
          {uploading ? 'Uploading...' : 'Connect SharePoint'}
        </button>
      </div>

      {/* Show connected file info */}
      <div>
        {uploadedFile && (
          <button
            onClick={handleRemoveFile}
            style={{
              width: '100%',
              padding: '10px 16px',
              fontSize: '13px',
              fontWeight: '400',
              border: '1px solid #D32F2F',
              borderRadius: '6px',
              background: '#FFFFFF',
              color: '#D32F2F',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#FFEBEE';
              e.currentTarget.style.borderColor = '#C62828';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#FFFFFF';
              e.currentTarget.style.borderColor = '#D32F2F';
            }}
          >
            <Trash2 size={14} />
            Remove File
          </button>
        )}
      </div>

      {/* SharePoint Picker Modal */}
      {showPicker && (
        <OneDriveNativePicker
          accountType="sharepoint"
          allowAllFileTypes={true}
          onSelect={handleFileSelect}
          onClose={() => setShowPicker(false)}
        />
      )}

      {/* Name Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Name (Optional)
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => onUpdate({ ...node.data, name: e.target.value })}
          placeholder="Enter custom name"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            background: '#FFFFFF',
            color: '#1F1F1F',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = '#036C70'}
          onBlur={(e) => e.currentTarget.style.borderColor = '#EDEBE9'}
        />
      </div>

      {/* Description Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Description (Optional)
        </label>
        <textarea
          value={node.data?.description || ''}
          onChange={(e) => onUpdate({ ...node.data, description: e.target.value })}
          placeholder="Add a description..."
          rows={3}
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>
    </div>
  );
}

// Google Drive Configuration Component
function GoogleDriveConfig({ node, onUpdate }: any) {
  const [showPicker, setShowPicker] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(
    node.data?.fileId ? {
      id: node.data.fileId,
      original_name: node.data.connectedFile || '',
      size: node.data.fileSize || 0,
      content_type: node.data.fileType || '',
    } as UploadedFile : null,
  );

  const displayName = node.data?.name || '';

  const handleFileSelect = async (file: File) => {
    setShowPicker(false);
    setUploading(true);

    try {
      // Upload Google Drive file to backend storage (same as Chat)
      const [uploaded] = await uploadService.uploadFiles([file]);
      setUploadedFile(uploaded);

      // Update node with BOTH file name AND file ID
      onUpdate({
        ...node.data,
        connectedFile: uploaded.original_name,
        fileId: uploaded.id, // NEW: Store backend file ID
        name: uploaded.original_name,
        fileSize: uploaded.size,
        fileType: uploaded.content_type,
      });

      toast.success('Google Drive file uploaded successfully');
    } catch (err) {
      console.error('Upload failed:', err);
      toast.error('Failed to upload Google Drive file');
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveFile = async () => {
    if (uploadedFile?.id) {
      try {
        await uploadService.deleteFile(uploadedFile.id);
        toast.success('File removed');
      } catch (err) {
        console.warn('Failed to delete file:', err);
      }
    }
    setUploadedFile(null);
    onUpdate({
      ...node.data,
      connectedFile: null,
      fileId: null,
      name: '',
      fileSize: null,
      fileType: null,
    });
  };

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Account Type - Static Label */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Account type
        </label>
        <span style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '400' }}>
          All
        </span>
      </div>

      {/* Connect Button */}
      <div>
        <button
          onClick={() => setShowPicker(true)}
          disabled={uploading}
          style={{
            width: '100%',
            padding: '10px 16px',
            fontSize: '13px',
            fontWeight: '500',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: uploading ? '#F5F5F5' : '#FAFAFA',
            color: uploading ? '#A19F9D' : '#1F1F1F',
            cursor: uploading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            transition: 'all 0.2s',
            opacity: uploading ? 0.6 : 1,
          }}
          onMouseEnter={(e) => {
            if (!uploading) {
              e.currentTarget.style.background = '#F5F5F5';
              e.currentTarget.style.borderColor = '#4285F4';
            }
          }}
          onMouseLeave={(e) => {
            if (!uploading) {
              e.currentTarget.style.background = '#FAFAFA';
              e.currentTarget.style.borderColor = '#EDEBE9';
            }
          }}
        >
          <Link size={16} style={{ color: uploading ? '#A19F9D' : '#4285F4' }} />
          {uploading ? 'Uploading...' : node.data?.connectedFile ? `Connected: ${node.data.connectedFile}` : 'Connect to Google Drive'}
        </button>

        {/* Remove File Button */}
        {uploadedFile && !uploading && (
          <button
            onClick={handleRemoveFile}
            style={{
              marginTop: '8px',
              width: '100%',
              padding: '8px',
              fontSize: '12px',
              border: '1px solid #E1DFDD',
              borderRadius: '6px',
              background: '#FFFFFF',
              color: '#A4262C',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#FFF4F4';
              e.currentTarget.style.borderColor = '#A4262C';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#FFFFFF';
              e.currentTarget.style.borderColor = '#E1DFDD';
            }}
          >
            <Trash2 size={14} />
            Remove File
          </button>
        )}
      </div>

      {/* Google Drive Picker Modal */}
      {showPicker && (
        <GoogleDriveNativePicker
          allowAllFileTypes={true}
          onSelect={handleFileSelect}
          onClose={() => setShowPicker(false)}
        />
      )}

      {/* Name Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Name (Optional)
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => onUpdate({ ...node.data, name: e.target.value })}
          placeholder="Enter custom name"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            background: '#FFFFFF',
            color: '#1F1F1F',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = '#4285F4'}
          onBlur={(e) => e.currentTarget.style.borderColor = '#EDEBE9'}
        />
      </div>

      {/* Description Field (Optional) */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Description (Optional)
        </label>
        <textarea
          value={node.data?.description || ''}
          onChange={(e) => onUpdate({ ...node.data, description: e.target.value })}
          placeholder="Add a description..."
          rows={4}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>
    </div>
  );
}

// PDF Report Configuration Component
function PDFReportConfig({ node, onUpdate }: any) {
  const [showDataIntensityDropdown, setShowDataIntensityDropdown] = useState(false);
  const [showVerbosityDropdown, setShowVerbosityDropdown] = useState(false);
  const [showStyleDropdown, setShowStyleDropdown] = useState(false);
  const [exportStyles, setExportStyles] = useState<ExportStyle[]>([]);
  const [loadingStyles, setLoadingStyles] = useState(true);

  const dataIntensityOptions = [
    { value: 'high', label: 'High' },
    { value: 'mid', label: 'Mid' },
    { value: 'low', label: 'Low' },
  ];

  const verbosityOptions = [
    { value: 'high', label: 'High' },
    { value: 'mid', label: 'Mid' },
    { value: 'low', label: 'Low' },
  ];

  const selectedDataIntensity = dataIntensityOptions.find(d => d.value === (node.data?.dataIntensity || 'mid')) || dataIntensityOptions[1];
  const selectedVerbosity = verbosityOptions.find(v => v.value === (node.data?.verbosity || 'mid')) || verbosityOptions[1];
  const displayName = node.data?.name || '';

  // Fetch export styles on mount
  useEffect(() => {
    const loadStyles = async () => {
      try {
        const styles = await userSettingsApiService.listExportStyles();
        setExportStyles(styles);
      } catch (error) {
        console.error('Failed to load export styles:', error);
        setExportStyles([]); // Fallback to empty
      } finally {
        setLoadingStyles(false);
      }
    };
    loadStyles();
  }, []);

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Name Field */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Name
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => onUpdate({ ...node.data, name: e.target.value })}
          placeholder="Enter report name"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            background: '#FFFFFF',
            color: '#1F1F1F',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = '#0078D4'}
          onBlur={(e) => e.currentTarget.style.borderColor = '#EDEBE9'}
        />
      </div>

      {/* Content Instructions */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Content Instructions
        </label>
        <textarea
          value={node.data?.contentInstructions || ''}
          onChange={(e) => onUpdate({ ...node.data, contentInstructions: e.target.value })}
          placeholder="Describe what should be included in the report..."
          rows={4}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>

      {/* Data Intensity - inline dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Data intensity
        </label>
        <button
          onClick={() => setShowDataIntensityDropdown(!showDataIntensityDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedDataIntensity.label}
          <ChevronDown size={12} />
        </button>

        {showDataIntensityDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '100px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {dataIntensityOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, dataIntensity: option.value });
                  setShowDataIntensityDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedDataIntensity.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedDataIntensity.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedDataIntensity.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Verbosity - inline dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Verbosity
        </label>
        <button
          onClick={() => setShowVerbosityDropdown(!showVerbosityDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedVerbosity.label}
          <ChevronDown size={12} />
        </button>

        {showVerbosityDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '100px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {verbosityOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, verbosity: option.value });
                  setShowVerbosityDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedVerbosity.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedVerbosity.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedVerbosity.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Export Style - inline dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Export Style
        </label>
        <button
          onClick={() => setShowStyleDropdown(!showStyleDropdown)}
          disabled={loadingStyles}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: loadingStyles ? 'not-allowed' : 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            opacity: loadingStyles ? 0.6 : 1,
          }}
        >
          {loadingStyles ? 'Loading...' : (node.data?.style_name || 'Default')}
          <ChevronDown size={12} />
        </button>

        {showStyleDropdown && !loadingStyles && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '120px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {/* Default option */}
            <div
              onClick={() => {
                onUpdate({ ...node.data, style_name: undefined });
                setShowStyleDropdown(false);
              }}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '12px',
                background: !node.data?.style_name ? '#F5F5F5' : 'transparent',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
              onMouseLeave={(e) => e.currentTarget.style.background = !node.data?.style_name ? '#F5F5F5' : 'transparent'}
            >
              <span>Default</span>
              {!node.data?.style_name && <span>✓</span>}
            </div>

            {/* User's saved styles */}
            {exportStyles.map((style) => (
              <div
                key={style.style_name}
                onClick={() => {
                  onUpdate({ ...node.data, style_name: style.style_name });
                  setShowStyleDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: style.style_name === node.data?.style_name ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = style.style_name === node.data?.style_name ? '#F5F5F5' : 'transparent'}
              >
                <span>{style.style_name}</span>
                {style.style_name === node.data?.style_name && <span>✓</span>}
              </div>
            ))}

            {exportStyles.length === 0 && (
              <div style={{ padding: '8px 12px', fontSize: '12px', color: '#8A8886', textAlign: 'center' }}>
                No custom styles
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// PPT Presentation Configuration Component
function PPTConfig({ node, onUpdate }: any) {
  const [showDataIntensityDropdown, setShowDataIntensityDropdown] = useState(false);
  const [showVerbosityDropdown, setShowVerbosityDropdown] = useState(false);
  const [showStyleDropdown, setShowStyleDropdown] = useState(false);
  const [exportStyles, setExportStyles] = useState<ExportStyle[]>([]);
  const [loadingStyles, setLoadingStyles] = useState(true);

  const dataIntensityOptions = [
    { value: 'high', label: 'High' },
    { value: 'mid', label: 'Mid' },
    { value: 'low', label: 'Low' },
  ];

  const verbosityOptions = [
    { value: 'high', label: 'High' },
    { value: 'mid', label: 'Mid' },
    { value: 'low', label: 'Low' },
  ];

  const selectedDataIntensity = dataIntensityOptions.find(d => d.value === (node.data?.dataIntensity || 'mid')) || dataIntensityOptions[1];
  const selectedVerbosity = verbosityOptions.find(v => v.value === (node.data?.verbosity || 'mid')) || verbosityOptions[1];
  const displayName = node.data?.name || '';

  // Fetch export styles on mount
  useEffect(() => {
    const loadStyles = async () => {
      try {
        const styles = await userSettingsApiService.listExportStyles();
        setExportStyles(styles);
      } catch (error) {
        console.error('Failed to load export styles:', error);
        setExportStyles([]); // Fallback to empty
      } finally {
        setLoadingStyles(false);
      }
    };
    loadStyles();
  }, []);

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Name Field */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Name
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => onUpdate({ ...node.data, name: e.target.value })}
          placeholder="Enter presentation name"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            background: '#FFFFFF',
            color: '#1F1F1F',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = '#0078D4'}
          onBlur={(e) => e.currentTarget.style.borderColor = '#EDEBE9'}
        />
      </div>

      {/* Content Instructions */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Content Instructions
        </label>
        <textarea
          value={node.data?.contentInstructions || ''}
          onChange={(e) => onUpdate({ ...node.data, contentInstructions: e.target.value })}
          placeholder="Describe what should be included in the presentation..."
          rows={4}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>

      {/* Data Intensity - inline dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Data intensity
        </label>
        <button
          onClick={() => setShowDataIntensityDropdown(!showDataIntensityDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedDataIntensity.label}
          <ChevronDown size={12} />
        </button>

        {showDataIntensityDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '100px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {dataIntensityOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, dataIntensity: option.value });
                  setShowDataIntensityDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedDataIntensity.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedDataIntensity.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedDataIntensity.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Verbosity - inline dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Verbosity
        </label>
        <button
          onClick={() => setShowVerbosityDropdown(!showVerbosityDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedVerbosity.label}
          <ChevronDown size={12} />
        </button>

        {showVerbosityDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '100px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {verbosityOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, verbosity: option.value });
                  setShowVerbosityDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedVerbosity.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedVerbosity.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedVerbosity.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Export Style - inline dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Export Style
        </label>
        <button
          onClick={() => setShowStyleDropdown(!showStyleDropdown)}
          disabled={loadingStyles}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: loadingStyles ? 'not-allowed' : 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            opacity: loadingStyles ? 0.6 : 1,
          }}
        >
          {loadingStyles ? 'Loading...' : (node.data?.style_name || 'Default')}
          <ChevronDown size={12} />
        </button>

        {showStyleDropdown && !loadingStyles && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '120px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {/* Default option */}
            <div
              onClick={() => {
                onUpdate({ ...node.data, style_name: undefined });
                setShowStyleDropdown(false);
              }}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '12px',
                background: !node.data?.style_name ? '#F5F5F5' : 'transparent',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
              onMouseLeave={(e) => e.currentTarget.style.background = !node.data?.style_name ? '#F5F5F5' : 'transparent'}
            >
              <span>Default</span>
              {!node.data?.style_name && <span>✓</span>}
            </div>

            {/* User's saved styles */}
            {exportStyles.map((style) => (
              <div
                key={style.style_name}
                onClick={() => {
                  onUpdate({ ...node.data, style_name: style.style_name });
                  setShowStyleDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: style.style_name === node.data?.style_name ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = style.style_name === node.data?.style_name ? '#F5F5F5' : 'transparent'}
              >
                <span>{style.style_name}</span>
                {style.style_name === node.data?.style_name && <span>✓</span>}
              </div>
            ))}

            {exportStyles.length === 0 && (
              <div style={{ padding: '8px 12px', fontSize: '12px', color: '#8A8886', textAlign: 'center' }}>
                No custom styles
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Workbook Configuration Component
function WorkbookConfig({ node, onUpdate }: any) {
  const [showWorkbookTypeDropdown, setShowWorkbookTypeDropdown] = useState(false);
  const [showVerbosityDropdown, setShowVerbosityDropdown] = useState(false);

  const workbookTypeOptions = [
    { value: 'excel', label: 'Excel' },
    { value: 'csv', label: 'CSV' },
  ];

  const verbosityOptions = [
    { value: 'high', label: 'High' },
    { value: 'mid', label: 'Mid' },
    { value: 'low', label: 'Low' },
  ];

  const selectedWorkbookType = workbookTypeOptions.find(w => w.value === (node.data?.workbookType || 'excel')) || workbookTypeOptions[0];
  const selectedVerbosity = verbosityOptions.find(v => v.value === (node.data?.verbosity || 'mid')) || verbosityOptions[1];
  const displayName = node.data?.name || '';

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Name Field */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Name
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => onUpdate({ ...node.data, name: e.target.value })}
          placeholder="Enter workbook name"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            outline: 'none',
            background: '#FFFFFF',
            color: '#1F1F1F',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = '#0078D4'}
          onBlur={(e) => e.currentTarget.style.borderColor = '#EDEBE9'}
        />
      </div>

      {/* Content Instructions */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Content Instructions
        </label>
        <textarea
          value={node.data?.contentInstructions || ''}
          onChange={(e) => onUpdate({ ...node.data, contentInstructions: e.target.value })}
          placeholder="Describe what should be included in the workbook..."
          rows={4}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: '#F5F5F5',
            color: '#605E5C',
            lineHeight: '1.5',
          }}
        />
      </div>

      {/* Workbook Type - inline dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Workbook type
        </label>
        <button
          onClick={() => setShowWorkbookTypeDropdown(!showWorkbookTypeDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedWorkbookType.label}
          <ChevronDown size={12} />
        </button>

        {showWorkbookTypeDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '100px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {workbookTypeOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, workbookType: option.value });
                  setShowWorkbookTypeDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedWorkbookType.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedWorkbookType.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedWorkbookType.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Verbosity - inline dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          Verbosity
        </label>
        <button
          onClick={() => setShowVerbosityDropdown(!showVerbosityDropdown)}
          style={{
            padding: '4px 20px 4px 8px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            background: 'transparent',
            color: '#1F1F1F',
            cursor: 'pointer',
            fontWeight: '400',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {selectedVerbosity.label}
          <ChevronDown size={12} />
        </button>

        {showVerbosityDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            minWidth: '100px',
            background: '#FFFFFF',
            border: '1px solid #EDEBE9',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 10,
            overflow: 'hidden',
          }}>
            {verbosityOptions.map((option) => (
              <div
                key={option.value}
                onClick={() => {
                  onUpdate({ ...node.data, verbosity: option.value });
                  setShowVerbosityDropdown(false);
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  background: option.value === selectedVerbosity.value ? '#F5F5F5' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#F5F5F5'}
                onMouseLeave={(e) => e.currentTarget.style.background = option.value === selectedVerbosity.value ? '#F5F5F5' : 'transparent'}
              >
                <span>{option.label}</span>
                {option.value === selectedVerbosity.value && <span>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Email Configuration Component
function EmailConfig({ node, onUpdate }: any) {
  const aiGeneratedMessage = node.data?.aiGeneratedMessage ?? false;
  const [emailInput, setEmailInput] = useState('');
  const [emailLists, setEmailLists] = useState<EmailList[]>([]);
  const [loadingLists, setLoadingLists] = useState(false);
  const [showListsModal, setShowListsModal] = useState(false);
  const [creatingList, setCreatingList] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [newListEmails, setNewListEmails] = useState<string[]>([]);
  const [newListEmailInput, setNewListEmailInput] = useState('');

  const emails = node.data?.emails || [];
  const selectedListIds = node.data?.emailListIds || [];

  // Fetch email lists on mount
  useEffect(() => {
    fetchEmailLists();
  }, []);

  const fetchEmailLists = async () => {
    setLoadingLists(true);
    try {
      const lists = await emailListsApi.list();
      setEmailLists(lists);
    } catch (error) {
      console.error('Failed to fetch email lists:', error);
      toast.error('Failed to load email lists');
    } finally {
      setLoadingLists(false);
    }
  };

  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleAddEmail = () => {
    const input = emailInput.trim();
    if (!input) return;

    // Support multiple emails separated by comma, semicolon, or space
    const emailsToAdd = input
      .split(/[,;\s]+/)
      .map(e => e.trim())
      .filter(e => e.length > 0)
      .filter(e => validateEmail(e))
      .filter(e => !emails.includes(e));

    if (emailsToAdd.length > 0) {
      onUpdate({ ...node.data, emails: [...emails, ...emailsToAdd] });
      setEmailInput('');
    }
  };

  const handleRemoveEmail = (emailToRemove: string) => {
    onUpdate({ ...node.data, emails: emails.filter((e: string) => e !== emailToRemove) });
  };

  const handleListSelection = (listId: string) => {
    const newSelectedListIds = selectedListIds.includes(listId)
      ? selectedListIds.filter((id: string) => id !== listId)
      : [...selectedListIds, listId];
    onUpdate({ ...node.data, emailListIds: newSelectedListIds });
  };

  const handleAddEmailToNewList = () => {
    const input = newListEmailInput.trim();
    if (!input) return;

    const emailsToAdd = input
      .split(/[,;\s]+/)
      .map(e => e.trim())
      .filter(e => e.length > 0)
      .filter(e => validateEmail(e))
      .filter(e => !newListEmails.includes(e));

    if (emailsToAdd.length > 0) {
      setNewListEmails([...newListEmails, ...emailsToAdd]);
      setNewListEmailInput('');
    }
  };

  const handleRemoveEmailFromNewList = (emailToRemove: string) => {
    setNewListEmails(newListEmails.filter(e => e !== emailToRemove));
  };

  const handleCreateList = async () => {
    if (!newListName.trim() || newListEmails.length === 0) {
      toast.error('Please provide a name and at least one email');
      return;
    }

    try {
      const newList = await emailListsApi.create({
        name: newListName.trim(),
        recipients: newListEmails,
      });
      toast.success('Email list created');
      setEmailLists([...emailLists, newList]);
      // Auto-select the new list
      onUpdate({ ...node.data, emailListIds: [...selectedListIds, newList.id] });
      // Reset form
      setCreatingList(false);
      setNewListName('');
      setNewListEmails([]);
      setNewListEmailInput('');
    } catch (error) {
      console.error('Failed to create email list:', error);
      toast.error('Failed to create email list');
    }
  };

  const handleDeleteList = async (listId: string, listName: string) => {
    if (!confirm(`Delete "${listName}"? This cannot be undone.`)) {
      return;
    }

    try {
      await emailListsApi.delete(listId);
      toast.success('Email list deleted');
      setEmailLists(emailLists.filter(l => l.id !== listId));
      // Remove from selected lists if it was selected
      if (selectedListIds.includes(listId)) {
        onUpdate({ ...node.data, emailListIds: selectedListIds.filter((id: string) => id !== listId) });
      }
    } catch (error) {
      console.error('Failed to delete email list:', error);
      toast.error('Failed to delete email list');
    }
  };

  // Calculate total recipient count
  const getResolvedRecipients = (): string[] => {
    const recipients = new Set(emails);
    selectedListIds.forEach((listId: string) => {
      const list = emailLists.find((l) => l.id === listId);
      if (list) {
        list.recipients.forEach((email) => recipients.add(email));
      }
    });
    return Array.from(recipients);
  };

  const resolvedRecipients = getResolvedRecipients();
  const totalRecipientCount = resolvedRecipients.length;

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Direct Email Input - Primary */}
      <div>
        <label style={{ fontSize: '11px', color: '#323130', fontWeight: '600', display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Email Recipients {emails.length > 0 && `(${emails.length})`}
        </label>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
          <div style={{
            flex: 1,
            border: '1px solid #E1DFDD',
            borderRadius: '4px',
            padding: '6px',
            minHeight: '36px',
            maxHeight: '120px',
            overflowY: 'auto',
            background: '#FFFFFF',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '4px',
            alignItems: 'center',
            cursor: 'text',
            transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          }}
          onClick={(e) => {
            const input = e.currentTarget.querySelector('input');
            if (input) input.focus();
          }}
          onMouseEnter={(e) => {
            if (document.activeElement?.tagName !== 'INPUT' || !e.currentTarget.contains(document.activeElement)) {
              e.currentTarget.style.backgroundColor = '#F8F9FA';
            }
          }}
          onMouseLeave={(e) => {
            if (document.activeElement?.tagName !== 'INPUT' || !e.currentTarget.contains(document.activeElement)) {
              e.currentTarget.style.backgroundColor = '#FFFFFF';
            }
          }}
          >
            {/* Email Chips */}
            {emails.map((email: string) => (
              <div
                key={email}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '2px 6px 2px 8px',
                  backgroundColor: '#E3F2FD',
                  border: '1px solid #0078D4',
                  borderRadius: '12px',
                  fontSize: '11px',
                  color: '#0078D4',
                }}
              >
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '150px',
                }}>
                  {email}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveEmail(email);
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#0078D4',
                    cursor: 'pointer',
                    fontSize: '14px',
                    padding: '0',
                    width: '14px',
                    height: '14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: '50%',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(0, 120, 212, 0.1)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  ×
                </button>
              </div>
            ))}

            {/* Inline Input */}
            <input
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddEmail();
                } else if (e.key === 'Backspace' && emailInput === '' && emails.length > 0) {
                  e.preventDefault();
                  handleRemoveEmail(emails[emails.length - 1]);
                }
              }}
              onFocus={(e) => {
                const container = e.target.closest('div[style*="border"]') as HTMLElement;
                if (container) {
                  container.style.borderColor = '#0078D4';
                  container.style.boxShadow = '0 1px 3px rgba(0, 120, 212, 0.2)';
                }
              }}
              onBlur={(e) => {
                const container = e.target.closest('div[style*="border"]') as HTMLElement;
                if (container) {
                  container.style.borderColor = '#E1DFDD';
                  container.style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)';
                }
              }}
              placeholder={emails.length === 0 ? 'Type or paste emails...' : ''}
              style={{
                flex: 1,
                minWidth: '120px',
                border: 'none',
                outline: 'none',
                fontSize: '13px',
                padding: '2px 0',
                backgroundColor: 'transparent',
                color: '#323130',
              }}
            />
          </div>
          {/* Add Button */}
          <button
            onClick={handleAddEmail}
            disabled={!emailInput.trim()}
            style={{
              padding: '8px 12px',
              fontSize: '14px',
              fontWeight: '500',
              background: emailInput.trim() ? '#0078D4' : '#E1DFDD',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '4px',
              cursor: emailInput.trim() ? 'pointer' : 'not-allowed',
              minWidth: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            }}
            onMouseEnter={(e) => {
              if (emailInput.trim()) {
                e.currentTarget.style.background = '#005A9E';
              }
            }}
            onMouseLeave={(e) => {
              if (emailInput.trim()) {
                e.currentTarget.style.background = '#0078D4';
              }
            }}
          >
            +
          </button>
        </div>
        {/* Simple link to manage lists */}
        <button
          onClick={() => setShowListsModal(true)}
          style={{
            marginTop: '8px',
            background: 'none',
            border: 'none',
            color: '#0078D4',
            fontSize: '12px',
            cursor: 'pointer',
            padding: '4px 0',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.textDecoration = 'underline';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.textDecoration = 'none';
          }}
        >
          {selectedListIds.length > 0 ? (
            <>📋 {selectedListIds.length} list{selectedListIds.length !== 1 ? 's' : ''} selected</>
          ) : (
            <>+ Use saved email lists</>
          )}
        </button>
      </div>

      {/* Total Recipients Count */}
      {totalRecipientCount > 0 && (
        <div style={{
          padding: '8px 12px',
          background: '#E3F2FD',
          borderRadius: '4px',
          border: '1px solid #0078D4',
          fontSize: '13px',
          color: '#323130',
          fontWeight: 500,
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        }}>
          Total Recipients: {totalRecipientCount}
        </div>
      )}

      {/* Email Lists Modal */}
      {showListsModal && createPortal(
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10000,
          }}
          onClick={() => {
            setShowListsModal(false);
            setCreatingList(false);
            setNewListName('');
            setNewListEmails([]);
            setNewListEmailInput('');
          }}
        >
          <div
            style={{
              background: '#FFFFFF',
              borderRadius: '8px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
              width: '500px',
              maxHeight: '600px',
              display: 'flex',
              flexDirection: 'column',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid #E1DFDD',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600', color: '#323130' }}>
                {creatingList ? 'Create Email List' : 'Manage Email Lists'}
              </h3>
              <button
                onClick={() => {
                  setShowListsModal(false);
                  setCreatingList(false);
                  setNewListName('');
                  setNewListEmails([]);
                  setNewListEmailInput('');
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  color: '#605E5C',
                  padding: '0',
                  width: '24px',
                  height: '24px',
                }}
              >
                ×
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
              {loadingLists ? (
                <div style={{ textAlign: 'center', padding: '40px', color: '#605E5C' }}>
                  Loading...
                </div>
              ) : creatingList ? (
                /* Create New List Form */
                <div>
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: '#323130', display: 'block', marginBottom: '6px' }}>
                      List Name
                    </label>
                    <input
                      type="text"
                      placeholder="e.g., Marketing Team"
                      value={newListName}
                      onChange={(e) => setNewListName(e.target.value)}
                      autoFocus
                      style={{
                        width: '100%',
                        padding: '10px',
                        fontSize: '13px',
                        border: '1px solid #E1DFDD',
                        borderRadius: '4px',
                        outline: 'none',
                      }}
                      onFocus={(e) => e.currentTarget.style.borderColor = '#0078D4'}
                      onBlur={(e) => e.currentTarget.style.borderColor = '#E1DFDD'}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: '#323130', display: 'block', marginBottom: '6px' }}>
                      Email Recipients
                    </label>
                    <div style={{
                      border: '1px solid #E1DFDD',
                      borderRadius: '4px',
                      padding: '8px',
                      minHeight: '100px',
                      maxHeight: '200px',
                      overflowY: 'auto',
                      background: '#FFFFFF',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px',
                      alignItems: 'flex-start',
                      alignContent: 'flex-start',
                    }}>
                      {newListEmails.map((email) => (
                        <div key={email} style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '4px 8px 4px 10px',
                          backgroundColor: '#E3F2FD',
                          border: '1px solid #0078D4',
                          borderRadius: '14px',
                          fontSize: '12px',
                          color: '#0078D4',
                        }}>
                          <span>{email}</span>
                          <button
                            onClick={() => handleRemoveEmailFromNewList(email)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#0078D4',
                              cursor: 'pointer',
                              fontSize: '16px',
                              padding: '0',
                              width: '16px',
                              height: '16px',
                            }}
                          >×</button>
                        </div>
                      ))}
                      <input
                        type="email"
                        value={newListEmailInput}
                        onChange={(e) => setNewListEmailInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleAddEmailToNewList();
                          }
                        }}
                        placeholder="Type or paste emails..."
                        style={{
                          flex: 1,
                          minWidth: '200px',
                          border: 'none',
                          outline: 'none',
                          fontSize: '13px',
                          padding: '4px 0',
                        }}
                      />
                    </div>
                    <div style={{ fontSize: '11px', color: '#605E5C', marginTop: '6px' }}>
                      Press Enter to add. You can paste multiple emails separated by commas.
                    </div>
                  </div>
                </div>
              ) : (
                /* List of Existing Lists */
                <div>
                  {emailLists.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px', color: '#605E5C' }}>
                      <div style={{ fontSize: '14px', marginBottom: '8px' }}>No email lists yet</div>
                      <div style={{ fontSize: '12px' }}>Create a list to reuse recipients across tasks</div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {emailLists.map((list) => {
                        const isSelected = selectedListIds.includes(list.id);
                        return (
                          <label
                            key={list.id}
                            style={{
                              display: 'flex',
                              alignItems: 'flex-start',
                              gap: '12px',
                              padding: '12px',
                              cursor: 'pointer',
                              background: isSelected ? '#F8F9FA' : '#FFFFFF',
                              border: '1px solid #E1DFDD',
                              borderRadius: '6px',
                              transition: 'all 0.15s ease',
                            }}
                            onMouseEnter={(e) => {
                              if (!isSelected) e.currentTarget.style.background = '#FAFAFA';
                            }}
                            onMouseLeave={(e) => {
                              if (!isSelected) e.currentTarget.style.background = '#FFFFFF';
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => handleListSelection(list.id)}
                              style={{ width: '18px', height: '18px', cursor: 'pointer', marginTop: '2px' }}
                            />
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: '14px', fontWeight: 600, color: '#323130', marginBottom: '4px' }}>
                                {list.name}
                              </div>
                              <div style={{ fontSize: '12px', color: '#605E5C' }}>
                                {list.recipients.length} recipient{list.recipients.length !== 1 ? 's' : ''}
                              </div>
                              {list.description && (
                                <div style={{ fontSize: '12px', color: '#8A8886', marginTop: '4px' }}>
                                  {list.description}
                                </div>
                              )}
                            </div>
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                handleDeleteList(list.id, list.name);
                              }}
                              style={{
                                background: 'none',
                                border: 'none',
                                color: '#605E5C',
                                cursor: 'pointer',
                                fontSize: '18px',
                                padding: '4px',
                                width: '24px',
                                height: '24px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                borderRadius: '4px',
                                transition: 'all 0.15s ease',
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.background = '#FEE';
                                e.currentTarget.style.color = '#D13438';
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.background = 'none';
                                e.currentTarget.style.color = '#605E5C';
                              }}
                              title="Delete list"
                            >
                              🗑️
                            </button>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '16px 20px',
              borderTop: '1px solid #E1DFDD',
              display: 'flex',
              justifyContent: creatingList ? 'space-between' : 'flex-end',
              gap: '12px',
            }}>
              {creatingList ? (
                <>
                  <button
                    onClick={() => {
                      setCreatingList(false);
                      setNewListName('');
                      setNewListEmails([]);
                      setNewListEmailInput('');
                    }}
                    style={{
                      padding: '8px 16px',
                      fontSize: '13px',
                      background: '#FFFFFF',
                      color: '#605E5C',
                      border: '1px solid #E1DFDD',
                      borderRadius: '4px',
                      cursor: 'pointer',
                    }}
                  >
                    Back
                  </button>
                  <button
                    onClick={handleCreateList}
                    disabled={!newListName.trim() || newListEmails.length === 0}
                    style={{
                      padding: '8px 20px',
                      fontSize: '13px',
                      fontWeight: '500',
                      background: (!newListName.trim() || newListEmails.length === 0) ? '#E1DFDD' : '#0078D4',
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: (!newListName.trim() || newListEmails.length === 0) ? 'not-allowed' : 'pointer',
                    }}
                  >
                    Create List
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setCreatingList(true)}
                  style={{
                    padding: '8px 20px',
                    fontSize: '13px',
                    fontWeight: '500',
                    background: '#0078D4',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>+</span>
                  Create New List
                </button>
              )}
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* Custom Message */}
      <div>
        <label style={{ fontSize: '11px', color: '#323130', fontWeight: '600', display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Custom Message
        </label>
        <textarea
          value={node.data?.customMessage || ''}
          onChange={(e) => onUpdate({ ...node.data, customMessage: e.target.value })}
          placeholder={aiGeneratedMessage ? 'AI will generate the message' : 'Enter your message...'}
          rows={4}
          disabled={aiGeneratedMessage}
          style={{
            width: '100%',
            padding: '8px',
            fontSize: '13px',
            border: '1px solid #E1DFDD',
            borderRadius: '4px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: aiGeneratedMessage ? '#FAFAFA' : '#FFFFFF',
            color: aiGeneratedMessage ? '#605E5C' : '#323130',
            lineHeight: '1.5',
            cursor: aiGeneratedMessage ? 'not-allowed' : 'text',
            opacity: aiGeneratedMessage ? 0.6 : 1,
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          }}
        />
      </div>

      {/* AI Generated Message Toggle */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <label style={{ fontSize: '13px', color: '#323130', fontWeight: '500' }}>
          AI generated message
        </label>
        <label style={{ position: 'relative', display: 'inline-block', width: '36px', height: '20px' }}>
          <input
            type="checkbox"
            checked={aiGeneratedMessage}
            onChange={(e) => onUpdate({ ...node.data, aiGeneratedMessage: e.target.checked })}
            style={{ opacity: 0, width: 0, height: 0 }}
          />
          <span style={{
            position: 'absolute',
            cursor: 'pointer',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: aiGeneratedMessage ? '#0078D4' : '#E1DFDD',
            transition: 'background-color 0.2s',
            borderRadius: '20px',
          }}>
            <span style={{
              position: 'absolute',
              content: '',
              height: '14px',
              width: '14px',
              left: aiGeneratedMessage ? '19px' : '3px',
              bottom: '3px',
              backgroundColor: 'white',
              transition: 'left 0.2s',
              borderRadius: '50%',
            }} />
          </span>
        </label>
      </div>
    </div>
  );
}


// Custom Workspace Select Component
function WorkspaceSelect({ value, onChange, workspaces, loading }: any) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      const handleClickOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as HTMLElement)) {
          setIsOpen(false);
        }
      };
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const selectedWorkspace = workspaces.find((w: any) => w.team_id === value);
  const displayText = loading
    ? 'Loading workspaces...'
    : workspaces.length === 0
    ? 'No workspaces connected'
    : value
    ? selectedWorkspace?.team_name || selectedWorkspace?.team_id || 'Select workspace'
    : 'Select workspace';

  return (
    <div ref={containerRef} style={{ position: 'relative', flex: 1 }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading || workspaces.length === 0}
        style={{
          width: '100%',
          padding: '10px 12px',
          fontSize: '12px',
          border: '1px solid #EDEBE9',
          borderRadius: '6px',
          background: '#FFFFFF',
          color: value ? '#667eea' : '#1F1F1F',
          cursor: workspaces.length === 0 ? 'not-allowed' : 'pointer',
          textAlign: 'left',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontWeight: value ? 500 : 400,
          transition: 'all 0.2s ease',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {displayText}
        </span>
        <ChevronDown size={14} style={{ color: '#5F6368', flexShrink: 0, marginLeft: '8px' }} />
      </button>
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          background: '#FFFFFF',
          border: '1px solid #DADCE0',
          borderRadius: '6px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          zIndex: 1000,
          maxHeight: '200px',
          overflow: 'auto',
        }}>
          {workspaces.map((workspace: any) => (
            <button
              key={workspace.team_id}
              onClick={() => {
                onChange(workspace.team_id);
                setIsOpen(false);
              }}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: 'none',
                background: value === workspace.team_id ? '#F1F3F4' : 'transparent',
                color: value === workspace.team_id ? '#667eea' : '#1F1F1F',
                fontSize: '12px',
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                fontWeight: value === workspace.team_id ? 500 : 400,
              }}
              onMouseEnter={(e) => {
                if (value !== workspace.team_id) {
                  e.currentTarget.style.background = '#F8F9FA';
                }
              }}
              onMouseLeave={(e) => {
                if (value !== workspace.team_id) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              {workspace.team_name || workspace.team_id}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Custom Channel Select Component (Multiselect)
function ChannelSelect({ value, onChange, channels, loading, workspaceSelected }: any) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Value is now an array of channel IDs
  const selectedChannelIds = Array.isArray(value) ? value : (value ? [value] : []);

  useEffect(() => {
    if (isOpen) {
      const handleClickOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as HTMLElement)) {
          setIsOpen(false);
        }
      };
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const displayText = !workspaceSelected
    ? 'Connect a workspace first'
    : loading
    ? 'Loading channels...'
    : channels.length === 0
    ? 'No channels available'
    : selectedChannelIds.length === 0
    ? 'Select channels'
    : `${selectedChannelIds.length} channel${selectedChannelIds.length > 1 ? 's' : ''} selected`;

  const handleToggleChannel = (channelId: string) => {
    const isSelected = selectedChannelIds.includes(channelId);
    const newSelection = isSelected
      ? selectedChannelIds.filter((id: string) => id !== channelId)
      : [...selectedChannelIds, channelId];
    onChange(newSelection);
  };

  const handleRemoveChannel = (channelId: string) => {
    const newSelection = selectedChannelIds.filter((id: string) => id !== channelId);
    onChange(newSelection);
  };

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={!workspaceSelected || loading || channels.length === 0}
        style={{
          width: '100%',
          padding: '10px 12px',
          fontSize: '12px',
          border: '1px solid #EDEBE9',
          borderRadius: '6px',
          background: '#FFFFFF',
          color: selectedChannelIds.length > 0 ? '#3b82f6' : '#1F1F1F',
          cursor: workspaceSelected ? 'pointer' : 'not-allowed',
          textAlign: 'left',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontWeight: selectedChannelIds.length > 0 ? 500 : 400,
          transition: 'all 0.2s ease',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {displayText}
        </span>
        <ChevronDown size={14} style={{ color: '#5F6368', flexShrink: 0, marginLeft: '8px' }} />
      </button>
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          background: '#FFFFFF',
          border: '1px solid #DADCE0',
          borderRadius: '6px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          zIndex: 1000,
          maxHeight: '200px',
          overflow: 'auto',
        }}>
          {channels.map((channel: any) => {
            const isSelected = selectedChannelIds.includes(channel.id);
            return (
              <button
                key={channel.id}
                onClick={() => handleToggleChannel(channel.id)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: 'none',
                  background: isSelected ? '#F1F3F4' : 'transparent',
                  color: isSelected ? '#3b82f6' : '#1F1F1F',
                  fontSize: '12px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontWeight: isSelected ? 500 : 400,
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = '#F8F9FA';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = 'transparent';
                  }
                }}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => {}}
                  style={{
                    pointerEvents: 'none',
                    accentColor: '#3b82f6',
                    width: '14px',
                    height: '14px',
                    cursor: 'pointer',
                  }}
                />
                <span>#{channel.name}</span>
                {channel.is_private && <span style={{ color: '#9CA3AF', fontSize: '11px' }}>🔒</span>}
              </button>
            );
          })}
        </div>
      )}

      {/* Selected Channels Display */}
      {selectedChannelIds.length > 0 && (
        <div style={{
          marginTop: '8px',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
        }}>
          {selectedChannelIds.map((channelId: string) => {
            const channel = channels.find((c: any) => c.id === channelId);
            if (!channel) return null;
            return (
              <div
                key={channelId}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '4px 8px',
                  background: '#EFF6FF',
                  border: '1px solid #BFDBFE',
                  borderRadius: '4px',
                  fontSize: '11px',
                  color: '#1e40af',
                }}
              >
                <span>#{channel.name}</span>
                <button
                  onClick={() => handleRemoveChannel(channelId)}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    cursor: 'pointer',
                    color: '#3b82f6',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                  title="Remove channel"
                >
                  <X size={12} />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Slack Configuration Component
function SlackConfig({ node, onUpdate }: any) {
  const aiGeneratedMessage = node.data?.aiGeneratedMessage ?? false;
  const selectedWorkspaceId = node.data?.workspaceId || '';
  const selectedChannelIds = node.data?.channelIds || [];

  const [workspaces, setWorkspaces] = useState<SlackWorkspace[]>([]);
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(false);
  const [loadingChannels, setLoadingChannels] = useState(false);
  const [connecting, setConnecting] = useState(false);

  const authWindowRef = useRef<Window | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  const cleanupAuthWindow = () => {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (authWindowRef.current && !authWindowRef.current.closed) {
      authWindowRef.current.close();
    }
    authWindowRef.current = null;
  };

  const updateNodeData = (patch: Record<string, any>) => {
    onUpdate({
      ...node.data,
      ...patch,
    });
  };

  const fetchWorkspaces = async (silent = false) => {
    try {
      if (!silent) setLoadingWorkspaces(true);
      const list = await slackIntegrationApi.listWorkspaces();
      console.log('[Slack] Fetched workspaces:', list);
      setWorkspaces(list);
    } catch (error) {
      console.error('[Slack] Failed to fetch workspaces:', error);
      if (!silent) toast.error('Failed to load Slack workspaces');
    } finally {
      if (!silent) setLoadingWorkspaces(false);
    }
  };

  const fetchChannels = async (teamId: string, silent = false) => {
    if (!teamId) {
      setChannels([]);
      return;
    }
    try {
      if (!silent) setLoadingChannels(true);
      const list = await slackIntegrationApi.listChannels(teamId);
      setChannels(list);
    } catch (error) {
      if (!silent) toast.error('Failed to load Slack channels');
    } finally {
      if (!silent) setLoadingChannels(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces(true);
    return () => cleanupAuthWindow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedWorkspaceId) {
      fetchChannels(selectedWorkspaceId, true);
    } else {
      setChannels([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkspaceId]);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      const url = await slackIntegrationApi.getAuthorizeUrl();
      const popup = window.open(url, 'slack_oauth', 'width=600,height=700');
      if (!popup) {
        toast.error('Unable to open Slack authorization window. Please allow popups.');
        return;
      }
      authWindowRef.current = popup;
      pollTimerRef.current = window.setInterval(() => {
        if (!popup || popup.closed) {
          cleanupAuthWindow();
          fetchWorkspaces();
        }
      }, 1000);
    } catch (error) {
      toast.error('Failed to start Slack authorization');
    } finally {
      setConnecting(false);
    }
  };

  const handleWorkspaceChange = async (teamId: string) => {
    if (!teamId) {
      updateNodeData({
        workspaceId: '',
        workspaceName: '',
        channelId: '',
        channelName: '',
        connected: false,
      });
      setChannels([]);
      return;
    }
    const workspace = workspaces.find((w) => w.team_id === teamId);
    updateNodeData({
      workspaceId: teamId,
      workspaceName: workspace?.team_name || teamId,
      channelId: '',
      channelName: '',
      connected: false,
    });
    await fetchChannels(teamId);
  };

  const handleChannelChange = (channelIds: string[]) => {
    if (!channelIds || channelIds.length === 0) {
      updateNodeData({
        channelIds: [],
        channelNames: [],
        connected: false,
      });
      return;
    }
    const channelNames = channelIds.map((id) => {
      const channel = channels.find((c: any) => c.id === id);
      return channel?.name || id;
    });
    updateNodeData({
      channelIds,
      channelNames,
      connected: true,
    });
  };

  const isConnected = Boolean(selectedWorkspaceId && selectedChannelIds.length > 0);

  const hasWorkspaces = workspaces.length > 0;
  const hasChannelSelected = Boolean(selectedWorkspaceId && selectedChannelIds.length > 0);

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Connect Button - Only shown when no workspaces */}
      {!hasWorkspaces && (
        <button
          onClick={handleConnect}
          disabled={connecting}
          style={{
            padding: '10px 14px',
            fontSize: '12px',
            fontWeight: 500,
            borderRadius: '6px',
            border: '1px solid #EDEBE9',
            background: '#FFFFFF',
            color: '#1F1F1F',
            cursor: connecting ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            opacity: connecting ? 0.6 : 1,
            transition: 'all 0.12s',
          }}
          onMouseEnter={(e) => {
            if (!connecting) {
              e.currentTarget.style.background = '#FAFAFA';
            }
          }}
          onMouseLeave={(e) => {
            if (!connecting) {
              e.currentTarget.style.background = '#FFFFFF';
            }
          }}
        >
          <Link size={14} />
          {connecting ? 'Connecting...' : 'Connect Slack'}
        </button>
      )}

      {/* Workspace Selector */}
      {hasWorkspaces && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: 600 }}>
              Workspace
            </label>
            <button
              onClick={handleConnect}
              disabled={connecting}
              style={{
                padding: '4px 8px',
                fontSize: '11px',
                borderRadius: '4px',
                border: '1px solid #EDEBE9',
                background: '#FFFFFF',
                color: '#4A154B',
                cursor: 'pointer',
                fontWeight: 500,
                opacity: connecting ? 0.6 : 1,
              }}
            >
              + Add Workspace
            </button>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <WorkspaceSelect
              value={selectedWorkspaceId}
              onChange={handleWorkspaceChange}
              workspaces={workspaces}
              loading={loadingWorkspaces}
            />
            <button
              onClick={() => fetchWorkspaces()}
              disabled={loadingWorkspaces}
              title="Refresh workspace list"
              style={{
                padding: '8px 10px',
                fontSize: '12px',
                borderRadius: '6px',
                border: '1px solid #EDEBE9',
                background: '#FFFFFF',
                cursor: 'pointer',
                opacity: loadingWorkspaces ? 0.6 : 1,
              }}
            >
              ↻
            </button>
          </div>
        </div>
      )}

      {/* Channel Selector */}
      {hasWorkspaces && (
        <div>
          <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
            Channel
          </label>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <ChannelSelect
                value={selectedChannelIds}
                onChange={handleChannelChange}
                channels={channels}
                loading={loadingChannels}
                workspaceSelected={!!selectedWorkspaceId}
              />
            </div>
            <button
              onClick={() => {
                if (selectedWorkspaceId) {
                  fetchChannels(selectedWorkspaceId);
                }
              }}
              disabled={loadingChannels || !selectedWorkspaceId}
              title="Refresh channel list"
              style={{
                padding: '8px 10px',
                fontSize: '12px',
                borderRadius: '6px',
                border: '1px solid #EDEBE9',
                background: '#FFFFFF',
                cursor: (loadingChannels || !selectedWorkspaceId) ? 'not-allowed' : 'pointer',
                opacity: (loadingChannels || !selectedWorkspaceId) ? 0.6 : 1,
              }}
            >
              ↻
            </button>
          </div>
        </div>
      )}

      {/* Custom Message */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Custom Message
        </label>
        <textarea
          value={node.data?.customMessage || ''}
          onChange={(e) => updateNodeData({ customMessage: e.target.value })}
          placeholder={aiGeneratedMessage ? 'AI will generate the message' : 'Enter your message...'}
          rows={4}
          disabled={aiGeneratedMessage}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: aiGeneratedMessage ? '#FAFAFA' : '#F5F5F5',
            color: aiGeneratedMessage ? '#C8C6C4' : '#605E5C',
            lineHeight: '1.5',
            cursor: aiGeneratedMessage ? 'not-allowed' : 'text',
            opacity: aiGeneratedMessage ? 0.6 : 1,
          }}
        />
      </div>

      {/* AI Generated Message Toggle */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          AI generated message
        </label>
        <label style={{ position: 'relative', display: 'inline-block', width: '36px', height: '20px' }}>
          <input
            type="checkbox"
            checked={aiGeneratedMessage}
            onChange={(e) => updateNodeData({ aiGeneratedMessage: e.target.checked })}
            style={{ opacity: 0, width: 0, height: 0 }}
          />
          <span style={{
            position: 'absolute',
            cursor: 'pointer',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: aiGeneratedMessage ? '#0078D4' : '#D1D1D1',
            transition: 'background-color 0.2s',
            borderRadius: '20px',
          }}>
            <span style={{
              position: 'absolute',
              content: '',
              height: '14px',
              width: '14px',
              left: aiGeneratedMessage ? '19px' : '3px',
              bottom: '3px',
              backgroundColor: 'white',
              transition: 'left 0.2s',
              borderRadius: '50%',
            }} />
          </span>
        </label>
      </div>
    </div>
  );
}

// Teams Configuration Component
function TeamsConfig({ node, onUpdate }: any) {
  const aiGeneratedMessage = node.data?.aiGeneratedMessage ?? false;
  const selectedTenantId = node.data?.tenantId || '';
  const selectedTeamId = node.data?.teamId || '';
  const selectedChannelIds = node.data?.channelIds || [];

  const [workspaces, setWorkspaces] = useState<TeamsWorkspace[]>([]);
  const [teams, setTeams] = useState<TeamsTeam[]>([]);
  const [channels, setChannels] = useState<TeamsChannel[]>([]);
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(false);
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingChannels, setLoadingChannels] = useState(false);
  const [connecting, setConnecting] = useState(false);

  const authWindowRef = useRef<Window | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  const cleanupAuthWindow = () => {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (authWindowRef.current && !authWindowRef.current.closed) {
      authWindowRef.current.close();
    }
    authWindowRef.current = null;
  };

  const updateNodeData = (patch: Record<string, any>) => {
    onUpdate({
      ...node.data,
      ...patch,
    });
  };

  const fetchWorkspaces = async (silent = false) => {
    try {
      if (!silent) setLoadingWorkspaces(true);
      const list = await teamsIntegrationApi.listWorkspaces();
      setWorkspaces(list);
    } catch (error) {
      if (!silent) toast.error('Failed to load Teams tenants');
    } finally {
      if (!silent) setLoadingWorkspaces(false);
    }
  };

  const fetchTeams = async (tenantId: string, silent = false) => {
    if (!tenantId) {
      setTeams([]);
      return;
    }
    try {
      if (!silent) setLoadingTeams(true);
      const list = await teamsIntegrationApi.listTeams(tenantId);
      setTeams(list);
    } catch (error) {
      if (!silent) toast.error('Failed to load Teams workspaces');
    } finally {
      if (!silent) setLoadingTeams(false);
    }
  };

  const fetchChannels = async (tenantId: string, teamId: string, silent = false) => {
    if (!tenantId || !teamId) {
      setChannels([]);
      return;
    }
    try {
      if (!silent) setLoadingChannels(true);
      const list = await teamsIntegrationApi.listChannels(tenantId, teamId);
      setChannels(list);
    } catch (error) {
      if (!silent) toast.error('Failed to load Teams channels');
    } finally {
      if (!silent) setLoadingChannels(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces(true);
    return () => cleanupAuthWindow();
  }, []);

  useEffect(() => {
    if (selectedTenantId) {
      fetchTeams(selectedTenantId, true);
    } else {
      setTeams([]);
    }
  }, [selectedTenantId]);

  useEffect(() => {
    if (selectedTenantId && selectedTeamId) {
      fetchChannels(selectedTenantId, selectedTeamId, true);
    } else {
      setChannels([]);
    }
  }, [selectedTenantId, selectedTeamId]);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      const url = await teamsIntegrationApi.getAuthorizeUrl();
      const popup = window.open(url, 'teams_oauth', 'width=600,height=700');
      if (!popup) {
        toast.error('Unable to open Teams authorization window. Please allow popups.');
        return;
      }
      authWindowRef.current = popup;
      pollTimerRef.current = window.setInterval(() => {
        if (!popup || popup.closed) {
          cleanupAuthWindow();
          fetchWorkspaces();
        }
      }, 1000);
    } catch (error) {
      toast.error('Failed to start Teams authorization');
    } finally {
      setConnecting(false);
    }
  };

  const handleWorkspaceChange = async (tenantId: string) => {
    if (!tenantId) {
      updateNodeData({
        tenantId: '',
        tenantName: '',
        teamId: '',
        teamName: '',
        channelId: '',
        channelName: '',
        connected: false,
      });
      setTeams([]);
      setChannels([]);
      return;
    }
    const workspace = workspaces.find((w) => w.tenant_id === tenantId);
    updateNodeData({
      tenantId,
      tenantName: workspace?.tenant_name || tenantId,
      teamId: '',
      teamName: '',
      channelId: '',
      channelName: '',
      connected: false,
    });
    await fetchTeams(tenantId);
  };

  const handleTeamChange = async (teamId: string) => {
    if (!teamId) {
      updateNodeData({
        teamId: '',
        teamName: '',
        channelId: '',
        channelName: '',
        connected: false,
      });
      setChannels([]);
      return;
    }
    const team = teams.find((t) => t.id === teamId);
    updateNodeData({
      teamId,
      teamName: team?.display_name || teamId,
      channelId: '',
      channelName: '',
      connected: false,
    });
    await fetchChannels(selectedTenantId, teamId);
  };

  const handleChannelChange = (channelIds: string[]) => {
    if (!channelIds || channelIds.length === 0) {
      updateNodeData({
        channelIds: [],
        channelNames: [],
        connected: false,
      });
      return;
    }
    const channelNames = channelIds.map((id) => {
      const channel = channels.find((c) => c.id === id);
      return channel?.display_name || id;
    });
    updateNodeData({
      channelIds,
      channelNames,
      connected: true,
    });
  };

  const handleRemoveChannel = (channelId: string) => {
    const newChannelIds = selectedChannelIds.filter((id: string) => id !== channelId);
    handleChannelChange(newChannelIds);
  };

  const hasWorkspaces = workspaces.length > 0;

  // Custom Tenant Select Component
  function TenantSelect({ value, onChange, workspaces, loading }: any) {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as HTMLElement)) {
          setIsOpen(false);
        }
      };
      if (isOpen) {
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
      }
    }, [isOpen]);

    const selectedWorkspace = workspaces.find((w: any) => w.tenant_id === value);
    const displayText = loading
      ? 'Loading...'
      : value
      ? selectedWorkspace?.connected_user_email
        ? `${selectedWorkspace.tenant_name || value} (${selectedWorkspace.connected_user_email})`
        : selectedWorkspace?.tenant_name || value
      : 'Select tenant';

    return (
      <div ref={containerRef} style={{ position: 'relative', flex: 1 }}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          disabled={loading || workspaces.length === 0}
          style={{
            width: '100%',
            padding: '10px 14px',
            fontSize: '12px',
            textAlign: 'left',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: '#FFFFFF',
            color: value ? '#667eea' : '#1F1F1F',
            cursor: loading || workspaces.length === 0 ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit',
            opacity: loading || workspaces.length === 0 ? 0.6 : 1,
          }}
        >
          <span>{displayText}</span>
          <ChevronDown size={14} />
        </button>
        {isOpen && workspaces.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% + 4px)',
              left: 0,
              right: 0,
              zIndex: 1000,
              maxHeight: '200px',
              overflowY: 'auto',
              background: '#FFFFFF',
              border: '1px solid #EDEBE9',
              borderRadius: '6px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
            }}
          >
            {workspaces.map((workspace: any) => (
              <button
                key={workspace.tenant_id}
                onClick={() => {
                  onChange(workspace.tenant_id);
                  setIsOpen(false);
                }}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  fontSize: '12px',
                  textAlign: 'left',
                  border: 'none',
                  background: value === workspace.tenant_id ? '#F5F5F5' : 'transparent',
                  color: value === workspace.tenant_id ? '#667eea' : '#1F1F1F',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  display: 'block',
                }}
                onMouseEnter={(e) => {
                  if (value !== workspace.tenant_id) {
                    e.currentTarget.style.background = '#FAFAFA';
                  }
                }}
                onMouseLeave={(e) => {
                  if (value !== workspace.tenant_id) {
                    e.currentTarget.style.background = 'transparent';
                  }
                }}
              >
                <div>
                  <div>{workspace.tenant_name || workspace.tenant_id}</div>
                  {workspace.connected_user_email && (
                    <div style={{ fontSize: '11px', opacity: 0.7, marginTop: '2px' }}>
                      {workspace.connected_user_email}
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Custom Team Select Component
  function TeamSelect({ value, onChange, teams, loading, disabled }: any) {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as HTMLElement)) {
          setIsOpen(false);
        }
      };
      if (isOpen) {
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
      }
    }, [isOpen]);

    const selectedTeam = teams.find((t: any) => t.id === value);
    const displayText = loading
      ? 'Loading...'
      : disabled
      ? 'Select a tenant first'
      : value
      ? selectedTeam?.display_name || value
      : teams.length > 0
      ? 'Select team'
      : 'No teams available';

    return (
      <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled || loading || teams.length === 0}
          style={{
            width: '100%',
            padding: '10px 14px',
            fontSize: '12px',
            textAlign: 'left',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: '#FFFFFF',
            color: value ? '#667eea' : '#1F1F1F',
            cursor: disabled || loading || teams.length === 0 ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit',
            opacity: disabled || loading || teams.length === 0 ? 0.6 : 1,
          }}
        >
          <span>{displayText}</span>
          <ChevronDown size={14} />
        </button>
        {isOpen && teams.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% + 4px)',
              left: 0,
              right: 0,
              zIndex: 1000,
              maxHeight: '200px',
              overflowY: 'auto',
              background: '#FFFFFF',
              border: '1px solid #EDEBE9',
              borderRadius: '6px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
            }}
          >
            {teams.map((team: any) => (
              <button
                key={team.id}
                onClick={() => {
                  onChange(team.id);
                  setIsOpen(false);
                }}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  fontSize: '12px',
                  textAlign: 'left',
                  border: 'none',
                  background: value === team.id ? '#F5F5F5' : 'transparent',
                  color: value === team.id ? '#667eea' : '#1F1F1F',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  display: 'block',
                }}
                onMouseEnter={(e) => {
                  if (value !== team.id) {
                    e.currentTarget.style.background = '#FAFAFA';
                  }
                }}
                onMouseLeave={(e) => {
                  if (value !== team.id) {
                    e.currentTarget.style.background = 'transparent';
                  }
                }}
              >
                {team.display_name || team.id}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Custom Channel Select Component with Multi-Select
  function TeamsChannelSelect({ values, onChange, channels, loading, disabled }: any) {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as HTMLElement)) {
          setIsOpen(false);
        }
      };
      if (isOpen) {
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
      }
    }, [isOpen]);

    const handleToggle = (channelId: string) => {
      const newValues = values.includes(channelId)
        ? values.filter((id: string) => id !== channelId)
        : [...values, channelId];
      onChange(newValues);
    };

    const displayText = loading
      ? 'Loading...'
      : disabled
      ? 'Select a team first'
      : values.length > 0
      ? `${values.length} channel${values.length > 1 ? 's' : ''} selected`
      : channels.length > 0
      ? 'Select channels'
      : 'No channels available';

    return (
      <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled || loading || channels.length === 0}
          style={{
            width: '100%',
            padding: '10px 14px',
            fontSize: '12px',
            textAlign: 'left',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: '#FFFFFF',
            color: values.length > 0 ? '#3b82f6' : '#1F1F1F',
            cursor: disabled || loading || channels.length === 0 ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit',
            opacity: disabled || loading || channels.length === 0 ? 0.6 : 1,
          }}
        >
          <span>{displayText}</span>
          <ChevronDown size={14} />
        </button>
        {isOpen && channels.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% + 4px)',
              left: 0,
              right: 0,
              zIndex: 1000,
              maxHeight: '200px',
              overflowY: 'auto',
              background: '#FFFFFF',
              border: '1px solid #EDEBE9',
              borderRadius: '6px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
            }}
          >
            {channels.map((channel: any) => {
              const isSelected = values.includes(channel.id);
              return (
                <button
                  key={channel.id}
                  onClick={() => handleToggle(channel.id)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    fontSize: '12px',
                    textAlign: 'left',
                    border: 'none',
                    background: isSelected ? '#EFF6FF' : 'transparent',
                    color: '#1F1F1F',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = '#FAFAFA';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    style={{
                      width: '14px',
                      height: '14px',
                      cursor: 'pointer',
                      accentColor: '#3b82f6',
                    }}
                  />
                  <span>{channel.display_name || channel.id}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Simple connect button when no workspaces */}
      {!hasWorkspaces && (
        <button
          onClick={handleConnect}
          disabled={connecting}
          style={{
            padding: '10px 14px',
            fontSize: '12px',
            border: '1px solid #EDEBE9',
            borderRadius: '6px',
            background: '#FFFFFF',
            color: '#1F1F1F',
            cursor: connecting ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontFamily: 'inherit',
            opacity: connecting ? 0.6 : 1,
          }}
        >
          <Link size={14} />
          {connecting ? 'Connecting...' : 'Connect Teams'}
        </button>
      )}

      {/* Selection UI when workspaces exist */}
      {hasWorkspaces && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Tenant
            </label>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <div style={{ flex: 1 }}>
                <TenantSelect
                  value={selectedTenantId}
                  onChange={handleWorkspaceChange}
                  workspaces={workspaces}
                  loading={loadingWorkspaces}
                />
              </div>
              <button
                onClick={() => fetchWorkspaces()}
                disabled={loadingWorkspaces}
                title="Refresh workspace list"
                style={{
                  padding: '8px 10px',
                  fontSize: '12px',
                  borderRadius: '6px',
                  border: '1px solid #EDEBE9',
                  background: '#FFFFFF',
                  cursor: 'pointer',
                  opacity: loadingWorkspaces ? 0.6 : 1,
                }}
              >
                ↻
              </button>
              <button
                onClick={handleConnect}
                disabled={connecting}
                title="Reconnect to update permissions"
                style={{
                  padding: '8px 12px',
                  fontSize: '12px',
                  borderRadius: '6px',
                  border: '1px solid #EDEBE9',
                  background: '#FFFFFF',
                  cursor: connecting ? 'not-allowed' : 'pointer',
                  opacity: connecting ? 0.6 : 1,
                  whiteSpace: 'nowrap',
                }}
              >
                {connecting ? 'Connecting...' : 'Reconnect'}
              </button>
            </div>
          </div>

          <div>
            <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Team
            </label>
            <TeamSelect
              value={selectedTeamId}
              onChange={handleTeamChange}
              teams={teams}
              loading={loadingTeams}
              disabled={!selectedTenantId}
            />
          </div>

          <div>
            <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Channels
            </label>
            <TeamsChannelSelect
              values={selectedChannelIds}
              onChange={handleChannelChange}
              channels={channels}
              loading={loadingChannels}
              disabled={!selectedTeamId}
            />

            {/* Selected Channels Display */}
            {selectedChannelIds.length > 0 && (
              <div style={{
                marginTop: '8px',
                display: 'flex',
                flexWrap: 'wrap',
                gap: '6px',
              }}>
                {selectedChannelIds.map((channelId: string) => {
                  const channel = channels.find((c: any) => c.id === channelId);
                  if (!channel) return null;
                  return (
                    <div
                      key={channelId}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 8px',
                        background: '#EFF6FF',
                        border: '1px solid #BFDBFE',
                        borderRadius: '4px',
                        fontSize: '11px',
                        color: '#1e40af',
                      }}
                    >
                      <span>{channel.display_name}</span>
                      <button
                        onClick={() => handleRemoveChannel(channelId)}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          color: '#3b82f6',
                          display: 'flex',
                          alignItems: 'center',
                        }}
                        title="Remove channel"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Custom Message
        </label>
        <textarea
          value={node.data?.customMessage || ''}
          onChange={(e) => updateNodeData({ customMessage: e.target.value })}
          placeholder={aiGeneratedMessage ? 'AI will generate the message' : 'Enter your message...'}
          rows={4}
          disabled={aiGeneratedMessage}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '6px',
            outline: 'none',
            resize: 'vertical',
            fontFamily: 'inherit',
            background: aiGeneratedMessage ? '#FAFAFA' : '#F5F5F5',
            color: aiGeneratedMessage ? '#C8C6C4' : '#605E5C',
            lineHeight: '1.5',
            cursor: aiGeneratedMessage ? 'not-allowed' : 'text',
            opacity: aiGeneratedMessage ? 0.6 : 1,
          }}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '500' }}>
          AI generated message
        </label>
        <label style={{ position: 'relative', display: 'inline-block', width: '36px', height: '20px' }}>
          <input
            type="checkbox"
            checked={aiGeneratedMessage}
            onChange={(e) => updateNodeData({ aiGeneratedMessage: e.target.checked })}
            style={{ opacity: 0, width: 0, height: 0 }}
          />
          <span style={{
            position: 'absolute',
            cursor: 'pointer',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: aiGeneratedMessage ? '#0078D4' : '#D1D1D1',
            transition: 'background-color 0.2s',
            borderRadius: '20px',
          }}>
            <span style={{
              position: 'absolute',
              content: '',
              height: '14px',
              width: '14px',
              left: aiGeneratedMessage ? '19px' : '3px',
              bottom: '3px',
              backgroundColor: 'white',
              transition: 'left 0.2s',
              borderRadius: '50%',
            }} />
          </span>
        </label>
      </div>
    </div>
  );
}

// Save to Sentry Configuration Component
function MergeConfig({ node, onUpdate }: any) {
  const [label, setLabel] = useState(node.data?.label || 'Merge');

  const handleLabelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newLabel = e.target.value;
    setLabel(newLabel);
    onUpdate({ label: newLabel });
  };

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Description */}
      <div style={{
        padding: '12px',
        background: '#F3E8FF',
        borderRadius: '6px',
        fontSize: '12px',
        color: '#605E5C',
        lineHeight: '1.5',
      }}>
        This node combines multiple data sources into a single output for the agent.
      </div>

      {/* Label Input */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Label
        </label>
        <input
          type="text"
          value={label}
          onChange={handleLabelChange}
          placeholder="Merge"
          style={{
            width: '100%',
            padding: '8px 12px',
            border: '1px solid #DADCE0',
            borderRadius: '6px',
            fontSize: '13px',
            color: '#202124',
            outline: 'none',
            transition: 'border-color 0.15s',
          }}
          onFocus={(e) => {
            e.target.style.borderColor = '#8B5CF6';
          }}
          onBlur={(e) => {
            e.target.style.borderColor = '#DADCE0';
          }}
        />
      </div>
    </div>
  );
}

function DistributeConfig({ node, onUpdate }: any) {
  const [label, setLabel] = useState(node.data?.label || 'Distribute');

  const handleLabelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newLabel = e.target.value;
    setLabel(newLabel);
    onUpdate({ label: newLabel });
  };

  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Description */}
      <div style={{
        padding: '12px',
        background: '#F3E8FF',
        borderRadius: '6px',
        fontSize: '12px',
        color: '#605E5C',
        lineHeight: '1.5',
      }}>
        This node distributes output to multiple delivery channels (Email, Slack, Teams, or Save to Sentry).
      </div>

      {/* Label Input */}
      <div>
        <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
          Label
        </label>
        <input
          type="text"
          value={label}
          onChange={handleLabelChange}
          placeholder="Distribute"
          style={{
            width: '100%',
            padding: '8px 12px',
            border: '1px solid #DADCE0',
            borderRadius: '6px',
            fontSize: '13px',
            color: '#202124',
            outline: 'none',
            transition: 'border-color 0.15s',
          }}
          onFocus={(e) => {
            e.target.style.borderColor = '#8B5CF6';
          }}
          onBlur={(e) => {
            e.target.style.borderColor = '#DADCE0';
          }}
        />
      </div>
    </div>
  );
}

function SaveToSentryConfig() {
  return (
    <div style={{ padding: '0 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {/* Description label */}
      <label style={{ fontSize: '12px', color: '#1F1F1F', fontWeight: '600' }}>
        Description
      </label>
      {/* Description - locked/read-only */}
      <div style={{
        padding: '12px',
        background: '#F5F5F5',
        borderRadius: '6px',
        fontSize: '12px',
        color: '#605E5C',
        lineHeight: '1.5',
      }}>
        This node saves the workflow results to your runs history for future reference.
      </div>
    </div>
  );
}
