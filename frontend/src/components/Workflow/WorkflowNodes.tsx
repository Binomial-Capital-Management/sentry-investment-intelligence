import { Handle, Position, NodeProps } from 'reactflow';
import type { InputNodeType, AgentNodeType, OutputNodeType } from '@/types/workflow';
import { Sparkles, Zap, FileText, BarChart3, LineChart, Code, Bitcoin, Scale, Calculator, Database, Paperclip, MessageSquare, Type, Presentation, Cloud } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// Input node - Portfolio, Uploaded File, or Prompt
export function InputNode({ data, selected }: NodeProps) {
  const inputType: InputNodeType = data.inputType || data.configuration?.inputType || 'prompt';
  const portfolioName = data.portfolioName || 'My Portfolio';
  const fileName = data.fileName || 'document.pdf';
  const promptPreview = data.promptText || data.configuration?.prompt_text ?
    (data.promptText || data.configuration?.prompt_text).substring(0, 50) +
    ((data.promptText || data.configuration?.prompt_text).length > 50 ? '...' : '') :
    'Enter prompt...';

  const getIconConfig = () => {
    switch(inputType) {
      case 'portfolio':
        return { Icon: Database, color: '#0078D4' };
      case 'uploaded_file':
        return { Icon: Paperclip, color: '#10b981' };
      case 'external_data':
        return { Icon: Cloud, color: '#f59e0b' };
      case 'prompt':
        return { Icon: MessageSquare, color: '#8b5cf6' };
      default:
        return { Icon: MessageSquare, color: '#8b5cf6' };
    }
  };

  const { Icon: InputIcon, color } = getIconConfig();

  const getDisplayText = () => {
    switch(inputType) {
      case 'portfolio': return portfolioName;
      case 'uploaded_file': return fileName;
      case 'external_data': return fileName;
      case 'prompt': return promptPreview;
    }
  };

  const getTypeLabel = () => {
    switch(inputType) {
      case 'portfolio': return 'Portfolio';
      case 'uploaded_file': return 'File Upload';
      case 'external_data': return 'External Data';
      case 'prompt': return 'Text Prompt';
    }
  };

  return (
    <div className={`dataset-node ${selected ? 'selected' : ''} ${data.executionStatus ? `executing-${data.executionStatus}` : ''}`}>
      {/* Header */}
      <div className="dataset-node-header">
        <div className="dataset-node-icon-box">
          <InputIcon size={18} style={{ color }} />
        </div>
        <div className="dataset-node-title">{data.label || 'Input'}</div>
      </div>

      {/* Body */}
      <div className="dataset-node-body">
        <div className="dataset-config-line">
          <span className="config-label">Type:</span>
          <span className="config-value">{getTypeLabel()}</span>
        </div>
        <div className="dataset-config-line">
          <span className="config-label">Data:</span>
          <span className="config-value" title={getDisplayText()}>{getDisplayText()}</span>
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="tactical-handle" />
    </div>
  );
}

