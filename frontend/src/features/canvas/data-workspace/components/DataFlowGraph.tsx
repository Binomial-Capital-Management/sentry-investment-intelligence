/**
 * OntologyGraph - Visual display of symbols and their endpoint connections
 * 
 * Groups datasets by symbol - one node per unique symbol
 * Each symbol node connects to its endpoint(s)
 */

import { memo, useMemo, useCallback, useState, useEffect } from 'react';
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
import { Database } from 'lucide-react';
import { useDataWorkspaceStore, DatasetConfig, selectDatasets } from '../stores/dataWorkspaceStore';

// ============================================================================
// COMPACT DATA NODE - One per unique symbol
// ============================================================================

const DataNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div
      style={{
        borderRadius: '4px',
        overflow: 'hidden',
        minWidth: '120px',
        boxShadow: selected
          ? `0 0 0 2px #3B82F6, 0 2px 8px rgba(0,0,0,0.15)`
          : '0 1px 4px rgba(0,0,0,0.08)',
        transition: 'all 0.15s ease',
        background: '#fff',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ 
          background: '#3B82F6', 
          width: 6, 
          height: 6,
          border: '1.5px solid white',
        }}
      />

      {/* Blue Header */}
      <div
        style={{
          background: '#3B82F6',
          padding: '3px 8px',
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
        }}
      >
        <Database size={10} style={{ color: '#fff' }} />
        <span
          style={{
            color: '#fff',
            fontSize: '8px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.4px',
          }}
        >
          DATA
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: '6px 8px' }}>
        <div style={{ 
          color: '#1F2937', 
          fontWeight: 600, 
          fontSize: '11px',
        }}>
          {data.label}
        </div>
        {data.datasetCount > 1 && (
          <div style={{ 
            color: '#9CA3AF', 
            fontSize: '9px',
            marginTop: '2px',
          }}>
            {data.datasetCount} datasets
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        style={{ 
          background: '#3B82F6', 
          width: 6, 
          height: 6,
          border: '1.5px solid white',
        }}
      />
    </div>
  );
});

DataNode.displayName = 'DataNode';

// Endpoint node - styled like DataNode with header/body
const EndpointNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div
      style={{
        borderRadius: '4px',
        overflow: 'hidden',
        minWidth: '140px',
        boxShadow: selected
          ? `0 0 0 2px #6B7280, 0 2px 8px rgba(0,0,0,0.15)`
          : '0 1px 4px rgba(0,0,0,0.08)',
        transition: 'all 0.15s ease',
        background: '#fff',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ 
          background: '#6B7280', 
          width: 6, 
          height: 6,
          border: '1.5px solid white',
        }}
      />

      {/* Gray Header */}
      <div
        style={{
          background: '#6B7280',
          padding: '3px 8px',
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
        }}
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="white">
          <path d="M4 6h16v2H4V6zm0 5h16v2H4v-2zm0 5h16v2H4v-2z"/>
        </svg>
        <span
          style={{
            color: '#fff',
            fontSize: '8px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.4px',
          }}
        >
          ENDPOINT
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: '6px 8px' }}>
        <div style={{ 
          color: '#1F2937', 
          fontWeight: 600, 
          fontSize: '10px',
          fontFamily: 'monospace',
        }}>
          {data.label}
        </div>
        {data.fieldCount > 0 && (
          <div style={{ 
            color: '#9CA3AF', 
            fontSize: '9px',
            marginTop: '2px',
          }}>
            {data.fieldCount} fields
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        style={{ 
          background: '#6B7280', 
          width: 6, 
          height: 6,
          border: '1.5px solid white',
        }}
      />
    </div>
  );
});

EndpointNode.displayName = 'EndpointNode';

