import { create } from 'zustand';

interface NodeState {
  status: 'queued' | 'running' | 'succeeded' | 'failed';
}

interface WorkflowExecutionState {
  // Active workflow execution
  activeExecution: {
    runId: string;
    workflowId: string;
    workflowName: string;
    startTime: Date;
    status: 'running' | 'succeeded' | 'failed';
  } | null;

  // UI state
  isMinimized: boolean;
  showBuilder: boolean;
  selectedWorkflowId: string | null;

  // Node states for real-time updates
  nodeStates: Map<string, NodeState>;

  // Actions
  setShowBuilder: (show: boolean, workflowId?: string | null) => void;
  startExecution: (runId: string, workflowId: string, name: string) => void;
  updateNodeState: (nodeId: string, status: NodeState['status']) => void;
  completeExecution: (status: 'succeeded' | 'failed') => void;
  minimize: () => void;
  restore: () => void;
  reset: () => void;
}

export const useWorkflowExecution = create<WorkflowExecutionState>((set, get) => ({
  activeExecution: null,
  isMinimized: false,
  showBuilder: false,
  selectedWorkflowId: null,
  nodeStates: new Map(),

  setShowBuilder: (show, workflowId) => {
    set({ showBuilder: show, selectedWorkflowId: workflowId || null });
  },

  startExecution: (runId, workflowId, name) => {
    console.log('[WORKFLOW STORE] Starting execution:', { runId, workflowId, name });
    set({
      activeExecution: {
        runId,
        workflowId,
        workflowName: name,
        startTime: new Date(),
        status: 'running',
      },
      showBuilder: true,
      selectedWorkflowId: workflowId,
      isMinimized: false,
      nodeStates: new Map(), // Reset node states for new execution
    });
  },

  updateNodeState: (nodeId, status) => {
    set(state => {
      const newStates = new Map(state.nodeStates);
      newStates.set(nodeId, { status });
      return { nodeStates: newStates };
    });
  },

  completeExecution: (status) => {
    console.log('[WORKFLOW STORE] Execution complete:', status);
    set(state => ({
      activeExecution: state.activeExecution ? {
        ...state.activeExecution,
        status,
      } : null,
    }));
  },

  minimize: () => {
    console.log('[WORKFLOW STORE] Minimizing workflow');
    set({ isMinimized: true });
  },

  restore: () => {
    console.log('[WORKFLOW STORE] Restoring workflow');
    set({ isMinimized: false });
  },

  reset: () => {
    console.log('[WORKFLOW STORE] Resetting workflow state');
    set({
      activeExecution: null,
      isMinimized: false,
      showBuilder: false,
      selectedWorkflowId: null,
      nodeStates: new Map(),
    });
  },
}));
