import { useState } from 'react';
import { useDraggable } from '@dnd-kit/core';

const TEXT_200 = '60 2.5% 23.3%';
const BORDER_200 = '30 3.3% 11.8%';
const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const FONT_MONO = "'SF Mono', 'Cascadia Code', 'JetBrains Mono', 'Roboto Mono', monospace";

export interface DraggableToolResult {
  tabId: string;
  localId: string;
  toolId: string;
  processName: string;
  tickers: string[];
  groupId?: string;
}

interface DraggableToolResultItemProps {
  result: DraggableToolResult;
  isActive: boolean;
  onClick: () => void;
  onRemove?: (localId: string) => void;
}

/**
 * Splits "Factor Analysis - ABCB" or "Monte Carlo Simulation - A, AA, AAPL"
 * into [toolLabel, tickersLabel] so the two-column row visually mirrors
 * DraggableDatasetItem's symbol/endpoint layout.
 */
function splitProcessName(name: string, fallback: string): { left: string; right: string } {
  const source = name || fallback;
  const idx = source.indexOf(' - ');
  if (idx === -1) return { left: source, right: '' };
  return { left: source.slice(0, idx), right: source.slice(idx + 3) };
}

export function DraggableToolResultItem({ result, isActive, onClick, onRemove }: DraggableToolResultItemProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `toolresult:${result.localId}`,
    data: { toolResult: result },
  });
  const [hovered, setHovered] = useState(false);
  const { left, right } = splitProcessName(result.processName, result.toolId);

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
      <span style={{
        fontWeight: 600,
        fontSize: '0.75rem',
        color: `hsl(${TEXT_200})`,
        flex: right ? '0 0 auto' : '1 1 0',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {left}
      </span>
      {right && (
        <span style={{
          fontFamily: FONT_MONO,
          fontSize: '0.6875rem',
          color: `hsl(${TEXT_200} / 55%)`,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          flex: 1,
        }}>
          {right}
        </span>
      )}
      {onRemove && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(result.localId); }}
          onPointerDown={(e) => e.stopPropagation()}
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
          title="Remove analysis"
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
export function ToolResultItemOverlay({ result }: { result: DraggableToolResult }) {
  const { left, right } = splitProcessName(result.processName, result.toolId);
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
      <span style={{ fontWeight: 600, fontSize: '0.75rem', color: `hsl(${TEXT_200})` }}>{left}</span>
      {right && (
        <span style={{
          fontFamily: FONT_MONO,
          fontSize: '0.6875rem',
          color: `hsl(${TEXT_200} / 55%)`,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {right}
        </span>
      )}
    </div>
  );
}
