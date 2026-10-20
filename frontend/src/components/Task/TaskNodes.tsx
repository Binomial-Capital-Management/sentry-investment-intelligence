import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Play, Square, Database, BarChart3, Upload, Sparkles, FileText, Presentation, BookOpen, Brain, Zap, LineChart, Code, Calculator, Bitcoin, Scale, Target, TrendingUp, Merge, Split } from 'lucide-react';

// Import model logos
import gptLogo from '@/assets/model-logos/gpt-logo.png';
import claudeLogo from '@/assets/model-logos/claude-logo.svg.png';
import geminiLogo from '@/assets/model-logos/gemini-logo.png';
import grokLogo from '@/assets/model-logos/grok.png';
import kimiLogo from '@/assets/model-logos/Kimi-logo-2025.png';
import qwenLogo from '@/assets/model-logos/Qwen_logo.svg.png';
import glmLogo from '@/assets/model-logos/Z.ai_(company_logo).svg.png';

// Agent modes configuration
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
];

// Models configuration
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

// Base node styling matching screenshot aesthetic
const baseNodeStyle: React.CSSProperties = {
  padding: '12px 16px',
  borderRadius: '10px',
  border: '1px solid #E1DFDD',
  background: '#FFFFFF',
  fontSize: '14px',
  fontWeight: '500',
  minWidth: '140px',
  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

// Start Node - Entry point
export const StartNode = memo(({ data }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#ffffff',
      border: '1px solid rgba(16, 185, 129, 0.3)',
      color: '#0F6D31',
    }}>
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Play size={12} style={{ color: '#10B981' }} />
      </div>
      <span>Start</span>
      <Handle type="source" position={Position.Right} style={{ background: '#10B981' }} />
    </div>
  );
});

StartNode.displayName = 'StartNode';

