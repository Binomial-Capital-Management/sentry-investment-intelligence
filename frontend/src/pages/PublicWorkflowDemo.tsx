import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import '../components/Workflow/palantir.css';
import toast from 'react-hot-toast';

import { WorkflowHeader } from '../components/Workflow/WorkflowHeader';
import { WorkflowCanvas } from '../components/Workflow/WorkflowCanvas';
import { WorkflowAIAssistant } from '../components/Workflow/WorkflowAIAssistant';
import { nodeTypes } from '../components/Workflow/WorkflowNodes';
import { NodeConfigModal } from '../components/Workflow/NodeConfigModal';
import { DatasetConfigModal } from '../components/Workflow/DatasetConfigModal';
import { OutputConfigModal } from '../components/Workflow/OutputConfigModal';

// Demo nodes - Simple workflow: External Data → Agent 1 → Agent 2 → PDF
// Horizontal: 15% less (400 * 0.85 = 340)
// Vertical: 20% more (100 * 1.2 = 120)
const initialNodes: Node[] = [
  {
    id: 'node_1',
    type: 'input',
    position: { x: 100, y: 300 },
    data: {
      label: 'External Data',
      inputType: 'external_data',
      fileName: 'Q4_2024_Earnings.xlsx',
      configuration: { source: 'OneDrive' },
    },
  },
  {
    id: 'node_2',
    type: 'agent',
    position: { x: 440, y: 420 },
    data: {
      label: 'Document Analyst',
      agentType: 'document_analyst',
      customPrompt: 'Extract key financial metrics from the earnings report including revenue, EBITDA, and growth rates.',
      operation: 'Financial Data Extraction',
      color: '#f59e0b',
    },
  },
  {
    id: 'node_3',
    type: 'agent',
    position: { x: 780, y: 540 },
    data: {
      label: 'Comparable Companies',
      agentType: 'comparable_companies',
      customPrompt: 'Compare valuation multiples (P/E, EV/EBITDA) against industry peers and generate comps table.',
      operation: 'Valuation Analysis',
      color: '#8b5cf6',
    },
  },
  {
    id: 'node_4',
    type: 'output',
    position: { x: 1120, y: 660 },
    data: {
      label: 'Investment Memo',
      format: 'pdf',
      outputType: 'pdf',
      title: 'Q4 2024 Investment Analysis',
      includeCharts: true,
      configuration: { title: 'Q4 2024 Investment Analysis' },
    },
  },
];

const initialEdges: Edge[] = [
  {
    id: 'e1-2',
    source: 'node_1',
    target: 'node_2',
    type: 'smoothstep',
    animated: true,
  },
  {
    id: 'e2-3',
    source: 'node_2',
    target: 'node_3',
    type: 'smoothstep',
    animated: true,
  },
  {
    id: 'e3-4',
    source: 'node_3',
    target: 'node_4',
    type: 'smoothstep',
    animated: true,
  },
];

