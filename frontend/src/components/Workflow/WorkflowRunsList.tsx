import React, { useState, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Play, Trash2, Eye, AlertCircle, CheckCircle, Clock, XCircle, Loader2 } from 'lucide-react';
import { workflowApi } from '@/services/api';
import toast from 'react-hot-toast';
import type { RunStatus } from '@/types/workflow';

interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: RunStatus;
  started_at: string;
  completed_at?: string;
  error?: string;
  result?: any;
  metadata?: any;
}

interface WorkflowRunsListProps {
  workflowId: string;
  onViewRun: (run: WorkflowRun) => void;
  refreshTrigger?: number;
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'succeeded':
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'running':
      return <Clock className="w-4 h-4 text-blue-500 animate-spin" />;
    case 'failed':
      return <XCircle className="w-4 h-4 text-red-500" />;
    default:
      return <AlertCircle className="w-4 h-4 text-gray-400" />;
  }
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'succeeded':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'running':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'failed':
      return 'bg-red-100 text-red-800 border-red-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
};

export const WorkflowRunsList: React.FC<WorkflowRunsListProps> = ({
  workflowId,
  onViewRun,
  refreshTrigger = 0,
}) => {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState<string | null>(null);

  useEffect(() => {
    loadRuns();
  }, [workflowId, refreshTrigger]);

  const loadRuns = async () => {
    try {
      setLoading(true);
      const response = await workflowApi.listRuns(workflowId, 20);
      setRuns(response || []); // Backend returns array directly, not wrapped
    } catch (error) {
      console.error('Failed to load runs:', error);
      toast.error('Failed to load workflow runs');
      setRuns([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRerun = async (runId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setRerunning(runId);
      await workflowApi.rerun(workflowId);
      toast.success('Workflow re-run started');
      await loadRuns();
    } catch (error) {
      console.error('Failed to re-run workflow:', error);
      toast.error('Failed to re-run workflow');
    } finally {
      setRerunning(null);
    }
  };

  const handleDelete = async (runId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this run? This cannot be undone.')) return;

    try {
      setDeleting(runId);
      await workflowApi.deleteRun(runId);
      toast.success('Run deleted');
      setRuns(runs.filter(r => r.id !== runId));
    } catch (error) {
      console.error('Failed to delete run:', error);
      toast.error('Failed to delete run');
    } finally {
      setDeleting(null);
    }
  };

  const formatDuration = (start: string, end?: string) => {
    if (!end) return '--';
    const ms = new Date(end).getTime() - new Date(start).getTime();
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Clock className="w-12 h-12 mx-auto mb-3 text-gray-400" />
        <p className="text-base font-medium">No runs yet</p>
        <p className="text-sm mt-1">Execute this workflow to see run history</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {runs.map((run) => (
        <div
          key={run.id}
          onClick={() => onViewRun(run)}
          className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                {getStatusIcon(run.status)}
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(run.status)}`}>
                  {run.status.toUpperCase()}
                </span>
                <span className="text-xs text-gray-500">
                  {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
                </span>
              </div>

              {run.error && (
                <p className="text-xs text-red-600 mt-1 line-clamp-2">{run.error}</p>
              )}

              <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                <span>Duration: {formatDuration(run.started_at, run.completed_at)}</span>
                {run.metadata?.triggered_by && (
                  <span>By: {run.metadata.triggered_by}</span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1 ml-4">
              <button
                onClick={(e) => { e.stopPropagation(); onViewRun(run); }}
                className="p-1.5 text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                title="View details"
              >
                <Eye className="w-4 h-4" />
              </button>

              {run.status === 'succeeded' && (
                <button
                  onClick={(e) => handleRerun(run.id, e)}
                  disabled={rerunning === run.id}
                  className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors disabled:opacity-50"
                  title="Re-run workflow"
                >
                  {rerunning === run.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                </button>
              )}

              <button
                onClick={(e) => handleDelete(run.id, e)}
                disabled={deleting === run.id}
                className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50"
                title="Delete run"
              >
                {deleting === run.id ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
