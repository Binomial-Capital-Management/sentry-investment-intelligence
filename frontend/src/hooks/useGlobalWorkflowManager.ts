import { useEffect, useRef } from 'react';
import { useWorkflowExecution } from '@/stores/workflowExecutionStore';
import { workflowApi } from '@/services/api';
import { useAuth } from '@clerk/clerk-react';
import { connectWorkflow, type WorkflowEvent } from '@/services/streaming';
import { toast } from 'sonner';

/**
 * Global workflow manager hook - handles polling and WebSocket connections
 * that persist across route changes. Should be called once at App.tsx level.
 */
export function useGlobalWorkflowManager() {
  const { activeExecution, updateNodeState, completeExecution } = useWorkflowExecution();
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const safetyTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const { getToken } = useAuth();

  // Polling for workflow status
  useEffect(() => {
    if (!activeExecution || activeExecution.status !== 'running') {
      // Clear polling if no active execution
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      if (safetyTimeoutRef.current) {
        clearTimeout(safetyTimeoutRef.current);
        safetyTimeoutRef.current = null;
      }
      return;
    }

    console.log('[GLOBAL MANAGER] Starting polling for run:', activeExecution.runId);

    // Set 20-minute safety timeout
    safetyTimeoutRef.current = setTimeout(() => {
      console.error('[GLOBAL MANAGER] 20-minute safety timeout triggered');
      toast.error('Workflow took too long (20 minutes) - resetting');
      completeExecution('failed');
      if (pollingRef.current) clearInterval(pollingRef.current);
    }, 20 * 60 * 1000);

    const pollStatus = async () => {
      try {
        const status = await workflowApi.getRunStatus(activeExecution.runId);

        // Update node states
        if (status.steps) {
          console.log('[GLOBAL MANAGER] Updating node states:', status.steps.length);
          status.steps.forEach((step: any) => {
            const normalizedStatus = step.status === 'started' ? 'running' : step.status;
            updateNodeState(step.node_id, normalizedStatus);
          });
        }

        // Check completion
        if (status.status === 'succeeded' || status.status === 'failed') {
          console.log('[GLOBAL MANAGER] Workflow completed:', status.status);
          completeExecution(status.status);

          // Show notification
          showCompletionNotification(activeExecution.workflowName, status.status === 'succeeded');

          // Clear polling
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          if (safetyTimeoutRef.current) {
            clearTimeout(safetyTimeoutRef.current);
            safetyTimeoutRef.current = null;
          }
        }
      } catch (err) {
        console.error('[GLOBAL MANAGER] Polling error:', err);
      }
    };

    // Start polling
    pollingRef.current = setInterval(pollStatus, 500);

    // Initial poll
    pollStatus();

    // Cleanup on unmount or when execution changes
    return () => {
      console.log('[GLOBAL MANAGER] Cleaning up polling');
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      if (safetyTimeoutRef.current) {
        clearTimeout(safetyTimeoutRef.current);
        safetyTimeoutRef.current = null;
      }
    };
  }, [activeExecution?.runId, activeExecution?.status, updateNodeState, completeExecution]);

  // WebSocket connection
  useEffect(() => {
    if (!activeExecution || activeExecution.status !== 'running') {
      // Close WebSocket if no active execution
      if (wsRef.current) {
        console.log('[GLOBAL MANAGER] Closing WebSocket');
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    let isMounted = true;

    const connectWs = async () => {
      try {
        const token = await getToken();
        if (!token || !isMounted) {
          console.warn('[GLOBAL MANAGER] No auth token or unmounted');
          return;
        }

        console.log('[GLOBAL MANAGER] Connecting WebSocket for run:', activeExecution.runId);

        const ws = connectWorkflow(activeExecution.runId, token, (event: WorkflowEvent) => {
          if (!isMounted) return; // Ignore events after unmount
          if (event.node_id && event.status) {
            const normalizedStatus = event.status === 'started' ? 'running' : event.status;
            updateNodeState(event.node_id, normalizedStatus as any);
          }
        });

        if (ws && isMounted) {
          wsRef.current = ws;
        } else if (ws && !isMounted) {
          // Clean up connection made after unmount
          ws.close();
        }
      } catch (err) {
        console.error('[GLOBAL MANAGER] WebSocket connection error:', err);
      }
    };

    connectWs();

    // Cleanup
    return () => {
      isMounted = false;
      if (wsRef.current) {
        console.log('[GLOBAL MANAGER] Cleaning up WebSocket');
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [activeExecution?.runId, activeExecution?.status, getToken, updateNodeState]);
}

/**
 * Show browser notification when workflow completes
 */
function showCompletionNotification(workflowName: string, success: boolean) {
  console.log('[NOTIFICATION] Showing completion notification:', { workflowName, success });

  // Browser notification
  if ('Notification' in window) {
    console.log('[NOTIFICATION] Browser notification permission:', Notification.permission);

    if (Notification.permission === 'granted') {
      try {
        new Notification(
          success ? 'Workflow Complete ✅' : 'Workflow Failed ❌',
          {
            body: `${workflowName} ${success ? 'finished successfully' : 'encountered an error'}`,
            icon: '/favicon.ico',
            tag: `workflow-${workflowName}`,
            requireInteraction: false,
          },
        );
        console.log('[NOTIFICATION] Browser notification sent');
      } catch (err) {
        console.warn('[NOTIFICATION] Failed to show browser notification:', err);
      }
    }
  }

  // Toast notification using sonner
  const message = success
    ? `🎉 Workflow Complete! ${workflowName} finished successfully`
    : `❌ Workflow Failed: ${workflowName} encountered an error`;

  if (success) {
    toast.success(message, {
      duration: 10000,
      position: 'top-right',
    });
  } else {
    toast.error(message, {
      duration: 10000,
      position: 'top-right',
    });
  }

  console.log('[NOTIFICATION] Toast notification sent:', message);
}