// Agent node - 9 agent types with custom prompts
export function AgentNode({ data, selected }: NodeProps) {
  const agentType: AgentNodeType = data.agentType || 'generalist';
  const hasPrompt = data.customPrompt && data.customPrompt.trim().length > 0;
  const promptPreview = hasPrompt ?
    data.customPrompt.substring(0, 40) + (data.customPrompt.length > 40 ? '...' : '') :
    'No prompt';

  const getAgentConfig = (type: AgentNodeType) => {
    const configs: Record<AgentNodeType, { name: string; color: string; Icon: LucideIcon }> = {
      generalist: { name: 'Generalist', color: '#3b82f6', Icon: Sparkles },
      risk_specialist: { name: 'Risk Specialist', color: '#ef4444', Icon: Zap },
      document_analyst: { name: 'Document Analyst', color: '#f59e0b', Icon: FileText },
      comparable_companies: { name: 'Comparable Companies', color: '#8b5cf6', Icon: BarChart3 },
      chart_analyst: { name: 'Chart Analyst', color: '#06b6d4', Icon: LineChart },
      quant_coding: { name: 'Quant Coding', color: '#ec4899', Icon: Code },
      alternatives_coding: { name: 'Alternatives Coding', color: '#f59e0b', Icon: Bitcoin },
      institutional_activity: { name: 'Institutional Activity', color: '#8b5cf6', Icon: Scale },
      dcf_agent: { name: 'DCF Agent', color: '#059669', Icon: Calculator },
    };
    return configs[type] || configs.generalist;
  };

  const config = getAgentConfig(agentType);
  const AgentIcon = config.Icon;

  return (
    <div className={`agent-node ${selected ? 'selected' : ''} ${hasPrompt ? 'configured' : ''} ${data.executionStatus ? `executing-${data.executionStatus}` : ''}`}>
      <Handle type="target" position={Position.Left} className="tactical-handle" />

      {/* Header */}
      <div className="agent-node-header">
        <div className="agent-node-icon-box">
          <AgentIcon size={18} style={{ color: config.color }} />
        </div>
        <div className="agent-node-title">{data.label || config.name}</div>
      </div>

      {/* Body */}
      <div className="agent-node-body">
        <div className="agent-config-line">
          <span className="config-label">Agent:</span>
          <span className="config-value">{config.name}</span>
        </div>
        <div className="agent-config-line">
          <span className="config-label">Prompt:</span>
          <span className="config-value" title={data.customPrompt}>
            {hasPrompt ? promptPreview : '❌ Required'}
          </span>
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="tactical-handle" />
    </div>
  );
}

// Output node - Text, PDF, or Presentation
export function OutputNode({ data, selected }: NodeProps) {
  // Support both data.outputType (from API) and data.format (from visual builder)
  const outputType: OutputNodeType = data.outputType || data.format || 'text';
  // Support both data.title (from API) and data.label (from visual builder)
  const title = data.title || data.label || 'Workflow Report';
  const includeCharts = data.includeCharts !== false;

  const getIconConfig = () => {
    switch(outputType) {
      case 'text':
        return { Icon: Type, color: '#10b981' };
      case 'pdf':
        return { Icon: FileText, color: '#ef4444' };
      case 'presentation':
        return { Icon: Presentation, color: '#f59e0b' };
      default:
        return { Icon: Type, color: '#10b981' };
    }
  };

  const { Icon: OutputIcon, color } = getIconConfig();

  const getTypeLabel = () => {
    switch(outputType) {
      case 'text': return 'Plain Text';
      case 'pdf': return 'PDF Document';
      case 'presentation': return 'PowerPoint';
    }
  };

  return (
    <div className={`output-node ${selected ? 'selected' : ''} ${data.executionStatus ? `executing-${data.executionStatus}` : ''}`}>
      <Handle type="target" position={Position.Left} className="tactical-handle" />

      {/* Header */}
      <div className="output-node-header">
        <div className="output-node-icon-box">
          <OutputIcon size={24} style={{ color, strokeWidth: 2 }} />
        </div>
        <div className="output-node-title">{data.label || 'Output'}</div>
      </div>

      {/* Body */}
      <div className="output-node-body">
        <div className="output-config-line">
          <span className="config-label">Format:</span>
          <span className="config-value">{getTypeLabel()}</span>
        </div>
        <div className="output-config-line">
          <span className="config-label">Title:</span>
          <span className="config-value" title={title}>{title}</span>
        </div>
        {(outputType === 'pdf' || outputType === 'presentation') && (
          <div className="output-config-line">
            <span className="config-label">Charts:</span>
            <span className="config-value">{includeCharts ? '✓ Included' : '✗ Disabled'}</span>
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Right} className="tactical-handle" />
    </div>
  );
}

export const nodeTypes = {
  dataset: InputNode,  // Keep 'dataset' name for ReactFlow compatibility
  input: InputNode,    // Also export as 'input' for new code
  agent: AgentNode,
  output: OutputNode,
};