function WorkflowBuilder() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [showAI, setShowAI] = useState(false);
  const [configuringNode, setConfiguringNode] = useState<Node | null>(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [showDatasetModal, setShowDatasetModal] = useState(false);
  const [showOutputModal, setShowOutputModal] = useState(false);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const idRef = useRef(6);

  const [history, setHistory] = useState<Array<{ nodes: Node[], edges: Edge[] }>>([
    { nodes: initialNodes, edges: initialEdges },
  ]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const maxHistorySize = 50;

  const [workflowName, setWorkflowName] = useState('Portfolio Risk Analysis Demo');
  const [activeTab, setActiveTab] = useState('graph');

  const getId = () => `node_${idRef.current++}`;

  const saveToHistory = useCallback((newNodes: Node[], newEdges: Edge[]) => {
    setHistory(prevHistory => {
      const newHistory = prevHistory.slice(0, historyIndex + 1);
      newHistory.push({ nodes: newNodes, edges: newEdges });

      if (newHistory.length > maxHistorySize) {
        newHistory.shift();
        return newHistory;
      }

      setHistoryIndex(prev => prev + 1);
      return newHistory;
    });
  }, [historyIndex]);

  const handleUndo = useCallback(() => {
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      const { nodes: prevNodes, edges: prevEdges } = history[newIndex];
      setNodes(prevNodes);
      setEdges(prevEdges);
      setHistoryIndex(newIndex);
    }
  }, [historyIndex, history, setNodes, setEdges]);

  const handleRedo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      const { nodes: nextNodes, edges: nextEdges } = history[newIndex];
      setNodes(nextNodes);
      setEdges(nextEdges);
      setHistoryIndex(newIndex);
    }
  }, [historyIndex, history, setNodes, setEdges]);

  const handleClearAll = useCallback(() => {
    setNodes([]);
    setEdges([]);
    saveToHistory([], []);
  }, [setNodes, setEdges, saveToHistory]);

  const handleReset = useCallback(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    saveToHistory(initialNodes, initialEdges);
  }, [setNodes, setEdges, saveToHistory]);

  const handleSave = useCallback(() => {
    toast('Demo Mode - Sign up to save workflows', { icon: '🔒' });
  }, []);

  const handleValidate = useCallback(() => {
    toast('Demo Mode - Sign up to validate workflows', { icon: '🔒' });
  }, []);

  const handleLoad = useCallback(() => {
    toast('Demo Mode - Sign up to load workflows', { icon: '🔒' });
  }, []);

  const handleDelete = useCallback(() => {
    toast('Demo Mode - Sign up to delete workflows', { icon: '🔒' });
  }, []);

  const handleRun = useCallback(() => {
    toast('Demo Mode - Sign up to run workflows', { icon: '🔒' });
  }, []);

  const handleMinimize = useCallback(() => {
    toast('Demo Mode - Sign up to minimize workflows', { icon: '🔒' });
  }, []);

  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => addEdge(params, eds));
  }, [setEdges]);

  const onNodeClick = useCallback((event: any, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onNodeDoubleClick = useCallback((event: any, node: Node) => {
    console.log('Node double-clicked:', node);
    setConfiguringNode(node);
    if (node.type === 'agent') {
      setShowConfigModal(true);
    } else if (node.type === 'input' || node.type === 'dataset') {
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
      type: 'input',
      position: { x: 250, y: 250 },
      data: {
        label,
        inputType: type === 'upload' ? 'uploaded_file' : type,
      },
    };
    const newNodes = [...nodes, newNode];
    setNodes(newNodes);
    saveToHistory(newNodes, edges);
  }, [nodes, edges, setNodes, saveToHistory]);

  const addAgentNode = useCallback((label: string, operation: string, color: string) => {
    const newNode: Node = {
      id: getId(),
      type: 'agent',
      position: { x: 450, y: 250 },
      data: {
        label,
        agentType: label.toLowerCase().replace(/ /g, '_'),
        customPrompt: '',
        operation,
        color,
      },
    };
    const newNodes = [...nodes, newNode];
    setNodes(newNodes);
    saveToHistory(newNodes, edges);
  }, [nodes, edges, setNodes, saveToHistory]);

  const addOutputNode = useCallback((label: string, format: string) => {
    const newNode: Node = {
      id: getId(),
      type: 'output',
      position: { x: 650, y: 250 },
      data: {
        label,
        format,
        outputType: format,
        title: label,
        includeCharts: true,
      },
    };
    const newNodes = [...nodes, newNode];
    setNodes(newNodes);
    saveToHistory(newNodes, edges);
  }, [nodes, edges, setNodes, saveToHistory]);

  const applyAIWorkflow = useCallback((newNodes: Node[], newEdges: Edge[]) => {
    const combinedNodes = [...nodes, ...newNodes];
    const combinedEdges = [...edges, ...newEdges];
    setNodes(combinedNodes);
    setEdges(combinedEdges);
    saveToHistory(combinedNodes, combinedEdges);
  }, [nodes, edges, setNodes, setEdges, saveToHistory]);

  const handleTabChange = useCallback((tab: string) => {
    if (tab === 'proposals' || tab === 'history' || tab === 'results') {
      toast('Demo Mode - Sign up to access this feature', { icon: '🔒' });
    } else {
      setActiveTab(tab);
    }
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        handleUndo();
      }
      else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        handleRedo();
      }
      else if (e.key === 'Delete' && selectedNode) {
        deleteNode();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [handleUndo, handleRedo, selectedNode, deleteNode]);

  return (
    <div className="workflow-builder">
      <WorkflowHeader
        onClose={undefined}
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
        onViewResults={undefined}
        isSaving={false}
        saveSuccess={false}
        isValidating={false}
        isDeploying={false}
        workflows={[]}
        workflowName={workflowName}
        onWorkflowNameChange={setWorkflowName}
        hasResults={false}
        activeTab={activeTab}
        onTabChange={handleTabChange}
      />

      {activeTab === 'graph' && (
        <WorkflowCanvas
          ref={reactFlowWrapper}
          nodes={nodes}
          edges={edges}
          selectedNode={selectedNode}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
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
          onSave={(updatedNode) => {
            toast('Demo Mode - Sign up to save configurations', { icon: '🔒' });
            setShowConfigModal(false);
            setConfiguringNode(null);
          }}
        />
      )}
      {configuringNode && (configuringNode.type === 'input' || configuringNode.type === 'dataset') && (
        <DatasetConfigModal
          node={configuringNode}
          isOpen={showDatasetModal}
          isDemo={true}
          onClose={() => {
            setShowDatasetModal(false);
            setConfiguringNode(null);
          }}
          onSave={(nodeId, config) => {
            toast('Demo Mode - Sign up to save configurations', { icon: '🔒' });
            setShowDatasetModal(false);
            setConfiguringNode(null);
          }}
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
          onSave={(updatedNode) => {
            toast('Demo Mode - Sign up to save configurations', { icon: '🔒' });
            setShowOutputModal(false);
            setConfiguringNode(null);
          }}
        />
      )}
    </div>
  );
}

export default function PublicWorkflowDemo() {
  return (
    <ReactFlowProvider>
      <WorkflowBuilder />
    </ReactFlowProvider>
  );
}
