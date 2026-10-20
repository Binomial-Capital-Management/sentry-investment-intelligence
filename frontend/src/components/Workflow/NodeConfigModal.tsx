import { useState, useEffect } from 'react';
import { Node } from 'reactflow';

interface Props {
  node: Node | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (nodeId: string, configuration: any) => void;
}

export function NodeConfigModal({ node, isOpen, onClose, onSave }: Props) {
  const [customPrompt, setCustomPrompt] = useState('');

  useEffect(() => {
    if (node?.data?.configuration?.prompt) {
      setCustomPrompt(node.data.configuration.prompt);
    } else {
      setCustomPrompt('');
    }
  }, [node]);

  const handleSave = () => {
    if (!node) return;
    onSave(node.id, { prompt: customPrompt.trim() });
    onClose();
  };

  if (!isOpen || !node) return null;

  // Get agent description for helper text
  const agentDescriptions: Record<string, string> = {
    'Generalist': 'General market research, data analysis, and web search',
    'Risk Specialist': 'VaR analysis, Monte Carlo, portfolio optimization, Barra factors',
    'Document Analyst': 'SEC filings, earnings transcripts, financial document analysis',
    'Comparable Companies': 'Peer analysis, valuation multiples, sector comparisons',
    'Chart Analyst': 'Financial charts, technical analysis, visualizations',
    'Quant Coding': 'Custom Python code execution, data analysis, file generation',
    'DCF Agent': 'Discounted cash flow valuation, intrinsic value analysis',
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="node-config-modal" role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Configure {node.data.label}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="agent-info" style={{ marginBottom: '16px', padding: '12px', background: '#F3F2F1', borderRadius: '4px' }}>
            <p className="agent-description" style={{ margin: 0, fontSize: '14px', color: '#605E5C' }}>
              {agentDescriptions[node.data.label] || 'AI agent for specialized analysis'}
            </p>
          </div>

          <div className="config-section">
            <label className="config-label" style={{ display: 'block', marginBottom: '8px', fontWeight: 600, fontSize: '14px' }}>
              Instructions for Agent
            </label>
            <textarea
              className="prompt-input"
              placeholder={`What should ${node.data.label} focus on? (optional)\n\nExample: "Focus on risk metrics" or "Generate trading strategy"\n\nLeave empty for default analysis.`}
              value={customPrompt}
              onChange={e => setCustomPrompt(e.target.value)}
              rows={8}
              style={{
                width: '100%',
                fontFamily: 'monospace',
                fontSize: '13px',
                padding: '8px',
                borderRadius: '4px',
                border: '1px solid #E1DFDD',
                resize: 'vertical',
              }}
            />
            <span className="config-hint" style={{ display: 'block', marginTop: '8px', fontSize: '12px', color: '#605E5C' }}>
              Leave blank for default agent behavior. Tools and data sources are selected automatically.
            </span>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSave}>Save Configuration</button>
        </div>
      </div>
    </div>
  );
}
