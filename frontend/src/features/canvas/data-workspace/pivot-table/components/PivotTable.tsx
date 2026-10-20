/**
 * PivotTableView - Excel-style pivot table with field picker panel
 * 
 * Layout (matches Microsoft Excel):
 * +----------------------------------+------------------+
 * |        Pivot Table               | PivotTable Fields|
 * |   (row headers | col headers)    |  [Search fields] |
 * |   (aggregated cells)             |  ☑ field1       |
 * +----------------------------------+  ☑ field2       |
 * |     Statistics Tabs              +------------------+
 * |  [Descriptive][Correlation]      | Filters | Columns|
 * |  [Regression][Distribution]      +---------+--------|
 * |  [Tests]                         |  Rows   | Values |
 * +----------------------------------+------------------+
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { FileDown, FileSpreadsheet } from 'lucide-react';
import { useDataWorkspaceStore, WorkspaceTab } from '../../stores/dataWorkspaceStore';
import { Tooltip } from '@/features/canvas/shared/Tooltip';

// Hooks
import { usePivotData } from '../hooks/usePivotData';
import { usePivotComputation } from '../hooks/usePivotComputation';
import { usePivotStatistics } from '../hooks/usePivotStatistics';
import { usePivotExport } from '../hooks/usePivotExport';

// Components
import { PivotTable as PivotTableGrid } from './PivotTableCore';
import { PivotStatsPanel } from './PivotStatsPanel';

interface Props {
  tabId: string;
  /** When set, renders the matching entry from tab.pivotResults instead of legacy tab.pivotConfig. */
  pivotLocalId?: string;
  headerLeftPortal?: HTMLDivElement | null;
  headerRightPortal?: HTMLDivElement | null;
  showAIPanel?: boolean;
  onToggleAIPanel?: () => void;
}

type PivotView = 'table' | 'descriptive' | 'correlation' | 'regression' | 'distribution' | 'tests';

