import { useState, useEffect, lazy, Suspense } from 'react';
import { Trash2, Edit } from 'lucide-react';
import { workflowApi } from '@/services/api';
import toast from 'react-hot-toast';
import { useWorkflowExecution } from '@stores/workflowExecutionStore';

// Lazy load the workflow builder
const VisualWorkflowBuilder = lazy(() => import('../components/Workflow/VisualWorkflowBuilder').then(module => ({ default: module.VisualWorkflowBuilder })));

interface Workflow {
  id: string;
  name: string;
  status: string;
  created_at: string;
  last_run_at?: string;
}

export default function Workflows() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);

  // Use global store for workflow builder state
  const { showBuilder, selectedWorkflowId, isMinimized, setShowBuilder, minimize, reset } = useWorkflowExecution();

  useEffect(() => {
    fetchWorkflows();
  }, []);

  // Request notification permission on mount for workflow completion alerts
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      console.log('[NOTIFICATIONS] Requesting permission for workflow alerts');
      Notification.requestPermission().then(permission => {
        console.log('[NOTIFICATIONS] Permission:', permission);
      });
    }
  }, []);

  const fetchWorkflows = async () => {
    try {
      const data = await workflowApi.list(true);
      setWorkflows(data.workflows || []);
    } catch (err) {
      toast.error('Failed to load workflows');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this workflow?')) return;
    try {
      await workflowApi.delete(id);
      toast.success('Workflow deleted');
      fetchWorkflows();
    } catch (err) {
      toast.error((err as any)?.message || 'Failed to delete workflow');
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const isToday = date.toDateString() === today.toDateString();
    const isYesterday = date.toDateString() === yesterday.toDateString();

    if (isToday) {
      return 'Today ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } else if (isYesterday) {
      return 'Yesterday ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
           ' ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-base)' }}>
      {/* Command Bar */}
      <div style={{ background: '#FFFFFF', borderBottom: '1px solid #E1DFDD', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <div className="flex items-center justify-between" style={{ padding: '11px 16px' }}>
          <div className="flex items-center gap-4">
            <span style={{ color: '#323130', fontSize: '14px', fontWeight: '600' }}>
              Workflow Manager
            </span>
            <div style={{ width: '1px', height: '16px', background: '#E1DFDD' }} />
            <span style={{ color: '#605E5C', fontSize: '14px' }}>
              Total: {workflows.length} workflows
            </span>
          </div>
          <button
            style={{
              padding: '6px 16px',
              fontSize: '14px',
              fontWeight: '500',
              background: '#0078D4',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
            onClick={() => {
              setShowBuilder(true, null); // Create new workflow
            }}
          >
            + Create Workflow
          </button>
        </div>
      </div>

      {/* Workflows Table */}
      <div className="flex-1 p-4">
        <div style={{
          background: '#FFFFFF',
          border: '1px solid #E1DFDD',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          overflow: 'hidden',
        }}>
          <table className="w-full" style={{
            fontSize: 'var(--fs-base)',
            borderCollapse: 'separate',
            borderSpacing: 0,
          }}>
            <thead>
              <tr style={{ background: '#FAFAFA', borderBottom: '2px solid #E1DFDD' }}>
                <th className="text-left px-4 py-3" style={{
                  fontWeight: '600',
                  color: '#323130',
                  fontSize: '11px',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}>Name</th>
                <th className="text-left px-4 py-3" style={{
                  fontWeight: '600',
                  color: '#323130',
                  fontSize: '11px',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}>Created</th>
                <th className="text-left px-4 py-3" style={{
                  fontWeight: '600',
                  color: '#323130',
                  fontSize: '11px',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}>Last Run</th>
                <th className="text-center px-4 py-3" style={{
                  fontWeight: '600',
                  color: '#323130',
                  fontSize: '11px',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={4} className="px-4 py-4">
                      <div style={{
                        height: '16px',
                        background: 'linear-gradient(90deg, #F3F2F1 25%, #FAFAFA 50%, #F3F2F1 75%)',
                        backgroundSize: '200% 100%',
                        animation: 'shimmer 1.5s infinite',
                        borderRadius: '4px',
                        width: `${60 + Math.random() * 30}%`,
                      }} />
                    </td>
                  </tr>
                ))
              ) : workflows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center py-16">
                    <div style={{ color: '#605E5C' }}>
                      <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.3 }}>⚡</div>
                      <p style={{ fontSize: '16px', fontWeight: '500', marginBottom: '8px', color: '#323130' }}>
                        No workflows yet
                      </p>
                      <p style={{ fontSize: '14px', color: '#8A8886', marginBottom: '16px' }}>
                        Create your first workflow to automate your processes
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                workflows.map((workflow, index) => (
                  <tr
                    key={workflow.id}
                    style={{
                      borderBottom: index < workflows.length - 1 ? '1px solid #F3F2F1' : 'none',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      background: '#FFFFFF',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#F8F9FA';
                      e.currentTarget.style.boxShadow = 'inset 0 0 0 1px #E1DFDD';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = '#FFFFFF';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                    onClick={() => {
                      setShowBuilder(true, workflow.id);
                    }}
                  >
                    <td className="px-4 py-3" style={{ fontSize: '14px', fontWeight: 500 }}>
                      <span style={{ color: '#0078D4', fontWeight: '500' }}>{workflow.name}</span>
                    </td>
                    <td className="px-4 py-3" style={{ fontSize: '13px', color: '#605E5C', fontFamily: 'var(--font-mono)' }}>
                      <span style={{ color: '#323130' }}>{formatDate(workflow.created_at)}</span>
                    </td>
                    <td className="px-4 py-3" style={{ fontSize: '13px', color: '#605E5C', fontFamily: 'var(--font-mono)' }}>
                      {workflow.last_run_at ? (
                        <span style={{ color: '#323130' }}>{formatDate(workflow.last_run_at)}</span>
                      ) : (
                        <span style={{ color: '#C8C6C4', fontStyle: 'italic' }}>Never</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex gap-1.5 justify-center">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowBuilder(true, workflow.id);
                          }}
                          title="Edit"
                          style={{
                            padding: '6px',
                            background: '#FFFFFF',
                            border: '1px solid #E1DFDD',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = '#F3F2F1';
                            e.currentTarget.style.borderColor = '#605E5C';
                            e.currentTarget.style.transform = 'translateY(-1px)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = '#FFFFFF';
                            e.currentTarget.style.borderColor = '#E1DFDD';
                            e.currentTarget.style.transform = 'translateY(0)';
                          }}
                        >
                          <Edit size={14} style={{ color: '#605E5C' }} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(workflow.id);
                          }}
                          title="Delete"
                          style={{
                            padding: '6px',
                            background: '#FFFFFF',
                            border: '1px solid #E1DFDD',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = '#FEE';
                            e.currentTarget.style.borderColor = '#D13438';
                            e.currentTarget.style.transform = 'translateY(-1px)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = '#FFFFFF';
                            e.currentTarget.style.borderColor = '#E1DFDD';
                            e.currentTarget.style.transform = 'translateY(0)';
                          }}
                        >
                          <Trash2 size={14} style={{ color: '#D13438' }} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add shimmer animation */}
      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>

      {/* Workflow Builder Modal - hidden with CSS when minimized to keep execution alive */}
      {showBuilder && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'white',
          zIndex: 1000,
          display: isMinimized ? 'none' : 'block', // Hide with CSS instead of unmounting
        }}>
          <Suspense fallback={
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
              <div>Loading Workflow Builder...</div>
            </div>
          }>
            <VisualWorkflowBuilder
              onClose={() => {
                setShowBuilder(false, null); // Close builder and clear selection
                reset(); // Reset global execution state
                fetchWorkflows(); // Refresh the list
              }}
              onMinimize={minimize} // Pass store's minimize action directly
              workflowId={selectedWorkflowId}
            />
          </Suspense>
        </div>
      )}
    </div>
  );
}
