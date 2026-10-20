import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown } from 'lucide-react';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import { useDataWorkspaceStore, type DatasetConfig } from '../../stores/dataWorkspaceStore';
import {
  selectDatasets,
  selectDatasetGroups,
  selectActiveGroup,
  selectTotalDatasetCount,
} from '../../stores/selectors';
import { DroppableGroupSection } from './DroppableGroupSection';
import { DatasetItemOverlay, type DraggableDataset } from './DraggableDatasetItem';
import { ToolResultItemOverlay, type DraggableToolResult } from './DraggableToolResultItem';
import { PivotItemOverlay, type DraggablePivot } from './DraggablePivotItem';
import { ChartItemOverlay, type DraggableChart } from './DraggableChartItem';
import type { ContentViewType } from '../../stores/types';
import { mapBackendToTimeStructure, areStructuresCompatible } from '@/utils/compatibilityMatrix';

// Canvas design tokens (matching WorkspaceMenu / TabBar add-menu)
const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const BORDER_200 = '30 3.3% 11.8%';
const BG_300 = '210 10% 87%';

const hoverCSS = `
.ds-menu-new-group:hover { background-color: hsl(${BG_300}) !important; }
`;

interface ToolResultEntry {
  tabId: string;
  localId: string;
  toolId: string;
  processName: string;
  tickers: string[];
  groupId?: string;
}

interface PivotResultEntry {
  tabId: string;
  localId: string;
  name: string;
  summary?: string;
  groupId?: string;
}

interface ChartResultEntry {
  tabId: string;
  localId: string;
  name: string;
  chartType?: string;
  summary?: string;
  groupId?: string;
}

interface DatasetsDropdownProps {
  onRemove: (id: string) => void;
  onNavigate?: (idOrEndpoint: string) => void;
  onOpenSidebarWithEndpoint?: (endpoint: string, datasetId?: string) => void;
  toolResults?: ToolResultEntry[];
  onToolResultClick?: (localId: string) => void;
  onSwitchToDataView?: () => void;
  activeContentView?: ContentViewType;
  mergedDatasetIds?: Set<string>;
  mergeAnchorDatasetId?: string;
  onToggleMerge?: (datasetId: string) => void;
  currentDataset?: DatasetConfig;
  /** All saved pivots on the active tab, grouped into the dropdown by groupId. */
  pivotResults?: PivotResultEntry[];
  /** Callback when a pivot entry is clicked in the dropdown. */
  onPivotClick?: (localId: string) => void;
  /** All saved charts on the active tab, grouped into the dropdown by groupId. */
  chartResults?: ChartResultEntry[];
  /** Callback when a chart entry is clicked in the dropdown. */
  onChartClick?: (localId: string) => void;
}

