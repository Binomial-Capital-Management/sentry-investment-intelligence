import React, { useCallback, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  ConnectionMode,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useOntologyStore } from '@/stores/ontologyStore';
import type { OntologyObject, OntologyLink } from '@/types/ontology';
import './ontology-redesign.css';

// Node component for different object types
function CompanyNode({ data }: { data: any }) {
  const company = data.object;
  const isSelected = data.isSelected;

  return (
    <div className={`ontology-graph-node company-node ${isSelected ? 'selected' : ''}`}>
      <div className="ontology-node-header">
        <span className="ontology-node-type-tag">CO</span>
        <span className="ontology-node-ticker">{company.ticker}</span>
      </div>
      <div className="ontology-node-body">
        <div className="ontology-node-title">{company.name}</div>
        <div className="ontology-node-metrics">
          <span className={`ontology-node-change ${company.change >= 0 ? 'positive' : 'negative'}`}>
            {company.change >= 0 ? '+' : ''}{company.change.toFixed(2)}%
          </span>
          <span className="ontology-node-price">${company.price.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}

function PortfolioNode({ data }: { data: any }) {
  const portfolio = data.object;
  const isSelected = data.isSelected;

  return (
    <div className={`ontology-graph-node portfolio-node ${isSelected ? 'selected' : ''}`}>
      <div className="ontology-node-header">
        <span className="ontology-node-type-tag">PF</span>
        <span className="ontology-node-ticker">PORTFOLIO</span>
      </div>
      <div className="ontology-node-body">
        <div className="ontology-node-title">{portfolio.name}</div>
        <div className="ontology-node-metrics">
          <span className="ontology-node-value">
            ${(portfolio.total_value / 1e6).toFixed(2)}M
          </span>
          {portfolio.returns && (
            <span className={`ontology-node-change ${portfolio.returns.ytd >= 0 ? 'positive' : 'negative'}`}>
              {portfolio.returns.ytd >= 0 ? '+' : ''}{portfolio.returns.ytd.toFixed(2)}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function FilingNode({ data }: { data: any }) {
  const filing = data.object;
  const isSelected = data.isSelected;

  return (
    <div className={`ontology-graph-node filing-node ${isSelected ? 'selected' : ''}`}>
      <div className="ontology-node-header">
        <span className="ontology-node-type-tag">DOC</span>
        <span className="ontology-node-ticker">{filing.form_type}</span>
      </div>
      <div className="ontology-node-body">
        <div className="ontology-node-title">{filing.ticker}</div>
        <div className="ontology-node-subtitle">
          {new Date(filing.filing_date).toLocaleDateString()}
        </div>
      </div>
    </div>
  );
}

function OptionNode({ data }: { data: any }) {
  const option = data.object;
  const isSelected = data.isSelected;

  return (
    <div className={`ontology-graph-node option-node ${isSelected ? 'selected' : ''}`}>
      <div className="ontology-node-header">
        <span className="ontology-node-type-tag">OPT</span>
        <span className="ontology-node-ticker">{option.contract_type.toUpperCase()}</span>
      </div>
      <div className="ontology-node-body">
        <div className="ontology-node-title">{option.underlying}</div>
        <div className="ontology-node-subtitle">Strike: ${option.strike}</div>
        <div className="ontology-node-metrics">
          <span className="ontology-node-price">${option.last.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}

function GenericNode({ data }: { data: any }) {
  const object = data.object;
  const isSelected = data.isSelected;

  const typeTags: Record<string, string> = {
    position: 'POS',
    institutional_holder: 'INST',
    analysis_report: 'RPT',
  };

  return (
    <div className={`ontology-graph-node generic-node ${isSelected ? 'selected' : ''}`}>
      <div className="ontology-node-header">
        <span className="ontology-node-type-tag">{typeTags[object.type] || 'OBJ'}</span>
      </div>
      <div className="ontology-node-body">
        <div className="ontology-node-title">
          {object.name || object.ticker || object.id}
        </div>
        <div className="ontology-node-subtitle">{object.type.replace('_', ' ').toUpperCase()}</div>
      </div>
    </div>
  );
}

// Node type mapping
const nodeTypes = {
  company: CompanyNode,
  portfolio: PortfolioNode,
  sec_filing: FilingNode,
  option_contract: OptionNode,
  position: GenericNode,
  institutional_holder: GenericNode,
  analysis_report: GenericNode,
};

interface RelationshipGraphProps {
  className?: string;
}

export default function RelationshipGraph({ className = '' }: RelationshipGraphProps) {
  const { objects, links, viewState, setSelectedObject } = useOntologyStore();

  // Convert ontology objects to ReactFlow nodes
  const initialNodes: Node[] = useMemo(() => {
    const nodes: Node[] = [];
    const objectArray = Array.from(objects.values());

    // Filter by object type filters if active
    const filteredObjects = viewState.object_type_filters.length > 0
      ? objectArray.filter(obj => viewState.object_type_filters.includes(obj.type))
      : objectArray;

    // Filter by search query
    const searchQuery = viewState.search_query.toLowerCase();
    const finalObjects = searchQuery
      ? filteredObjects.filter(obj => {
          const searchableText = JSON.stringify(obj).toLowerCase();
          return searchableText.includes(searchQuery);
        })
      : filteredObjects;

    // Calculate positions in a circular layout
    const radius = 300;
    const centerX = 400;
    const centerY = 300;

    finalObjects.forEach((obj, index) => {
      const angle = (2 * Math.PI * index) / finalObjects.length;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);

      nodes.push({
        id: obj.id,
        type: obj.type,
        position: { x, y },
        data: {
          object: obj,
          isSelected: viewState.selected_object_id === obj.id,
        },
      });
    });

    return nodes;
  }, [objects, viewState.object_type_filters, viewState.search_query, viewState.selected_object_id]);

  // Convert ontology links to ReactFlow edges
  const initialEdges: Edge[] = useMemo(() => {
    const visibleNodeIds = new Set(initialNodes.map(n => n.id));

    return links
      .filter(link => visibleNodeIds.has(link.from_id) && visibleNodeIds.has(link.to_id))
      .map(link => ({
        id: link.id,
        source: link.from_id,
        target: link.to_id,
        type: 'smoothstep', // "Pipeline" style edges
        animated: link.type === 'peer_of',
        label: link.type.replace('_', ' '),
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 16,
          height: 16,
          color: getLinkColor(link.type),
        },
        style: {
          stroke: getLinkColor(link.type),
          strokeWidth: 1.5,
          opacity: 0.6,
        },
        labelStyle: {
          fill: '#9ca3af',
          fontSize: 10,
          fontWeight: 500,
          letterSpacing: '0.3px',
          fontFamily: 'var(--font-mono)',
        },
      }));
  }, [links, initialNodes]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes when data changes
  useMemo(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  // Update edges when data changes
  useMemo(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  // Handle node click
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const object = objects.get(node.id);
      if (object) {
        setSelectedObject(object.id, object.type);
      }
    },
    [objects, setSelectedObject],
  );

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    setSelectedObject(null, null);
  }, [setSelectedObject]);

  return (
    <div className={`ontology-graph-container ${className}`}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'default',
          animated: false,
        }}
        className="ontology-reactflow"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={0.5}
          color="#e5e7eb"
        />
        <Controls
          showZoom={true}
          showFitView={true}
          showInteractive={false}
          className="ontology-controls"
        />
      </ReactFlow>
    </div>
  );
}

// Helper function to get link color by type
function getLinkColor(linkType: string): string {
  const colors: Record<string, string> = {
    peer_of: '#3b82f6',      // Blue
    supplier_of: '#8b5cf6',  // Violet
    held_by: '#10b981',      // Emerald
    contains: '#ef4444',     // Red (Position)
    references: '#06b6d4',   // Cyan
    has_filing: '#f59e0b',   // Amber
    has_options: '#8b5cf6',  // Violet
    analyzes: '#6366f1',     // Indigo
    competes_with: '#ef4444', // Red
  };
  return colors[linkType] || '#94a3b8'; // Slate 400
}
