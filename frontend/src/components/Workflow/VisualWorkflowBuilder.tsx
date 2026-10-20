import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  useReactFlow,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './palantir.css';
import toast from 'react-hot-toast';
import { formatDistanceToNow } from 'date-fns';
import { useWorkflowExecution } from '@stores/workflowExecutionStore';

import { WorkflowHeader } from './WorkflowHeader';
import { WorkflowCanvas } from './WorkflowCanvas';
import { WorkflowAIAssistant } from './WorkflowAIAssistant';
import { NodeConfigModal } from './NodeConfigModal';
import { DatasetConfigModal } from './DatasetConfigModal';
import { OutputConfigModal } from './OutputConfigModal';
import { RunHistoryModal } from './RunHistoryModal';
import { workflowApi } from '@/services/api';
// Removed: useAuth, connectWorkflow, ContentRenderer - no longer needed
import type {
  WorkflowResponse,
  SimplifiedWorkflow,
  InputNode as InputNodeType,
  AgentNode as AgentNodeType,
  OutputNode as OutputNodeType,
  InputNodeType as InputTypeEnum,
  AgentNodeType as AgentTypeEnum,
  OutputNodeType as OutputTypeEnum,
} from '@/types/workflow';
import { WorkflowResults } from './WorkflowResults';

// ===== TYPE MAPPINGS FOR SIMPLIFIED WORKFLOW =====

// Agent display label → backend AgentNodeType enum
const AGENT_LABEL_TO_TYPE: Record<string, AgentTypeEnum> = {
  'Risk Specialist': 'risk_specialist',
  'Generalist': 'generalist',
  'Document Analyst': 'document_analyst',
  'Comparable Companies': 'comparable_companies',
  'Chart Analyst': 'chart_analyst',
  'Quant Coding': 'quant_coding',
  'Alternatives Coding': 'alternatives_coding',
  'Institutional Activity': 'institutional_activity',
  'DCF Agent': 'dcf_agent',
  'Options Coding': 'options_coding',
  'Prediction Markets': 'prediction_markets',
};

// Reverse mapping: backend enum → display label
const AGENT_TYPE_TO_LABEL: Record<AgentTypeEnum, string> = Object.entries(AGENT_LABEL_TO_TYPE)
  .reduce((acc, [label, type]) => ({ ...acc, [type]: label }), {} as Record<AgentTypeEnum, string>);

// Input source → backend InputNodeType
const INPUT_SOURCE_TO_TYPE: Record<string, InputTypeEnum> = {
  'portfolio': 'portfolio',
  'upload': 'uploaded_file',
  'uploaded_file': 'uploaded_file',
  'external_data': 'external_data',
  'prompt': 'prompt',
};

// Output format → backend OutputNodeType
const OUTPUT_FORMAT_TO_TYPE: Record<string, OutputTypeEnum> = {
  'chart': 'text',
  'table': 'text',
  'document': 'pdf',
  'pdf': 'pdf',
  'presentation': 'presentation',
  'text': 'text',
};

// Empty canvas for new workflows - users build from scratch
const initialNodes: Node[] = [];
const initialEdges: Edge[] = [];

