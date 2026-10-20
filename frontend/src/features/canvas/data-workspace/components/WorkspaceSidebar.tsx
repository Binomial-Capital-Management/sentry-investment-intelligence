/**
 * WorkspaceSidebar - Persistent sidebar that stays mounted across all view modes.
 *
 * Renders:
 * 1. ViewModeToggle at top (Sources / Analysis / Pivot / Chart)
 * 2. Mode-specific content below:
 *    - explorer: AddDatasetPanel
 *    - tools: ToolSourcesPanel (embedded)
 *    - pivot: placeholder
 *    - chart: placeholder
 * 3. Resize handle on right edge
 *
 * Open/close state uses the Zustand fieldPickerOpen field.
 * Width, resize, and animation state are local.
 */

import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useDataWorkspaceStore } from '../stores/dataWorkspaceStore';
import { selectActiveGroupDatasets } from '../stores/selectors';
import { AddDatasetPanel } from '../dataset-viewer/components';
import { ToolSourcesPanel } from '@/features/canvas/tool-workflow/components';
import { PivotTableCreator } from '../pivot-table';
import ChartCreator from '../chart/creator';
import ViewModeToggle from './ViewModeToggle';
import type { WorkspaceViewMode } from '../stores/types';

interface SelectedObject {
  symbol: string;
  name?: string;
  objectType: string;
}

interface WorkspaceSidebarProps {
  viewMode: WorkspaceViewMode;
  tabId?: string;
  onModeChange: (mode: WorkspaceViewMode) => void;
  selectedObjects: SelectedObject[];
  onRemoveDataset?: (id: string) => void;
  onNavigateToDataset: (endpoint: string) => void;
}

