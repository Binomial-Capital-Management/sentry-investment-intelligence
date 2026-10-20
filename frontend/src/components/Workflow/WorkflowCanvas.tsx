import { forwardRef } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  NodeMouseHandler,
} from 'reactflow';
import { nodeTypes } from './WorkflowNodes';
import { WorkflowToolbar } from './WorkflowToolbar';

interface WorkflowCanvasProps {
  nodes: Node[];
  edges: Edge[];
  selectedNode: Node | null;
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  onNodeClick: NodeMouseHandler;
  onNodeDoubleClick?: NodeMouseHandler;
  onPaneClick: () => void;
  onDeleteNode: () => void;
  onAddAgent: (label: string, operation: string, color: string) => void;
  onAddDataset: (type: string, label: string) => void;
  onAddOutput: (label: string, format: string) => void;
  selectMode: boolean;
  onSelectModeChange: (mode: boolean) => void;
  onToggleAI: () => void;
}

export const WorkflowCanvas = forwardRef<HTMLDivElement, WorkflowCanvasProps>(
  ({
    nodes,
    edges,
    selectedNode,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onNodeClick,
    onNodeDoubleClick,
    onPaneClick,
    onDeleteNode,
    onAddAgent,
    onAddDataset,
    onAddOutput,
    selectMode,
    onSelectModeChange,
    onToggleAI,
  }, ref) => {
    return (
      <div className="workflow-canvas">
        <WorkflowToolbar
          selectedNode={selectedNode}
          onDeleteNode={onDeleteNode}
          onAddAgent={onAddAgent}
          onAddDataset={onAddDataset}
          onAddOutput={onAddOutput}
          selectMode={selectMode}
          onSelectModeChange={onSelectModeChange}
          onToggleAI={onToggleAI}
        />

        <div ref={ref} className="react-flow-wrapper">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onNodeDoubleClick={onNodeDoubleClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            nodesDraggable={!selectMode}
            nodesConnectable={!selectMode}
            elementsSelectable={!selectMode}
            defaultEdgeOptions={{
              type: 'smoothstep',
              animated: false,
              style: { stroke: '#C0C0C0', strokeWidth: 1.5 },
            }}
            fitView
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1.5}
              color="#E0E0E0"
            />
            <Controls />
          </ReactFlow>
        </div>
      </div>
    );
  },
);

WorkflowCanvas.displayName = 'WorkflowCanvas';
