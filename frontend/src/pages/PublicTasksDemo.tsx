import { useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactFlow, {
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  Connection,
  Background,
  BackgroundVariant,
} from 'reactflow';
import 'reactflow/dist/style.css';
import toast from 'react-hot-toast';

// Import existing components from the Task feature
import { TaskHeader } from '@/components/Task/TaskHeader';
import { TaskSidebar } from '@/components/Task/TaskSidebar';
import { NodeConfigPanel } from '@/components/Task/NodeConfigPanel';
import { taskNodeTypes } from '@/components/Task/TaskNodes';
import { TaskCanvasControls } from '@/components/Task/TaskCanvasControls';

// Simplified Demo Workflow
const initialNodes: Node[] = [
  { id: 'start-1', type: 'start', position: { x: 100, y: 300 }, data: { label: 'Start' } },

  // Data Ingestion
  { id: 'portfolio-1', type: 'portfolio', position: { x: 350, y: 300 }, data: { label: 'Tech Growth Fund' } },

  // Analysis
  { id: 'agent-risk', type: 'agent', position: { x: 600, y: 300 }, data: { label: 'Daily Risk Scan', agent: 'risk' } },

  // Decision / Output
  { id: 'agent-summary', type: 'agent', position: { x: 850, y: 300 }, data: { label: 'Draft Summary', agent: 'auto' } },

  // Distribution
  { id: 'email-1', type: 'email', position: { x: 1100, y: 300 }, data: { label: 'Risk Alert' } },

  { id: 'end-1', type: 'end', position: { x: 1350, y: 300 }, data: { label: 'End' } },
];

const initialEdges: Edge[] = [
  { id: 'e1', source: 'start-1', target: 'portfolio-1', type: 'smoothstep', style: { stroke: '#C0C0C0', strokeWidth: 2 } },
  { id: 'e2', source: 'portfolio-1', target: 'agent-risk', type: 'smoothstep', animated: true, style: { stroke: '#C0C0C0', strokeWidth: 2 } },
  { id: 'e3', source: 'agent-risk', target: 'agent-summary', type: 'smoothstep', style: { stroke: '#C0C0C0', strokeWidth: 2 } },
  { id: 'e4', source: 'agent-summary', target: 'email-1', type: 'smoothstep', style: { stroke: '#C0C0C0', strokeWidth: 2 } },
  { id: 'e5', source: 'email-1', target: 'end-1', type: 'smoothstep', style: { stroke: '#C0C0C0', strokeWidth: 2 } },
];

// Custom Canvas for Demo to control zoom
const DemoTaskCanvas = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodesDelete,
  onNodeClick,
  onPaneClick,
  onSave,
  onRun,
  onDeleteSelected,
  selectionMode,
  onSelectionModeChange,
}: any) => {
  const selectedCount = nodes.filter((node: any) => node.selected).length;

  return (
    <>
      <style>{`
        .react-flow__selectionrect {
          background: rgba(79, 70, 229, 0.08) !important;
          border: 1.5px dashed #4F46E5 !important;
          z-index: 9999 !important;
          pointer-events: none !important;
          position: absolute !important;
          display: block !important;
          visibility: visible !important;
          opacity: 1 !important;
        }
        .react-flow__selection {
          background: rgba(79, 70, 229, 0.08) !important;
          border: 1.5px dashed #4F46E5 !important;
          z-index: 9999 !important;
          pointer-events: none !important;
          display: block !important;
          visibility: visible !important;
          opacity: 1 !important;
        }
      `}</style>
      <div style={{ width: '100%', height: '100%', background: '#F8F8F8', position: 'relative' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodesDelete={onNodesDelete}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={taskNodeTypes}
          defaultEdgeOptions={{
            type: 'smoothstep',
            animated: true,
            style: { stroke: '#C0C0C0', strokeWidth: 2, strokeDasharray: '5, 5' },
          }}
          // Zoomed out view
          defaultViewport={{ x: 150, y: 200, zoom: 0.75 }}
          minZoom={0.2}
          maxZoom={2}
          style={{ background: '#F8F8F8' }}
          panOnDrag={!selectionMode}
          panOnScroll={!selectionMode}
          selectNodesOnDrag={selectionMode}
          selectionOnDrag={selectionMode}
          nodesDraggable={!selectionMode}
          elementsSelectable={true}
          zoomOnDoubleClick={false}
          selectionMode={selectionMode ? 'full' : undefined}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={25}
            size={1.5}
            color="#AAAAAA"
          />
          <TaskCanvasControls
            onSave={onSave}
            onRun={onRun}
            selectedCount={selectedCount}
            onDeleteSelected={onDeleteSelected}
            selectionMode={selectionMode}
            onSelectionModeChange={onSelectionModeChange}
          />
        </ReactFlow>
      </div>
    </>
  );
};

function PublicTaskBuilderInner() {
  const navigate = useNavigate();
  const idRef = useRef(20);

  // Task configuration state
  const [taskName, setTaskName] = useState('Daily Risk Monitor');
  const [description, setDescription] = useState('Automated daily analysis of portfolio risk metrics sent via email.');
  const [frequency, setFrequency] = useState('daily');
  const [cronExpression, setCronExpression] = useState('08:00 AM');
  const [customCronExpression, setCustomCronExpression] = useState('');
  const [email, setEmail] = useState('risk@fund.com');
  const [deliveryPreference, setDeliveryPreference] = useState('email');

  // Additional task settings
  const [selectedDate, setSelectedDate] = useState<Date | null>(new Date());
  const [timezone, setTimezone] = useState('America/New_York');
  const [tags, setTags] = useState<string[]>(['risk', 'automated']);
  const [selectedDays, setSelectedDays] = useState<number[]>([1, 2, 3, 4, 5]);
  const [dayOfMonth, setDayOfMonth] = useState<number | null>(null);

  // Canvas state
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);

  // Fake UI state for interactions
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);

  // --- Handlers (Mocked for Demo) ---

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => {
      setIsSaving(false);
      toast.success('Demo Mode: Changes simulated saved');
    }, 1000);
  };

  const handleRun = () => {
    setIsTesting(true);
    setTimeout(() => {
      setIsTesting(false);
      toast.success('Demo Mode: Test run simulation complete');
    }, 2000);
  };

  const handleDeploy = () => {
    setIsDeploying(true);
    setTimeout(() => {
      setIsDeploying(false);
      toast.success('Demo Mode: Deployment simulation complete');
    }, 1500);
  };

  const handleAIAssistant = () => {
    toast('AI Assistant is available in the full version', { icon: '🤖' });
  };

  const handleValidate = () => {
    toast.success('Workflow looks good!', { icon: '✅' });
  };

  // --- Canvas Interactions ---

  const onConnect = useCallback(
    (params: Connection) => {
      if (!params.source || !params.target) return;
      const newEdge = {
        ...params,
        id: `e${params.source}-${params.target}`,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#C0C0C0', strokeWidth: 2, strokeDasharray: '5, 5' },
      };
      setEdges((eds) => [...eds, newEdge]);
    },
    [setEdges],
  );

  const handleAddNode = useCallback((type: string) => {
    const id = `${type}-${idRef.current++}`;
    const labelMap: Record<string, string> = {
      start: 'Start', agent: 'Agent', end: 'End', merge: 'Merge',
      distribute: 'Distribute', portfolio: 'Portfolio', graph: 'Graph',
      fileUpload: 'File Upload', email: 'Email', pdfReport: 'PDF Report',
      pptPresentation: 'PPT', workbook: 'Workbook', slack: 'Slack',
      teams: 'Teams', saveToSentry: 'Save to Sentry',
    };

    const lastNode = nodes[nodes.length - 1];
    const newX = lastNode ? lastNode.position.x + 200 : 250;
    const newY = lastNode ? lastNode.position.y : 100;

    const newNode: Node = {
      id,
      type,
      position: { x: newX, y: newY },
      data: { label: labelMap[type] || type },
    };

    setNodes((nds) => [...nds, newNode]);

    if (lastNode) {
      setEdges((eds) => [
        ...eds,
        {
          id: `e${lastNode.id}-${newNode.id}`,
          source: lastNode.id,
          target: newNode.id,
          type: 'smoothstep',
          animated: true,
          style: { stroke: '#C0C0C0', strokeWidth: 2, strokeDasharray: '5, 5' },
        },
      ]);
    }
  }, [nodes, setNodes, setEdges]);

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleUpdateNode = useCallback((nodeId: string, data: any) => {
    setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, data } : n)));
    setSelectedNode((prev) => (prev?.id === nodeId ? { ...prev, data } : prev));
  }, [setNodes]);

  const handleDeleteNode = useCallback((nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    setSelectedNode(null);
  }, [setNodes, setEdges]);

  const handleDeleteSelected = useCallback(() => {
    setNodes((nds) => nds.filter((n) => !n.selected));
    setEdges((eds) => eds.filter((e) => {
      const source = nodes.find((n) => n.id === e.source);
      const target = nodes.find((n) => n.id === e.target);
      return !source?.selected && !target?.selected;
    }));
  }, [nodes, setNodes, setEdges]);

  const onNodesDelete = useCallback((deleted: Node[]) => {
    const ids = new Set(deleted.map((n) => n.id));
    setEdges((eds) => eds.filter((e) => !ids.has(e.source) && !ids.has(e.target)));
  }, [setEdges]);

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#F0F0F0' }}>
      <div style={{ position: 'relative', zIndex: 1 }}>
        <TaskHeader
          taskName={taskName}
          onTaskNameChange={setTaskName}
          isDraft={true}
          onSave={handleSave}
          onDelete={() => toast('Cannot delete in demo mode')}
          onAIAssistant={handleAIAssistant}
          onDeploy={handleDeploy}
          onTest={handleRun}
          onValidate={handleValidate}
          isSaving={isSaving}
          isTesting={isTesting}
          isDeploying={isDeploying}
        />
        {/* Overlay to block header interactions to prevent breaches/navigation */}
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            height: '48px',
            zIndex: 2000, // Higher than TaskHeader's 1000
            cursor: 'not-allowed',
          }}
          onClick={(e) => {
            e.stopPropagation();
            e.preventDefault();
            toast('Header actions disabled in demo');
          }}
        />
      </div>

      <div style={{ flex: 1, position: 'relative', background: '#F8F8F8', overflow: 'hidden' }}>
        <DemoTaskCanvas
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodesDelete={onNodesDelete}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onSave={handleSave}
          onRun={handleRun}
          onDeleteSelected={handleDeleteSelected}
          selectionMode={selectionMode}
          onSelectionModeChange={setSelectionMode}
        />

        <TaskSidebar
          taskName={taskName}
          onTaskNameChange={setTaskName}
          description={description}
          onDescriptionChange={setDescription}
          frequency={frequency}
          onFrequencyChange={setFrequency}
          cronExpression={cronExpression}
          onCronExpressionChange={setCronExpression}
          customCronExpression={customCronExpression}
          onCustomCronExpressionChange={setCustomCronExpression}
          email={email}
          onEmailChange={setEmail}
          deliveryPreference={deliveryPreference}
          onDeliveryPreferenceChange={setDeliveryPreference}
          onAddNode={handleAddNode}
          selectedDate={selectedDate}
          onSelectedDateChange={setSelectedDate}
          timezone={timezone}
          onTimezoneChange={setTimezone}
          tags={tags}
          onTagsChange={setTags}
          selectedDays={selectedDays}
          onSelectedDaysChange={setSelectedDays}
          dayOfMonth={dayOfMonth}
          onDayOfMonthChange={setDayOfMonth}
        />

        {selectedNode && (
          <div style={{ position: 'absolute', top: '80px', right: '16px', bottom: '16px', zIndex: 5 }}>
            <NodeConfigPanel
              selectedNode={selectedNode}
              onUpdateNode={handleUpdateNode}
              onDeleteNode={handleDeleteNode}
              onClose={() => setSelectedNode(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default function PublicTasksDemo() {
  return (
    <ReactFlowProvider>
      <PublicTaskBuilderInner />
    </ReactFlowProvider>
  );
}