export default function PivotTableView({ tabId, pivotLocalId, headerLeftPortal, headerRightPortal, showAIPanel, onToggleAIPanel }: Props) {
  const tabs = useDataWorkspaceStore(s => s.tabs);
  const updatePivotConfig = useDataWorkspaceStore(s => s.updatePivotConfig);

  // Find the current pivot tab
  const pivotTab = tabs.find(t => t.id === tabId) as WorkspaceTab | undefined;

  // New model: resolve config from pivotResults by localId. Legacy fallback: tab.pivotConfig.
  const config = pivotLocalId
    ? (pivotTab?.pivotResults?.find(r => r.localId === pivotLocalId)?.config)
    : pivotTab?.pivotConfig;
  
  // Find the source sheet and its data
  // Handle: no sourceSheetId (inline pivot on same tab), legacy format, and sheets array
  const sourceTab = tabs.find(t => t.id === config?.sourceTabId);
  const isLegacyOrInline = !config?.sourceSheetId || config?.sourceSheetId?.startsWith('legacy-');

  // Memoize sourceSheet to prevent infinite re-render loops
  const sourceSheet = useMemo(() => {
    if (isLegacyOrInline) {
      return sourceTab?.datasets && sourceTab.datasets.length > 0
        ? { id: config?.sourceSheetId || `legacy-${sourceTab?.id}`, name: sourceTab?.name || 'Unknown', datasets: sourceTab.datasets, compatibilityGroup: 'unknown' }
        : undefined;
    }
    return sourceTab?.sheets?.find(s => s.id === config?.sourceSheetId);
  }, [isLegacyOrInline, sourceTab?.datasets, sourceTab?.sheets, sourceTab?.name, sourceTab?.id, config?.sourceSheetId]);

  // Derive active filters from persisted store config
  const activeFilters = useMemo(() => {
    const result: Record<string, Set<string>> = {};
    for (const [field, cond] of Object.entries(config?.filters || {})) {
      if (cond.operator === 'in' && Array.isArray(cond.value)) {
        result[field] = new Set(cond.value);
      }
    }
    return result;
  }, [config?.filters]);

  // Data fetching hook
  const {
    sourceData,
    fields,
    loading,
    datasetRefs,
  } = usePivotData(config, sourceSheet, activeFilters);

  // Pivot computation hook (uses server-side fetch via dataset refs)
  const {
    pivotResult,
    cellMap,
    sortColumn,
    sortDirection,
    handleSort,
    sortedRowHeaders,
    formatValue,
    columnTotals,
  } = usePivotComputation(datasetRefs, activeFilters, config);

  // Statistics hook
  const statisticsHook = usePivotStatistics(sourceData, fields, config);

  // Export hook
  const exportHook = usePivotExport(pivotResult, cellMap, config);

  // View state (must be before early returns)
  const [activeView, setActiveView] = useState<PivotView>('table');
  const [statsHeight, setStatsHeight] = useState(55);

  // Reset overlay when switching pivots
  const prevPivotId = useRef(pivotLocalId);
  useEffect(() => {
    if (pivotLocalId !== prevPivotId.current) {
      prevPivotId.current = pivotLocalId;
      setActiveView('table');
    }
  }, [pivotLocalId]);

  // Early returns
  if (!pivotTab || !config) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400">
        <div className="text-center">
          <svg className="w-12 h-12 mx-auto mb-3 text-slate-200" fill="none" stroke="currentColor" strokeWidth={1} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <div className="text-sm">Pivot configuration not found</div>
        </div>
      </div>
    );
  }
  
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-500">
          <div className="w-5 h-5 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
          <span className="text-sm">Loading data...</span>
        </div>
      </div>
    );
  }

  const hslIcon = 'hsl(30 3.3% 11.8% / 85%)';
  const hslIconDisabled = 'hsl(30 3.3% 11.8% / 25%)';
  const hslHoverBg = 'hsl(30 3.3% 11.8% / 6%)';
  const hslActiveBg = 'hsl(30 3.3% 11.8% / 8%)';
  const hslActiveText = 'hsl(30 3.3% 11.8% / 85%)';
  const hslInactiveText = 'hsl(30 3.3% 11.8% / 45%)';
  const hasData = !!(pivotResult && pivotResult.cells.length > 0);

  const viewTabs: { key: PivotView; label: string }[] = [
    { key: 'descriptive', label: 'Descriptive' },
    { key: 'correlation', label: 'Correlation' },
    { key: 'regression', label: 'Regression' },
    { key: 'distribution', label: 'Distribution' },
    { key: 'tests', label: 'Tests' },
  ];

  const headerLeftContent = (
    <div className="flex items-center gap-0.5 min-w-0 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
      {viewTabs.map(tab => {
        const isActive = activeView === tab.key;
        return (
          <button
            key={tab.key}
            onClick={() => setActiveView(activeView === tab.key ? 'table' : tab.key)}
            className="flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
            style={{
              backgroundColor: isActive ? hslActiveBg : 'transparent',
              color: isActive ? hslActiveText : hslInactiveText,
            }}
            onMouseEnter={e => { if (!isActive) e.currentTarget.style.backgroundColor = hslHoverBg; }}
            onMouseLeave={e => { if (!isActive) e.currentTarget.style.backgroundColor = isActive ? hslActiveBg : 'transparent'; }}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );

  const headerRightContent = (
    <div className="flex items-center gap-0.5 flex-shrink-0">
      <button
        onClick={() => updatePivotConfig(tabId, { showGrandTotalColumn: !config?.showGrandTotalColumn })}
        className="flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
        style={{
          backgroundColor: config?.showGrandTotalColumn ? hslActiveBg : 'transparent',
          color: config?.showGrandTotalColumn ? hslActiveText : hslInactiveText,
        }}
        onMouseEnter={e => { if (!config?.showGrandTotalColumn) e.currentTarget.style.backgroundColor = hslHoverBg; }}
        onMouseLeave={e => { if (!config?.showGrandTotalColumn) e.currentTarget.style.backgroundColor = 'transparent'; }}
      >
        Grand Total
      </button>
      <button
        onClick={() => updatePivotConfig(tabId, { showSubtotals: !config?.showSubtotals })}
        className="flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
        style={{
          backgroundColor: config?.showSubtotals ? hslActiveBg : 'transparent',
          color: config?.showSubtotals ? hslActiveText : hslInactiveText,
        }}
        onMouseEnter={e => { if (!config?.showSubtotals) e.currentTarget.style.backgroundColor = hslHoverBg; }}
        onMouseLeave={e => { if (!config?.showSubtotals) e.currentTarget.style.backgroundColor = 'transparent'; }}
      >
        Subtotals
      </button>
      <Tooltip label="Export as CSV">
        <button
          onClick={exportHook.exportToCSV}
          disabled={!hasData}
          className="p-1.5 rounded-md transition-colors disabled:cursor-not-allowed"
          style={{ color: hasData ? hslIcon : hslIconDisabled }}
          onMouseEnter={e => { if (hasData) e.currentTarget.style.backgroundColor = hslHoverBg; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <FileDown className="w-4 h-4" />
        </button>
      </Tooltip>
      <Tooltip label="Export as Excel">
        <button
          onClick={exportHook.exportToExcel}
          disabled={!hasData}
          className="p-1.5 rounded-md transition-colors disabled:cursor-not-allowed"
          style={{ color: hasData ? hslIcon : hslIconDisabled }}
          onMouseEnter={e => { if (hasData) e.currentTarget.style.backgroundColor = hslHoverBg; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <FileSpreadsheet className="w-4 h-4" />
        </button>
      </Tooltip>
      {onToggleAIPanel && !showAIPanel && (
        <Tooltip label="Open Agent">
          <button
            onClick={onToggleAIPanel}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: hslIcon }}
            onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
            onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            <img src="/sentry-icon.png" alt="" className="w-5 h-5 block" />
          </button>
        </Tooltip>
      )}
    </div>
  );

  return (
    <div className="flex-1 relative flex flex-col overflow-hidden min-h-0">
      {headerLeftPortal && createPortal(headerLeftContent, headerLeftPortal)}
      {headerRightPortal && createPortal(headerRightContent, headerRightPortal)}

      {/* Pivot Table — always rendered */}
      <PivotTableGrid
        config={config}
        pivotResult={pivotResult}
        cellMap={cellMap}
        sortedRowHeaders={sortedRowHeaders}
        sortColumn={sortColumn}
        sortDirection={sortDirection}
        handleSort={handleSort}
        formatValue={formatValue}
        columnTotals={columnTotals}
        overlayOpen={activeView !== 'table'}
        overlayHeightPct={statsHeight}
      />

      {/* Statistics Panel — slide-up overlay */}
      <PivotStatsPanel
        activeStatsTab={activeView === 'table' ? 'descriptive' : activeView}
        isOpen={activeView !== 'table'}
        height={statsHeight}
        onHeightChange={setStatsHeight}
        onClose={() => setActiveView('table')}
        descriptiveStats={statisticsHook.descriptiveStats}
        correlationResult={statisticsHook.correlationResult}
        distributionData={statisticsHook.distributionData}
        fields={fields}
        regressionX={statisticsHook.regressionX}
        setRegressionX={statisticsHook.setRegressionX}
        regressionY={statisticsHook.regressionY}
        setRegressionY={statisticsHook.setRegressionY}
        regressionResult={statisticsHook.regressionResult}
        regressionLoading={statisticsHook.regressionLoading}
        runRegression={statisticsHook.runRegression}
        selectedTest={statisticsHook.selectedTest}
        setSelectedTest={statisticsHook.setSelectedTest}
        testFieldA={statisticsHook.testFieldA}
        setTestFieldA={statisticsHook.setTestFieldA}
        testFieldB={statisticsHook.testFieldB}
        setTestFieldB={statisticsHook.setTestFieldB}
        testGroupBy={statisticsHook.testGroupBy}
        setTestGroupBy={statisticsHook.setTestGroupBy}
        testPopulationMean={statisticsHook.testPopulationMean}
        setTestPopulationMean={statisticsHook.setTestPopulationMean}
        testResult={statisticsHook.testResult}
        testLoading={statisticsHook.testLoading}
        runTest={statisticsHook.runTest}
      />
    </div>
  );
}