export default function WorkspaceSidebar({
  viewMode,
  tabId,
  onModeChange,
  selectedObjects,
  onRemoveDataset,
  onNavigateToDataset,
}: WorkspaceSidebarProps) {
  // Store state
  const showSidebar = useDataWorkspaceStore(s => s.fieldPickerOpen);
  const setShowSidebar = useDataWorkspaceStore(s => s.setFieldPickerOpen);
  const setTabMode = useDataWorkspaceStore(s => s.setTabMode);
  const addDatasetWithMetadata = useDataWorkspaceStore(s => s.addDatasetWithMetadata);
  const updateDataset = useDataWorkspaceStore(s => s.updateDataset);
  const sidebarInitialEndpoint = useDataWorkspaceStore(s => s.sidebarInitialEndpoint);
  const setSidebarInitialEndpoint = useDataWorkspaceStore(s => s.setSidebarInitialEndpoint);
  const sidebarInitialDatasetId = useDataWorkspaceStore(s => s.sidebarInitialDatasetId);
  const setSidebarInitialDatasetId = useDataWorkspaceStore(s => s.setSidebarInitialDatasetId);
  const datasets = useDataWorkspaceStore(selectActiveGroupDatasets);

  const tabs = useDataWorkspaceStore(s => s.tabs);
  const activeTabId = useDataWorkspaceStore(s => s.activeTabId);

  const activeTab = tabs.find(t => t.id === activeTabId);
  const activeContentView = activeTab?.contentView;
  const activePivotLocalId = activeContentView?.type === 'pivot' ? activeContentView.pivotLocalId : undefined;

  // Derived data for AddDatasetPanel
  const addedEndpoints = useMemo(() => new Set(datasets.map(d => d.endpoint)), [datasets]);
  const existingDatasets = useMemo(() => datasets.map(d => ({
    id: d.id,
    symbol: d.symbol,
    endpoint: d.endpoint,
    fields: d.fields,
    params: d.params,
  })), [datasets]);

  // Resizable sidebar
  const [sidebarWidth, setSidebarWidth] = useState(288);
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);

  // Transition overflow gate
  const [transitionDone, setTransitionDone] = useState(showSidebar);
  useEffect(() => {
    if (!showSidebar) {
      setTransitionDone(false);
    } else {
      const timer = setTimeout(() => setTransitionDone(true), 300);
      return () => clearTimeout(timer);
    }
  }, [showSidebar]);

  // Resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    resizeRef.current = { startX: e.clientX, startWidth: sidebarWidth };
  }, [sidebarWidth]);

  useEffect(() => {
    if (!isResizing) return;
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizeRef.current) return;
      const delta = e.clientX - resizeRef.current.startX;
      const newWidth = Math.max(200, Math.min(500, resizeRef.current.startWidth + delta));
      setSidebarWidth(newWidth);
    };
    const handleMouseUp = () => {
      setIsResizing(false);
      resizeRef.current = null;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  // Collapse handler
  const handleCollapse = useCallback(() => {
    setShowSidebar(false);
    if (viewMode === 'explorer' && tabId) {
      setTabMode(tabId, 'data');
    }
  }, [setShowSidebar, setTabMode, viewMode, tabId]);


  return (
    <div
      className={`flex-shrink-0 self-stretch ${isResizing ? 'select-none' : ''}`}
      style={{
        width: showSidebar ? sidebarWidth : 0,
        overflow: transitionDone ? 'visible' : 'hidden',
        pointerEvents: showSidebar ? 'auto' : 'none',
        transition: isResizing ? 'none' : 'width 0.3s ease-out',
      }}
    >
      <div
        className="flex flex-col h-full gap-2 relative"
        style={{
          minWidth: sidebarWidth,
          opacity: showSidebar ? 1 : 0,
          transform: showSidebar ? 'translateX(0)' : 'translateX(-20px)',
          transition: isResizing ? 'none' : 'opacity 0.3s ease-out, transform 0.3s ease-out',
        }}
      >
        {/* View mode toggle — separate floating card */}
        <div
          className="flex-shrink-0"
          style={{
            backgroundColor: 'white',
            borderRadius: '1.5rem',
            boxShadow: '0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)',
            border: '1px solid hsl(30 3.3% 11.8% / 15%)',
          }}
        >
          <ViewModeToggle
            activeMode={viewMode}
            onModeChange={onModeChange}
            onCollapse={handleCollapse}
          />
        </div>

        {/* Mode-specific content — separate floating card */}
        <div
          className="flex-1 flex flex-col overflow-hidden"
          style={{
            backgroundColor: 'white',
            borderRadius: '1.5rem',
            boxShadow: '0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)',
            border: '1px solid hsl(30 3.3% 11.8% / 15%)',
          }}
        >
          {viewMode === 'explorer' && (
            <AddDatasetPanel
              selectedObjects={selectedObjects}
              onAddDataset={addDatasetWithMetadata}
              onClose={() => setShowSidebar(false)}
              addedEndpoints={addedEndpoints}
              existingDatasets={existingDatasets}
              onUpdateDataset={(id, updates) => updateDataset(id, updates)}
              onNavigateToDataset={onNavigateToDataset}
              onRemoveDataset={onRemoveDataset}
              hideHeader={true}
              initialEndpoint={sidebarInitialEndpoint ?? undefined}
              initialDatasetId={sidebarInitialDatasetId ?? undefined}
              onClearInitialEndpoint={() => { setSidebarInitialEndpoint(null); setSidebarInitialDatasetId(null); }}
            />
          )}

          {viewMode === 'tools' && (
            <ToolSourcesPanel tabId={tabId} embedded />
          )}

          {viewMode === 'pivot' && (
            <PivotTableCreator show={true} onClose={() => {}} editingPivotLocalId={activePivotLocalId} />
          )}

          {viewMode === 'chart' && (
            <ChartCreator show={true} />
          )}
        </div>

        {/* Resize handle on right edge */}
        <div
          onMouseDown={handleResizeStart}
          className="absolute top-0 bottom-0 right-0 w-2 cursor-col-resize z-10"
          style={{ transform: 'translateX(50%)' }}
          title="Drag to resize"
        />
      </div>
    </div>
  );
}
