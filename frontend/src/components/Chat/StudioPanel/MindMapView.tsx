/**
 * MindMapView - Interactive mind map visualization
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';

// Professional SVG Icons
const Icons = {
  ArrowLeft: ({ size = 18, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Plus: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  Minus: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  Expand: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M7 15l5 5 5-5M7 9l5-5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Download: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Fullscreen: ({ size = 16, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Chat: ({ size = 14, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

interface MindMapNode {
  id: string;
  label: string;
  children: string[];
  query?: string; // AI-generated query for this node
}

interface MindMapData {
  title: string;
  nodes: MindMapNode[];
}

interface MindMapViewProps {
  data: MindMapData;
  title: string;
  sourceCount?: number;
  onNodeClick: (nodeLabel: string) => void;
  onBack: () => void;
}

// Tooltip component for showing query preview
const NodeTooltip: React.FC<{
  query: string;
  position: { x: number; y: number } | null;
}> = ({ query, position }) => {
  if (!position) return null;
  
  // Truncate long queries
  const displayQuery = query.length > 100 ? query.slice(0, 100) + '...' : query;
  
  return (
    <div 
      className="fixed z-50 pointer-events-none animate-in fade-in duration-150"
      style={{ 
        left: position.x,
        top: position.y - 8,
        transform: 'translate(-50%, -100%)',
        maxWidth: 280,
      }}
    >
      <div className="bg-gray-900 text-white text-xs px-3 py-2 rounded-lg shadow-lg">
        <div className="flex items-center gap-1.5 text-gray-400 mb-1">
          <Icons.Chat size={10} className="flex-shrink-0" />
          <span className="font-medium">Click to ask:</span>
        </div>
        <p className="text-gray-100 leading-relaxed">{displayQuery}</p>
      </div>
      {/* Arrow pointing down (centered) */}
      <div 
        className="absolute w-2 h-2 bg-gray-900 rotate-45 left-1/2 -translate-x-1/2"
        style={{ bottom: -4 }}
      />
    </div>
  );
};

