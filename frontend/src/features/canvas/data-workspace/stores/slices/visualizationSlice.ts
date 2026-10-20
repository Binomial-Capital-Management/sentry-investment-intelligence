/**
 * Visualization Slice - Pivot and Chart configurations
 *
 * Handles:
 * - Pivot tab creation and configuration
 * - Chart creation (inline results on current tab) and configuration
 */

import { StateCreator } from 'zustand';
import type { PivotConfig, ChartConfig, WorkspaceTab } from '../types';
import type { CoreSlice } from './coreSlice';

export interface VisualizationSlice {
  // Pivot actions
  createPivotTab: (
    sourceTabId: string,
    sourceSheetId: string,
    initialConfig?: Partial<PivotConfig>,
  ) => string;
  updatePivotConfig: (tabId: string, config: Partial<Omit<PivotConfig, 'id'>>) => void;

  // Chart actions
  createChartTab: (
    sourceTabId: string,
    sourceSheetId: string,
    initialConfig?: Partial<ChartConfig>,
  ) => string;
  updateChartConfig: (tabId: string, config: Partial<Omit<ChartConfig, 'id'>>) => void;
}

type CombinedSlice = CoreSlice & VisualizationSlice;

export const createVisualizationSlice: StateCreator<
  CombinedSlice,
  [],
  [],
  VisualizationSlice
> = (set, get) => ({
  createPivotTab: (sourceTabId, sourceSheetId, initialConfig) => {
    const tabId = `pivot-${Date.now()}`;
    const pivotConfig: PivotConfig = {
      id: `config-${Date.now()}`,
      sourceTabId,
      sourceSheetId,
      rows: initialConfig?.rows || [],
      columns: initialConfig?.columns || [],
      values: initialConfig?.values || [],
      filters: initialConfig?.filters || {},
      filterableFields: initialConfig?.filterableFields || [],
      selectedDatasetIds: initialConfig?.selectedDatasetIds || [],
      mergeMode: initialConfig?.mergeMode,
      mergeKey: initialConfig?.mergeKey,
      showGrandTotalColumn: initialConfig?.showGrandTotalColumn,
      showSubtotals: initialConfig?.showSubtotals,
    };

    const { tabs } = get();
    const sourceTab = tabs.find(t => t.id === sourceTabId);
    const tabName = `Pivot: ${sourceTab?.name || 'Unknown'}`;

    const newTab: WorkspaceTab = {
      id: tabId,
      name: tabName,
      type: 'pivot',
      datasets: [],
      symbols: [],
      activeView: 'table',
      createdAt: Date.now(),
      mode: 'data',
      pivotConfig,
    };

    set(state => ({
      tabs: [...state.tabs, newTab],
      activeTabId: tabId,
    }));

    return tabId;
  },

  updatePivotConfig: (tabId, config) => {
    set(state => ({
      tabs: state.tabs.map(tab => {
        if (tab.id !== tabId) return tab;

        // New model: route to the pivot result addressed by contentView.pivotLocalId
        if (tab.contentView?.type === 'pivot') {
          const localId = tab.contentView.pivotLocalId;
          const results = tab.pivotResults ?? [];
          if (results.some(r => r.localId === localId)) {
            return {
              ...tab,
              pivotResults: results.map(r =>
                r.localId === localId
                  ? { ...r, config: { ...r.config, ...config } }
                  : r
              ),
            };
          }
        }

        // Legacy fallback: update the single tab.pivotConfig if it exists
        if (tab.pivotConfig) {
          return { ...tab, pivotConfig: { ...tab.pivotConfig, ...config } };
        }

        return tab;
      }),
    }));
  },

  createChartTab: (sourceTabId, sourceSheetId, initialConfig) => {
    const localId = `chart-result-${Date.now()}`;
    const chartConfig: ChartConfig = {
      id: `config-${Date.now()}`,
      sourceTabId,
      sourceSheetId,
      chartType: initialConfig?.chartType || 'line',
      xAxis: initialConfig?.xAxis || '',
      ySeries: initialConfig?.ySeries || [],
      selectedDatasetIds: initialConfig?.selectedDatasetIds || [],
      title: initialConfig?.title,
      showLegend: initialConfig?.showLegend ?? true,
      showGrid: initialConfig?.showGrid ?? true,
      typeOptions: initialConfig?.typeOptions || {},
      filters: initialConfig?.filters || [],
      xAxisLabel: initialConfig?.xAxisLabel,
      yAxisLabel: initialConfig?.yAxisLabel,
      zAxisLabel: initialConfig?.zAxisLabel,
      xAxisRange: initialConfig?.xAxisRange,
      yAxisRange: initialConfig?.yAxisRange,
      ohlcFields: initialConfig?.ohlcFields,
    };

    const { activeTabId } = get();

    const seriesFields = initialConfig?.ySeries?.map(s => s.label || s.field).join(', ');
    const xField = initialConfig?.xAxis;
    const chartName = initialConfig?.title
      || (seriesFields && xField ? `${seriesFields} vs. ${xField}` : seriesFields || xField || 'Chart');

    // Target: use the source tab (which has the data)
    const targetTabId = sourceTabId || activeTabId;
    if (!targetTabId) return localId;

    get().addChartResult(targetTabId, {
      localId,
      name: chartName,
      config: chartConfig,
      createdAt: Date.now(),
    });

    // Switch sidebar to chart mode
    set({ sidebarViewMode: 'chart' });

    return localId;
  },

  updateChartConfig: (tabId, config) => {
    set(state => ({
      tabs: state.tabs.map(tab => {
        if (tab.id !== tabId) return tab;

        // New model: route to chart result addressed by contentView.chartLocalId
        if (tab.contentView?.type === 'chart') {
          const localId = tab.contentView.chartLocalId;
          const results = tab.chartResults ?? [];
          if (results.some(r => r.localId === localId)) {
            return {
              ...tab,
              chartResults: results.map(r =>
                r.localId === localId
                  ? { ...r, config: { ...r.config, ...config } }
                  : r
              ),
            };
          }
        }

        // Legacy fallback: update the single tab.chartConfig if it exists
        if (tab.chartConfig) {
          return { ...tab, chartConfig: { ...tab.chartConfig, ...config } };
        }

        return tab;
      }),
    }));
  },
});
