import { useState, useEffect } from 'react';
import { Node } from 'reactflow';

interface OutputConfiguration {
  format: 'text' | 'pdf' | 'presentation';
  title?: string;
  includeCharts: boolean;
}

interface OutputConfigModalProps {
  node: Node;
  isOpen: boolean;
  onClose: () => void;
  onSave: (nodeId: string, configuration: OutputConfiguration) => void;
}

export function OutputConfigModal({ node, isOpen, onClose, onSave }: OutputConfigModalProps) {
  const [config, setConfig] = useState<OutputConfiguration>({
    format: 'text',
    title: '',
    includeCharts: true,
  });

  useEffect(() => {
    if (node.data.configuration) {
      setConfig({
        format: node.data.configuration.format || 'text',
        title: node.data.configuration.title || '',
        includeCharts: node.data.configuration.includeCharts ?? true,
      });
    }
  }, [node]);

  if (!isOpen) return null;

  const handleSave = () => {
    onSave(node.id, config);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="node-config-modal output-config-modal" role="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Configure {node.data.label}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {/* Output Format Selection */}
          <div className="config-form-group" style={{ marginBottom: '20px' }}>
            <label className="config-label" style={{ display: 'block', marginBottom: '8px', fontWeight: 600, fontSize: '14px' }}>
              Output Format
            </label>
            <select
              className="config-select"
              value={config.format}
              onChange={(e) => setConfig({...config, format: e.target.value as any})}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '4px',
                border: '1px solid #E1DFDD',
                fontSize: '14px',
              }}
            >
              <option value="text">Text Summary</option>
              <option value="pdf">PDF Report</option>
              <option value="presentation">PowerPoint Presentation</option>
            </select>
            <span className="config-hint" style={{ display: 'block', marginTop: '8px', fontSize: '12px', color: '#605E5C' }}>
              {config.format === 'text' && 'Plain text output displayed in the chat interface'}
              {config.format === 'pdf' && 'Professional PDF report with charts and detailed analysis'}
              {config.format === 'presentation' && 'PowerPoint slides with visualizations and key insights'}
            </span>
          </div>

          {/* Report Title (for PDF/PPT) */}
          {(config.format === 'pdf' || config.format === 'presentation') && (
            <div className="config-form-group" style={{ marginBottom: '20px' }}>
              <label className="config-label" style={{ display: 'block', marginBottom: '8px', fontWeight: 600, fontSize: '14px' }}>
                Report Title (Optional)
              </label>
              <input
                type="text"
                className="config-input"
                placeholder="e.g., Portfolio Risk Analysis Q4 2025"
                value={config.title || ''}
                onChange={(e) => setConfig({...config, title: e.target.value})}
                style={{
                  width: '100%',
                  padding: '8px',
                  borderRadius: '4px',
                  border: '1px solid #E1DFDD',
                  fontSize: '14px',
                }}
              />
              <span className="config-hint" style={{ display: 'block', marginTop: '8px', fontSize: '12px', color: '#605E5C' }}>
                Leave blank to auto-generate a title based on the analysis
              </span>
            </div>
          )}

          {/* Include Charts */}
          <div className="config-form-group">
            <label className="checkbox-label" style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={config.includeCharts}
                onChange={(e) => setConfig({...config, includeCharts: e.target.checked})}
                style={{ marginRight: '8px' }}
              />
              <span style={{ fontSize: '14px' }}>Include charts and visualizations</span>
            </label>
            <span className="config-hint" style={{ display: 'block', marginTop: '8px', marginLeft: '24px', fontSize: '12px', color: '#605E5C' }}>
              Agent will automatically generate relevant charts based on the analysis type
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
