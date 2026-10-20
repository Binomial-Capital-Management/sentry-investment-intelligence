import React, { useState } from 'react';
import { X, ChevronLeft, FileJson, AlertCircle } from 'lucide-react';
import { WorkflowRunsList } from './WorkflowRunsList';
import { format } from 'date-fns';

interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  error?: string;
  result?: any;
  metadata?: any;
}

interface RunHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId: string;
  workflowName: string;
  refreshTrigger?: number;
}

export const RunHistoryModal: React.FC<RunHistoryModalProps> = ({
  isOpen,
  onClose,
  workflowId,
  workflowName,
  refreshTrigger,
}) => {
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);

  if (!isOpen) return null;

  const handleViewRun = (run: WorkflowRun) => {
    setSelectedRun(run);
  };

  const handleBack = () => {
    setSelectedRun(null);
  };

  const renderRunDetails = () => {
    if (!selectedRun) return null;

    return (
      <div className="flex-1 overflow-auto">
        <div className="flex items-center gap-2 mb-4">
          <button
            onClick={handleBack}
            className="p-1 hover:bg-gray-100 rounded-md transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <h3 className="text-lg font-semibold">Run Details</h3>
        </div>

        <div className="space-y-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Information</h4>
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Status:</dt>
                <dd className="font-medium">{selectedRun.status}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Started:</dt>
                <dd>{format(new Date(selectedRun.started_at), 'PPpp')}</dd>
              </div>
              {selectedRun.completed_at && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Completed:</dt>
                  <dd>{format(new Date(selectedRun.completed_at), 'PPpp')}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-gray-500">Run ID:</dt>
                <dd className="font-mono text-xs">{selectedRun.id.slice(0, 8)}...</dd>
              </div>
            </dl>
          </div>

          {selectedRun.error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 mt-0.5" />
                <div className="flex-1">
                  <h4 className="text-sm font-medium text-red-800 mb-1">Error</h4>
                  <p className="text-sm text-red-700">{selectedRun.error}</p>
                </div>
              </div>
            </div>
          )}

          {selectedRun.result && (
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileJson className="w-4 h-4 text-gray-500" />
                <h4 className="text-sm font-medium text-gray-700">Result</h4>
              </div>
              <pre className="text-xs bg-white p-3 rounded border border-gray-200 overflow-x-auto">
                {JSON.stringify(selectedRun.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className={isOpen ? 'h-full flex flex-col' : 'hidden'}>
      <div className="bg-white rounded-lg shadow-xl w-full h-full flex flex-col">
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">Run History</h2>
            <p className="text-sm text-gray-500 mt-1">{workflowName}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden p-6">
          {selectedRun ? (
            renderRunDetails()
          ) : (
            <WorkflowRunsList
              workflowId={workflowId}
              onViewRun={handleViewRun}
              refreshTrigger={refreshTrigger}
            />
          )}
        </div>
      </div>
    </div>
  );
};
