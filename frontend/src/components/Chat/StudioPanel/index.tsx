/**
 * StudioPanel - NotebookLM-style Studio panel (exact replica)
 * 
 * 2x4 grid of generation options + list of generated artifacts
 */

import React, { useState } from 'react';
import { useUIStore, StudioArtifact } from '@/stores/uiStore';
import StudioModal from './StudioModal';
import MindMapView from './MindMapView';
import DataTableView from './DataTableView';
import ReportsView from './ReportsView';

// Professional SVG Icons
const Icons = {
  Close: ({ size = 18, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  Sparkles: ({ size = 18, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M19 13l.5 1.5 1.5.5-1.5.5-.5 1.5-.5-1.5L17 15l1.5-.5.5-1.5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M5 17l.5 1.5L7 19l-1.5.5L5 21l-.5-1.5L3 19l1.5-.5L5 17z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  MindMap: ({ size = 18, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="4" cy="6" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="20" cy="6" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="4" cy="18" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="20" cy="18" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M9.5 10L6 7.5M14.5 10L18 7.5M9.5 14L6 16.5M14.5 14L18 16.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  Document: ({ size = 18, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  Table: ({ size = 18, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Presentation: ({ size = 18, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="2" y="3" width="20" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 21l4-4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12 17v-4" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Edit: ({ size = 14, className = '' }: { size?: number; className?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

type GenerationType = 'mindmap' | 'report' | 'slides' | 'datatable';

interface StudioPanelProps {
  sessionId: string;
  onClose?: () => void;
  onSendToChat?: (message: string) => void;
}

// Generation type configurations
const generationTypes: { id: GenerationType; icon: React.ReactNode; label: string; beta?: boolean; disabled?: boolean }[] = [
  { id: 'mindmap', icon: <Icons.MindMap size={18} />, label: 'Mind Map' },
  { id: 'report', icon: <Icons.Document size={18} />, label: 'Reports' },
  { id: 'slides', icon: <Icons.Presentation size={18} />, label: 'Slide Deck', beta: true },
  { id: 'datatable', icon: <Icons.Table size={18} />, label: 'Data Table' },
];

const StudioPanel: React.FC<StudioPanelProps> = ({ sessionId, onClose, onSendToChat }) => {
  const [activeModal, setActiveModal] = useState<GenerationType | null>(null);
  const { studioArtifacts, activeStudioArtifact, setActiveStudioArtifact, removeStudioArtifact, selectedSources } = useUIStore();
  const sourceCount = selectedSources?.length || 0;

  const formatTimeAgo = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - new Date(date).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  const getArtifactIcon = (type: string) => {
    switch (type) {
      case 'mindmap': return <Icons.MindMap size={16} className="text-teal-600" />;
      case 'report': return <Icons.Document size={16} style={{ color: '#0051cc' }} />;
      case 'slides': return <Icons.Presentation size={16} className="text-orange-600" />;
      case 'datatable': return <Icons.Table size={16} className="text-blue-600" />;
      default: return <Icons.Sparkles size={16} className="text-gray-600" />;
    }
  };

  // Render artifact view if one is active
  if (activeStudioArtifact) {
    // MindMap has its own full UI - render without wrapper
    if (activeStudioArtifact.type === 'mindmap') {
      return (
        <MindMapView 
          data={activeStudioArtifact.data}
          title={activeStudioArtifact.data?.title || activeStudioArtifact.title}
          sourceCount={activeStudioArtifact.data?.sourceCount || 1}
          onNodeClick={(query) => {
            onSendToChat?.(query);
            // Keep mind map open so user can continue exploring
          }}
          onBack={() => setActiveStudioArtifact(null)}
        />
      );
    }

    // Report has its own full UI with fullscreen support
    if (activeStudioArtifact.type === 'report') {
      return (
        <ReportsView 
          data={activeStudioArtifact.data}
          title={activeStudioArtifact.title}
          onBack={() => setActiveStudioArtifact(null)}
        />
      );
    }

    // Other artifacts (datatable) need a wrapper with back button
    return (
      <div className="flex flex-col h-full bg-white">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <button
            onClick={() => setActiveStudioArtifact(null)}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Back to Studio
          </button>
          {onClose && (
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
              <Icons.Close size={18} className="text-gray-500" />
            </button>
          )}
        </div>
        <div className="flex-1 overflow-hidden p-4">
          {activeStudioArtifact.type === 'datatable' && (
            <DataTableView data={activeStudioArtifact.data} />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white" style={{ fontFamily: "'Google Sans', sans-serif" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Icons.Sparkles size={18} style={{ color: '#0051cc' }} />
          <span className="font-medium text-gray-900 text-base">Studio</span>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <Icons.Close size={18} className="text-gray-500" />
          </button>
        )}
      </div>

      {/* Generation Buttons - 2x2 Grid */}
      <div className="p-4">
        <div className="grid grid-cols-2 gap-2">
          {generationTypes.map((gen) => (
            <button
              key={gen.id}
              onClick={() => !gen.disabled && setActiveModal(gen.id)}
              disabled={gen.disabled}
              className={`flex items-center justify-between p-3 rounded-xl border transition-all group ${
                gen.disabled 
                  ? 'border-gray-100 bg-gray-50 opacity-50 cursor-not-allowed' 
                  : 'border-gray-200 hover:border-[#0051cc]/30 hover:bg-[#0051cc]/5'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={gen.disabled ? 'text-gray-400' : 'text-gray-600 group-hover:text-[#0051cc]'}>
                  {gen.icon}
                </span>
                <span className="text-sm text-gray-800">{gen.label}</span>
                {gen.beta && (
                  <span className="px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-700 rounded">
                    BETA
                  </span>
                )}
              </div>
              {!gen.disabled && (
                <Icons.Edit size={14} className="text-gray-400 group-hover:text-[#0051cc]" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Generated Artifacts List */}
      <div className="flex-1 overflow-y-auto border-t border-gray-100">
        {studioArtifacts.length > 0 ? (
          <div className="divide-y divide-gray-100">
            {studioArtifacts.map((artifact) => (
              <div
                key={artifact.id}
                onClick={() => setActiveStudioArtifact(artifact)}
                className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer group"
              >
                {getArtifactIcon(artifact.type)}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-800 truncate">{artifact.title}</div>
                  <div className="text-xs text-gray-500">
                    {artifact.sourceCount} source{artifact.sourceCount !== 1 ? 's' : ''} · {formatTimeAgo(artifact.createdAt)}
                  </div>
                </div>
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    removeStudioArtifact(artifact.id);
                  }}
                  className="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-100 rounded transition-colors"
                  title="Delete"
                >
                  <Icons.Close size={14} className="text-gray-400 hover:text-red-500" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full py-12 text-center px-6">
            <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
              <Icons.Sparkles size={20} className="text-gray-400" />
            </div>
            <p className="text-sm text-gray-700 mb-1">No artifacts yet</p>
            <p className="text-xs text-gray-500">Generate mind maps, reports, and more from your sources</p>
          </div>
        )}
      </div>

      {/* Modal */}
      {activeModal && (
        <StudioModal
          type={activeModal as 'mindmap' | 'report' | 'datatable' | 'slides'}
          sessionId={sessionId}
          onClose={() => setActiveModal(null)}
        />
      )}
    </div>
  );
};

export default StudioPanel;
