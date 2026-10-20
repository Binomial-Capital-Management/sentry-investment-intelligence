import ReactFlow, {
  Node,
  Edge,
  Background,
  BackgroundVariant,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  OnNodesDelete,
  NodeMouseHandler,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { taskNodeTypes } from './TaskNodes';
import { TaskCanvasControls } from './TaskCanvasControls';

interface TaskCanvasProps {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  onNodesDelete?: OnNodesDelete;
  onNodeClick: NodeMouseHandler;
  onPaneClick: () => void;
  onSave?: () => void;
  onRun?: () => void;
  onDeleteSelected?: () => void;
  selectionMode?: boolean;
  onSelectionModeChange?: (mode: boolean) => void;
}

export function TaskCanvas({
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
  selectionMode = false,
  onSelectionModeChange,
}: TaskCanvasProps) {
  const selectedCount = nodes.filter(node => node.selected).length;
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
        .react-flow__nodesselection-rect {
          background: rgba(79, 70, 229, 0.08) !important;
          border: 1.5px dashed #4F46E5 !important;
          border-radius: 4px !important;
          z-index: 9999 !important;
          display: block !important;
          visibility: visible !important;
          opacity: 1 !important;
        }
      `}</style>
      <div style={{
        width: '100%',
        height: '100%',
        background: '#F8F8F8',
        position: 'relative',
      }}>
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
          style: {
            stroke: '#C0C0C0',
            strokeWidth: 2,
            strokeDasharray: '5, 5',
          },
        }}
        fitView
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
}
