import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useDataWorkspaceStore } from '../../stores/dataWorkspaceStore';
import type { ChartConfig } from '../../stores/dataWorkspaceStore';
import { API_BASE } from '@/services/api';
import { C } from './tokens';
import { ChartField, ChartConfigState } from './types';
import SheetSelectionStep from './SheetSelectionStep';
import ChartConfigStep from './ChartConfigStep';
import { ChartOptionsPanel } from '../components/ChartOptionsPanel';
import { useChartData } from '../hooks/useChartData';
import { getChartType, CONFIG_PANEL_REGISTRY } from '../chartTypes';
import { GroupPicker } from '../../dataset-viewer/components/GroupPicker';
import { selectActiveChartGroupId } from '../../stores/selectors';

interface Props {
  show: boolean;
  onCreated?: () => void;
}

function deriveChartName(config: ChartConfigState): string {
  const series = config.ySeries.map(s => s.label || s.field).join(', ');
  const x = config.xAxis;
  if (series && x) return `${series} vs. ${x}`;
  if (series) return series;
  if (x) return x;
  return 'Chart';
}

function configStateToChartConfig(
  state: ChartConfigState,
  sourceTabId: string,
  sourceSheetId: string,
  datasetIds: string[],
): ChartConfig {
  const isCandlestick = state.chartType === 'candlestick';
  const isMatrixChart = state.chartType === 'heatmap' || state.chartType === 'surface3d';
  const isScatter3D = state.chartType === 'scatter3d';

  const typeOptions: Record<string, any> = {};
  if (isScatter3D && state.zAxis) typeOptions.zAxis = state.zAxis;
  if (isMatrixChart && state.matrix) {
    typeOptions.xField = state.matrix.xField;
    typeOptions.yField = state.matrix.yField;
    typeOptions.zField = state.matrix.zField;
  }

  return {
    id: `config-${Date.now()}`,
    sourceTabId,
    sourceSheetId,
    chartType: state.chartType,
    xAxis: isCandlestick ? state.ohlc?.dateField || '' : isMatrixChart ? state.matrix?.xField || '' : state.xAxis,
    ySeries: isCandlestick ? [{ field: state.ohlc?.closeField || '' }] : isMatrixChart ? [{ field: state.matrix?.zField || '' }] : state.ySeries,
    selectedDatasetIds: datasetIds,
    showLegend: true,
    showGrid: true,
    typeOptions: Object.keys(typeOptions).length > 0 ? typeOptions : {},
    filters: [],
    ohlcFields: isCandlestick && state.ohlc ? {
      date: state.ohlc.dateField, open: state.ohlc.openField,
      high: state.ohlc.highField, low: state.ohlc.lowField,
      close: state.ohlc.closeField, volume: state.ohlc.volumeField,
    } : undefined,
  };
}

