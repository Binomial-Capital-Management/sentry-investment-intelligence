import { useState } from 'react';
import { useDraggable } from '@dnd-kit/core';
import { Tooltip } from '@/features/canvas/shared/Tooltip';

const TEXT_200 = '60 2.5% 23.3%';
const BORDER_200 = '30 3.3% 11.8%';
const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const FONT_MONO = "'SF Mono', 'Cascadia Code', 'JetBrains Mono', 'Roboto Mono', monospace";

export interface DraggableDataset {
  id: string;
  symbol: string;
  endpoint: string;
  params: Record<string, string>;
  fields: string[];
  compatibilityGroup?: string;
  groupId?: string;
}

interface DraggableDatasetItemProps {
  dataset: DraggableDataset;
  isActive: boolean;
  isCurrent?: boolean;
  isMerged?: boolean;
  isMergeable?: boolean;
  onToggleMerge?: (datasetId: string) => void;
  onRemove: (id: string) => void;
  onClick: () => void;
}

export function DraggableDatasetItem({ dataset, isActive, isCurrent, isMerged, isMergeable, onToggleMerge, onRemove, onClick }: DraggableDatasetItemProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: dataset.id,
    data: { dataset },
  });
  const [hovered, setHovered] = useState(false);
  const showMerge = isMergeable && !isCurrent && onToggleMerge;
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: '0.5rem',
        margin: '3px 0',
        padding: '0.375rem 0.625rem',
        fontFamily: FONT_UI,
        fontSize: '0.688rem',
        borderRadius: '0.5rem',
        cursor: 'pointer',
        opacity: isDragging ? 0.4 : 1,
        border: isActive
          ? `0.5px solid hsl(${BORDER_200} / 18%)`
          : '0.5px solid transparent',
        backgroundColor: isActive
          ? `hsl(${BORDER_200} / 6%)`
          : hovered
            ? `hsl(${BORDER_200} / 4%)`
            : 'transparent',
        transition: 'all 0.1s ease',
      }}
    >
      {/* Symbol chip */}
      <span style={{
        fontWeight: 600,
        fontSize: '0.75rem',
        color: `hsl(${TEXT_200})`,
        flexShrink: 0,
      }}>
        {dataset.symbol}
      </span>

      {/* Endpoint name */}
      <span style={{
        fontFamily: FONT_MONO,
        fontSize: '0.6875rem',
        color: `hsl(${TEXT_200} / 55%)`,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        flex: 1,
      }}>
        {dataset.endpoint}
      </span>

      {/* Merge toggle */}
      {showMerge && (
        <Tooltip label={isMerged ? 'Unmerge from current dataset' : 'Merge into current dataset view'}>
          <button
            onClick={(e) => { e.stopPropagation(); onToggleMerge!(dataset.id); }}
            style={{
              flexShrink: 0,
              padding: 0,
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: isMerged ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 40%)`,
              transition: 'all 0.1s ease',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = `hsl(${TEXT_200} / 70%)`; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = isMerged ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 40%)`; }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
              <circle cx="18" cy="18" r="3" />
              <circle cx="6" cy="6" r="3" />
              <path d="M6 21V9a9 9 0 0 0 9 9" />
            </svg>
          </button>
        </Tooltip>
      )}

      {/* Remove — only on hover, only if no merge toggle */}
      {!showMerge && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(dataset.id); }}
          style={{
            flexShrink: 0,
            padding: 0,
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: `hsl(${TEXT_200} / 20%)`,
            opacity: hovered ? 1 : 0,
            transition: 'all 0.1s ease',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = `hsl(${TEXT_200} / 50%)`; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = `hsl(${TEXT_200} / 20%)`; }}
          title="Remove"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}

/** Static version for DragOverlay */
export function DatasetItemOverlay({ dataset }: { dataset: DraggableDataset }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      padding: '0.375rem 0.625rem',
      fontFamily: FONT_UI,
      fontSize: '0.688rem',
      backgroundColor: '#fff',
      borderRadius: '0.5rem',
      boxShadow: '0px 4px 12px rgba(0,0,0,0.12)',
      border: `0.5px solid hsl(${BORDER_200} / 25%)`,
      transform: 'rotate(1deg)',
    }}>
      <span style={{ fontWeight: 600, fontSize: '0.75rem', color: `hsl(${TEXT_200})` }}>{dataset.symbol}</span>
      <span style={{ fontFamily: FONT_MONO, fontSize: '0.6875rem', color: `hsl(${TEXT_200} / 55%)`, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{dataset.endpoint}</span>
    </div>
  );
}
