/**
 * ProcessFlowView - Tensor-based process graph visualization
 * 
 * Uses a 2D coordinate system: [primitive_type, instance]
 * - 1 = data (raw data sources)
 * - 2 = truth (derived facts/state)
 * - 3 = action (transformations)
 * - 4 = output (results/artifacts)
 * - 5 = system (external connections)
 */

import { memo, useEffect, useState, useCallback, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  BackgroundVariant,
  Position,
  Handle,
  NodeProps,
  Controls,
  MiniMap,
  ReactFlowProvider,
  applyNodeChanges,
  NodeChange,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Database, CheckCircle, Zap, FileOutput, Globe } from 'lucide-react';

// ============================================================================
// PRIMITIVE DEFINITIONS
// ============================================================================

type PrimitiveType = 'data' | 'truth' | 'action' | 'output' | 'system';

interface PrimitiveDef {
  index: number;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ComponentType<any>;
  label: string;
}

const PRIMITIVES: Record<PrimitiveType, PrimitiveDef> = {
  data: {
    index: 1,
    color: '#3B82F6',
    bgColor: '#EFF6FF',
    borderColor: '#3B82F6',
    icon: Database,
    label: 'Data',
  },
  truth: {
    index: 2,
    color: '#8B5CF6',
    bgColor: '#F5F3FF',
    borderColor: '#8B5CF6',
    icon: CheckCircle,
    label: 'Truth',
  },
  action: {
    index: 3,
    color: '#F59E0B',
    bgColor: '#FFFBEB',
    borderColor: '#F59E0B',
    icon: Zap,
    label: 'Action',
  },
  output: {
    index: 4,
    color: '#10B981',
    bgColor: '#ECFDF5',
    borderColor: '#10B981',
    icon: FileOutput,
    label: 'Output',
  },
  system: {
    index: 5,
    color: '#6B7280',
    bgColor: '#F9FAFB',
    borderColor: '#6B7280',
    icon: Globe,
    label: 'System',
  },
};

// ============================================================================
// PROCESS STEP INTERFACE
// ============================================================================

export interface ProcessStep {
  coord: [number, number]; // [primitive_type, instance]
  label: string;
  value?: any;
  primitive: PrimitiveType;
  // Extra metadata for inspection
  ticker?: string;      // For data nodes
  chartKey?: string;    // For output nodes (charts)
  toolId?: string;      // For action nodes
}

export interface ProcessEdge {
  source: [number, number];
  target: [number, number];
}

export interface ProcessGraph {
  steps: ProcessStep[];
  edges: ProcessEdge[];
}

// ============================================================================
// CUSTOM NODE COMPONENT
// ============================================================================

