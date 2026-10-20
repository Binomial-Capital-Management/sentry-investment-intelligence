import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { X } from 'lucide-react';
import { DraggableDatasetItem, type DraggableDataset } from './DraggableDatasetItem';
import { DraggableToolResultItem, type DraggableToolResult } from './DraggableToolResultItem';
import { DraggablePivotItem, type DraggablePivot } from './DraggablePivotItem';
import { DraggableChartItem, type DraggableChart } from './DraggableChartItem';

// Canvas design tokens
const TEXT_200 = '60 2.5% 23.3%';
const BORDER_200 = '30 3.3% 11.8%';
const BG_300 = '210 10% 87%';
const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";

interface DatasetGroup {
  id: string;
  name: string;
}

interface DroppableGroupSectionProps {
  group: DatasetGroup;
  datasets: DraggableDataset[];
  toolResults?: DraggableToolResult[];
  activeToolResultId?: string;
  onToolResultClick?: (localId: string) => void;
  onRemoveToolResult?: (result: DraggableToolResult) => void;
  pivots?: DraggablePivot[];
  activePivotLocalId?: string;
  onPivotClick?: (localId: string) => void;
  onRemovePivot?: (pivot: DraggablePivot) => void;
  charts?: DraggableChart[];
  activeChartLocalId?: string;
  onChartClick?: (localId: string) => void;
  onRemoveChart?: (chart: DraggableChart) => void;
  isActive: boolean;
  canDelete: boolean;
  onActivate: () => void;
  onRename: (name: string) => void;
  onDelete: () => void;
  onClear: () => void;
  onRemoveDataset: (id: string) => void;
  onDatasetClick: (dataset: DraggableDataset) => void;
  mergedDatasetIds?: Set<string>;
  mergeableIds?: Set<string>;
  onToggleMerge?: (datasetId: string) => void;
  currentDatasetId?: string;
  mergeAnchorDatasetId?: string;
}

