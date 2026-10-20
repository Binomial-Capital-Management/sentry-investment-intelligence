import { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle, XCircle, Clock, Paperclip, FileText, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface TaskRun {
  id: string;
  timestamp: Date;
  status: 'success' | 'failed' | 'running';
  duration: number; // in seconds
  output?: string;
  errorMessage?: string;
  attachments?: {
    name: string;
    size?: string;
    url?: string;
  }[];
}

interface TaskHistoryProps {
  runs: TaskRun[];
}

// Custom typography components for markdown rendering
const CustomStrong = ({ children }: any) => (
  <strong style={{ fontWeight: '600', color: '#202124' }}>{children}</strong>
);

const CustomH2 = ({ children }: any) => (
  <h2 style={{ fontSize: '16px', fontWeight: '600', marginTop: '16px', marginBottom: '8px', color: '#202124' }}>{children}</h2>
);

const CustomH3 = ({ children }: any) => (
  <h3 style={{ fontSize: '14px', fontWeight: '600', marginTop: '12px', marginBottom: '6px', color: '#202124' }}>{children}</h3>
);

const CustomParagraph = ({ children }: any) => (
  <p style={{ marginTop: '8px', marginBottom: '8px', lineHeight: '1.6' }}>{children}</p>
);

const CustomUL = ({ children }: any) => (
  <ul style={{ marginTop: '8px', marginBottom: '8px', paddingLeft: '24px', listStyleType: 'disc' }}>{children}</ul>
);

const CustomOL = ({ children }: any) => (
  <ol style={{ marginTop: '8px', marginBottom: '8px', paddingLeft: '24px', listStyleType: 'decimal' }}>{children}</ol>
);

const CustomTable = ({ children }: any) => (
  <table style={{
    borderCollapse: 'collapse',
    width: '100%',
    marginTop: '12px',
    marginBottom: '12px',
    fontSize: '12px',
  }}>{children}</table>
);

const CustomTH = ({ children }: any) => (
  <th style={{
    border: '1px solid #E8EAED',
    padding: '8px',
    backgroundColor: '#F8F9FA',
    fontWeight: '600',
    textAlign: 'left',
  }}>{children}</th>
);

const CustomTD = ({ children }: any) => (
  <td style={{
    border: '1px solid #E8EAED',
    padding: '8px',
  }}>{children}</td>
);

const CustomCode = ({ children, inline }: any) => (
  inline ? (
    <code style={{
      backgroundColor: '#F1F3F4',
      padding: '2px 6px',
      borderRadius: '3px',
      fontSize: '11px',
      fontFamily: 'monospace',
    }}>{children}</code>
  ) : (
    <code style={{
      display: 'block',
      backgroundColor: '#F1F3F4',
      padding: '12px',
      borderRadius: '6px',
      fontSize: '11px',
      fontFamily: 'monospace',
      overflowX: 'auto',
      marginTop: '8px',
      marginBottom: '8px',
    }}>{children}</code>
  )
);

export function TaskHistory({ runs }: TaskHistoryProps) {
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());

  const toggleExpand = (runId: string) => {
    const newExpanded = new Set(expandedRuns);
    if (newExpanded.has(runId)) {
      newExpanded.delete(runId);
    } else {
      newExpanded.add(runId);
    }
    setExpandedRuns(newExpanded);
  };

  const formatTimestamp = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const getStatusIcon = (status: TaskRun['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircle size={16} color="#34A853" />;
      case 'failed':
        return <XCircle size={16} color="#EA4335" />;
      case 'running':
        return <Clock size={16} color="#FBBC04" />;
    }
  };

  const getStatusColor = (status: TaskRun['status']) => {
    switch (status) {
      case 'success':
        return '#34A853';
      case 'failed':
        return '#EA4335';
      case 'running':
        return '#FBBC04';
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: '48px',
      left: 0,
      right: 0,
      bottom: 0,
      background: '#F9F9F9',
      overflowY: 'auto',
      padding: '24px',
    }}>
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
      }}>
        {/* Header */}
        <div style={{
          marginBottom: '24px',
        }}>
          <h2 style={{
            fontSize: '20px',
            fontWeight: '500',
            color: '#202124',
            margin: 0,
          }}>
            Run History
          </h2>
          <p style={{
            fontSize: '13px',
            color: '#5F6368',
            margin: '4px 0 0 0',
          }}>
            {runs.length} {runs.length === 1 ? 'run' : 'runs'}
          </p>
        </div>

        {/* Run List */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}>
          {runs.length === 0 ? (
            <div style={{
              background: '#FFFFFF',
              borderRadius: '12px',
              padding: '48px 24px',
              textAlign: 'center',
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            }}>
              <Clock size={48} color="#DADCE0" style={{ margin: '0 auto 16px' }} />
              <p style={{
                fontSize: '14px',
                color: '#5F6368',
                margin: 0,
              }}>
                No runs yet. Deploy your task to see run history here.
              </p>
            </div>
          ) : (
            runs.map((run) => {
              const isExpanded = expandedRuns.has(run.id);

              return (
                <div
                  key={run.id}
                  style={{
                    background: '#FFFFFF',
                    borderRadius: '12px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                    overflow: 'hidden',
                  }}
                >
                  {/* Run Header */}
                  <div
                    onClick={() => toggleExpand(run.id)}
                    style={{
                      padding: '16px 20px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      borderBottom: isExpanded ? '1px solid #F1F3F4' : 'none',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#F8F9FA'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    {/* Expand Icon */}
                    <div>
                      {isExpanded ? (
                        <ChevronDown size={18} color="#5F6368" />
                      ) : (
                        <ChevronRight size={18} color="#5F6368" />
                      )}
                    </div>

                    {/* Status Icon */}
                    <div>{getStatusIcon(run.status)}</div>

                    {/* Run Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '4px',
                      }}>
                        <span style={{
                          fontSize: '14px',
                          fontWeight: '500',
                          color: '#202124',
                        }}>
                          {run.status === 'success' ? 'Completed' : run.status === 'failed' ? 'Failed' : 'Running'}
                        </span>
                        <span style={{
                          fontSize: '12px',
                          color: '#5F6368',
                        }}>
                          •
                        </span>
                        <span style={{
                          fontSize: '12px',
                          color: '#5F6368',
                        }}>
                          {formatTimestamp(run.timestamp)}
                        </span>
                      </div>
                      <div style={{
                        fontSize: '12px',
                        color: '#5F6368',
                      }}>
                        Duration: {formatDuration(run.duration)}
                        {run.attachments && run.attachments.length > 0 && (
                          <>
                            <span style={{ margin: '0 6px' }}>•</span>
                            {run.attachments.length} {run.attachments.length === 1 ? 'attachment' : 'attachments'}
                          </>
                        )}
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div style={{
                      padding: '4px 12px',
                      borderRadius: '12px',
                      fontSize: '11px',
                      fontWeight: '500',
                      color: getStatusColor(run.status),
                      background: `${getStatusColor(run.status)}15`,
                    }}>
                      {run.status.toUpperCase()}
                    </div>
                  </div>

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div style={{
                      padding: '20px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '16px',
                    }}>
                      {/* Output Section */}
                      {(run.output || run.errorMessage) && (
                        <div>
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            marginBottom: '8px',
                          }}>
                            <FileText size={14} color="#5F6368" />
                            <span style={{
                              fontSize: '13px',
                              fontWeight: '500',
                              color: '#202124',
                            }}>
                              {run.status === 'failed' ? 'Error Output' : 'Output'}
                            </span>
                          </div>
                          <div style={{
                            background: '#F8F9FA',
                            borderRadius: '8px',
                            padding: '12px',
                            border: '1px solid #E8EAED',
                            fontSize: '12px',
                            color: run.status === 'failed' ? '#EA4335' : '#202124',
                            maxHeight: '300px',
                            overflowY: 'auto',
                          }}>
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                strong: CustomStrong,
                                b: CustomStrong,
                                h2: CustomH2,
                                h3: CustomH3,
                                p: CustomParagraph,
                                ul: CustomUL,
                                ol: CustomOL,
                                table: CustomTable,
                                th: CustomTH,
                                td: CustomTD,
                                code: CustomCode,
                              }}
                            >
                              {run.errorMessage || run.output || ''}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}

                      {/* Attachments Section */}
                      {run.attachments && run.attachments.length > 0 && (
                        <div>
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            marginBottom: '8px',
                          }}>
                            <Paperclip size={14} color="#5F6368" />
                            <span style={{
                              fontSize: '13px',
                              fontWeight: '500',
                              color: '#202124',
                            }}>
                              Attachments
                            </span>
                          </div>
                          <div style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px',
                          }}>
                            {run.attachments.map((attachment, idx) => (
                              <div
                                key={idx}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '12px',
                                  padding: '10px 12px',
                                  background: '#F8F9FA',
                                  borderRadius: '8px',
                                  border: '1px solid #E8EAED',
                                }}
                              >
                                <Paperclip size={14} color="#5F6368" />
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div style={{
                                    fontSize: '13px',
                                    color: '#202124',
                                    fontWeight: '500',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                  }}>
                                    {attachment.name}
                                  </div>
                                  <div style={{
                                    fontSize: '11px',
                                    color: '#5F6368',
                                  }}>
                                    {attachment.size || 'Available'}
                                  </div>
                                </div>
                                {attachment.url ? (
                                  <button
                                    onClick={() => attachment.url && window.open(attachment.url, '_blank')}
                                    style={{
                                      padding: '6px',
                                      background: 'transparent',
                                      border: 'none',
                                      borderRadius: '4px',
                                      cursor: 'pointer',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                    }}
                                    onMouseEnter={(e) => e.currentTarget.style.background = '#E8EAED'}
                                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                                  >
                                    <Download size={14} color="#5F6368" />
                                  </button>
                                ) : (
                                  <span style={{ fontSize: '11px', color: '#9AA0A6' }}>
                                    No link
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