// Agent Node - AI agent with configuration
export const AgentNode = memo(({ data, selected }: NodeProps) => {
  // Get selected agent and model from data
  const selectedAgent = agentModes.find(a => a.id === (data.agent || 'auto')) || agentModes[0];
  const selectedModel = models.find(m => m.id === (data.model || 'gpt-6.1-sol')) || models[0];
  const AgentIcon = selectedAgent.icon;

  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? `1px solid ${selectedAgent.color}` : `1px solid ${selectedAgent.color}40`,
      boxShadow: selected ? `0 0 0 2px ${selectedAgent.color}` : '0 1px 3px rgba(0,0,0,0.08)',
      flexDirection: 'column',
      alignItems: 'flex-start',
      gap: '4px',
      padding: '10px 14px',
      minWidth: '200px',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />

      {/* Main row with icon and agent name */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
        <div style={{
          width: '18px',
          height: '18px',
          borderRadius: '4px',
          background: 'transparent',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          <AgentIcon size={12} style={{ color: selectedAgent.color }} />
        </div>
        <span style={{ fontWeight: '600', color: '#2C2C2C', fontSize: '13px' }}>
          {selectedAgent.name}
        </span>
      </div>

      {/* Subtitle with model logo and name */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
      }}>
        <img
          src={selectedModel.logo}
          alt={selectedModel.name}
          style={{
            width: '12px',
            height: '12px',
            borderRadius: '2px',
            objectFit: 'contain',
          }}
        />
        <span style={{
          fontSize: '11px',
          color: '#6B7280',
          fontWeight: '400',
          whiteSpace: 'nowrap',
        }}>
          {selectedModel.name}
        </span>
      </div>

      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

AgentNode.displayName = 'AgentNode';

// End Node - Terminal node
export const EndNode = memo(({ data }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: '1px solid rgba(239, 68, 68, 0.3)',
      color: '#7F1D1D',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Square size={12} style={{ color: '#EF4444', fill: '#EF4444' }} />
      </div>
      <span>End</span>
    </div>
  );
});

EndNode.displayName = 'EndNode';

// Google Drive Node
export const GoogleDriveNode = memo(({ data: _data, selected: _selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      flexDirection: 'column',
      alignItems: 'flex-start',
      gap: '4px',
      padding: '10px 14px',
      minWidth: '160px',
    }}>
      <Handle type="target" position={Position.Left} />

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
        <div style={{ width: '18px', height: '18px' }}>
          <img
            src="/connector-logos/google-drive.png"
            alt="Google Drive"
            style={{ width: '14px', height: '14px', objectFit: 'contain' }}
          />
        </div>
        <span style={{ fontWeight: '600', color: '#2C2C2C', fontSize: '13px' }}>
          Google Drive
        </span>
      </div>

      <span style={{
        fontSize: '11px',
        color: '#6B7280',
        fontWeight: '400',
        whiteSpace: 'nowrap',
      }}>
        All
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
});

GoogleDriveNode.displayName = 'GoogleDriveNode';

// Portfolio Node
export const PortfolioNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #9C27B0' : '1px solid rgba(156, 39, 176, 0.3)',
      boxShadow: selected ? '0 0 0 2px #9C27B0' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Database size={12} style={{ color: '#9C27B0' }} />
      </div>
      <span>{data.name || 'Portfolio'}</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

PortfolioNode.displayName = 'PortfolioNode';

// Graph Node
export const GraphNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #4CAF50' : '1px solid rgba(76, 175, 80, 0.3)',
      boxShadow: selected ? '0 0 0 2px #4CAF50' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <BarChart3 size={12} style={{ color: '#4CAF50' }} />
      </div>
      <span>Graph</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

GraphNode.displayName = 'GraphNode';

// File Upload Node
export const FileUploadNode = memo(({ data, selected }: NodeProps) => {
  const fileName = data.fileName;

  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #FF9800' : '1px solid rgba(255, 152, 0, 0.3)',
      boxShadow: selected ? '0 0 0 2px #FF9800' : '0 2px 4px rgba(0,0,0,0.06)',
      flexDirection: 'column',
      alignItems: 'flex-start',
      gap: '4px',
      padding: '10px 14px',
      minWidth: '180px',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />

      {/* Main row with icon and label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
        <div style={{
          width: '18px',
          height: '18px',
          borderRadius: '4px',
          background: 'transparent',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          <Upload size={12} style={{ color: '#FF9800' }} />
        </div>
        <span style={{ fontWeight: '600', color: '#2C2C2C', fontSize: '13px' }}>
          File Upload
        </span>
      </div>

      {/* Subtitle with file name */}
      {fileName && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}>
          <span style={{
            fontSize: '11px',
            color: '#6B7280',
            fontWeight: '400',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '150px',
          }}>
            {fileName}
          </span>
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

FileUploadNode.displayName = 'FileUploadNode';

// Email Node
export const EmailNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #F44336' : '1px solid rgba(244, 67, 54, 0.3)',
      boxShadow: selected ? '0 0 0 2px #F44336' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <img
          src="/connector-logos/email-icon.png"
          alt="Email"
          style={{ width: '14px', height: '14px', objectFit: 'contain' }}
        />
      </div>
      <span>Email</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

EmailNode.displayName = 'EmailNode';

// PDF Report Node
export const PDFReportNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #E91E63' : '1px solid rgba(233, 30, 99, 0.3)',
      boxShadow: selected ? '0 0 0 2px #E91E63' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <FileText size={12} style={{ color: '#E91E63' }} />
      </div>
      <span>PDF Report</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

PDFReportNode.displayName = 'PDFReportNode';

// PPT Node
export const PPTNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #F57C00' : '1px solid rgba(245, 124, 0, 0.3)',
      boxShadow: selected ? '0 0 0 2px #F57C00' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Presentation size={12} style={{ color: '#F57C00' }} />
      </div>
      <span>PPT</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

PPTNode.displayName = 'PPTNode';

// Workbook Node
export const WorkbookNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #4CAF50' : '1px solid rgba(76, 175, 80, 0.3)',
      boxShadow: selected ? '0 0 0 2px #4CAF50' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <BookOpen size={12} style={{ color: '#4CAF50' }} />
      </div>
      <span>Workbook</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

WorkbookNode.displayName = 'WorkbookNode';

// Save to Sentry Node
export const SaveToSentryNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #111827' : '1px solid rgba(17, 24, 39, 0.3)',
      boxShadow: selected ? '0 0 0 2px #111827' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <img src="/binomial-icon-logo.png" alt="Binomial" style={{ width: '16px', height: '16px', objectFit: 'contain' }} />
      </div>
      <span>Save to Sentry</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

SaveToSentryNode.displayName = 'SaveToSentryNode';

// OneDrive Node
export const OneDriveNode = memo(({ data, selected }: NodeProps) => {
  const accountType = data.accountType;
  const accountTypeLabel = accountType === 'business' ? 'Business' : 'Personal';

  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #0078D4' : '1px solid rgba(0, 120, 212, 0.3)',
      boxShadow: selected ? '0 0 0 2px #0078D4' : '0 2px 4px rgba(0,0,0,0.06)',
      flexDirection: 'column',
      alignItems: 'flex-start',
      gap: '4px',
      padding: '10px 14px',
      minWidth: '160px',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />

      {/* Main row with icon and label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
        <div style={{
          width: '18px',
          height: '18px',
          borderRadius: '4px',
          background: 'transparent',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          <img
            src="/connector-logos/one-drive.png"
            alt="OneDrive"
            style={{ width: '14px', height: '14px', objectFit: 'contain' }}
          />
        </div>
        <span style={{ fontWeight: '600', color: '#2C2C2C', fontSize: '13px' }}>
          OneDrive
        </span>
      </div>

      {/* Subtitle with account type */}
      {accountType && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}>
          <span style={{
            fontSize: '11px',
            color: '#6B7280',
            fontWeight: '400',
            whiteSpace: 'nowrap',
          }}>
            {accountTypeLabel}
          </span>
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

OneDriveNode.displayName = 'OneDriveNode';

// SharePoint Node
export const SharePointNode = memo(({ data, selected }: NodeProps) => {
  const fileName = data.fileName;

  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #036C70' : '1px solid rgba(3, 108, 112, 0.3)',
      boxShadow: selected ? '0 0 0 2px #036C70' : '0 2px 4px rgba(0,0,0,0.06)',
      flexDirection: 'column',
      alignItems: 'flex-start',
      gap: '4px',
      padding: '10px 14px',
      minWidth: '160px',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />

      {/* Main row with icon and label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
        <div style={{
          width: '18px',
          height: '18px',
          borderRadius: '4px',
          background: 'transparent',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          <img
            src="/connector-logos/sharepoint-logo.png"
            alt="SharePoint"
            style={{ width: '14px', height: '14px', objectFit: 'contain' }}
          />
        </div>
        <span style={{ fontWeight: '600', color: '#2C2C2C', fontSize: '13px' }}>
          SharePoint
        </span>
      </div>

      {/* File name if available */}
      {fileName && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}>
          <span style={{
            fontSize: '11px',
            color: '#6B7280',
            fontWeight: '400',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '140px',
          }}>
            {fileName}
          </span>
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

SharePointNode.displayName = 'SharePointNode';

// Slack Node
export const SlackNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #4A154B' : '1px solid rgba(74, 21, 75, 0.3)',
      boxShadow: selected ? '0 0 0 2px #4A154B' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <img
          src="/connector-logos/slack-logo.png"
          alt="Slack"
          style={{ width: '14px', height: '14px', objectFit: 'contain' }}
        />
      </div>
      <span>Slack</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

SlackNode.displayName = 'SlackNode';

// Teams Node
export const TeamsNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #5B5FC7' : '1px solid rgba(91, 95, 199, 0.3)',
      boxShadow: selected ? '0 0 0 2px #5B5FC7' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <img
          src="/connector-logos/teams-logo.png"
          alt="Teams"
          style={{ width: '14px', height: '14px', objectFit: 'contain' }}
        />
      </div>
      <span>Teams</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

TeamsNode.displayName = 'TeamsNode';

// Merge Node - Combines multiple data sources
export const MergeNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #8B5CF6' : '1px solid rgba(139, 92, 246, 0.3)',
      boxShadow: selected ? '0 0 0 2px #8B5CF6' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Merge size={12} style={{ color: '#8B5CF6', transform: 'rotate(90deg)' }} />
      </div>
      <span>{data.label || 'Merge'}</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

MergeNode.displayName = 'MergeNode';

// Distribute Node - Distributes to multiple delivery channels (inverse of merge)
export const DistributeNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div style={{
      ...baseNodeStyle,
      background: '#FFFFFF',
      border: selected ? '1px solid #8B5CF6' : '1px solid rgba(139, 92, 246, 0.3)',
      boxShadow: selected ? '0 0 0 2px #8B5CF6' : '0 2px 4px rgba(0,0,0,0.06)',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: '#6B7280' }} />
      <div style={{
        width: '20px',
        height: '20px',
        borderRadius: '4px',
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Split size={12} style={{ color: '#8B5CF6', transform: 'rotate(90deg)' }} />
      </div>
      <span>{data.label || 'Distribute'}</span>
      <Handle type="source" position={Position.Right} style={{ background: '#6B7280' }} />
    </div>
  );
});

DistributeNode.displayName = 'DistributeNode';

// Export node types for ReactFlow
export const taskNodeTypes = {
  start: StartNode,
  agent: AgentNode,
  merge: MergeNode,
  distribute: DistributeNode,
  end: EndNode,
  portfolio: PortfolioNode,
  graph: GraphNode,
  fileUpload: FileUploadNode,
  oneDrive: OneDriveNode,
  sharepoint: SharePointNode,
  googleDrive: GoogleDriveNode,
  slack: SlackNode,
  teams: TeamsNode,
  email: EmailNode,
  pdfReport: PDFReportNode,
  pptPresentation: PPTNode,
  workbook: WorkbookNode,
  saveToSentry: SaveToSentryNode,
};