// Main workflow builder component
function WorkflowBuilder({
  onClose,
  workflowId,
  onMinimize,
}: {
  onClose?: () => void;
  workflowId?: string | null;
  onMinimize?: () => void; // Updated signature - no arguments needed
}) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [showAI, setShowAI] = useState(false);
  const [configuringNode, setConfiguringNode] = useState<Node | null>(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [showDatasetModal, setShowDatasetModal] = useState(false);
  const [showOutputModal, setShowOutputModal] = useState(false);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { project, getNodes, getEdges } = useReactFlow();
  const idRef = useRef(6);

  // Use global execution store instead of local state
  const { activeExecution, nodeStates, startExecution } = useWorkflowExecution();

  // Workflow API state
  const [currentWorkflowId, setCurrentWorkflowId] = useState<string | null>(null);
  const [workflowName, setWorkflowName] = useState('Pipeline Builder AI');
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isValidating, setIsValidating] = useState(false);

  // Deployment state now managed by global store (activeExecution)
  // Removed: isDeploying, deploymentRunId, pollingIntervalRef, safetyTimeoutRef

  // History management for undo/redo
  const [history, setHistory] = useState<Array<{ nodes: Node[], edges: Edge[] }>>([
    { nodes: initialNodes, edges: initialEdges },
  ]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const maxHistorySize = 50;

  const getId = () => `node_${idRef.current++}`;

  // Sync global store's nodeStates to local ReactFlow nodes for visual feedback
  // Always sync regardless of Map size to ensure state changes are reflected
  useEffect(() => {
    console.log('[WORKFLOW BUILDER] Syncing node states from global store');
    setNodes(currentNodes =>
      currentNodes.map(node => {
        const storeState = nodeStates.get(node.id);
        if (storeState) {
          return {
            ...node,
            data: { ...node.data, executionStatus: storeState.status },
          };
        }
        return node;
      }),
    );
  }, [nodeStates, setNodes]);

  // Watch for workflow completion and fetch results
  useEffect(() => {
    const fetchResults = async () => {
      if (activeExecution?.status === 'succeeded' && activeExecution.runId) {
        try {
          console.log('[WORKFLOW BUILDER] Fetching results for completed workflow:', activeExecution.runId);
          const status = await workflowApi.getRunStatus(activeExecution.runId);

          if (status.summary || status.output_data) {
            const results = status.summary || status.output_data;
            setWorkflowResults(results);
            setActiveTab('results');
            console.log('[WORKFLOW BUILDER] Results loaded and switched to results tab');
          } else {
            console.warn('[WORKFLOW BUILDER] No summary or output_data in status:', status);
          }
        } catch (err) {
          console.error('[WORKFLOW BUILDER] Failed to fetch results:', err);
        }
      }
    };

    fetchResults();
  }, [activeExecution?.status, activeExecution?.runId]);

  // Request notification permission on mount with prominent UI
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      // Show prominent toast asking for permission
      toast((t) => (
        <div style={{ textAlign: 'left' }}>
          <p style={{ fontWeight: '600', marginBottom: '4px', fontSize: '15px' }}>
            <span style={{ marginRight: '6px' }}>🔔</span>
            Enable workflow notifications?
          </p>
          <p style={{ fontSize: '13px', color: '#666', marginBottom: '12px' }}>
            Get notified when workflows complete
          </p>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => {
                Notification.requestPermission().then(permission => {
                  console.log('[NOTIFICATION] Permission:', permission);
                  toast.dismiss(t.id);
                  if (permission === 'granted') {
                    toast.success('Notifications enabled!', { icon: '✅', duration: 3000 });
                  }
                });
              }}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                background: '#3b82f6',
                color: 'white',
                border: 'none',
                cursor: 'pointer',
                fontWeight: '500',
                fontSize: '13px',
              }}
            >
              Enable
            </button>
            <button
              onClick={() => {
                toast.dismiss(t.id);
                toast('Using toast notifications only', { icon: 'ℹ️', duration: 3000 });
              }}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                background: '#e5e7eb',
                color: '#374151',
                border: 'none',
                cursor: 'pointer',
                fontWeight: '500',
                fontSize: '13px',
              }}
            >
              Skip
            </button>
          </div>
        </div>
      ), {
        duration: 15000,
        position: 'top-center',
        style: {
          background: 'white',
          padding: '16px',
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        },
      });
    }
  }, []);

  // NEW: Convert ReactFlow to SimplifiedWorkflow format
  const reactFlowToSimplified = useCallback((nodes: Node[], edges: Edge[]): SimplifiedWorkflow => {
    // Find input node (dataset)
    const inputNode = nodes.find(n => n.type === 'dataset');
    if (!inputNode) {
      throw new Error('Workflow must have exactly one input node');
    }

    // Find output node
    const outputNode = nodes.find(n => n.type === 'output');
    if (!outputNode) {
      throw new Error('Workflow must have exactly one output node');
    }

    // Find all agent nodes and order them by following edges
    const agentNodes = nodes.filter(n => n.type === 'agent');
    if (agentNodes.length === 0) {
      throw new Error('Workflow must have at least one agent node');
    }

    // Order agents by edges (simple sequential order for now)
    const orderedAgents: Node[] = [];
    let currentId = inputNode.id;

    while (orderedAgents.length < agentNodes.length) {
      const nextEdge = edges.find(e => e.source === currentId && agentNodes.some(a => a.id === e.target));
      if (!nextEdge) break;

      const nextAgent = agentNodes.find(a => a.id === nextEdge.target);
      if (nextAgent && !orderedAgents.includes(nextAgent)) {
        orderedAgents.push(nextAgent);
        currentId = nextAgent.id;
      } else {
        break;
      }
    }

    // Convert input node
    const config = inputNode.data.configuration || {};
    const inputType = INPUT_SOURCE_TO_TYPE[config.inputType || config.source || 'portfolio'] || 'portfolio';

    const simplifiedInput: InputNodeType = {
      id: inputNode.id,
      type: inputType as InputTypeEnum,
      portfolio_id: config.portfolio_id || null,
      file_id: config.file_id || null,
      prompt_text: config.prompt_text || null,
      external_source: config.external_source || null,
    };

    // Convert agent nodes
    const simplifiedAgents: AgentNodeType[] = orderedAgents.map(agent => {
      // Try agentType field first, then fallback to label lookup
      const agentType = agent.data.agentType || AGENT_LABEL_TO_TYPE[agent.data.label] || 'generalist';
      const customPrompt = agent.data.configuration?.prompt || agent.data.configuration?.customPrompt ||
                          `Analyze using ${agent.data.label}`;

      return {
        id: agent.id,
        agent_type: agentType as AgentTypeEnum,
        custom_prompt: customPrompt,
      };
    });

    // Convert output node
    const outputConfig = outputNode.data.configuration || {};
    const outputType = OUTPUT_FORMAT_TO_TYPE[outputConfig.format || outputNode.data.format || 'text'] || 'text';

    const simplifiedOutput: OutputNodeType = {
      id: outputNode.id,
      type: outputType as OutputTypeEnum,
      title: outputNode.data.label || 'Workflow Result',
      include_charts: outputConfig.include_charts !== false,
    };

    return {
      input_node: simplifiedInput,
      agent_nodes: simplifiedAgents,
      output_node: simplifiedOutput,
    };
  }, []);

  // NEW: Convert SimplifiedWorkflow to ReactFlow format
  const simplifiedToReactFlow = useCallback((simplified: SimplifiedWorkflow) => {
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];
    let xPos = 200;
    const yPos = 250;

    // Create input node
    const inputConfig: any = {
      inputType: simplified.input_node.type,
      portfolio_id: simplified.input_node.portfolio_id,
      file_id: simplified.input_node.file_id,
      prompt_text: simplified.input_node.prompt_text,
      external_source: simplified.input_node.external_source,
    };

    newNodes.push({
      id: simplified.input_node.id,
      type: 'dataset',
      position: { x: xPos, y: yPos },
      data: {
        label: 'Input Data',
        configuration: inputConfig,
      },
    });

    let previousId = simplified.input_node.id;
    xPos += 300;

    // Create agent nodes
    simplified.agent_nodes.forEach((agent, idx) => {
      const agentLabel = AGENT_TYPE_TO_LABEL[agent.agent_type] || 'Agent';

      newNodes.push({
        id: agent.id,
        type: 'agent',
        position: { x: xPos, y: yPos },
        data: {
          label: agentLabel,
          agentType: agent.agent_type,  // Preserve agent type from database
          configuration: {
            prompt: agent.custom_prompt,
            customPrompt: agent.custom_prompt,
          },
        },
      });

      // Connect to previous node
      newEdges.push({
        id: `e${previousId}-${agent.id}`,
        source: previousId,
        target: agent.id,
        type: 'smoothstep',
      });

      previousId = agent.id;
      xPos += 300;
    });

    // Create output node
    newNodes.push({
      id: simplified.output_node.id,
      type: 'output',
      position: { x: xPos, y: yPos },
      data: {
        label: simplified.output_node.title || 'Output',
        format: simplified.output_node.type,
        configuration: {
          format: simplified.output_node.type,
          include_charts: simplified.output_node.include_charts,
        },
      },
    });

    // Connect last agent to output
    newEdges.push({
      id: `e${previousId}-${simplified.output_node.id}`,
      source: previousId,
      target: simplified.output_node.id,
      type: 'smoothstep',
    });

    return { nodes: newNodes, edges: newEdges };
  }, []);

  // OLD: Legacy converter (keep for backward compatibility during migration)
  const reactFlowToApi = useCallback((nodes: Node[], edges: Edge[]) => ({
    nodes: nodes.map(n => ({
      id: n.id,
      type: n.type?.toLowerCase() as 'dataset' | 'agent' | 'output',
      position: { x: n.position.x, y: n.position.y },
      data: {
        label: n.data.label || '',
        configuration: n.data.configuration || {},
        // Pull source from configuration for dataset nodes
        ...(n.type === 'dataset' && { source: n.data.configuration?.source || n.data.source || 'portfolio' }),
        ...(n.type === 'agent' && {
          ...(n.data.toolMode && { toolMode: n.data.toolMode }),
          ...(n.data.selectedTools && { selectedTools: n.data.selectedTools }),
        }),
        ...(n.type === 'output' && n.data.format && { format: n.data.format }),
      },
    })),
    edges: edges.map(e => ({
      id: e.id,
      source: e.source,
      target: e.target,
    })),
  }), []);

  // State for workflow results display
  const [workflowResults, setWorkflowResults] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<string>('graph');

  // PR3b: Run history refresh trigger
  const [historyRefreshTrigger] = useState(0);

  // Handle tab changes
  const handleTabChange = useCallback((tab: string) => {
    setActiveTab(tab);
    // History tab will show inline content based on currentWorkflowId
    if (tab === 'history' && !currentWorkflowId) {
      toast('Save your workflow first to see run history', { icon: 'ℹ️' });
    }
  }, [currentWorkflowId]);

  // Load workflow if workflowId is provided, or reset to initial state for new workflow
  useEffect(() => {
    if (workflowId) {
      const loadWorkflow = async () => {
        try {
          const workflow = await workflowApi.get(workflowId);
          if (workflow) {
            setWorkflowName(workflow.name || 'Pipeline Builder AI');
            setCurrentWorkflowId(workflowId);

            let reactFlowNodes, reactFlowEdges;

            // Check if it's SimplifiedWorkflow format (new)
            if (workflow.simplified_workflow) {
              const { nodes, edges } = simplifiedToReactFlow(workflow.simplified_workflow);
              reactFlowNodes = nodes;
              reactFlowEdges = edges;
            } else {
              // Legacy format - fallback for old workflows
              let flowNodes, flowEdges;

              // Handle both raw data and pre-parsed data
              if (typeof workflow.nodes === 'string') {
                flowNodes = JSON.parse(workflow.nodes);
              } else {
                flowNodes = workflow.nodes;
              }

              if (typeof workflow.edges === 'string') {
                flowEdges = JSON.parse(workflow.edges);
              } else {
                flowEdges = workflow.edges;
              }

              // Convert to ReactFlow format
              reactFlowNodes = flowNodes.map((n: any) => ({
                id: n.id,
                type: n.type,
                position: n.position,
                data: n.data || {},
              }));

              reactFlowEdges = flowEdges.map((e: any) => ({
                id: e.id,
                source: e.source,
                target: e.target,
                type: 'smoothstep',
                animated: false,
                style: { stroke: '#C8C6C4', strokeWidth: 1.5 },
              }));
            }

            // Update the nodes and edges
            setNodes(reactFlowNodes);
            setEdges(reactFlowEdges);

            // Update history after setting nodes and edges
            setHistory([{ nodes: reactFlowNodes, edges: reactFlowEdges }]);
            setHistoryIndex(0);

            // Auto-load most recent completed run results
            try {
              const runsResponse = await workflowApi.listRuns(workflowId, 1);
              const lastRun = runsResponse?.[0]; // Response is array, not { runs: [] }

              if (lastRun && lastRun.status === 'succeeded' && lastRun.output_data) {
                setWorkflowResults(lastRun.output_data); // Field is output_data, not summary
                // deploymentRunId no longer tracked locally - managed by global store
                setActiveTab('results'); // Auto-switch to results tab when loading from history
                toast.success(`Loaded results from ${formatDistanceToNow(new Date(lastRun.completed_at), { addSuffix: true })}`);
              }
            } catch (err) {
              // Silently fail - not critical, user can still manually view runs
              console.warn('Failed to auto-load last run:', err);
            }
          }
        } catch (err) {
          console.error('Failed to load workflow:', err);
          toast.error('Failed to load workflow');
        }
      };

      loadWorkflow();
    } else {
      // Reset to initial state for new workflow
      setWorkflowName('Pipeline Builder AI');
      setCurrentWorkflowId(null);
      setNodes(initialNodes);
      setEdges(initialEdges);
      setHistory([{ nodes: initialNodes, edges: initialEdges }]);
      setHistoryIndex(0);
    }
  }, [workflowId, setNodes, setEdges, simplifiedToReactFlow]);

  const apiToReactFlow = useCallback((apiData: any) => ({
    nodes: apiData.nodes.map((n: any) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: n.data,
    })),
    edges: apiData.edges.map((e: any) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
    })),
  }), []);

  // Load workflow list on mount
  useEffect(() => {
    workflowApi.list(true).then(res => {
      setWorkflows(res.workflows);
    }).catch(err => {
      console.error('Failed to load workflows:', err);
    });
  }, []);

  // Handle save/update
  const handleSave = useCallback(async () => {
    if (isSaving) return;

    setIsSaving(true);
    setSaveSuccess(false);
    try {
      // Validate input node is configured
      const inputNode = nodes.find(n => n.type === 'dataset');
      if (inputNode && !inputNode.data.configuration) {
        toast.error('Please configure the input node before saving');
        setIsSaving(false);
        return;
      }
      if (inputNode?.data.configuration) {
        const cfg = inputNode.data.configuration;
        if (cfg.inputType === 'portfolio' && !cfg.portfolio_id) {
          toast.error('Please select a portfolio in the input node configuration');
          setIsSaving(false);
          return;
        }
      }

      // Convert to SimplifiedWorkflow format
      const simplified_workflow = reactFlowToSimplified(nodes, edges);

      const data = {
        name: workflowName,
        simplified_workflow,
      };

      if (currentWorkflowId) {
        await workflowApi.update(currentWorkflowId, data);
        toast.success('Workflow updated');
      } else {
        const result = await workflowApi.create(data);
        setCurrentWorkflowId(result.id);
        toast.success('Workflow created');
        // Refresh list
        const updatedList = await workflowApi.list(true);
        setWorkflows(updatedList.workflows);
      }

      // Show success state
      setSaveSuccess(true);

      // Reset success state after animation
      setTimeout(() => {
        setSaveSuccess(false);
      }, 2000);

    } catch (err: any) {
      // Handle Error objects from axios interceptor first
      if (err.message) {
        toast.error(err.message);
      } else if (err.detail) {
        // Fallback for direct API errors
        if (err.detail.message) {
          toast.error(err.detail.message);
        }
        if (err.detail.errors && Array.isArray(err.detail.errors)) {
          err.detail.errors.forEach((e: string) => toast.error(e));
        }
      } else {
        toast.error('Failed to save workflow');
      }
    } finally {
      setIsSaving(false);
    }
  }, [isSaving, workflowName, currentWorkflowId, nodes, edges, reactFlowToSimplified]);

  // Handle load
  const handleLoad = useCallback(async (id: string) => {
    try {
      const fullData = await workflowApi.get(id);
      setCurrentWorkflowId(id);
      setWorkflowName(fullData.name);
      const { nodes: newNodes, edges: newEdges } = apiToReactFlow(fullData);
      setNodes(newNodes);
      setEdges(newEdges);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load workflow');
    }
  }, [apiToReactFlow, setNodes, setEdges]);

  // Handle validation
  const handleValidate = useCallback(async () => {
    if (isValidating) return;

    setIsValidating(true);
    try {
      let result;
      if (currentWorkflowId) {
        result = await workflowApi.validateExisting(currentWorkflowId);
      } else {
        // Use SimplifiedWorkflow format for validation
        const simplified_workflow = reactFlowToSimplified(nodes, edges);
        result = await workflowApi.validate({ simplified_workflow });
      }

      if (result.is_valid) {
        toast.success('Workflow is valid');
      } else {
        if (result.errors && Array.isArray(result.errors)) {
          result.errors.forEach((e: string) => toast.error(e));
        }
        if (result.warnings && Array.isArray(result.warnings)) {
          result.warnings.forEach((w: string) => toast(w, { icon: '⚠️' }));
        }
      }
    } catch (err: any) {
      // Handle Error objects from axios interceptor first
      if (err.message) {
        toast.error(err.message);
      } else if (err.detail) {
        // Fallback for direct API errors
        if (err.detail.message) {
          toast.error(err.detail.message);
        }
        if (err.detail.errors && Array.isArray(err.detail.errors)) {
          err.detail.errors.forEach((e: string) => toast.error(e));
        }
      } else {
        toast.error('Validation failed');
      }
    } finally {
      setIsValidating(false);
    }
  }, [isValidating, currentWorkflowId, nodes, edges, reactFlowToSimplified]);

  // Save current state to history
  const saveToHistory = useCallback((newNodes: Node[], newEdges: Edge[]) => {
    setHistory(prevHistory => {
      const newHistory = prevHistory.slice(0, historyIndex + 1);
      newHistory.push({ nodes: newNodes, edges: newEdges });

      // Limit history size
      if (newHistory.length > maxHistorySize) {
        newHistory.shift();
        return newHistory;
      }

      setHistoryIndex(prev => prev + 1);
      return newHistory;
    });
  }, [historyIndex]);

  // Undo handler
  const handleUndo = useCallback(() => {
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      const { nodes: prevNodes, edges: prevEdges } = history[newIndex];
      setNodes(prevNodes);
      setEdges(prevEdges);
      setHistoryIndex(newIndex);
    }
  }, [historyIndex, history, setNodes, setEdges]);

  // Redo handler
  const handleRedo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      const { nodes: nextNodes, edges: nextEdges } = history[newIndex];
      setNodes(nextNodes);
      setEdges(nextEdges);
      setHistoryIndex(newIndex);
    }
  }, [historyIndex, history, setNodes, setEdges]);

  // Clear all nodes and edges
  const handleClearAll = useCallback(() => {
    setNodes([]);
    setEdges([]);
    saveToHistory([], []);
  }, [setNodes, setEdges, saveToHistory]);

  // Handle delete
  const handleDelete = useCallback(async () => {
    if (!currentWorkflowId) {
      toast.error('No workflow loaded to delete');
      return;
    }

    if (!confirm('Are you sure you want to delete this workflow? This action cannot be undone.')) {
      return;
    }

    try {
      await workflowApi.delete(currentWorkflowId);
      toast.success('Workflow deleted successfully');

      // Clean up state after successful deletion
      setCurrentWorkflowId(null);
      setWorkflowName('Pipeline Builder AI');
      setNodes(initialNodes);
      setEdges(initialEdges);
      saveToHistory(initialNodes, initialEdges);

      // Optionally close the builder
      if (onClose) {
        setTimeout(() => onClose(), 1000); // Give time for toast to show
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete workflow');
    }
  }, [currentWorkflowId, onClose, setNodes, setEdges, saveToHistory]);

  // Handle minimize - notify parent to hide builder while workflow continues running
  const handleMinimize = useCallback(() => {
    if (onMinimize) {
      onMinimize(); // Call with no arguments - store manages all state
      toast.success('Workflow minimized - running in background', {
        icon: '📦',
        duration: 4000,
      });
    }
  }, [onMinimize]);

  // Run workflow - global manager handles polling, WebSocket, and notifications
  const handleRun = useCallback(async () => {
    if (activeExecution?.status === 'running') {
      toast('Workflow is already running', { icon: '⚠️' });
      return;
    }

    if (!currentWorkflowId) {
      // Save first if needed
      await handleSave();
      if (!currentWorkflowId) {
        toast.error('Failed to save workflow before running');
        return;
      }
    }

    // Clear results from previous run
    setWorkflowResults(null);

    // Initialize node execution states for immediate visual feedback
    // Agent nodes start as 'queued' so spinning indicators appear right away
    // Other nodes (input/output) remain undefined
    setNodes(currentNodes =>
      currentNodes.map(node => ({
        ...node,
        data: {
          ...node.data,
          executionStatus: node.type === 'agent' ? 'queued' : undefined,
        },
      })),
    );

    try {
      // Start workflow execution via API
      const runData = await workflowApi.run(currentWorkflowId);
      const runId = runData.run_id;

      console.log('[WORKFLOW BUILDER] Starting execution:', { runId, currentWorkflowId, workflowName });

      // Initialize global execution state - global manager will handle polling/WebSocket
      startExecution(runId, currentWorkflowId, workflowName);

      toast.success(`Workflow started: ${runId}`);

    } catch (err: any) {
      toast.error(err.message || 'Failed to run workflow');
    }
  }, [currentWorkflowId, workflowName, activeExecution, handleSave, startExecution, setNodes]);

  // Polling, WebSocket, and notifications now handled by global manager in App.tsx
  // Global sync effect above applies nodeStates from store to local ReactFlow nodes

  // Reset to initial state
  const handleReset = useCallback(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    saveToHistory(initialNodes, initialEdges);
  }, [setNodes, setEdges, saveToHistory]);

  // Validate connections: Dataset → Agent, Agent → Agent, Agent → Output
  // Note: This is currently not used by WorkflowCanvas but kept for future use
  // @ts-ignore - Kept for future use
  const _isValidConnection = useCallback((connection: Connection) => {
    const source = nodes.find(n => n.id === connection.source);
    const target = nodes.find(n => n.id === connection.target);

    if (!source || !target) return false;

    // Valid connections:
    // Dataset -> Agent
    if (source.type === 'dataset' && target.type === 'agent') return true;
    // Agent -> Agent (chaining)
    if (source.type === 'agent' && target.type === 'agent') return true;
    // Agent -> Output
    if (source.type === 'agent' && target.type === 'output') return true;

    return false;
  }, [nodes]);

  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => {
      const newEdges = addEdge({
        ...params,
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#C8C6C4', strokeWidth: 1.5 },
      }, eds);
      saveToHistory(nodes, newEdges);
      return newEdges;
    });
  }, [setEdges, nodes, saveToHistory]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onNodeDoubleClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setConfiguringNode(node);
    if (node.type === 'agent') {
      setShowConfigModal(true);
    } else if (node.type === 'dataset') {
      setShowDatasetModal(true);
    } else if (node.type === 'output') {
      setShowOutputModal(true);
    }
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const deleteNode = useCallback(() => {
    if (!selectedNode) return;
    const newNodes = nodes.filter(n => n.id !== selectedNode.id);
    const newEdges = edges.filter(e => e.source !== selectedNode.id && e.target !== selectedNode.id);
    setNodes(newNodes);
    setEdges(newEdges);
    setSelectedNode(null);
    saveToHistory(newNodes, newEdges);
  }, [selectedNode, nodes, edges, setNodes, setEdges, saveToHistory]);

  const addDatasetNode = useCallback((type: string, label: string) => {
    const newNode: Node = {
      id: getId(),
      type: 'dataset',
      position: project({ x: 250, y: 250 }),
      data: {
        label,
        inputType: type === 'upload' ? 'uploaded_file' : type,
      },
    };
    const newNodes = [...nodes, newNode];
    setNodes(newNodes);
    saveToHistory(newNodes, edges);
  }, [project, nodes, edges, setNodes, saveToHistory]);

  const addAgentNode = useCallback((label: string, operation: string, color: string) => {
    const newNode: Node = {
      id: getId(),
      type: 'agent',
      position: project({ x: 450, y: 250 }),
      data: {
        label,
        agentType: label.toLowerCase().replace(/ /g, '_'),
        operation,
        color,
      },
    };
    const newNodes = [...nodes, newNode];
    setNodes(newNodes);
    saveToHistory(newNodes, edges);
  }, [project, nodes, edges, setNodes, saveToHistory]);

  const addOutputNode = useCallback((label: string, format: string) => {
    const newNode: Node = {
      id: getId(),
      type: 'output',
      position: project({ x: 650, y: 250 }),
      data: { label, format },
    };
    const newNodes = [...nodes, newNode];
    setNodes(newNodes);
    saveToHistory(newNodes, edges);
  }, [project, nodes, edges, setNodes, saveToHistory]);

  const applyAIWorkflow = useCallback((newNodes: Node[], newEdges: Edge[]) => {
    const combinedNodes = [...nodes, ...newNodes];
    const combinedEdges = [...edges, ...newEdges];
    setNodes(combinedNodes);
    setEdges(combinedEdges);
    saveToHistory(combinedNodes, combinedEdges);
  }, [nodes, edges, setNodes, setEdges, saveToHistory]);

  const handleNodeConfigSave = useCallback((nodeId: string, configuration: any) => {
    const updatedNodes = nodes.map(node => {
      if (node.id === nodeId) {
        return {
          ...node,
          data: {
            ...node.data,
            configuration,
          },
        };
      }
      return node;
    });
    setNodes(updatedNodes);
    saveToHistory(updatedNodes, edges);
    setShowConfigModal(false);
    setConfiguringNode(null);
  }, [nodes, edges, setNodes, saveToHistory]);

  // Wrapped handlers for ReactFlow that save history
  const handleNodesChange = useCallback((changes: any) => {
    onNodesChange(changes);

    // Debounce saving history for drag operations
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(() => {
      // Only save if it's a position change (dragging)
      const hasPositionChange = changes.some((change: any) => change.type === 'position');
      if (hasPositionChange) {
        saveToHistory(getNodes(), getEdges());
      }
    }, 500); // Save history 500ms after dragging stops
  }, [onNodesChange, getNodes, getEdges, saveToHistory]);

  const handleEdgesChange = useCallback((changes: any) => {
    onEdgesChange(changes);
    // Save history immediately for edge changes (less frequent)
    saveToHistory(getNodes(), getEdges());
  }, [onEdgesChange, getNodes, getEdges, saveToHistory]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Undo: Ctrl+Z or Cmd+Z
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        handleUndo();
      }
      // Redo: Ctrl+Y or Ctrl+Shift+Z or Cmd+Shift+Z
      else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        handleRedo();
      }
      // Delete selected node
      else if (e.key === 'Delete' && selectedNode) {
        deleteNode();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [handleUndo, handleRedo, selectedNode, deleteNode]);

  // Cleanup now handled by global manager - no local refs to clean up


  return (
    <>
      {/* Minimized indicator removed - now managed by parent component */}

      {/* Main workflow builder content - always rendered, parent controls visibility with CSS */}
      <div className="workflow-builder">
          <WorkflowHeader
        onClose={onClose}
        onUndo={handleUndo}
        onRedo={handleRedo}
        canUndo={historyIndex > 0}
        canRedo={historyIndex < history.length - 1}
        onClearAll={handleClearAll}
        onReset={handleReset}
        onSave={handleSave}
        onValidate={handleValidate}
        onLoad={handleLoad}
        onDelete={handleDelete}
        onDeploy={handleRun}
        onMinimize={handleMinimize}
        onViewResults={() => setActiveTab('results')}
        isSaving={isSaving}
        saveSuccess={saveSuccess}
        isValidating={isValidating}
        isDeploying={activeExecution?.status === 'running'}
        workflows={workflows}
        workflowName={workflowName}
        onWorkflowNameChange={setWorkflowName}
        hasResults={!!workflowResults}
        activeTab={activeTab}
        onTabChange={handleTabChange}
      />

      {/* Tab Content */}
      {activeTab === 'graph' && (
        <WorkflowCanvas
          ref={reactFlowWrapper}
          nodes={nodes}
          edges={edges}
          selectedNode={selectedNode}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onNodeDoubleClick={onNodeDoubleClick}
          onPaneClick={onPaneClick}
          onDeleteNode={deleteNode}
          onAddAgent={addAgentNode}
          onAddDataset={addDatasetNode}
          onAddOutput={addOutputNode}
          selectMode={selectMode}
          onSelectModeChange={setSelectMode}
          onToggleAI={() => setShowAI(!showAI)}
        />
      )}

      {activeTab === 'proposals' && (
        <div className="tab-content">
          <div className="tab-content-placeholder">
            <h2>Proposals</h2>
            <p>Workflow proposals will be displayed here.</p>
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <div className="tab-content">
          {currentWorkflowId ? (
            <RunHistoryModal
              isOpen={true}
              onClose={() => setActiveTab('graph')}
              workflowId={currentWorkflowId}
              workflowName={workflowName}
              refreshTrigger={historyRefreshTrigger}
            />
          ) : (
            <div className="tab-content-placeholder">
              <h2>History</h2>
              <p>Save your workflow first to see run history.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'results' && (
        <div className="tab-content" style={{ padding: '20px' }}>
          <WorkflowResults results={workflowResults} />
        </div>
      )}

      <WorkflowAIAssistant
        isOpen={showAI}
        onClose={() => setShowAI(false)}
        nodes={nodes}
        edges={edges}
        onApplyWorkflow={applyAIWorkflow}
      />

      {/* Node Configuration Modals */}
      {configuringNode && configuringNode.type === 'agent' && (
        <NodeConfigModal
          node={configuringNode}
          isOpen={showConfigModal}
          onClose={() => {
            setShowConfigModal(false);
            setConfiguringNode(null);
          }}
          onSave={handleNodeConfigSave}
        />
      )}
      {configuringNode && configuringNode.type === 'dataset' && (
        <DatasetConfigModal
          node={configuringNode}
          isOpen={showDatasetModal}
          onClose={() => {
            setShowDatasetModal(false);
            setConfiguringNode(null);
          }}
          onSave={handleNodeConfigSave}
        />
      )}
      {configuringNode && configuringNode.type === 'output' && (
        <OutputConfigModal
          node={configuringNode}
          isOpen={showOutputModal}
          onClose={() => {
            setShowOutputModal(false);
            setConfiguringNode(null);
          }}
          onSave={handleNodeConfigSave}
        />
      )}

      {/* Status Bar */}
      <div className="status-bar">
        <div className="status-text">
          {selectedNode ? (
            <>Selected: {selectedNode.data.label}</>
          ) : (
            <>Click a node to select it</>
          )}
        </div>
        <div className="status-text">
          Nodes: {nodes.length} | Edges: {edges.length}
        </div>
      </div>

        </div>
    </>
  );
}

// Export with provider wrapper
export function VisualWorkflowBuilder({
  onClose,
  workflowId,
  onMinimize,
}: {
  onClose?: () => void;
  workflowId?: string | null;
  onMinimize?: () => void; // Updated to match new signature
}) {
  return (
    <ReactFlowProvider>
      <WorkflowBuilder onClose={onClose} workflowId={workflowId} onMinimize={onMinimize} />
    </ReactFlowProvider>
  );
}