export function DatasetsDropdown({
  onRemove,
  onNavigate,
  onOpenSidebarWithEndpoint,
  toolResults,
  onToolResultClick,
  onSwitchToDataView,
  activeContentView,
  mergedDatasetIds,
  mergeAnchorDatasetId,
  onToggleMerge,
  currentDataset,
  pivotResults,
  onPivotClick,
  chartResults,
  onChartClick,
}: DatasetsDropdownProps) {
  const allDatasets = useDataWorkspaceStore(selectDatasets);
  const groups = useDataWorkspaceStore(selectDatasetGroups);
  const activeGroup = useDataWorkspaceStore(selectActiveGroup);
  const totalCount = useDataWorkspaceStore(selectTotalDatasetCount);

  const removeDatasetGroup = useDataWorkspaceStore(s => s.removeDatasetGroup);
  const renameDatasetGroup = useDataWorkspaceStore(s => s.renameDatasetGroup);
  const setActiveGroup = useDataWorkspaceStore(s => s.setActiveGroup);
  const updateDataset = useDataWorkspaceStore(s => s.updateDataset);
  const removeDataset = useDataWorkspaceStore(s => s.removeDataset);
  const patchToolResult = useDataWorkspaceStore(s => s.patchToolResult);
  const removeToolResult = useDataWorkspaceStore(s => s.removeToolResult);
  const patchPivotResult = useDataWorkspaceStore(s => s.patchPivotResult);
  const removePivotResult = useDataWorkspaceStore(s => s.removePivotResult);
  const patchChartResult = useDataWorkspaceStore(s => s.patchChartResult);
  const removeChartResult = useDataWorkspaceStore(s => s.removeChartResult);

  const [open, setOpen] = useState(false);
  const [activeDragDataset, setActiveDragDataset] = useState<DraggableDataset | null>(null);
  const [activeDragToolResult, setActiveDragToolResult] = useState<DraggableToolResult | null>(null);
  const [activeDragPivot, setActiveDragPivot] = useState<DraggablePivot | null>(null);
  const [activeDragChart, setActiveDragChart] = useState<DraggableChart | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const savedScrollTop = useRef(0);

  useEffect(() => {
    if (!open) return;
    requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = savedScrollTop.current;
    });
    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (dropdownRef.current?.contains(target)) return;
      if (buttonRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [open]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const datasetsForGroup = useCallback(
    (groupId: string): DraggableDataset[] =>
      allDatasets.filter(d => d.groupId === groupId) as DraggableDataset[],
    [allDatasets]
  );

  const firstGroupId = groups[0]?.id;
  const toolResultsForGroup = useCallback(
    (groupId: string): DraggableToolResult[] => {
      if (!toolResults) return [];
      return toolResults.filter(tr =>
        tr.groupId === groupId || (!tr.groupId && groupId === firstGroupId)
      );
    },
    [toolResults, firstGroupId],
  );

  const pivotsForGroup = useCallback(
    (groupId: string): DraggablePivot[] => {
      if (!pivotResults) return [];
      return pivotResults
        .filter(pv =>
          pv.groupId === groupId || (!pv.groupId && groupId === firstGroupId)
        )
        .map(pv => ({
          tabId: pv.tabId,
          localId: pv.localId,
          name: pv.name,
          groupId: pv.groupId,
        }));
    },
    [pivotResults, firstGroupId],
  );

  const chartsForGroup = useCallback(
    (groupId: string): DraggableChart[] => {
      if (!chartResults) return [];
      return chartResults
        .filter(cr =>
          cr.groupId === groupId || (!cr.groupId && groupId === firstGroupId)
        )
        .map(cr => ({
          tabId: cr.tabId,
          localId: cr.localId,
          name: cr.name,
          chartType: cr.chartType,
          groupId: cr.groupId,
        }));
    },
    [chartResults, firstGroupId],
  );

  // When a tool-result is active, the group that owns it should show as active
  const activeToolResultGroupId = useMemo(() => {
    if (activeContentView?.type !== 'tool-result' || !toolResults) return null;
    const tr = toolResults.find(r => r.localId === activeContentView.resultLocalId);
    if (!tr) return null;
    return tr.groupId ?? firstGroupId ?? null;
  }, [activeContentView, toolResults, firstGroupId]);

  const activePivotGroupId = useMemo(() => {
    if (activeContentView?.type !== 'pivot' || !pivotResults) return null;
    const pv = pivotResults.find(r => r.localId === activeContentView.pivotLocalId);
    if (!pv) return null;
    return pv.groupId ?? firstGroupId ?? null;
  }, [activeContentView, pivotResults, firstGroupId]);

  const activeChartGroupId = useMemo(() => {
    if (activeContentView?.type !== 'chart' || !chartResults) return null;
    const cr = chartResults.find(r => r.localId === activeContentView.chartLocalId);
    if (!cr) return null;
    return cr.groupId ?? firstGroupId ?? null;
  }, [activeContentView, chartResults, firstGroupId]);

  const activePivotLocalId = activeContentView?.type === 'pivot'
    ? activeContentView.pivotLocalId
    : undefined;

  const activeChartLocalId = activeContentView?.type === 'chart'
    ? activeContentView.chartLocalId
    : undefined;

  // Compute which dataset IDs are mergeable with the current dataset
  const mergeableIds = useMemo(() => {
    if (!currentDataset || !onToggleMerge) return new Set<string>();
    const currentStructure = mapBackendToTimeStructure(currentDataset.structureType);
    if (currentStructure === 'none') return new Set<string>();
    const ids = new Set<string>();
    for (const d of allDatasets) {
      if (d.id === currentDataset.id) continue;
      if (areStructuresCompatible(currentStructure, mapBackendToTimeStructure(d.structureType))) {
        ids.add(d.id);
      }
    }
    return ids;
  }, [currentDataset, allDatasets, onToggleMerge]);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const data = event.active.data.current;
    setActiveDragDataset(data?.dataset ?? null);
    setActiveDragToolResult(data?.toolResult ?? null);
    setActiveDragPivot(data?.pivot ?? null);
    setActiveDragChart(data?.chart ?? null);
  }, []);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    setActiveDragDataset(null);
    setActiveDragToolResult(null);
    setActiveDragPivot(null);
    setActiveDragChart(null);
    const { active, over } = event;
    if (!over) return;

    const targetGroupId = over.id as string;

    const dataset = active.data.current?.dataset as DraggableDataset | undefined;
    if (dataset) {
      if (dataset.groupId === targetGroupId) return;
      updateDataset(dataset.id, { groupId: targetGroupId });
      return;
    }

    const toolResult = active.data.current?.toolResult as DraggableToolResult | undefined;
    if (toolResult) {
      if (toolResult.groupId === targetGroupId) return;
      patchToolResult(toolResult.tabId, toolResult.toolId, toolResult.localId, { groupId: targetGroupId });
      return;
    }

    const pivot = active.data.current?.pivot as DraggablePivot | undefined;
    if (pivot) {
      if (pivot.groupId === targetGroupId) return;
      patchPivotResult(pivot.tabId, pivot.localId, { groupId: targetGroupId });
      return;
    }

    const chart = active.data.current?.chart as DraggableChart | undefined;
    if (chart) {
      if (chart.groupId === targetGroupId) return;
      patchChartResult(chart.tabId, chart.localId, { groupId: targetGroupId });
    }
  }, [updateDataset, patchToolResult, patchPivotResult, patchChartResult]);

  const handleDatasetClick = useCallback((ds: DraggableDataset) => {
    const isCurrentlyViewing = activeContentView?.type === 'data'
      && (ds.id === currentDataset?.id || mergedDatasetIds?.has(ds.id));
    if (isCurrentlyViewing) {
      setOpen(false);
      return;
    }
    if (ds.groupId) setActiveGroup(ds.groupId);
    onNavigate?.(ds.id);
    onOpenSidebarWithEndpoint?.(ds.endpoint, ds.id);
    onSwitchToDataView?.();
    setOpen(false);
  }, [onNavigate, onOpenSidebarWithEndpoint, onSwitchToDataView, setActiveGroup, currentDataset, mergedDatasetIds, activeContentView]);

  const handleClearGroup = useCallback((groupId: string) => {
    const groupDatasets = allDatasets.filter(d => d.groupId === groupId);
    groupDatasets.forEach(ds => removeDataset(ds.id));
  }, [allDatasets, removeDataset]);


  const toolResultCount = toolResults?.length ?? 0;
  const pivotResultCount = pivotResults?.length ?? 0;
  const chartResultCount = chartResults?.length ?? 0;
  const combinedCount = totalCount + toolResultCount + pivotResultCount + chartResultCount;
  if (combinedCount === 0) return null;

  const getDropdownPosition = () => {
    if (!buttonRef.current) return { top: 0, left: 0 };
    const rect = buttonRef.current.getBoundingClientRect();
    return { top: rect.bottom + 6, left: rect.left };
  };

  return (
    <div className="ml-1">
      <button
        ref={buttonRef}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
        style={{
          fontFamily: FONT_UI,
          backgroundColor: open ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
          color: 'hsl(30 3.3% 11.8% / 85%)',
        }}
        onMouseEnter={e => { if (!open) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
        onMouseLeave={e => { if (!open) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
      >
        {activeContentView?.type === 'tool-result'
          ? (toolResults?.find(tr => tr.localId === activeContentView.resultLocalId)?.processName ?? 'Analysis')
          : activeContentView?.type === 'pivot'
            ? (() => {
                const pv = pivotResults?.find(pv => pv.localId === activeContentView.pivotLocalId);
                const name = pv?.name;
                return name && !name.startsWith('Pivot') ? `Pivot · ${name}` : (name ?? 'Pivot');
              })()
            : activeContentView?.type === 'chart'
              ? (() => {
                  const cr = chartResults?.find(cr => cr.localId === activeContentView.chartLocalId);
                  const name = cr?.name;
                  const raw = cr?.chartType || 'chart';
                  const type = raw.charAt(0).toUpperCase() + raw.slice(1) + ' Chart';
                  return name ? `${type} · ${name}` : type;
                })()
              : (activeGroup?.name ?? 'Data')}
        <ChevronDown
          size={13}
          strokeWidth={2}
          className={`transition-transform ${open ? 'rotate-180' : ''}`}
          style={{ color: 'hsl(30 3.3% 11.8% / 45%)' }}
        />
      </button>

      {open && createPortal(
        <>
          <style>{hoverCSS}</style>
          <div
            ref={dropdownRef}
            className="fixed overflow-hidden"
            style={{
              ...getDropdownPosition(),
              width: 272,
              maxHeight: 'min(60vh, 480px)',
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: '#fff',
              border: `0.5px solid hsl(${BORDER_200} / 30%)`,
              borderRadius: '1rem',
              boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
              fontFamily: FONT_UI,
              zIndex: 9999,
            }}
          >
            {/* Top fade */}
            <div className="pointer-events-none absolute top-0 left-0 right-0 h-3 z-10" style={{ background: 'linear-gradient(to bottom, white, transparent)', borderRadius: '1rem 1rem 0 0' }} />
            {/* Bottom fade */}
            <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-3 z-10" style={{ background: 'linear-gradient(to top, white, transparent)', borderRadius: '0 0 1rem 1rem' }} />

            <div
              ref={scrollRef}
              className="overflow-auto flex-1"
              style={{ padding: '0.375rem' }}
              onScroll={() => { if (scrollRef.current) savedScrollTop.current = scrollRef.current.scrollTop; }}
            >
            {/* Groups with drag-and-drop */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <DndContext
                sensors={sensors}
                collisionDetection={closestCorners}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
              >
                {groups.map((group) => (
                  <DroppableGroupSection
                    key={group.id}
                    group={group}
                    datasets={datasetsForGroup(group.id)}
                    toolResults={toolResultsForGroup(group.id)}
                    activeToolResultId={
                      activeContentView?.type === 'tool-result'
                        ? activeContentView.resultLocalId
                        : undefined
                    }
                    onToolResultClick={(localId) => { onToolResultClick?.(localId); setOpen(false); }}
                    onRemoveToolResult={(tr) => removeToolResult(tr.tabId, tr.toolId, tr.localId)}
                    pivots={pivotsForGroup(group.id)}
                    activePivotLocalId={activePivotLocalId}
                    onPivotClick={(localId) => { onPivotClick?.(localId); setOpen(false); }}
                    onRemovePivot={(pv) => removePivotResult(pv.tabId, pv.localId)}
                    charts={chartsForGroup(group.id)}
                    activeChartLocalId={activeChartLocalId}
                    onChartClick={(localId) => { onChartClick?.(localId); setOpen(false); }}
                    onRemoveChart={(ch) => removeChartResult(ch.tabId, ch.localId)}
                    isActive={
                      activeContentView?.type === 'tool-result'
                        ? activeToolResultGroupId === group.id
                        : activeContentView?.type === 'pivot'
                          ? activePivotGroupId === group.id
                          : activeContentView?.type === 'chart'
                            ? activeChartGroupId === group.id
                            : activeGroup?.id === group.id
                    }
                    canDelete={groups.length > 1}
                    onActivate={() => { setActiveGroup(group.id); onSwitchToDataView?.(); }}
                    onRename={(name) => renameDatasetGroup(group.id, name)}
                    onDelete={() => removeDatasetGroup(group.id)}
                    onClear={() => handleClearGroup(group.id)}
                    onRemoveDataset={onRemove}
                    onDatasetClick={handleDatasetClick}
                    mergedDatasetIds={activeContentView?.type === 'data' ? mergedDatasetIds : undefined}
                    mergeableIds={mergeableIds}
                    onToggleMerge={onToggleMerge}
                    currentDatasetId={activeContentView?.type === 'data' ? currentDataset?.id : undefined}
                    mergeAnchorDatasetId={mergeAnchorDatasetId}
                  />
                ))}

                <DragOverlay dropAnimation={null}>
                  {activeDragDataset ? <DatasetItemOverlay dataset={activeDragDataset} />
                    : activeDragToolResult ? <ToolResultItemOverlay result={activeDragToolResult} />
                    : activeDragPivot ? <PivotItemOverlay pivot={activeDragPivot} />
                    : activeDragChart ? <ChartItemOverlay chart={activeDragChart} />
                    : null}
                </DragOverlay>
              </DndContext>
            </div>
            </div>
          </div>
        </>,
        document.body
      )}
    </div>
  );
}

export default DatasetsDropdown;