const PrimitiveNode = memo(({ data, selected }: NodeProps) => {
  const primitive = PRIMITIVES[data.primitive as PrimitiveType];
  const Icon = primitive.icon;
  
  return (
    <div
      style={{
        borderRadius: '8px',
        overflow: 'hidden',
        minWidth: '180px',
        maxWidth: '220px',
        boxShadow: selected
          ? `0 0 0 2px ${primitive.color}, 0 4px 12px rgba(0,0,0,0.15)`
          : '0 2px 8px rgba(0,0,0,0.1)',
        transition: 'all 0.15s ease',
        background: '#fff',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ 
          background: primitive.color, 
          width: 10, 
          height: 10,
          border: '2px solid white',
        }}
      />

      {/* Colored Header Strip */}
      <div
        style={{
          background: primitive.color,
          padding: '8px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <Icon size={14} style={{ color: '#fff' }} />
        <span
          style={{
            color: '#fff',
            fontSize: '10px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {primitive.label}
        </span>
      </div>

      {/* White Body */}
      <div
        style={{
          padding: '12px',
          background: '#fff',
        }}
      >
        {/* Main label */}
        <div style={{ 
          color: '#1F2937', 
          fontWeight: 600, 
          fontSize: '13px',
          lineHeight: 1.3,
          marginBottom: data.value ? '6px' : 0,
        }}>
          {data.label}
        </div>

        {/* Value display for outputs */}
        {data.value && data.primitive === 'output' && (
          <div style={{
            fontSize: '12px',
            color: primitive.color,
            fontWeight: 700,
            background: primitive.bgColor,
            padding: '4px 8px',
            borderRadius: '4px',
            display: 'inline-block',
          }}>
            {typeof data.value === 'object'
              ? JSON.stringify(data.value).slice(0, 20)
              : String(data.value)}
          </div>
        )}

        {/* Weight display for data nodes */}
        {data.value && data.primitive === 'data' && (
          <div style={{
            fontSize: '11px',
            color: '#6B7280',
            background: '#F3F4F6',
            padding: '3px 6px',
            borderRadius: '4px',
            display: 'inline-block',
          }}>
            Weight: {data.value}
          </div>
        )}

        {/* Tool name for action nodes */}
        {data.toolId && data.primitive === 'action' && (
          <div style={{
            fontSize: '11px',
            color: '#6B7280',
            marginTop: '4px',
          }}>
            {data.toolId}
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        style={{ 
          background: primitive.color, 
          width: 10, 
          height: 10,
          border: '2px solid white',
        }}
      />
    </div>
  );
});

PrimitiveNode.displayName = 'PrimitiveNode';

const nodeTypes = {
  primitive: PrimitiveNode,
};

// ============================================================================
// GRAPH BUILDER - Convert ProcessGraph to ReactFlow nodes/edges
// ============================================================================

function coordToId(coord: [number, number]): string {
  return `${coord[0]}_${coord[1]}`;
}

function buildReactFlowGraph(graph: ProcessGraph): { nodes: Node[]; edges: Edge[] } {
  // Layout: horizontal flow, vertical grouping by primitive type
  const ROW_HEIGHT = 90;  // Tighter vertical spacing
  const COL_WIDTH = 280;  // More horizontal space for connections
  const START_X = 80;
  const START_Y = 60;

  // Count nodes per column to center them vertically
  const columnCounts: Record<number, number> = {};
  graph.steps.forEach(step => {
    const col = step.coord[0];
    columnCounts[col] = (columnCounts[col] || 0) + 1;
  });
  
  // Track current index per column for positioning
  const columnIndex: Record<number, number> = {};

  // Calculate positions - arrange by execution order (left to right)
  // X position based on primitive type, Y position based on instance number
  const nodes: Node[] = graph.steps.map((step) => {
    const col = step.coord[0];
    const currentIndex = columnIndex[col] || 0;
    columnIndex[col] = currentIndex + 1;
    
    // Determine x position based on primitive type (data first, output last)
    const primitiveOrder = [1, 5, 2, 3, 4]; // data → system → truth → action → output
    const xOrder = primitiveOrder.indexOf(col);
    const xPos = xOrder >= 0 ? xOrder : 0;

    // Calculate y position - center the tool node with the ticker nodes
    let yPos = START_Y + currentIndex * ROW_HEIGHT;
    
    // Special handling for action (tool) node - center it
    if (step.primitive === 'action') {
      const dataCount = columnCounts[1] || 1;
      yPos = START_Y + ((dataCount - 1) * ROW_HEIGHT) / 2;
    }

    const node = {
      id: coordToId(step.coord),
      type: 'primitive',
      position: {
        x: START_X + xPos * COL_WIDTH,
        y: yPos,
      },
      data: {
        label: step.label,
        value: step.value,
        primitive: step.primitive,
        coord: step.coord,
        // Extra metadata for inspection
        ticker: step.ticker,
        chartKey: step.chartKey,
        toolId: step.toolId,
      },
    };
    
    return node;
  });

  const edges: Edge[] = graph.edges.map((edge, idx) => ({
    id: `e${idx}`,
    source: coordToId(edge.source),
    target: coordToId(edge.target),
    type: 'smoothstep',
    animated: false,  // Cleaner without animation
    style: {
      stroke: '#D1D5DB',
      strokeWidth: 2,
    },
    markerEnd: {
      type: 'arrowclosed' as any,
      color: '#9CA3AF',
      width: 15,
      height: 15,
    },
  }));

  return { nodes, edges };
}

// ============================================================================
// GRAPH FROM PROCESS DATA
// ============================================================================

// Format tool_id to readable name
function formatToolName(toolId: string): string {
  const names: Record<string, string> = {
    monte_carlo: 'Monte Carlo Simulation',
    barra_factors: 'Factor Analysis',
    vol_surface: 'Volatility Surface',
    correlation_matrix: 'Correlation Matrix',
    pca_analysis: 'PCA Analysis',
    cointegration: 'Cointegration',
    var: 'Value at Risk',
    stress_test: 'Stress Test',
    optimization: 'Portfolio Optimization',
    dcf_traditional: 'DCF Valuation',
    dcf_monte_carlo: 'Monte Carlo DCF',
    comps: 'Comparable Companies',
    reverse_dcf: 'Reverse DCF',
  };
  return names[toolId] || toolId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// Auto-generate graph from process data when graph_steps is missing
function autoGenerateGraph(process: any): ProcessGraph {
  const steps: ProcessStep[] = [];
  const edges: ProcessEdge[] = [];
  
  const tickers = process.tickers || [];
  const charts = process.charts || {};
  const metricCards = process.metric_cards || [];
  
  // 1. Add ticker/object nodes (left column - DATA)
  tickers.slice(0, 8).forEach((ticker: string, i: number) => { // Limit to 8 for readability
    const weight = process.weights?.[i];
    steps.push({
      coord: [1, i + 1] as [number, number],
      primitive: 'data',
      label: ticker,
      value: weight ? `${(weight * 100).toFixed(1)}%` : undefined,
      ticker: ticker, // Store ticker for inspection
    });
  });
  
  // If more than 8 tickers, add a summary node
  if (tickers.length > 8) {
    steps.push({
      coord: [1, 9] as [number, number],
      primitive: 'data',
      label: `+${tickers.length - 8} more`,
      value: undefined,
    });
  }
  
  // 2. Add tool node (center - ACTION)
  const toolNode: ProcessStep = {
    coord: [3, 1] as [number, number],
    primitive: 'action',
    label: formatToolName(process.tool_id),
    value: process.tool_id,
    toolId: process.tool_id, // Store tool ID for inspection
  };
  steps.push(toolNode);
  
  // 3. Add chart output nodes (right column - OUTPUT)
  const chartKeys = Object.keys(charts).filter(k => charts[k]?.plotly);
  chartKeys.forEach((chartKey, i) => {
    steps.push({
      coord: [4, i + 1] as [number, number],
      primitive: 'output',
      label: charts[chartKey]?.label || chartKey.replace(/_/g, ' '),
      value: 'Chart',
      chartKey: chartKey, // Store chart key for inspection
    });
  });
  
  // 4. Add key metric nodes (also OUTPUT, below charts)
  const metricsToShow = metricCards.slice(0, 4); // Show up to 4 key metrics
  metricsToShow.forEach((card: any, i: number) => {
    steps.push({
      coord: [4, chartKeys.length + i + 1] as [number, number],
      primitive: 'output',
      label: card.label || 'Metric',
      value: card.value,
    });
  });
  
  // 5. Connect all tickers → tool
  const tickerCount = Math.min(tickers.length, 8) + (tickers.length > 8 ? 1 : 0);
  for (let i = 1; i <= tickerCount; i++) {
    edges.push({
      source: [1, i] as [number, number],
      target: [3, 1] as [number, number],
    });
  }
  
  // 6. Connect tool → all outputs
  const outputCount = chartKeys.length + metricsToShow.length;
  for (let i = 1; i <= outputCount; i++) {
    edges.push({
      source: [3, 1] as [number, number],
      target: [4, i] as [number, number],
    });
  }
  
  return { steps, edges };
}

function parseProcessGraph(process: any): ProcessGraph | null {
  // Always auto-generate from actual process data (tickers, tool, charts)
  // This gives a more useful object-centric view than stored execution steps
  if (process?.tickers?.length > 0 && process?.tool_id) {
    return autoGenerateGraph(process);
  }
  
  // Fallback to stored graph data if no tickers
  if (process?.graph_steps?.length > 0 && process?.graph_edges?.length > 0) {
    const steps: ProcessStep[] = process.graph_steps.map((s: any) => ({
      coord: Array.isArray(s.coord) ? s.coord as [number, number] : [0, 0],
      label: s.label || 'Unknown',
      value: s.value,
      primitive: s.primitive || 'data',
    }));
    
    const edges: ProcessEdge[] = process.graph_edges.map((e: any) => ({
      source: Array.isArray(e.source) ? e.source as [number, number] : [0, 0],
      target: Array.isArray(e.target) ? e.target as [number, number] : [0, 0],
    }));
    
    return { steps, edges };
  }
  
  return null;
}

// ============================================================================
// MAIN COMPONENT - Inline view (not a modal)
// ============================================================================

interface ProcessFlowViewProps {
  process: any;
}

// Inspection Panel Component
function InspectionPanel({ 
  node, 
  process, 
  onClose 
}: { 
  node: Node | null; 
  process: any; 
  onClose: () => void;
}) {
  if (!node) return null;

  const { primitive, label, value, chartKey, ticker } = node.data;
  const primitiveDef = PRIMITIVES[primitive as PrimitiveType];

  // Get relevant data based on node type
  const getContent = () => {
    switch (primitive) {
      case 'data': {
        // Show ticker info
        const tickerIndex = process?.tickers?.indexOf(ticker || label);
        const weight = tickerIndex >= 0 ? process?.weights?.[tickerIndex] : null;
        return (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="text-gray-500">Ticker</div>
              <div className="font-medium">{ticker || label}</div>
              {weight !== null && weight !== undefined && (
                <>
                  <div className="text-gray-500">Weight</div>
                  <div className="font-medium">{(weight * 100).toFixed(1)}%</div>
                </>
              )}
              <div className="text-gray-500">Type</div>
              <div className="font-medium">Equity</div>
            </div>
            <div className="pt-2 border-t border-gray-100">
              <div className="text-xs text-gray-400">
                This asset provides: price, volume, fundamentals, ratios
              </div>
            </div>
          </div>
        );
      }
      case 'action': {
        // Show tool parameters
        const params = process?.parameters || {};
        return (
          <div className="space-y-3">
            <div className="text-sm">
              <div className="text-gray-500 mb-1">Tool</div>
              <div className="font-medium">{formatToolName(process?.tool_id)}</div>
            </div>
            {Object.keys(params).length > 0 && (
              <div className="pt-2 border-t border-gray-100">
                <div className="text-xs text-gray-500 mb-2">Parameters</div>
                <div className="space-y-1">
                  {Object.entries(params).slice(0, 8).map(([key, val]) => (
                    <div key={key} className="flex justify-between text-xs">
                      <span className="text-gray-500">{key.replace(/_/g, ' ')}</span>
                      <span className="font-medium text-gray-700">
                        {typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      }
      case 'output': {
        // Show chart or metric data
        if (chartKey && process?.charts?.[chartKey]) {
          const chart = process.charts[chartKey];
          return (
            <div className="space-y-3">
              <div className="text-sm">
                <div className="text-gray-500 mb-1">Chart</div>
                <div className="font-medium">{label}</div>
              </div>
              <div className="pt-2 border-t border-gray-100">
                <div className="text-xs text-gray-500 mb-2">Chart Data</div>
                <div className="text-xs space-y-1">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Type</span>
                    <span className="font-medium">{chart.spec?.mark || chart.type || 'chart'}</span>
                  </div>
                  {chart.spec?.data?.values && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Data points</span>
                      <span className="font-medium">{chart.spec.data.values.length}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        } else {
          // Metric card
          return (
            <div className="space-y-3">
              <div className="text-sm">
                <div className="text-gray-500 mb-1">Metric</div>
                <div className="font-medium">{label}</div>
              </div>
              <div className="pt-2 border-t border-gray-100">
                <div className="text-3xl font-bold" style={{ color: primitiveDef.color }}>
                  {value || 'N/A'}
                </div>
              </div>
            </div>
          );
        }
      }
      default:
        return <div className="text-sm text-gray-500">No details available</div>;
    }
  };

  return (
    <div 
      className="absolute right-4 top-16 w-72 bg-white rounded-lg shadow-xl border border-gray-200 z-50 overflow-hidden"
      style={{ maxHeight: 'calc(100% - 100px)' }}
    >
      {/* Header */}
      <div 
        className="px-4 py-3 flex items-center justify-between"
        style={{ background: primitiveDef.color }}
      >
        <div className="flex items-center gap-2">
          <primitiveDef.icon size={16} className="text-white" />
          <span className="text-white font-medium text-sm uppercase tracking-wide">
            {primitiveDef.label}
          </span>
        </div>
        <button 
          onClick={onClose}
          className="text-white/80 hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      {/* Content */}
      <div className="p-4">
        {getContent()}
      </div>
    </div>
  );
}

function ProcessFlowViewInner({ process }: ProcessFlowViewProps) {
  // Parse graph data once with useMemo (stable reference)
  const { initialNodes, initialEdges, hasData } = useMemo(() => {
    const graph = parseProcessGraph(process);
    if (graph) {
      const { nodes, edges } = buildReactFlowGraph(graph);
      return { initialNodes: nodes, initialEdges: edges, hasData: true };
    }
    return { initialNodes: [], initialEdges: [], hasData: false };
  }, [process?.id]); // Only recompute when process ID changes
  
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges] = useState<Edge[]>(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  // Reset nodes when process changes
  useEffect(() => {
    setNodes(initialNodes);
    setSelectedNode(null);
  }, [initialNodes]);

  // Handle node position changes (dragging)
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds));
    },
    []
  );

  // Handle node click for inspection
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  // No graph data available
  if (!hasData) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8 bg-gradient-to-b from-gray-50 to-white">
        <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-4">
          <svg className="w-10 h-10 text-gray-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z"/>
          </svg>
        </div>
        <h3 className="text-base font-semibold text-gray-800 mb-2">No Process Data</h3>
        <p className="text-sm text-gray-500 max-w-sm">
          Select a process with tickers and run it to visualize the data flow.
        </p>
      </div>
    );
  }

  // Get process info for header
  const tickerCount = process?.tickers?.length || 0;
  
  return (
    <div style={{ width: '100%', height: '100%' }}>
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-6">
          <div>
            <div className="text-sm font-semibold text-gray-900">Process Flow</div>
            <div className="text-xs text-gray-500">{tickerCount} assets → {process?.tool_id} → {Object.keys(process?.charts || {}).length} outputs</div>
          </div>
          <div className="flex items-center gap-3 pl-6 border-l border-gray-200">
            {['data', 'action', 'output'].map((key) => {
              const def = PRIMITIVES[key as PrimitiveType];
              const Icon = def.icon;
              return (
                <div key={key} className="flex items-center gap-1.5 text-xs">
                  <div
                    className="w-5 h-5 rounded flex items-center justify-center"
                    style={{ background: def.bgColor, border: `1px solid ${def.color}` }}
                  >
                    <Icon size={10} style={{ color: def.color }} />
                  </div>
                  <span className="text-gray-600 capitalize font-medium">{def.label}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="text-xs text-gray-400">
          Drag nodes to rearrange • Scroll to zoom
        </div>
      </div>

      {/* Graph Canvas */}
      <div style={{ width: '100%', height: 'calc(100% - 40px)', position: 'relative' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          style={{ background: '#FAFAFA' }}
          nodesDraggable={true}
          nodesConnectable={false}
          elementsSelectable={true}
          panOnDrag={true}
          zoomOnScroll={true}
          minZoom={0.2}
          maxZoom={3}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#E5E7EB" />
          <Controls />
          <MiniMap 
            nodeColor={(node) => {
              const primitive = node.data?.primitive as PrimitiveType;
              return PRIMITIVES[primitive]?.color || '#9CA3AF';
            }}
            style={{ background: '#fff', border: '1px solid #E5E7EB' }}
          />
        </ReactFlow>
        
        {/* Inspection Panel */}
        <InspectionPanel 
          node={selectedNode} 
          process={process} 
          onClose={() => setSelectedNode(null)} 
        />
      </div>
    </div>
  );
}

// Wrap with ReactFlowProvider for proper context
export default function ProcessFlowView({ process }: ProcessFlowViewProps) {
  return (
    <ReactFlowProvider>
      <ProcessFlowViewInner process={process} />
    </ReactFlowProvider>
  );
}