// Field node - expandable with metadata
const FieldNode = memo(({ data }: NodeProps) => {
  const [expanded, setExpanded] = useState(false);
  const fields = data.fields || [];
  const maxCollapsed = 4;
  const displayFields = expanded ? fields : fields.slice(0, maxCollapsed);
  const hasMore = fields.length > maxCollapsed;

  return (
    <div
      style={{
        borderRadius: '4px',
        overflow: 'hidden',
        minWidth: '130px',
        maxWidth: expanded ? '200px' : '150px',
        background: '#fff',
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
        transition: 'all 0.2s ease',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: '#10B981', width: 6, height: 6, border: '1.5px solid white' }}
      />
      
      {/* Green Header */}
      <div
        style={{
          background: '#10B981',
          padding: '3px 8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '5px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="white">
            <path d="M3 4h18v2H3V4zm0 7h12v2H3v-2zm0 7h18v2H3v-2z"/>
          </svg>
          <span
            style={{
              color: '#fff',
              fontSize: '8px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.4px',
            }}
          >
            FIELDS
          </span>
        </div>
        <span style={{ 
          color: 'rgba(255,255,255,0.8)', 
          fontSize: '8px',
          fontWeight: 500,
        }}>
          {fields.length}
        </span>
      </div>

      {/* Metadata row */}
      <div style={{ 
        padding: '4px 8px', 
        background: '#F0FDF4',
        borderBottom: '1px solid #D1FAE5',
        display: 'flex',
        gap: '8px',
      }}>
        <div style={{ fontSize: '8px', color: '#059669' }}>
          <span style={{ fontWeight: 600 }}>Source:</span> {data.source || 'FMP'}
        </div>
        <div style={{ fontSize: '8px', color: '#059669' }}>
          <span style={{ fontWeight: 600 }}>Type:</span> {data.dataType || 'numeric'}
        </div>
      </div>

      {/* Field list */}
      <div style={{ padding: '4px 8px', maxHeight: expanded ? '200px' : 'auto', overflowY: expanded ? 'auto' : 'hidden' }}>
        {displayFields.map((field: string, i: number) => (
          <div
            key={i}
            style={{
              fontSize: '9px',
              color: '#374151',
              fontFamily: 'monospace',
              padding: '2px 0',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span style={{ color: '#10B981', fontSize: '8px' }}>•</span>
            {field}
          </div>
        ))}
      </div>

      {/* Expand/collapse button */}
      {hasMore && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(!expanded);
          }}
          style={{
            width: '100%',
            padding: '4px 8px',
            background: '#F9FAFB',
            border: 'none',
            borderTop: '1px solid #E5E7EB',
            cursor: 'pointer',
            fontSize: '8px',
            color: '#6B7280',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
          }}
        >
          <svg 
            width="10" 
            height="10" 
            viewBox="0 0 24 24" 
            fill="currentColor"
            style={{ 
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s ease',
            }}
          >
            <path d="M7 10l5 5 5-5H7z"/>
          </svg>
          {expanded ? 'Collapse' : `Show all ${fields.length} fields`}
        </button>
      )}
    </div>
  );
});

FieldNode.displayName = 'FieldNode';

const nodeTypes = {
  data: DataNode,
  endpoint: EndpointNode,
  field: FieldNode,
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

interface OntologyGraphProps {
  height?: number;
}

function OntologyGraphInner({ height = 500 }: OntologyGraphProps) {
  const datasets = useDataWorkspaceStore(selectDatasets);

  const { initialNodes, initialEdges, hasData } = useMemo(() => {
    const flowNodes: Node[] = [];
    const flowEdges: Edge[] = [];

    if (datasets.length === 0) {
      return { initialNodes: flowNodes, initialEdges: flowEdges, hasData: false };
    }

    // Group datasets by symbol
    const symbolGroups: Record<string, DatasetConfig[]> = {};
    datasets.forEach(ds => {
      if (!symbolGroups[ds.symbol]) {
        symbolGroups[ds.symbol] = [];
      }
      symbolGroups[ds.symbol].push(ds);
    });

    const symbols = Object.keys(symbolGroups);
    
    // Get unique endpoints
    const allEndpoints = new Set<string>();
    datasets.forEach(ds => allEndpoints.add(ds.endpoint));
    const endpoints = Array.from(allEndpoints);

    // Layout
    const NODE_HEIGHT = 50;
    const NODE_SPACING = 12;
    const START_X = 50;
    const START_Y = 30;
    const ENDPOINT_X = 220;
    const FIELD_X = 400;

    // Create one DATA node per unique symbol
    symbols.forEach((symbol, i) => {
      const group = symbolGroups[symbol];
      flowNodes.push({
        id: `symbol-${symbol}`,
        type: 'data',
        position: { x: START_X, y: START_Y + i * (NODE_HEIGHT + NODE_SPACING) },
        data: { 
          label: symbol,
          datasetCount: group.length,
        },
      });
    });

    // Create endpoint nodes and field nodes
    const ENDPOINT_HEIGHT = 60;
    const ENDPOINT_SPACING = 20;
    let fieldNodeIndex = 0;
    
    endpoints.forEach((endpoint, i) => {
      // Find which symbols use this endpoint
      const connectedSymbols = symbols.filter(sym => 
        symbolGroups[sym].some(ds => ds.endpoint === endpoint)
      );
      
      // Get all fields for this endpoint (from all datasets using it)
      const fieldsForEndpoint = new Set<string>();
      datasets.filter(ds => ds.endpoint === endpoint).forEach(ds => {
        ds.fields.forEach(f => fieldsForEndpoint.add(f));
      });
      const fields = Array.from(fieldsForEndpoint);
      
      // Position endpoints in a simple vertical stack - evenly distributed
      const yPos = START_Y + i * (ENDPOINT_HEIGHT + ENDPOINT_SPACING);

      flowNodes.push({
        id: `endpoint-${endpoint}`,
        type: 'endpoint',
        position: { x: ENDPOINT_X, y: yPos },
        data: { 
          label: endpoint,
          fieldCount: fields.length,
        },
      });

      // Connect each symbol that uses this endpoint
      connectedSymbols.forEach(symbol => {
        flowEdges.push({
          id: `edge-${symbol}-${endpoint}`,
          source: `symbol-${symbol}`,
          target: `endpoint-${endpoint}`,
          type: 'smoothstep',
          style: { stroke: '#D1D5DB', strokeWidth: 1 },
        });
      });

      // Create field node for this endpoint if there are fields
      if (fields.length > 0) {
        const fieldNodeId = `fields-${endpoint}`;
        // Infer data type from endpoint name
        const dataType = endpoint.includes('price') || endpoint.includes('quote') ? 'price' 
          : endpoint.includes('ratio') || endpoint.includes('metric') ? 'ratio'
          : endpoint.includes('estimate') ? 'estimate'
          : 'numeric';
        
        flowNodes.push({
          id: fieldNodeId,
          type: 'field',
          position: { x: FIELD_X, y: yPos - 20 },
          data: { 
            label: `${endpoint} fields`,
            fields: fields,
            source: 'FMP',
            dataType: dataType,
            endpoint: endpoint,
          },
        });

        // Connect endpoint to fields
        flowEdges.push({
          id: `edge-${endpoint}-fields`,
          source: `endpoint-${endpoint}`,
          target: fieldNodeId,
          type: 'smoothstep',
          style: { stroke: '#10B981', strokeWidth: 1 },
        });
        
        fieldNodeIndex++;
      }
    });

    return { initialNodes: flowNodes, initialEdges: flowEdges, hasData: true };
  }, [datasets]);

  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds));
    },
    []
  );

  if (!hasData) return null;

  const uniqueSymbols = new Set(datasets.map(d => d.symbol)).size;
  const totalFields = new Set(datasets.flatMap(d => d.fields)).size;

  return (
    <div style={{ width: '100%', height: '100%' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-gray-700">Data Flow</span>
          <span className="text-xs text-gray-400">{uniqueSymbols} symbols, {datasets.length} datasets, {totalFields} fields</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-[#3B82F6]" />
          <span className="text-[10px] text-gray-500">Symbol</span>
          <div className="w-2.5 h-2.5 rounded-sm bg-gray-300 ml-2" />
          <span className="text-[10px] text-gray-500">Endpoint</span>
          <div className="w-2.5 h-2.5 rounded-sm bg-[#10B981] ml-2" />
          <span className="text-[10px] text-gray-500">Fields</span>
        </div>
      </div>

      {/* Graph */}
      <div style={{ width: '100%', height: `calc(100% - 36px)` }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          style={{ background: '#FAFAFA' }}
          nodesDraggable={true}
          nodesConnectable={false}
          elementsSelectable={true}
          panOnDrag={true}
          zoomOnScroll={true}
          minZoom={0.4}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={12} size={1} color="#E5E7EB" />
          <Controls />
          <MiniMap 
            nodeColor={(node) => {
              if (node.type === 'data') return '#3B82F6';
              if (node.type === 'field') return '#10B981';
              return '#9CA3AF';
            }}
            style={{ background: '#fff', border: '1px solid #E5E7EB' }}
          />
        </ReactFlow>
      </div>
    </div>
  );
}

export default function OntologyGraph(props: OntologyGraphProps) {
  return (
    <ReactFlowProvider>
      <OntologyGraphInner {...props} />
    </ReactFlowProvider>
  );
}

export { OntologyGraph };