export default function ChartCreator({ show }: Props) {
  const workspaceTabs = useDataWorkspaceStore((s) => s.tabs) || [];
  const activeTabId = useDataWorkspaceStore((s) => s.activeTabId);
  const activeTab = useDataWorkspaceStore(s => s.tabs.find(t => t.id === s.activeTabId));
  const addChartResult = useDataWorkspaceStore(s => s.addChartResult);
  const patchChartResult = useDataWorkspaceStore(s => s.patchChartResult);
  const setContentView = useDataWorkspaceStore(s => s.setContentView);
  const createDatasetGroup = useDataWorkspaceStore(s => s.createDatasetGroup);
  const activeChartGroupId = useDataWorkspaceStore(selectActiveChartGroupId);

  const editingChartLocalId = useMemo(() => {
    if (activeTab?.contentView?.type === 'chart') return activeTab.contentView.chartLocalId;
    return undefined;
  }, [activeTab]);

  const storeConfig = useDataWorkspaceStore(s => {
    if (!editingChartLocalId) return undefined;
    const tab = s.tabs.find(t => t.id === s.activeTabId);
    return tab?.chartResults?.find(r => r.localId === editingChartLocalId)?.config;
  });

  const updateChartConfig = useDataWorkspaceStore(s => s.updateChartConfig);

  // ── Derive initial local state from store config ──

  const allDatasets = activeTab?.datasets || [];

  function resolveSelectedDatasets() {
    if (!storeConfig?.selectedDatasetIds?.length) return [];
    const ids = new Set(storeConfig.selectedDatasetIds);
    return allDatasets.filter(ds => ids.has(ds.id) || ids.has(ds.endpoint));
  }

  function storeConfigToLocal(sc: ChartConfig): ChartConfigState {
    return {
      chartType: (sc.chartType || 'line') as ChartConfigState['chartType'],
      xAxis: sc.xAxis || '',
      ySeries: sc.ySeries || [],
      zAxis: sc.typeOptions?.zAxis,
      ohlc: sc.ohlcFields ? {
        dateField: sc.ohlcFields.date || '', openField: sc.ohlcFields.open || '',
        highField: sc.ohlcFields.high || '', lowField: sc.ohlcFields.low || '',
        closeField: sc.ohlcFields.close || '', volumeField: sc.ohlcFields.volume,
      } : undefined,
      matrix: sc.typeOptions?.xField ? {
        xField: sc.typeOptions.xField, yField: sc.typeOptions.yField, zField: sc.typeOptions.zField,
      } : undefined,
    };
  }

  const [selectedDatasets, setSelectedDatasets] = useState<any[]>(() => resolveSelectedDatasets());
  const [fields, setFields] = useState<ChartField[]>([]);
  const [loadingFields, setLoadingFields] = useState(false);
  const [config, setConfig] = useState<ChartConfigState>(() =>
    storeConfig ? storeConfigToLocal(storeConfig) : { chartType: 'line', xAxis: '', ySeries: [] }
  );
  const analyzeRef = useRef(0);
  const [sourceTabId, setSourceTabId] = useState<string>(() => storeConfig?.sourceTabId || '');
  const [sourceSheetId, setSourceSheetId] = useState<string>(() => storeConfig?.sourceSheetId || '');

  // Re-seed local state when switching to a different chart
  const prevEditingId = useRef(editingChartLocalId);
  useEffect(() => {
    if (editingChartLocalId === prevEditingId.current) return;
    prevEditingId.current = editingChartLocalId;
    if (storeConfig) {
      setSelectedDatasets(resolveSelectedDatasets());
      setConfig(storeConfigToLocal(storeConfig));
      setSourceTabId(storeConfig.sourceTabId || '');
      setSourceSheetId(storeConfig.sourceSheetId || '');
    } else {
      setSelectedDatasets([]);
      setFields([]);
      setConfig({ chartType: 'line', xAxis: '', ySeries: [] });
      setSourceTabId('');
      setSourceSheetId('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingChartLocalId]);

  // ── Chart options panel data ──

  const chartSourceTab = useMemo(() => {
    if (!storeConfig?.sourceTabId) return undefined;
    if (storeConfig.sourceTabId === activeTabId) return activeTab;
    return workspaceTabs.find(t => t.id === storeConfig.sourceTabId);
  }, [storeConfig?.sourceTabId, workspaceTabs, activeTabId, activeTab]);

  const isLegacySheet = storeConfig?.sourceSheetId?.startsWith('legacy-');
  const chartSourceSheet = useMemo(() => {
    if (!storeConfig) return undefined;
    if (isLegacySheet) {
      return chartSourceTab?.datasets && chartSourceTab.datasets.length > 0
        ? { id: storeConfig.sourceSheetId || '', name: chartSourceTab?.name || 'Unknown', datasets: chartSourceTab.datasets, compatibilityGroup: 'unknown' }
        : undefined;
    }
    return chartSourceTab?.sheets?.find(s => s.id === storeConfig.sourceSheetId);
  }, [isLegacySheet, chartSourceTab, storeConfig]);

  const { data: chartData } = useChartData(storeConfig, chartSourceSheet, workspaceTabs);

  const chartAvailableFields = useMemo(() => {
    if (chartData.length === 0) return [];
    const sample = chartData[0];
    return Object.keys(sample).map(field => {
      const val = sample[field];
      let type: 'date' | 'numeric' | 'string' = 'string';
      if (typeof val === 'number') type = 'numeric';
      else if (typeof val === 'string' && val.match(/^\d{4}-\d{2}/)) type = 'date';
      return { field, type };
    });
  }, [chartData]);

  const handleChartConfigUpdate = useCallback((updates: Partial<ChartConfig>) => {
    if (activeTabId) updateChartConfig(activeTabId, updates);
  }, [activeTabId, updateChartConfig]);

  const chartTypeDef = useMemo(() => storeConfig ? getChartType(storeConfig.chartType) : undefined, [storeConfig?.chartType]);
  const chartTypeOptions = useMemo(() => {
    if (!chartTypeDef) return {};
    return { ...chartTypeDef.defaultOptions, ...(storeConfig?.typeOptions || {}) };
  }, [chartTypeDef, storeConfig?.typeOptions]);

  const handleTypeOptionsChange = useCallback((newOptions: Record<string, any>) => {
    if (activeTabId) updateChartConfig(activeTabId, { typeOptions: newOptions });
  }, [activeTabId, updateChartConfig]);

  // ── Write config to store on every change (like pivot) ──

  const updateConfig = useCallback((next: ChartConfigState) => {
    if (!activeTabId) return;
    if (!sourceTabId) return;

    const datasetIds = selectedDatasets.map((d: any) => d.id || d.endpoint);
    const chartConfig = configStateToChartConfig(next, sourceTabId, sourceSheetId, datasetIds);

    if (storeConfig && editingChartLocalId) {
      patchChartResult(activeTabId, editingChartLocalId, {
        config: chartConfig,
        name: deriveChartName(next),
      });
    } else {
      const localId = (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
        ? crypto.randomUUID()
        : `chart-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

      let targetGroupId = activeChartGroupId;
      if (!targetGroupId) targetGroupId = createDatasetGroup('Charts');

      addChartResult(activeTabId, {
        localId,
        name: deriveChartName(next),
        config: chartConfig,
        groupId: targetGroupId,
        createdAt: Date.now(),
      });

      setContentView(activeTabId, { type: 'chart', chartLocalId: localId });
    }
  }, [activeTabId, sourceTabId, sourceSheetId, selectedDatasets, storeConfig,
      editingChartLocalId, patchChartResult, activeChartGroupId,
      addChartResult, createDatasetGroup, setContentView]);

  const handleSetConfig: React.Dispatch<React.SetStateAction<ChartConfigState>> = useCallback((action) => {
    setConfig(prev => {
      const next = typeof action === 'function' ? action(prev) : action;
      updateConfig(next);
      return next;
    });
  }, [updateConfig]);

  // ── Auto-analyze fields when selected datasets change ──

  const datasetKey = useMemo(
    () => selectedDatasets.map(ds => ds.id || ds.endpoint + ds.symbol).sort().join('|'),
    [selectedDatasets],
  );

  useEffect(() => {
    if (selectedDatasets.length === 0) {
      setFields([]);
      setConfig({ chartType: 'line', xAxis: '', ySeries: [] });
      setSourceTabId('');
      setSourceSheetId('');
      return;
    }

    const token = ++analyzeRef.current;

    const analyze = async () => {
      setLoadingFields(true);
      const allFields: ChartField[] = [];
      const seenFields = new Set<string>();

      for (const ds of selectedDatasets) {
        try {
          const dataResponse = await fetch(`${API_BASE}/api/canvas/data/endpoint/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ endpoint: ds.endpoint, symbol: ds.symbol || '_MARKET_', params: ds.params || {}, fields: [] }),
          });
          const dataResult = await dataResponse.json();
          const data = dataResult.data?.[ds.endpoint] || [];

          if (data.length > 0) {
            const analysisResponse = await fetch(`${API_BASE}/api/canvas/pivot/field-analysis`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ data }),
            });
            const analysisResult = await analysisResponse.json();

            if (analysisResult.success && analysisResult.fields) {
              analysisResult.fields.forEach((field: any) => {
                if (!seenFields.has(field.name)) {
                  seenFields.add(field.name);
                  let fieldType: 'numeric' | 'datetime' | 'categorical' = 'categorical';
                  if (field.can_aggregate === true) fieldType = 'numeric';
                  else if (field.inferred_type === 'datetime' || field.name.toLowerCase().includes('date')) fieldType = 'datetime';
                  allFields.push({ name: field.name, type: fieldType, source: ds.endpoint });
                }
              });
            }
          } else {
            (ds.fields || []).forEach((f: string) => {
              if (!seenFields.has(f)) {
                seenFields.add(f);
                allFields.push({ name: f, type: 'categorical', source: ds.endpoint });
              }
            });
          }
        } catch (err) {
          console.error('Failed to analyze fields for', ds.endpoint, err);
          (ds.fields || []).forEach((f: string) => {
            if (!seenFields.has(f)) {
              seenFields.add(f);
              allFields.push({ name: f, type: 'categorical', source: ds.endpoint });
            }
          });
        }
      }

      if (token === analyzeRef.current) {
        setFields(allFields);
        setLoadingFields(false);

        const firstDs = selectedDatasets[0];
        const tab = workspaceTabs.find(t =>
          t.datasets?.some((d: any) => (d.id || d.endpoint + d.symbol) === (firstDs.id || firstDs.endpoint + firstDs.symbol))
        );
        const tabId = tab?.id || activeTabId || '';
        setSourceTabId(tabId);
        setSourceSheetId(`legacy-${tabId}`);
      }
    };

    analyze();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetKey]);

  // ── Pivot source handler ──

  const handleSelectPivot = async (tabId: string, sheetId: string, sheet: any) => {
    setSourceTabId(tabId);
    setSourceSheetId(sheetId);
    setLoadingFields(true);
    setConfig({ chartType: 'line', xAxis: '', ySeries: [] });

    try {
      const pivotConfig = sheet.pivotConfig;
      const sourceTab = workspaceTabs.find((t) => t.id === pivotConfig.sourceTabId);
      const sourceSheet = sourceTab?.datasets?.length ? { datasets: sourceTab.datasets } : null;

      if (!sourceSheet?.datasets?.length) {
        setFields([]);
        setLoadingFields(false);
        return;
      }

      const allSourceData: any[] = [];
      for (const ds of sourceSheet.datasets) {
        if (pivotConfig.selectedDatasetIds?.length &&
            !pivotConfig.selectedDatasetIds.includes(ds.id) &&
            !pivotConfig.selectedDatasetIds.includes(ds.endpoint)) {
          continue;
        }
        try {
          const resp = await fetch(`${API_BASE}/api/canvas/data/endpoint/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ endpoint: ds.endpoint, symbol: ds.symbol || '_MARKET_', params: ds.params || {}, fields: [] }),
          });
          const result = await resp.json();
          allSourceData.push(...(result.data?.[ds.endpoint] || []));
        } catch (e) {
          console.error('Failed to fetch data for pivot source', e);
        }
      }

      if (allSourceData.length === 0) {
        setFields([]);
        setLoadingFields(false);
        return;
      }

      const pivotResp = await fetch(`${API_BASE}/api/canvas/pivot/compute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data: allSourceData,
          rows: pivotConfig.rows || [],
          columns: pivotConfig.columns || [],
          values: pivotConfig.values || [],
          filters: {},
        }),
      });
      const pivotResult = await pivotResp.json();

      if (!pivotResult.success) {
        setFields([]);
        setLoadingFields(false);
        return;
      }

      const flatRowsWide: any[] = [];
      const flatRowsLong: any[] = [];
      const rowHeaders = pivotResult.row_headers || [];
      const colHeaders = pivotResult.column_headers || [];
      const cells = pivotResult.cells || {};

      if (colHeaders.length > 0) {
        const rowFieldName = pivotConfig.rows?.[0] || '_row';
        const colFieldName = pivotConfig.columns?.[0] || '_col';
        const valueFieldName = pivotConfig.values?.[0]?.field || 'value';

        for (const rowKey of rowHeaders) {
          const row: any = { [rowFieldName]: rowKey };
          for (const colKey of colHeaders) {
            const cellKey = `${rowKey}||${colKey}`;
            const cellVal = cells[cellKey];
            if (cellVal !== undefined && cellVal !== null) {
              row[colKey] = typeof cellVal === 'number' ? cellVal : parseFloat(cellVal) || 0;
            }
          }
          flatRowsWide.push(row);
        }

        for (const rowKey of rowHeaders) {
          for (const colKey of colHeaders) {
            const cellKey = `${rowKey}||${colKey}`;
            const cellVal = cells[cellKey];
            if (cellVal !== undefined && cellVal !== null) {
              flatRowsLong.push({
                [rowFieldName]: rowKey,
                [colFieldName]: colKey,
                [valueFieldName]: typeof cellVal === 'number' ? cellVal : parseFloat(cellVal) || 0,
              });
            }
          }
        }
      } else {
        for (const rowKey of rowHeaders) {
          const row: any = {};
          if (pivotConfig.rows?.length === 1) {
            row[pivotConfig.rows[0]] = rowKey;
          } else {
            row['_row'] = rowKey;
          }

          const totals = pivotResult.row_totals?.[rowKey];
          if (typeof totals === 'number') {
            row['value'] = totals;
          } else if (totals && typeof totals === 'object') {
            Object.entries(totals).forEach(([k, v]) => {
              row[k] = v;
            });
          }
          flatRowsWide.push(row);
          flatRowsLong.push(row);
        }
      }

      const allFields: ChartField[] = [];
      if (flatRowsWide.length > 0) {
        const sampleRow = flatRowsWide[0];
        Object.keys(sampleRow).forEach((key) => {
          const val = sampleRow[key];
          const isNumeric = typeof val === 'number';
          const isDate = typeof val === 'string' && val.match(/^\d{4}-\d{2}/);
          allFields.push({
            name: key,
            type: isNumeric ? 'numeric' : isDate ? 'datetime' : 'categorical',
            source: 'pivot',
          });
        });
      }

      if (flatRowsLong.length > 0 && colHeaders.length > 0) {
        const colFieldName = pivotConfig.columns?.[0] || '_col';
        const valueFieldName = pivotConfig.values?.[0]?.field || 'value';

        if (!allFields.find(f => f.name === colFieldName)) {
          allFields.push({ name: colFieldName, type: 'categorical', source: 'pivot_long' });
        }
        if (!allFields.find(f => f.name === valueFieldName)) {
          allFields.push({ name: valueFieldName, type: 'numeric', source: 'pivot_long' });
        }
      }

      setFields(allFields);
      setLoadingFields(false);
    } catch (err) {
      console.error('Failed to analyze pivot fields', err);
      setFields([]);
      setLoadingFields(false);
    }
  };

  const handleNewChart = useCallback(() => {
    if (!activeTabId) return;
    setSelectedDatasets([]);
    setFields([]);
    setConfig({ chartType: 'line', xAxis: '', ySeries: [] });
    setSourceTabId('');
    setSourceSheetId('');
    setContentView(activeTabId, { type: 'none' as any });
  }, [activeTabId, setContentView]);

  if (!show) return null;

  const hasSource = workspaceTabs.some(t =>
    (t.type !== 'pivot' && t.type !== 'chart' && t.datasets && t.datasets.length > 0) ||
    (t.type === 'pivot' && t.pivotConfig)
  );

  if (!hasSource) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center" style={{ padding: '2rem', gap: '0.75rem' }}>
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          backgroundColor: C.bgActive, border: C.borderSel,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={C.textFaint} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
            <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
          </svg>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.688rem', fontWeight: 500, color: C.textMuted, marginBottom: '0.25rem' }}>No data sources</div>
          <div style={{ fontSize: '0.563rem', color: C.textFaint }}>Add datasets in Sources first</div>
        </div>
      </div>
    );
  }

  const showConfig = fields.length > 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-h-0">
      <div className="scrollbar-auto" style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '0.5rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', scrollbarGutter: 'stable' }}>

        {/* Source picker — always visible */}
        <SheetSelectionStep
          workspaceTabs={workspaceTabs}
          selectedDatasets={selectedDatasets}
          setSelectedDatasets={setSelectedDatasets}
          onSelectPivot={handleSelectPivot}
          onNewChart={handleNewChart}
        />

        {/* Add to group */}
        <div style={{ marginLeft: '-0.75rem', marginRight: '-0.75rem' }}>
          <GroupPicker mode="chart" />
        </div>

        {/* Loading */}
        {loadingFields && (
          <div style={{ textAlign: 'center', padding: '1rem 0' }}>
            <svg className="w-4 h-4 animate-spin mx-auto" style={{ color: C.textMuted }} fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <div style={{ fontSize: '0.563rem', color: C.textFaint, marginTop: '0.375rem' }}>Analyzing fields...</div>
          </div>
        )}

        {/* Chart config — appears inline, writes to store live */}
        {!loadingFields && showConfig && (
          <ChartConfigStep
            fields={fields}
            config={config}
            setConfig={handleSetConfig}
            loadingFields={loadingFields}
            xAxisLabel={storeConfig?.xAxisLabel}
            yAxisLabel={storeConfig?.yAxisLabel}
            onXAxisLabelChange={v => handleChartConfigUpdate({ xAxisLabel: v || undefined })}
            onYAxisLabelChange={v => handleChartConfigUpdate({ yAxisLabel: v || undefined })}
            chartTitle={storeConfig?.title}
            onChartTitleChange={v => handleChartConfigUpdate({ title: v || undefined })}
            filterFields={(storeConfig?.filters || []).map(f => f.field)}
            onAddFilter={field => {
              const existing = storeConfig?.filters || [];
              const isDate = fields.some(f => f.name === field && f.type === 'datetime');
              handleChartConfigUpdate({
                filters: [...existing, {
                  id: `filter-${Date.now()}`,
                  field,
                  filterType: isDate ? 'date_range' : 'numeric_range',
                }],
              });
            }}
            onRemoveFilter={field => {
              handleChartConfigUpdate({
                filters: (storeConfig?.filters || []).filter(f => f.field !== field),
              });
            }}
            filters={storeConfig?.filters}
            onUpdateFilter={(field, patch) => {
              handleChartConfigUpdate({
                filters: (storeConfig?.filters || []).map(f =>
                  f.field === field ? { ...f, ...patch } : f
                ),
              });
            }}
            xAxisRange={storeConfig?.xAxisRange as [number | string | null, number | string | null] | undefined}
            yAxisRange={storeConfig?.yAxisRange as [number | string | null, number | string | null] | undefined}
            onXAxisRangeChange={range => handleChartConfigUpdate({ xAxisRange: range as any })}
            onYAxisRangeChange={range => handleChartConfigUpdate({ yAxisRange: range as any })}
          />
        )}

        {/* Chart options — title, labels, axis range, filters, display, styling */}
        {storeConfig && chartAvailableFields.length > 0 && (
          <div>
            <ChartOptionsPanel
              config={storeConfig}
              availableFields={chartAvailableFields}
              data={chartData}
              onUpdate={handleChartConfigUpdate}
              typeOptionsPanel={(() => {
                const ct = storeConfig.chartType;
                const Panel = ct ? CONFIG_PANEL_REGISTRY[ct] : null;
                if (!Panel) return null;
                const needsFieldStrings = ['scatter3d', 'heatmap', 'surface3d', 'scatterMatrix', 'bubble'].includes(ct);
                return (
                  <Panel
                    options={chartTypeOptions}
                    onChange={handleTypeOptionsChange}
                    {...(needsFieldStrings && { availableFields: chartAvailableFields.map(f => f.field) })}
                  />
                );
              })()}
            />
          </div>
        )}
      </div>
    </div>
  );
}