export function DroppableGroupSection({
  group,
  datasets,
  toolResults = [],
  activeToolResultId,
  onToolResultClick,
  onRemoveToolResult,
  pivots = [],
  activePivotLocalId,
  onPivotClick,
  onRemovePivot,
  charts = [],
  activeChartLocalId,
  onChartClick,
  onRemoveChart,
  isActive,
  canDelete,
  onActivate,
  onRename,
  onDelete,
  onClear,
  onRemoveDataset,
  onDatasetClick,
  mergedDatasetIds,
  mergeableIds,
  onToggleMerge,
  currentDatasetId,
  mergeAnchorDatasetId,
}: DroppableGroupSectionProps) {
  const { setNodeRef, isOver } = useDroppable({ id: group.id });
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(group.name);
  const [headerHovered, setHeaderHovered] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const [fades, setFades] = useState({ top: false, bottom: false });

  const updateFades = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    setFades({
      top: el.scrollTop > 2,
      bottom: el.scrollTop + el.clientHeight < el.scrollHeight - 2,
    });
  }, []);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    updateFades();
    el.addEventListener('scroll', updateFades, { passive: true });
    return () => el.removeEventListener('scroll', updateFades);
  }, [updateFades, datasets.length]);

  const anchorId = mergeAnchorDatasetId ?? currentDatasetId;
  const hasMerge = mergedDatasetIds && mergedDatasetIds.size > 0 && anchorId;
  const mergedCluster = useMemo(() => {
    if (!hasMerge) return [];
    return datasets.filter(ds => ds.id === anchorId || mergedDatasetIds!.has(ds.id));
  }, [hasMerge, datasets, anchorId, mergedDatasetIds]);
  const unmergedDatasets = useMemo(() => {
    if (!hasMerge) return datasets;
    return datasets.filter(ds => ds.id !== anchorId && !mergedDatasetIds!.has(ds.id));
  }, [hasMerge, datasets, anchorId, mergedDatasetIds]);

  const handleRename = () => {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== group.name) {
      onRename(trimmed);
    } else {
      setEditName(group.name);
    }
    setEditing(false);
  };

  return (
    <div
      ref={setNodeRef}
      style={{
        borderRadius: '0.5rem',
        transition: 'all 0.15s ease',
        border: `0.5px solid hsl(${BORDER_200} / ${isActive ? '20%' : '12%'})`,
        background: isActive
            ? `hsl(${BORDER_200} / 5%)`
            : 'transparent',
      }}
    >
      {/* Group header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.375rem',
          padding: '0.375rem 0.625rem',
          cursor: 'pointer',
          borderRadius: '0.5rem',
          transition: 'background-color 0.1s ease',
          backgroundColor: isActive
            ? `hsl(${BORDER_200} / 6%)`
            : headerHovered
              ? `hsl(${BG_300})`
              : 'transparent',
        }}
        onClick={onActivate}
        onMouseEnter={() => setHeaderHovered(true)}
        onMouseLeave={() => setHeaderHovered(false)}
      >
        <span style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          flexShrink: 0,
          backgroundColor: isActive ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 25%)`,
          transition: 'background-color 0.15s ease',
        }} />

        {editing ? (
          <input
            autoFocus
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={handleRename}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleRename();
              if (e.key === 'Escape') { setEditName(group.name); setEditing(false); }
            }}
            onClick={(e) => e.stopPropagation()}
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              fontFamily: FONT_UI,
              color: `hsl(${TEXT_200})`,
              background: '#fff',
              border: `0.5px solid hsl(${BORDER_200} / 30%)`,
              borderRadius: '0.25rem',
              padding: '0.125rem 0.375rem',
              outline: 'none',
              width: 96,
            }}
          />
        ) : (
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              fontFamily: FONT_UI,
              color: `hsl(${TEXT_200} / ${isActive ? '80%' : '55%'})`,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            onDoubleClick={(e) => { e.stopPropagation(); setEditName(group.name); setEditing(true); }}
            title="Double-click to rename"
          >
            {group.name}
          </span>
        )}

        <span style={{
          fontSize: '0.6875rem',
          color: `hsl(${TEXT_200} / 30%)`,
          flexShrink: 0,
        }}>
          ({datasets.length + toolResults.length + pivots.length + charts.length})
        </span>

        <div style={{ flex: 1 }} />

        {canDelete && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            style={{
              padding: 2,
              color: `hsl(${TEXT_200} / 25%)`,
              background: 'transparent',
              border: 'none',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              display: 'flex',
              transition: 'color 0.1s ease',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = `hsl(${TEXT_200} / 50%)`; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = `hsl(${TEXT_200} / 25%)`; }}
            title="Delete group"
          >
            <X style={{ width: 13, height: 13 }} />
          </button>
        )}
      </div>

      {/* Datasets list */}
      <div style={{ position: 'relative', minHeight: 24 }}>
        {fades.top && (
          <div style={{
            pointerEvents: 'none', position: 'absolute', top: 0, left: 0, right: 0,
            height: 20, zIndex: 10, background: 'linear-gradient(to bottom, #fff, transparent)',
          }} />
        )}
        {fades.bottom && (
          <div style={{
            pointerEvents: 'none', position: 'absolute', bottom: 0, left: 0, right: 0,
            height: 20, zIndex: 10, background: 'linear-gradient(to top, #fff, transparent)',
          }} />
        )}
        <div ref={listRef} style={{ maxHeight: 210, overflowY: 'auto' }}>
          {datasets.length === 0 && toolResults.length === 0 && pivots.length === 0 && charts.length === 0 ? (
            <div style={{
              padding: '0.5rem 0.75rem',
              fontSize: '0.6875rem',
              fontFamily: FONT_UI,
              fontStyle: 'italic',
              textAlign: 'center',
              color: `hsl(${TEXT_200} / 30%)`,
              borderTop: `0.5px dashed hsl(${BORDER_200} / 15%)`,
            }}>
              Drop datasets, analyses, pivots, or charts here
            </div>
          ) : (
            <>
              {/* Merged cluster — grouped in a shared container */}
              {mergedCluster.length > 1 && (
                <div style={{
                  margin: '3px 0',
                  borderRadius: '0.5rem',
                  border: `0.5px solid hsl(${BORDER_200} / 18%)`,
                  backgroundColor: `hsl(${BORDER_200} / 4%)`,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    padding: '0.25rem 0.625rem 0.125rem',
                    fontSize: '0.5rem',
                    fontWeight: 600,
                    fontFamily: FONT_UI,
                    color: `hsl(${TEXT_200} / 35%)`,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.375rem',
                  }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={`hsl(${TEXT_200} / 35%)`} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="18" cy="18" r="3" />
                      <circle cx="6" cy="6" r="3" />
                      <path d="M6 21V9a9 9 0 0 0 9 9" />
                    </svg>
                    Merged
                  </div>
                  {mergedCluster.map((ds) => (
                    <DraggableDatasetItem
                      key={ds.id}
                      dataset={ds}
                      isActive={false}
                      isCurrent={ds.id === anchorId}
                      isMerged={mergedDatasetIds?.has(ds.id) ?? false}
                      isMergeable={mergeableIds?.has(ds.id) ?? false}
                      onToggleMerge={onToggleMerge}
                      onRemove={onRemoveDataset}
                      onClick={() => onDatasetClick(ds)}
                    />
                  ))}
                </div>
              )}
              {/* Unmerged datasets */}
              {unmergedDatasets.map((ds) => (
                <DraggableDatasetItem
                  key={ds.id}
                  dataset={ds}
                  isActive={ds.id === currentDatasetId}
                  isCurrent={ds.id === currentDatasetId}
                  isMerged={mergedDatasetIds?.has(ds.id) ?? false}
                  isMergeable={mergeableIds?.has(ds.id) ?? false}
                  onToggleMerge={onToggleMerge}
                  onRemove={onRemoveDataset}
                  onClick={() => onDatasetClick(ds)}
                />
              ))}
              {toolResults.map((tr) => (
                <DraggableToolResultItem
                  key={tr.localId}
                  result={tr}
                  isActive={tr.localId === activeToolResultId}
                  onClick={() => onToolResultClick?.(tr.localId)}
                  onRemove={onRemoveToolResult ? () => onRemoveToolResult(tr) : undefined}
                />
              ))}
              {pivots.map((pv) => (
                <DraggablePivotItem
                  key={pv.localId}
                  pivot={pv}
                  isActive={pv.localId === activePivotLocalId}
                  onClick={() => onPivotClick?.(pv.localId)}
                  onRemove={onRemovePivot ? () => onRemovePivot(pv) : undefined}
                />
              ))}
              {charts.map((ch) => (
                <DraggableChartItem
                  key={ch.localId}
                  chart={ch}
                  isActive={ch.localId === activeChartLocalId}
                  onClick={() => onChartClick?.(ch.localId)}
                  onRemove={onRemoveChart ? () => onRemoveChart(ch) : undefined}
                />
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
