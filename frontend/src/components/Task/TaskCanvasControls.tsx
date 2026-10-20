import React from 'react';
import { useReactFlow } from 'reactflow';
import { ZoomIn, ZoomOut, Maximize2, MousePointer2, Trash2, Square } from 'lucide-react';

interface TaskCanvasControlsProps {
  onSave?: () => void;
  onRun?: () => void;
  selectedCount?: number;
  onDeleteSelected?: () => void;
  selectionMode?: boolean;
  onSelectionModeChange?: (mode: boolean) => void;
}

export const TaskCanvasControls: React.FC<TaskCanvasControlsProps> = ({
  onSave,
  onRun,
  selectedCount = 0,
  onDeleteSelected,
  selectionMode = false,
  onSelectionModeChange,
}) => {
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  const handleZoomIn = () => {
    zoomIn({ duration: 200 });
  };

  const handleZoomOut = () => {
    zoomOut({ duration: 200 });
  };

  const handleFitView = () => {
    fitView({ duration: 200, padding: 0.2 });
  };

  return (
    <div style={{
      position: 'absolute',
      bottom: '16px',
      left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      background: '#FFFFFF',
      borderRadius: '8px',
      padding: '8px',
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
      zIndex: 10,
    }}>
      {/* Cursor Button - Normal Mode */}
      <button
        onClick={() => onSelectionModeChange?.(false)}
        style={{
          background: !selectionMode ? '#E0E7FF' : 'transparent',
          border: 'none',
          padding: '6px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '4px',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => {
          if (selectionMode) e.currentTarget.style.background = '#F3F4F6';
        }}
        onMouseLeave={(e) => {
          if (selectionMode) e.currentTarget.style.background = 'transparent';
        }}
        title="Normal Mode"
      >
        <MousePointer2 size={16} color={!selectionMode ? '#4F46E5' : '#6B7280'} />
      </button>

      {/* Box Select Button */}
      <button
        onClick={() => onSelectionModeChange?.(true)}
        style={{
          background: selectionMode ? '#E0E7FF' : 'transparent',
          border: 'none',
          padding: '6px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '4px',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => {
          if (!selectionMode) e.currentTarget.style.background = '#F3F4F6';
        }}
        onMouseLeave={(e) => {
          if (!selectionMode) e.currentTarget.style.background = 'transparent';
        }}
        title="Box Select Mode"
      >
        <Square size={16} color={selectionMode ? '#4F46E5' : '#6B7280'} strokeDasharray="3 3" />
      </button>

      {/* Delete Button - Only visible when nodes are selected */}
      {selectedCount > 0 && (
        <>
          <div style={{
            width: '1px',
            height: '20px',
            background: '#E5E7EB',
          }} />
          <button
            onClick={onDeleteSelected}
            style={{
              background: 'transparent',
              border: 'none',
              padding: '6px 8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              borderRadius: '4px',
              transition: 'background 0.2s',
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = '#FEE2E2'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            title={`Delete ${selectedCount} selected node${selectedCount > 1 ? 's' : ''}`}
          >
            <Trash2 size={16} color="#EF4444" />
            <span style={{ fontSize: '12px', color: '#EF4444', fontWeight: '500' }}>
              {selectedCount}
            </span>
          </button>
        </>
      )}

      {/* Separator */}
      <div style={{
        width: '1px',
        height: '20px',
        background: '#E5E7EB',
      }} />

      {/* Zoom Out */}
      <button
        onClick={handleZoomOut}
        style={{
          background: 'transparent',
          border: 'none',
          padding: '6px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '4px',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = '#F3F4F6'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        title="Zoom Out"
      >
        <ZoomOut size={16} color="#6B7280" />
      </button>

      {/* Zoom In */}
      <button
        onClick={handleZoomIn}
        style={{
          background: 'transparent',
          border: 'none',
          padding: '6px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '4px',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = '#F3F4F6'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        title="Zoom In"
      >
        <ZoomIn size={16} color="#6B7280" />
      </button>

      {/* Fit View */}
      <button
        onClick={handleFitView}
        style={{
          background: 'transparent',
          border: 'none',
          padding: '6px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '4px',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = '#F3F4F6'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        title="Fit View"
      >
        <Maximize2 size={16} color="#6B7280" />
      </button>
    </div>
  );
};
