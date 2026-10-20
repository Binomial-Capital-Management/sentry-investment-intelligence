import { X, CheckCircle2 } from 'lucide-react';

interface ValidationIssue {
  severity: 'error' | 'warning' | 'info';
  message: string;
  node_id?: string;
  category: string;
}

interface ValidationResults {
  valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  info: ValidationIssue[];
  summary: {
    total_nodes: number;
    total_edges: number;
    error_count: number;
    warning_count: number;
    info_count: number;
  };
}

interface ValidationResultsModalProps {
  isOpen: boolean;
  onClose: () => void;
  results: ValidationResults | null;
  onFixIssue?: (nodeId: string) => void;
}

export function ValidationResultsModal({
  isOpen,
  onClose,
  results,
  onFixIssue,
}: ValidationResultsModalProps) {
  if (!isOpen || !results) return null;

  const getSeverityLabel = (severity: string) => {
    switch (severity) {
      case 'error': return { label: 'Error', color: '#DC3545' };
      case 'warning': return { label: 'Warning', color: '#F59E0B' };
      case 'info': return { label: 'Info', color: '#6B7280' };
      default: return { label: '', color: '#6B7280' };
    }
  };

  const renderIssueList = (issues: ValidationIssue[], severity: string) => {
    if (issues.length === 0) return null;

    const { label, color } = getSeverityLabel(severity);

    return (
      <div style={{ marginBottom: '16px' }}>
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          color: '#9CA3AF',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          marginBottom: '8px',
        }}>
          {label}s ({issues.length})
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {issues.map((issue, idx) => (
            <div
              key={idx}
              style={{
                padding: '10px 12px',
                background: '#FAFAFA',
                border: '1px solid #E5E7EB',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
              }}
            >
              <div style={{
                width: '3px',
                height: '16px',
                background: color,
                borderRadius: '2px',
                marginTop: '1px',
                flexShrink: 0,
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  fontSize: '13px',
                  color: '#1F2937',
                  margin: 0,
                  lineHeight: '1.5',
                }}>
                  {issue.message}
                </p>
                {issue.node_id && (
                  <p style={{
                    fontSize: '11px',
                    color: '#9CA3AF',
                    margin: '4px 0 0 0',
                    fontFamily: 'monospace',
                  }}>
                    {issue.node_id}
                  </p>
                )}
              </div>
              {issue.node_id && onFixIssue && (
                <button
                  onClick={() => onFixIssue(issue.node_id!)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '11px',
                    color: '#6B7280',
                    background: 'white',
                    border: '1px solid #E5E7EB',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    flexShrink: 0,
                    fontWeight: 500,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#F9FAFB';
                    e.currentTarget.style.color = '#111827';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'white';
                    e.currentTarget.style.color = '#6B7280';
                  }}
                >
                  Fix
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.4)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 10000,
      padding: '20px',
    }}>
      <div style={{
        background: 'white',
        borderRadius: '8px',
        maxWidth: '600px',
        width: '100%',
        maxHeight: '80vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid #E5E7EB',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '15px', fontWeight: 600, color: '#111827', margin: 0 }}>
              Validation
            </h2>
            <div style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 500,
              background: results.valid ? '#DCFCE7' : '#FEE2E2',
              color: results.valid ? '#15803D' : '#DC2626',
            }}>
              {results.valid ? 'Valid' : `${results.summary.error_count} ${results.summary.error_count === 1 ? 'issue' : 'issues'}`}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '4px',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = '#F3F4F6'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <X size={16} color="#6B7280" />
          </button>
        </div>

        {/* Content */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
        }}>
          {results.valid ? (
            <div style={{ textAlign: 'center', padding: '32px 20px' }}>
              <CheckCircle2 size={48} color="#22C55E" strokeWidth={2} style={{ marginBottom: '12px' }} />
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#111827', marginBottom: '4px' }}>
                Workflow Valid
              </h3>
              <p style={{ fontSize: '13px', color: '#6B7280', margin: 0 }}>
                Ready to save or deploy
              </p>
            </div>
          ) : (
            <>
              {renderIssueList(results.errors, 'error')}
              {renderIssueList(results.warnings, 'warning')}
              {renderIssueList(results.info, 'info')}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