const MindMapView: React.FC<MindMapViewProps> = ({ 
  data, 
  title, 
  sourceCount = 1,
  onNodeClick, 
  onBack 
}) => {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set(['root']));
  const [zoom, setZoom] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<{ id: string; query: string; position: { x: number; y: number } } | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-dismiss onboarding after 6 seconds
  useEffect(() => {
    if (showOnboarding) {
      const timer = setTimeout(() => setShowOnboarding(false), 6000);
      return () => clearTimeout(timer);
    }
  }, [showOnboarding]);

  // Build node lookup
  const nodeMap = new Map<string, MindMapNode>();
  data.nodes.forEach(node => nodeMap.set(node.id, node));

  // Find root node
  const rootNode = data.nodes.find(n => n.id === 'root') || data.nodes[0];
  
  // Get direct children of root
  const rootChildren = rootNode?.children?.map(id => nodeMap.get(id)).filter(Boolean) as MindMapNode[] || [];

  const toggleExpand = (nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  // Get the query that would be sent for a node (for tooltip preview)
  const getNodeQuery = (node: MindMapNode): string => {
    if (node.query) {
      return node.query;
    }
    const overallTopic = rootNode?.label || title;
    const isRoot = node.id === 'root';
    
    if (isRoot) {
      return `Give me a comprehensive overview of "${node.label}". What are the main themes, key points, and important takeaways from my sources?`;
    }
    return `In the context of "${overallTopic}", explain "${node.label}" in detail. What specific information do my sources provide about this? Include any relevant data, examples, or insights.`;
  };

  const handleAnalyze = (node: MindMapNode) => {
    setShowOnboarding(false); // Dismiss onboarding after first click
    onNodeClick(getNodeQuery(node));
  };

  const handleNodeHover = (node: MindMapNode, e: React.MouseEvent) => {
    const query = getNodeQuery(node);
    // Get the node element's bounding rect for proper positioning
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setHoveredNode({
      id: node.id,
      query,
      position: { x: rect.left + rect.width / 2, y: rect.top }
    });
  };

  const handleNodeLeave = () => {
    setHoveredNode(null);
  };

  const isRootExpanded = expandedNodes.has('root');

  // Handle trackpad/wheel - pinch to zoom, scroll to pan
  const handleWheel = useCallback((e: WheelEvent) => {
    // Pinch zoom (ctrl+scroll or trackpad pinch)
    if (e.ctrlKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.05 : 0.05;
      setZoom(z => Math.min(2, Math.max(0.3, z + delta)));
    }
    // Regular scroll pans the view (handled by overflow:auto)
  }, []);

  // Attach wheel listener for zoom
  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.addEventListener('wheel', handleWheel, { passive: false });
      return () => container.removeEventListener('wheel', handleWheel);
    }
  }, [handleWheel]);

  // Click and drag to pan
  const handleMouseDown = (e: React.MouseEvent) => {
    // Only start pan if clicking on the background, not on nodes
    if ((e.target as HTMLElement).closest('button, [data-node]')) return;
    setIsPanning(true);
    setPanStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;
    setPanOffset({
      x: e.clientX - panStart.x,
      y: e.clientY - panStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const handleMouseLeave = () => {
    setIsPanning(false);
  };

  // Calculate SVG path for curved connectors
  const getConnectorPath = (index: number, total: number) => {
    const startX = 0;
    const startY = (total * 60) / 2; // Center point
    const endX = 50;
    const endY = index * 60 + 24; // Center of each child node
    const controlX = 25;
    
    return `M ${startX} ${startY} Q ${controlX} ${startY} ${controlX} ${endY} L ${endX} ${endY}`;
  };

  return (
    <div className="flex flex-col h-full bg-[#FAFAFA]">
      {/* Header */}
      <div className="px-4 py-3 bg-white border-b border-gray-100 flex items-center gap-3">
        <button
          onClick={onBack}
          className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
          title="Back to Studio"
        >
          <Icons.ArrowLeft size={18} className="text-gray-600" />
        </button>
        <div>
          <h1 className="text-base font-medium text-gray-900">{title}</h1>
          <p className="text-xs text-gray-500">Based on {sourceCount} source{sourceCount !== 1 ? 's' : ''}</p>
        </div>
      </div>

      {/* Mind Map Content */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-auto relative"
        style={{ 
          padding: '60px 40px',
          cursor: isPanning ? 'grabbing' : 'grab',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
      >
        <div 
          className="inline-flex items-center"
          style={{ 
            transform: `scale(${zoom}) translate(${panOffset.x / zoom}px, ${panOffset.y / zoom}px)`, 
            transformOrigin: 'top left',
            minWidth: 'max-content',
            transition: isPanning ? 'none' : 'transform 0.1s ease-out',
          }}
        >
          {/* Root Node */}
          <div className="flex items-center">
            <div 
              data-node="true"
              className="group relative px-5 py-3 rounded-lg text-sm font-medium text-white cursor-pointer select-none transition-all duration-150 hover:scale-[1.02] hover:shadow-md"
              style={{ backgroundColor: '#B8A9C9' }}
              onClick={() => handleAnalyze(rootNode)}
              onMouseEnter={(e) => handleNodeHover(rootNode, e)}
              onMouseLeave={handleNodeLeave}
            >
              <span className="flex items-center gap-2">
                {rootNode?.label || title}
                <Icons.Chat size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
              </span>
            </div>
            <button
              onClick={() => toggleExpand('root')}
              className="ml-2 w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold"
              style={{ backgroundColor: '#9F8FBF' }}
            >
              {isRootExpanded ? '<' : '>'}
            </button>
          </div>

          {/* Connector Lines + Children */}
          {isRootExpanded && rootChildren.length > 0 && (
            <div className="flex items-center ml-1">
              {/* SVG Curved Connectors */}
              <svg 
                width="50" 
                height={rootChildren.length * 60}
                className="flex-shrink-0"
                style={{ marginRight: '-1px' }}
              >
                {rootChildren.map((_, index) => (
                  <path
                    key={index}
                    d={getConnectorPath(index, rootChildren.length)}
                    fill="none"
                    stroke="#D4D4D8"
                    strokeWidth="1.5"
                  />
                ))}
              </svg>

              {/* Child Nodes */}
              <div className="flex flex-col" style={{ gap: '12px' }}>
                {rootChildren.map((child) => {
                  const hasGrandchildren = child.children && child.children.length > 0;
                  const isExpanded = expandedNodes.has(child.id);
                  const grandchildren = hasGrandchildren 
                    ? child.children.map(id => nodeMap.get(id)).filter(Boolean) as MindMapNode[]
                    : [];

                  return (
                    <div key={child.id} className="flex items-center">
                      {/* Child Node */}
                      <div 
                        data-node="true"
                        className="group px-4 py-2.5 rounded-lg text-sm font-medium cursor-pointer select-none transition-all duration-150 hover:scale-[1.02] hover:shadow-md"
                        style={{ 
                          backgroundColor: '#DBEAFE',
                          color: '#1E40AF',
                        }}
                        onClick={() => handleAnalyze(child)}
                        onMouseEnter={(e) => handleNodeHover(child, e)}
                        onMouseLeave={handleNodeLeave}
                      >
                        <span className="flex items-center gap-2">
                          {child.label}
                          <Icons.Chat size={11} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                        </span>
                      </div>
                      
                      {/* Expand Button */}
                      <button
                        onClick={() => hasGrandchildren ? toggleExpand(child.id) : handleAnalyze(child)}
                        className="ml-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
                        style={{ 
                          backgroundColor: '#BFDBFE',
                          color: '#1E40AF',
                        }}
                      >
                        {hasGrandchildren ? (isExpanded ? '<' : '>') : '>'}
                      </button>

                      {/* Grandchildren */}
                      {hasGrandchildren && isExpanded && (
                        <div className="flex items-center ml-1">
                          <svg width="40" height={grandchildren.length * 50} className="flex-shrink-0">
                            {grandchildren.map((_, idx) => {
                              const sy = (grandchildren.length * 50) / 2;
                              const ey = idx * 50 + 20;
                              return (
                                <path
                                  key={idx}
                                  d={`M 0 ${sy} Q 20 ${sy} 20 ${ey} L 40 ${ey}`}
                                  fill="none"
                                  stroke="#D4D4D8"
                                  strokeWidth="1.5"
                                />
                              );
                            })}
                          </svg>
                          <div className="flex flex-col" style={{ gap: '10px' }}>
                            {grandchildren.map((gc) => (
                              <div 
                                key={gc.id}
                                data-node="true"
                                className="group px-4 py-2 rounded-lg text-sm cursor-pointer transition-all duration-150 hover:scale-[1.02] hover:shadow-md"
                                style={{ 
                                  backgroundColor: '#DBEAFE',
                                  color: '#1E40AF',
                                }}
                                onClick={() => handleAnalyze(gc)}
                                onMouseEnter={(e) => handleNodeHover(gc, e)}
                                onMouseLeave={handleNodeLeave}
                              >
                                <span className="flex items-center gap-2">
                                  {gc.label}
                                  <Icons.Chat size={10} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tooltip for hovered node */}
      <NodeTooltip 
        query={hoveredNode?.query || ''} 
        position={hoveredNode?.position || null} 
      />

      {/* Onboarding hint - shows on first load */}
      {showOnboarding && (
        <div className="absolute left-1/2 top-24 -translate-x-1/2 z-40 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="bg-blue-600 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg flex items-center gap-3">
            <Icons.Chat size={16} className="flex-shrink-0" />
            <span>Click any topic to explore it in chat</span>
            <button 
              onClick={() => setShowOnboarding(false)}
              className="ml-2 hover:bg-blue-500 rounded p-1 transition-colors"
            >
              <svg width={14} height={14} viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1.5 w-3 h-3 bg-blue-600 rotate-45" />
        </div>
      )}

      {/* Footer */}
      <div className="px-6 py-3 bg-white border-t border-gray-100 flex items-center justify-center gap-2">
        <Icons.Chat size={14} className="text-gray-400" />
        <p className="text-xs text-gray-500">Hover to preview question • Click to send to chat</p>
      </div>

      {/* Floating Controls (Right Side) */}
      <div className="absolute right-6 top-20 flex flex-col gap-1 bg-white rounded-lg shadow-sm border border-gray-200 p-1">
        <button 
          onClick={() => { setZoom(1); setPanOffset({ x: 0, y: 0 }); }} 
          className="p-2 hover:bg-gray-100 rounded" 
          title="Reset View"
        >
          <Icons.Expand size={16} className="text-gray-500" />
        </button>
        <button onClick={() => setZoom(z => Math.min(2, z + 0.15))} className="p-2 hover:bg-gray-100 rounded" title="Zoom In">
          <Icons.Plus size={16} className="text-gray-500" />
        </button>
        <button onClick={() => setZoom(z => Math.max(0.3, z - 0.15))} className="p-2 hover:bg-gray-100 rounded" title="Zoom Out">
          <Icons.Minus size={16} className="text-gray-500" />
        </button>
      </div>

      {/* Top Right Controls */}
      <div className="absolute right-6 top-4 flex items-center gap-2">
        <button className="p-2 hover:bg-gray-100 rounded" title="Fullscreen">
          <Icons.Fullscreen size={16} className="text-gray-500" />
        </button>
        <button className="p-2 hover:bg-gray-100 rounded" title="Download">
          <Icons.Download size={16} className="text-gray-500" />
        </button>
      </div>
    </div>
  );
};

export default MindMapView;
