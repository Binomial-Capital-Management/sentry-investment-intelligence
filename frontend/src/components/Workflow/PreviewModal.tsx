import { Node } from 'reactflow';
import { generateMockPreview } from '@/utils/mockPipelineData';

interface PreviewModalProps {
  node: Node;
  onClose: () => void;
}

const PreviewModal = ({ node, onClose }: PreviewModalProps) => {
  // Map node types to preview types that generateMockPreview expects
  const getPreviewType = (node: Node) => {
    if (node.type === 'dataset') {
      // Use configuration source if available, otherwise check data.type, fallback to portfolio
      const source = node.data.configuration?.source || node.data.type;
      switch(source) {
        case 'market':
        case 'server': return 'marketData';
        case 'upload':
        case 'document':
        case 'custom': return 'upload';
        default: return 'portfolio';
      }
    }
    if (node.type === 'agent') return 'riskAnalysis';
    if (node.type === 'output') return 'report';
    return 'portfolio'; // fallback
  };

  const previewData = generateMockPreview(getPreviewType(node), node.data);

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="preview-modal-title"
        style={{
        background: '#FFFFFF',
        borderRadius: '8px',
        padding: '24px',
        minWidth: '600px',
        maxWidth: '800px',
        maxHeight: '80vh',
        overflow: 'auto',
        boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
        fontFamily: '"Segoe UI Variable", "Segoe UI", sans-serif',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 id="preview-modal-title" style={{ margin: 0, color: '#323130', fontSize: '20px', fontWeight: '600' }}>
            Preview: {node.data.label || node.type}
          </h2>
          <button
            aria-label="Close modal"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '24px',
              color: '#605E5C',
              cursor: 'pointer',
              padding: '4px 8px',
            }}
          >
            ×
          </button>
        </div>

        {previewData.length > 0 ? (
          <div>
            <div style={{ marginBottom: '16px', color: '#605E5C', fontSize: '14px' }}>
              Showing first {Math.min(previewData.length, 5)} rows • {Object.keys(previewData[0] || {}).length} columns
            </div>

            <div style={{
              overflow: 'auto',
              border: '1px solid #E1DFDD',
              borderRadius: '4px',
            }}>
              <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '14px',
              }}>
                <thead>
                  <tr style={{ background: '#FAF9F8' }}>
                    {Object.keys(previewData[0] || {}).map(col => (
                      <th key={col} style={{
                        padding: '12px 16px',
                        textAlign: 'left',
                        fontWeight: '600',
                        color: '#323130',
                        borderBottom: '1px solid #E1DFDD',
                      }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewData.slice(0, 5).map((row, i) => (
                    <tr key={i} style={{
                      borderBottom: i < 4 ? '1px solid #F3F2F1' : 'none',
                    }}>
                      {Object.values(row).map((value, j) => (
                        <td key={j} style={{
                          padding: '12px 16px',
                          color: '#323130',
                        }}>
                          {typeof value === 'number' ? value.toLocaleString() : String(value)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div style={{
            textAlign: 'center',
            padding: '40px',
            color: '#A19F9D',
            fontSize: '14px',
          }}>
            No preview data available for this node type
          </div>
        )}

        <div style={{ marginTop: '24px', textAlign: 'right' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              background: '#0078D4',
              border: 'none',
              borderRadius: '4px',
              color: 'white',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default PreviewModal;
