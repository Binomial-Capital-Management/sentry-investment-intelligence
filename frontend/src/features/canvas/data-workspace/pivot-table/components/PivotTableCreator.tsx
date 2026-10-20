/**
 * PivotTableCreator - Pivot configuration sidebar panel.
 *
 * Two modes:
 *   - Creating: uses local draft state, writes to store on "Create" click.
 *   - Editing: reads/writes store directly (controlled component), live updates.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useDataWorkspaceStore } from '../../stores/dataWorkspaceStore';
import { selectActivePivotGroupId, selectDatasetGroups } from '../../stores/selectors';
import { GroupPicker } from '../../dataset-viewer/components/GroupPicker';
import { API_BASE } from '@/services/api';
import type { PivotConfig } from '../../stores/types';
import { FilterValueSelector } from './FilterValueSelector';
import { Tooltip } from '@/features/canvas/shared/Tooltip';

// ============================================================================
// Design system tokens
// ============================================================================
const C = {
  text:       'hsl(60 2.5% 23.3%)',
  textMuted:  'hsl(60 2.5% 23.3% / 60%)',
  textFaint:  'hsl(60 2.5% 23.3% / 35%)',
  textGhost:  'hsl(60 2.5% 23.3% / 25%)',
  border:     '0.5px solid hsl(30 3.3% 11.8% / 10%)',
  borderSel:  '0.5px solid hsl(30 3.3% 11.8% / 15%)',
  bgActive:   'hsl(30 3.3% 11.8% / 8%)',
  bgSubtle:   'hsl(30 3.3% 11.8% / 3%)',
  bgHover:    'hsl(30 3.3% 11.8% / 5%)',
} as const;

const sectionHeader: React.CSSProperties = {
  fontSize: '0.563rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: C.textFaint,
};

// ============================================================================
// Types
// ============================================================================

interface PivotField {
  name: string;
  type: 'measure' | 'dimension';
}

interface DatasetFields {
  datasetKey: string;
  endpoint: string;
  symbol: string;
  fields: PivotField[];
}

interface LocalValueConfig {
  field: string;
  aggregation: string;
  showTotal?: boolean;
  totalAggregation?: string;
  showAs?: string;
}

function derivePivotName(config: { values?: { field: string }[]; rows?: string[] }, fallbackIndex: number): string {
  const value = config.values?.[0]?.field;
  const row = config.rows?.[0];
  if (value && row) return `${value} by ${row}`;
  if (value) return value;
  if (row) return `by ${row}`;
  return `Pivot ${fallbackIndex}`;
}

interface LocalConfig {
  rows: string[];
  columns: string[];
  values: LocalValueConfig[];
  filterableFields: string[];
  filters?: Record<string, { operator: string; value: any }>;
  mergeMode?: 'union' | 'inner';
  mergeKey?: string;
}

interface PivotTableCreatorProps {
  show: boolean;
  onClose: () => void;
  editingPivotLocalId?: string;
}

// ============================================================================
// Helpers
// ============================================================================

function storeConfigToLocal(sc: PivotConfig): LocalConfig {
  return {
    rows: sc.rows || [],
    columns: sc.columns || [],
    values: (sc.values || []).map(v => ({
      field: v.field, aggregation: v.aggregation,
      showTotal: v.showTotal, totalAggregation: v.totalAggregation, showAs: v.showAs,
    })),
    filterableFields: sc.filterableFields || [],
    filters: sc.filters,
    mergeMode: sc.mergeMode,
    mergeKey: sc.mergeKey,
  };
}

function localConfigToStore(lc: LocalConfig, base: Partial<PivotConfig>, datasetIds: string[]): PivotConfig {
  return {
    id: base.id || `config-${Date.now()}`,
    sourceTabId: base.sourceTabId || '',
    rows: lc.rows,
    columns: lc.columns,
    values: lc.values.map(v => ({
      field: v.field,
      aggregation: v.aggregation as any,
      showTotal: v.showTotal,
      totalAggregation: v.totalAggregation as any,
      showAs: v.showAs as any,
    })),
    filterableFields: lc.filterableFields,
    filters: lc.filters,
    mergeMode: lc.mergeMode,
    mergeKey: lc.mergeKey,
    selectedDatasetIds: datasetIds,
  };
}

const EMPTY_CONFIG: LocalConfig = { rows: [], columns: [], values: [], filterableFields: [] };

// ============================================================================
// Main Component
// ============================================================================

export default function PivotTableCreator({ show, editingPivotLocalId }: PivotTableCreatorProps) {
  const activeTab = useDataWorkspaceStore(s => s.tabs.find(t => t.id === s.activeTabId));
  const activeTabId = activeTab?.id;
  const activePivotGroupId = useDataWorkspaceStore(selectActivePivotGroupId);
  const datasetGroups = useDataWorkspaceStore(selectDatasetGroups);
  const addPivotResult = useDataWorkspaceStore(s => s.addPivotResult);
  const patchPivotResult = useDataWorkspaceStore(s => s.patchPivotResult);
  const createDatasetGroup = useDataWorkspaceStore(s => s.createDatasetGroup);
  const setContentView = useDataWorkspaceStore(s => s.setContentView);

  // Read store config directly for editing mode
  const storeConfig = useDataWorkspaceStore(s => {
    if (!editingPivotLocalId) return undefined;
    const tab = s.tabs.find(t => t.id === s.activeTabId);
    return tab?.pivotResults?.find(r => r.localId === editingPivotLocalId)?.config;
  });

  const allDatasets = activeTab?.datasets || [];

  // Build group options: each group is a single selectable source
  const groupOptions = useMemo(() => {
    if (datasetGroups.length === 0) {
      return allDatasets.length > 0
        ? [{ id: '_all_', name: 'All Data', datasets: allDatasets }]
        : [];
    }
    return datasetGroups.map(g => ({
      id: g.id,
      name: g.name,
      datasets: allDatasets.filter(d => d.groupId === g.id),
    })).filter(g => g.datasets.length > 0);
  }, [datasetGroups, allDatasets]);

  // Per-dataset selection — initialized from store config when editing
  const [includedDatasetKeys, setIncludedDatasetKeys] = useState<Set<string>>(() =>
    storeConfig?.selectedDatasetIds?.length ? new Set(storeConfig.selectedDatasetIds) : new Set()
  );

  // Re-seed dataset keys when switching to a different pivot
  const prevEditingId = useRef(editingPivotLocalId);
  useEffect(() => {
    if (editingPivotLocalId === prevEditingId.current) return;
    prevEditingId.current = editingPivotLocalId;
    setIncludedDatasetKeys(
      storeConfig?.selectedDatasetIds?.length ? new Set(storeConfig.selectedDatasetIds) : new Set()
    );
  }, [editingPivotLocalId, storeConfig?.selectedDatasetIds]);

  const getDatasetKey = useCallback((ds: any) => ds.id || ds.endpoint + ds.symbol, []);

  const sourceDatasets = useMemo(
    () => allDatasets.filter(ds => includedDatasetKeys.has(getDatasetKey(ds))),
    [allDatasets, includedDatasetKeys, getDatasetKey],
  );

  const toggleDataset = useCallback((ds: any) => {
    const key = getDatasetKey(ds);
    setIncludedDatasetKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }, [getDatasetKey]);

  // ── Config: always store-direct ──

  const config: LocalConfig = storeConfig ? storeConfigToLocal(storeConfig) : EMPTY_CONFIG;

  const updateConfig = useCallback((updater: (prev: LocalConfig) => LocalConfig) => {
    if (!activeTabId) return;
    const datasetIds = sourceDatasets.map(ds => ds.id || ds.endpoint + ds.symbol);

    if (storeConfig && editingPivotLocalId) {
      const next = updater(storeConfigToLocal(storeConfig));
      const existingCount = (activeTab?.pivotResults ?? []).filter(
        r => r.groupId === (activeTab?.pivotResults?.find(p => p.localId === editingPivotLocalId)?.groupId)
      ).length;
      patchPivotResult(activeTabId, editingPivotLocalId, {
        config: localConfigToStore(next, storeConfig, datasetIds),
        name: derivePivotName(next, existingCount),
      });
    } else {
      // No pivot exists yet — create one with the applied change
      const next = updater(EMPTY_CONFIG);

      let targetGroupId = activePivotGroupId;
      if (!targetGroupId) targetGroupId = createDatasetGroup('Pivots');

      const localId = (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
        ? crypto.randomUUID()
        : `pivot-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

      const existingPivotsInGroup = (activeTab?.pivotResults ?? []).filter(
        r => r.groupId === targetGroupId
      ).length;

      addPivotResult(activeTabId, {
        localId,
        name: derivePivotName(next, existingPivotsInGroup + 1),
        groupId: targetGroupId,
        createdAt: Date.now(),
        config: localConfigToStore(next, { sourceTabId: activeTabId }, datasetIds),
      });

      setContentView(activeTabId, { type: 'pivot', pivotLocalId: localId });
    }
  }, [activeTabId, storeConfig, editingPivotLocalId, sourceDatasets, patchPivotResult,
      activePivotGroupId, activeTab?.pivotResults, addPivotResult, createDatasetGroup, setContentView]);

  // ── Field analysis ──

  const [fieldsByDataset, setFieldsByDataset] = useState<DatasetFields[]>([]);
  const [expandedDatasets, setExpandedDatasets] = useState<Set<string>>(new Set());
  const [loadingFields, setLoadingFields] = useState(false);
  const analyzeRef = useRef(0);

  const toggleDatasetExpand = useCallback((key: string) => {
    setExpandedDatasets(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }, []);

  const allFields = useMemo(() => {
    const seen = new Set<string>();
    const result: PivotField[] = [];
    for (const df of fieldsByDataset) {
      for (const f of df.fields) {
        if (!seen.has(f.name)) { seen.add(f.name); result.push(f); }
      }
    }
    return result;
  }, [fieldsByDataset]);

  // Reset fields when active tab changes
  useEffect(() => {
    if (!editingPivotLocalId) {
      setFieldsByDataset([]);
    }
  }, [activeTabId, editingPivotLocalId]);

  // Auto-analyze fields when source datasets change
  const sourceKey = useMemo(
    () => sourceDatasets.map(ds => ds.id || ds.endpoint + ds.symbol).sort().join('|'),
    [sourceDatasets],
  );

  useEffect(() => {
    if (sourceDatasets.length === 0) {
      setFieldsByDataset([]);
      return;
    }

    const token = ++analyzeRef.current;

    const analyze = async () => {
      setLoadingFields(true);
      const result: DatasetFields[] = [];

      for (const ds of sourceDatasets) {
        const key = getDatasetKey(ds);
        const sym = ds.symbol !== '_MARKET_' ? ds.symbol : 'Market';
        const dsFields: PivotField[] = [];

        try {
          const res = await fetch(`${API_BASE}/api/canvas/data/endpoint/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ endpoint: ds.endpoint, symbol: ds.symbol || '_MARKET_', params: ds.params || {}, fields: [] }),
          });
          const fetchResult = await res.json();
          const data = fetchResult.data?.[ds.endpoint] || [];

          if (data.length > 0) {
            const analysisRes = await fetch(`${API_BASE}/api/canvas/pivot/field-analysis`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ data }),
            });
            const analysis = await analysisRes.json();
            if (analysis.success && analysis.fields) {
              analysis.fields.forEach((f: any) => {
                dsFields.push({ name: f.name, type: f.can_aggregate ? 'measure' : 'dimension' });
              });
            }
          } else {
            (ds.fields || []).forEach((f: string) => {
              dsFields.push({ name: f, type: 'dimension' });
            });
          }
        } catch {
          (ds.fields || []).forEach((f: string) => {
            dsFields.push({ name: f, type: 'dimension' });
          });
        }

        result.push({ datasetKey: key, endpoint: ds.endpoint, symbol: sym, fields: dsFields });
      }

      if (token === analyzeRef.current) {
        setFieldsByDataset(result);
        setExpandedDatasets(new Set(result.map(r => r.datasetKey)));
        setLoadingFields(false);
      }
    };

    analyze();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceKey]);

  // ── Filter options fetch ──
  const [filterOptions, setFilterOptions] = useState<Record<string, string[]>>({});
  const [filterOptionsLoading, setFilterOptionsLoading] = useState(false);
  const filterableFieldsKey = config.filterableFields.join(',');

  useEffect(() => {
    if (config.filterableFields.length === 0 || sourceDatasets.length === 0) {
      setFilterOptions({});
      return;
    }
    const refs = sourceDatasets.map(ds => ({
      symbol: ds.symbol || '_MARKET_',
      endpoint: ds.endpoint,
      params: ds.params || {},
    }));
    setFilterOptionsLoading(true);
    fetch(`${API_BASE}/api/canvas/pivot/filter-options-from-refs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_refs: refs,
        filterable_fields: config.filterableFields,
        merge_mode: config.mergeMode || 'union',
        merge_key: config.mergeKey,
      }),
    })
      .then(r => r.json())
      .then(result => {
        if (result.success) setFilterOptions(result.options);
      })
      .catch(() => {})
      .finally(() => setFilterOptionsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterableFieldsKey, sourceKey, config.mergeMode, config.mergeKey]);

  const getFieldZone = useCallback((name: string): 'rows' | 'columns' | 'values' | 'filters' | null => {
    if (config.rows.includes(name)) return 'rows';
    if (config.columns.includes(name)) return 'columns';
    if (config.values.some(v => v.field === name)) return 'values';
    if (config.filterableFields.includes(name)) return 'filters';
    return null;
  }, [config]);

  const toggleField = useCallback((field: PivotField) => {
    const zone = getFieldZone(field.name);
    if (zone) {
      updateConfig(p => {
        if (zone === 'values') return { ...p, values: p.values.filter(v => v.field !== field.name) };
        if (zone === 'filters') return { ...p, filterableFields: p.filterableFields.filter(f => f !== field.name) };
        return { ...p, [zone]: (p[zone] as string[]).filter(f => f !== field.name) };
      });
    } else {
      if (field.type === 'measure') {
        updateConfig(p => ({ ...p, values: [...p.values, { field: field.name, aggregation: 'sum' }] }));
      } else {
        updateConfig(p => ({ ...p, rows: [...p.rows, field.name] }));
      }
    }
  }, [getFieldZone, updateConfig]);

  // ── New Pivot ──

  const handleNewPivot = useCallback(() => {
    if (!activeTabId) return;

    let targetGroupId = activePivotGroupId;
    if (!targetGroupId) {
      targetGroupId = createDatasetGroup('Pivots');
    }

    const existingPivotsInGroup = (activeTab?.pivotResults ?? []).filter(
      r => r.groupId === targetGroupId
    ).length;

    const localId = (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
      ? crypto.randomUUID()
      : `pivot-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    addPivotResult(activeTabId, {
      localId,
      name: `Pivot ${existingPivotsInGroup + 1}`,
      groupId: targetGroupId,
      createdAt: Date.now(),
      config: localConfigToStore(EMPTY_CONFIG, { sourceTabId: activeTabId }, []),
    });

    setContentView(activeTabId, { type: 'pivot', pivotLocalId: localId });
  }, [activeTabId, activePivotGroupId, activeTab?.pivotResults, addPivotResult, createDatasetGroup, setContentView]);

  if (!show) return null;

  const hasSource = groupOptions.length > 0;

  // ── Render ──

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

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-h-0">
      <div className="scrollbar-auto" style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '0.5rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', scrollbarGutter: 'stable' }}>

        {/* ── TOP ── */}
        <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <SourceGroupPicker
          groupOptions={groupOptions}
          includedDatasetKeys={includedDatasetKeys}
          getDatasetKey={getDatasetKey}
          toggleDataset={toggleDataset}
          onNewPivot={handleNewPivot}
        />

        {/* ── ADD TO GROUP ── */}
        <div style={{ marginLeft: '-0.75rem', marginRight: '-0.75rem' }}>
          <GroupPicker mode="pivot" />
        </div>

        {/* ── LOADING ── */}
        {loadingFields && (
          <div style={{ textAlign: 'center', padding: '1rem 0' }}>
            <svg className="w-4 h-4 animate-spin mx-auto" style={{ color: C.textMuted }} fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <div style={{ fontSize: '0.563rem', color: C.textFaint, marginTop: '0.375rem' }}>Analyzing fields...</div>
          </div>
        )}
        </div>

        {/* ── PER-DATASET FIELDS (scrollable) ── */}
        {!loadingFields && fieldsByDataset.length > 0 && (
          <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              {fieldsByDataset.map(df => {
                const isExpanded = expandedDatasets.has(df.datasetKey);
                return (
                  <div key={df.datasetKey} style={{ border: C.border, borderRadius: '0.5rem', overflow: 'hidden', flexShrink: 0 }}>
                    <div
                      style={{
                        display: 'flex', alignItems: 'center', gap: '0.375rem',
                        padding: '0.375rem 0.5rem', backgroundColor: C.bgSubtle,
                        cursor: 'pointer', fontSize: '0.625rem', fontWeight: 600, color: C.text,
                      }}
                      onClick={() => toggleDatasetExpand(df.datasetKey)}
                    >
                      <svg
                        style={{ width: 8, height: 8, flexShrink: 0, transition: 'transform 0.15s ease', transform: isExpanded ? 'rotate(90deg)' : 'none' }}
                        fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: "'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace" }}>
                        {df.endpoint}
                      </span>
                      <span style={{ fontSize: '0.5rem', fontWeight: 400, color: C.textFaint }}>
                        ({df.symbol})
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          const ds = sourceDatasets.find(d => getDatasetKey(d) === df.datasetKey);
                          if (ds) toggleDataset(ds);
                        }}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textGhost, display: 'flex', padding: 0, flexShrink: 0, marginLeft: 'auto' }}
                      >
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                          <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    {isExpanded && (
                      <FieldScrollList>
                        {df.fields.map(field => {
                          const zone = getFieldZone(field.name);
                          const zoneLabel = zone === 'values' ? 'Val' : zone === 'rows' ? 'Row' : zone === 'columns' ? 'Col' : zone === 'filters' ? 'Flt' : null;
                          return (
                            <div
                              key={field.name}
                              draggable
                              onDragStart={e => e.dataTransfer.setData('field', JSON.stringify({ name: field.name, type: field.type }))}
                              onClick={() => toggleField(field)}
                              style={{
                                padding: '0.375rem 0.5rem',
                                fontSize: '0.688rem', display: 'flex', alignItems: 'center', gap: '0.375rem',
                                borderRadius: '0.5rem',
                                border: zone ? C.borderSel : '0.5px solid transparent',
                                backgroundColor: zone ? C.bgActive : 'transparent',
                                color: zone ? C.text : C.textMuted,
                                cursor: 'pointer', transition: 'all 0.1s ease',
                              }}
                              onMouseEnter={e => { if (!zone) e.currentTarget.style.backgroundColor = C.bgHover; }}
                              onMouseLeave={e => { if (!zone) e.currentTarget.style.backgroundColor = zone ? C.bgActive : 'transparent'; }}
                            >
                              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${field.type === 'measure' ? 'bg-emerald-500' : 'bg-blue-500'}`} />
                              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: "'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace" }}>{field.name}</span>
                              {zoneLabel ? (
                                <span style={{ fontSize: '0.5rem', fontWeight: 600, padding: '0.0625rem 0.25rem', borderRadius: '0.25rem', backgroundColor: C.bgActive, border: C.borderSel, color: C.textMuted, flexShrink: 0 }}>{zoneLabel}</span>
                              ) : (
                                <span style={{ fontSize: '0.563rem', color: C.textGhost, flexShrink: 0 }}>{field.type === 'measure' ? '#' : 'Abc'}</span>
                              )}
                            </div>
                          );
                        })}
                      </FieldScrollList>
                    )}
                  </div>
                );
              })}
          </div>
        )}

        {/* ── LEGEND ── */}
        {!loadingFields && fieldsByDataset.length > 0 && (
          <div style={{ fontSize: '0.5rem', color: C.textFaint, display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Measure</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-blue-500" /> Dimension</span>
          </div>
        )}

        {/* ── DROP ZONES ── */}
        {!loadingFields && allFields.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', flexShrink: 0 }}>
            <DropZone label="Rows" items={config.rows}
              onDrop={f => { if (!config.rows.includes(f)) updateConfig(p => ({ ...p, rows: [...p.rows, f] })); }}
              onRemove={f => updateConfig(p => ({ ...p, rows: p.rows.filter(x => x !== f) }))} />
            <DropZone label="Columns" items={config.columns}
              onDrop={f => { if (!config.columns.includes(f)) updateConfig(p => ({ ...p, columns: [...p.columns, f] })); }}
              onRemove={f => updateConfig(p => ({ ...p, columns: p.columns.filter(x => x !== f) }))} />
            <ValuesDropZone
              values={config.values}
              onDrop={f => { if (!config.values.some(v => v.field === f)) updateConfig(p => ({ ...p, values: [...p.values, { field: f, aggregation: 'sum' }] })); }}
              onRemove={idx => updateConfig(p => ({ ...p, values: p.values.filter((_, i) => i !== idx) }))}
              onChangeAggregation={(idx, agg) => updateConfig(p => { const v = [...p.values]; v[idx] = { ...v[idx], aggregation: agg }; return { ...p, values: v }; })}
              onPatchValue={(idx, patch) => updateConfig(p => { const v = [...p.values]; v[idx] = { ...v[idx], ...patch }; return { ...p, values: v }; })} />
            <DropZone label="Filters" items={config.filterableFields}
              onDrop={f => { if (!config.filterableFields.includes(f)) updateConfig(p => ({ ...p, filterableFields: [...p.filterableFields, f] })); }}
              onRemove={f => updateConfig(p => {
                const nextFilters = { ...(p.filters || {}) };
                delete nextFilters[f];
                return { ...p, filterableFields: p.filterableFields.filter(x => x !== f), filters: nextFilters };
              })} />
            <FilterValueSelector
              filterableFields={config.filterableFields}
              filterOptions={filterOptions}
              activeFilters={config.filters || {}}
              loading={filterOptionsLoading}
              onFiltersChange={(filters) => updateConfig(p => ({ ...p, filters }))}
            />

            {/* ── MERGE MODE (multi-dataset only) ── */}
            {sourceDatasets.length > 1 && (
              <div>
                <div style={{ ...sectionHeader, marginBottom: '0.25rem' }}>Merge Mode</div>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button
                    onClick={() => updateConfig(p => ({ ...p, mergeMode: 'union' }))}
                    style={{
                      flex: 1, padding: '0.25rem', fontSize: '0.563rem', fontWeight: 500,
                      borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                      border: (config.mergeMode || 'union') === 'union' ? C.borderSel : C.border,
                      backgroundColor: (config.mergeMode || 'union') === 'union' ? C.bgActive : 'transparent',
                      color: (config.mergeMode || 'union') === 'union' ? C.text : C.textMuted,
                    }}
                  >
                    Union All
                  </button>
                  <button
                    onClick={() => updateConfig(p => ({ ...p, mergeMode: 'inner' }))}
                    style={{
                      flex: 1, padding: '0.25rem', fontSize: '0.563rem', fontWeight: 500,
                      borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                      border: config.mergeMode === 'inner' ? C.borderSel : C.border,
                      backgroundColor: config.mergeMode === 'inner' ? C.bgActive : 'transparent',
                      color: config.mergeMode === 'inner' ? C.text : C.textMuted,
                    }}
                  >
                    Inner Join
                  </button>
                </div>
                {config.mergeMode === 'inner' && (
                  <div style={{ marginTop: '0.375rem' }}>
                    <div style={{ fontSize: '0.5rem', color: C.textFaint, marginBottom: '0.125rem' }}>Join Key</div>
                    <select
                      value={config.mergeKey || 'date'}
                      onChange={e => updateConfig(p => ({ ...p, mergeKey: e.target.value }))}
                      style={{
                        width: '100%', padding: '0.25rem 0.375rem', fontSize: '0.563rem',
                        border: C.border, borderRadius: '0.375rem', outline: 'none',
                        color: C.text, backgroundColor: 'white',
                      }}
                    >
                      {allFields.filter(f => f.type === 'dimension').map(f => (
                        <option key={f.name} value={f.name}>{f.name}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div style={{ fontSize: '0.5rem', color: C.textGhost, marginTop: '0.25rem' }}>
                  {(config.mergeMode || 'union') === 'union'
                    ? 'All rows, missing values as -'
                    : 'Only rows where key exists in all datasets'}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}

// ============================================================================
// Drop Zone
// ============================================================================

interface DropZoneProps {
  label: string;
  items: string[];
  onDrop: (fieldName: string) => void;
  onRemove: (fieldName: string) => void;
}

function DropZone({ label, items, onDrop, onRemove }: DropZoneProps) {
  return (
    <div>
      <div style={{ ...sectionHeader, marginBottom: '0.25rem' }}>{label}</div>
      <div
        style={{ border: '0.5px dashed hsl(30 3.3% 11.8% / 15%)', borderRadius: '0.5rem', backgroundColor: C.bgSubtle, minHeight: '1.75rem', padding: '0.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.25rem', transition: 'all 0.1s ease' }}
        onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 30%)'; e.currentTarget.style.backgroundColor = C.bgActive; }}
        onDragLeave={e => { e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 15%)'; e.currentTarget.style.backgroundColor = C.bgSubtle; }}
        onDrop={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 15%)'; e.currentTarget.style.backgroundColor = C.bgSubtle; try { onDrop(JSON.parse(e.dataTransfer.getData('field')).name); } catch {} }}
      >
        {items.map(item => (
          <span key={item} style={{ padding: '0.125rem 0.375rem', backgroundColor: 'white', border: '0.5px solid hsl(30 3.3% 11.8% / 12%)', borderRadius: '0.25rem', fontSize: '0.563rem', color: C.text, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            {item}
            <button onClick={() => onRemove(item)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textGhost, fontSize: '0.625rem', padding: 0, lineHeight: 1 }}
              onMouseEnter={e => { e.currentTarget.style.color = 'hsl(0 70% 50%)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = C.textGhost; }}>×</button>
          </span>
        ))}
        {items.length === 0 && <span style={{ fontSize: '0.563rem', color: C.textGhost, padding: '0.125rem 0.25rem' }}>Drag fields here</span>}
      </div>
    </div>
  );
}

// ============================================================================
// Values Drop Zone
// ============================================================================

interface ValuesDropZoneProps {
  values: LocalValueConfig[];
  onDrop: (fieldName: string) => void;
  onRemove: (idx: number) => void;
  onChangeAggregation: (idx: number, aggregation: string) => void;
  onPatchValue: (idx: number, patch: Partial<LocalValueConfig>) => void;
}

function ValuesDropZone({ values, onDrop, onRemove, onChangeAggregation, onPatchValue }: ValuesDropZoneProps) {
  return (
    <div>
      <div style={{ ...sectionHeader, marginBottom: '0.25rem' }}>Values</div>
      <div
        style={{ border: '0.5px dashed hsl(30 3.3% 11.8% / 15%)', borderRadius: '0.5rem', backgroundColor: C.bgSubtle, minHeight: '1.75rem', padding: '0.25rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', transition: 'all 0.1s ease' }}
        onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 30%)'; e.currentTarget.style.backgroundColor = C.bgActive; }}
        onDragLeave={e => { e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 15%)'; e.currentTarget.style.backgroundColor = C.bgSubtle; }}
        onDrop={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 15%)'; e.currentTarget.style.backgroundColor = C.bgSubtle; try { onDrop(JSON.parse(e.dataTransfer.getData('field')).name); } catch {} }}
      >
        {values.map((v, idx) => (
          <div key={v.field} style={{ backgroundColor: 'white', border: '0.5px solid hsl(30 3.3% 11.8% / 12%)', borderRadius: '0.25rem', fontSize: '0.563rem', color: C.text }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.125rem 0.375rem' }}>
              <InlineSelect value={v.aggregation} onChange={val => onChangeAggregation(idx, val)}
                options={[
                  { value: 'none', label: 'Value' }, { value: 'sum', label: 'Sum' }, { value: 'avg', label: 'Avg' },
                  { value: 'count', label: 'Count' }, { value: 'min', label: 'Min' }, { value: 'max', label: 'Max' },
                  { value: 'first', label: 'First' }, { value: 'last', label: 'Last' },
                ]} />
              <span style={{ flex: 1 }}>{v.aggregation === 'none' ? v.field : `of ${v.field}`}</span>
              <button onClick={() => onRemove(idx)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textGhost, fontSize: '0.625rem', padding: 0, lineHeight: 1 }}
                onMouseEnter={e => { e.currentTarget.style.color = 'hsl(0 70% 50%)'; }}
                onMouseLeave={e => { e.currentTarget.style.color = C.textGhost; }}>×</button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.0625rem 0.375rem 0.125rem', borderTop: '0.5px solid hsl(30 3.3% 11.8% / 6%)', fontSize: '0.5rem', color: C.textFaint }}>
              <input type="checkbox" checked={v.showTotal !== false}
                onChange={e => onPatchValue(idx, { showTotal: e.target.checked })}
                onClick={e => e.stopPropagation()}
                style={{ width: '0.5rem', height: '0.5rem', accentColor: C.textMuted }} />
              <InlineSelect value={v.totalAggregation || v.aggregation}
                onChange={val => onPatchValue(idx, { totalAggregation: val })}
                disabled={v.showTotal === false} fontSize="0.5rem"
                options={[
                  { value: 'sum', label: 'Tot:Σ' }, { value: 'avg', label: 'Tot:μ' },
                  { value: 'count', label: 'Tot:#' }, { value: 'min', label: 'Tot:↓' }, { value: 'max', label: 'Tot:↑' },
                ]} />
              <span style={{ color: 'hsl(30 3.3% 11.8% / 10%)' }}>|</span>
              <InlineSelect value={v.showAs || 'value'}
                onChange={val => onPatchValue(idx, { showAs: val })}
                fontSize="0.5rem"
                options={[
                  { value: 'value', label: 'Val' }, { value: 'pct_row', label: '%Row' },
                  { value: 'pct_col', label: '%Col' }, { value: 'pct_grand', label: '%All' },
                ]} />
            </div>
          </div>
        ))}
        {values.length === 0 && <span style={{ fontSize: '0.563rem', color: C.textGhost, padding: '0.125rem 0.25rem' }}>Drop here</span>}
      </div>
    </div>
  );
}

// ============================================================================
// Source Group Picker (dropdown + dataset checklist)
// ============================================================================

interface GroupOption {
  id: string;
  name: string;
  datasets: Array<{ id: string; symbol: string; endpoint: string; params?: Record<string, string>; fields?: string[]; groupId?: string }>;
}

function SourceGroupPicker({ groupOptions, includedDatasetKeys, getDatasetKey, toggleDataset, onNewPivot }: {
  groupOptions: GroupOption[];
  includedDatasetKeys: Set<string>;
  getDatasetKey: (ds: any) => string;
  toggleDataset: (ds: any) => void;
  onNewPivot?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const toggleGroupExpand = useCallback((id: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const totalIncluded = groupOptions.reduce((n, g) =>
    n + g.datasets.filter(ds => includedDatasetKeys.has(getDatasetKey(ds))).length, 0
  );


  if (groupOptions.length === 0) {
    return (
      <div>
        <div style={{ ...sectionHeader, marginBottom: '0.375rem' }}>Source</div>
        <div style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 35%)', fontStyle: 'italic' }}>No datasets. Add data first.</div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ ...sectionHeader, marginBottom: '0.375rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        Source
        {onNewPivot && (
          <Tooltip label="New pivot">
            <button
              onClick={onNewPivot}
              style={{ background: 'none', border: 'none', padding: '0.125rem', borderRadius: '0.25rem', cursor: 'pointer', color: C.textGhost, display: 'flex', transition: 'all 0.15s ease' }}
              onMouseEnter={e => { e.currentTarget.style.color = C.text; e.currentTarget.style.backgroundColor = C.bgActive; }}
              onMouseLeave={e => { e.currentTarget.style.color = C.textGhost; e.currentTarget.style.backgroundColor = 'transparent'; }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          </Tooltip>
        )}
      </div>
      <div style={{ position: 'relative' }}>
        {/* Single trigger button */}
        <button
          type="button"
          onClick={() => setOpen(!open)}
          style={{
            width: '100%',
            height: 30,
            padding: '0.3rem 0.625rem',
            fontSize: '0.688rem',
            fontWeight: 500,
            textAlign: 'left' as const,
            border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
            borderRadius: '0.5rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            color: totalIncluded > 0 ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 35%)',
            backgroundColor: 'white',
            cursor: 'pointer',
          }}
        >
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
            {totalIncluded > 0 ? `${totalIncluded} selected` : 'Select datasets...'}
          </span>
          <svg
            style={{ width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', flexShrink: 0, transition: 'transform 0.15s ease', transform: open ? 'rotate(180deg)' : 'none' }}
            fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Dropdown panel with all groups */}
        {open && (
          <div style={{
            marginTop: 4,
            backgroundColor: 'white',
            borderRadius: '0.75rem',
            border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
            maxHeight: 300,
            overflowY: 'auto',
            padding: '0.375rem',
          }}>
            {groupOptions.map(g => {
              const enabledCount = g.datasets.filter(ds => includedDatasetKeys.has(getDatasetKey(ds))).length;
              const isGroupExpanded = expandedGroups.has(g.id);
              return (
                <div key={g.id}>
                  {/* Group header — clickable to expand/collapse */}
                  <button
                    type="button"
                    onClick={() => toggleGroupExpand(g.id)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.375rem',
                      padding: '0.3rem 0.5rem',
                      fontSize: '0.563rem',
                      fontWeight: 600,
                      textTransform: 'uppercase' as const,
                      letterSpacing: '0.05em',
                      color: 'hsl(60 2.5% 23.3% / 35%)',
                      background: 'none',
                      border: 'none',
                      borderRadius: '0.375rem',
                      cursor: 'pointer',
                      marginTop: g.id !== groupOptions[0].id ? '0.25rem' : 0,
                      textAlign: 'left' as const,
                    }}
                    onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'hsl(210 10% 87% / 50%)'; }}
                    onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                  >
                    <svg
                      style={{ width: 8, height: 8, flexShrink: 0, transition: 'transform 0.15s ease', transform: isGroupExpanded ? 'rotate(90deg)' : 'none' }}
                      fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                    <span>{g.name} ({enabledCount}/{g.datasets.length})</span>
                  </button>
                  {isGroupExpanded && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem', padding: '0.125rem 0' }}>
                      {g.datasets.map((ds) => {
                        const key = getDatasetKey(ds);
                        const checked = includedDatasetKeys.has(key);
                        const sym = ds.symbol !== '_MARKET_' ? ds.symbol : 'Market';
                        return (
                          <SourceDatasetRow
                            key={key}
                            symbol={sym}
                            endpoint={ds.endpoint}
                            checked={checked}
                            onToggle={() => toggleDataset(ds)}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Source Dataset Row (TickerPicker row-matched styling)
// ============================================================================

function SourceDatasetRow({ symbol, endpoint, checked, onToggle }: {
  symbol: string;
  endpoint: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      style={{
        width: '100%',
        textAlign: 'left' as const,
        padding: '0.375rem 0.5rem',
        fontSize: '0.688rem',
        borderRadius: '0.5rem',
        border: 'none',
        backgroundColor: checked ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
        opacity: checked ? 0.4 : 1,
        color: 'hsl(60 2.5% 23.3% / 60%)',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '0.5rem',
      }}
      onMouseEnter={e => { if (!checked) e.currentTarget.style.backgroundColor = 'hsl(210 10% 87% / 50%)'; }}
      onMouseLeave={e => { e.currentTarget.style.backgroundColor = checked ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent'; }}
    >
      <span style={{ fontWeight: 500, fontFamily: 'monospace', color: 'hsl(60 2.5% 23.3%)' }}>{symbol}</span>
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, fontSize: '0.563rem', color: 'hsl(60 2.5% 23.3% / 35%)' }}>
        {endpoint}
      </span>
    </button>
  );
}

// ============================================================================
// Field Scroll List with edge fades
// ============================================================================

function FieldScrollList({ children }: { children: React.ReactNode }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showTopFade, setShowTopFade] = useState(false);
  const [showBottomFade, setShowBottomFade] = useState(false);

  const updateFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setShowTopFade(el.scrollTop > 2);
    setShowBottomFade(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
  }, []);

  useEffect(() => {
    requestAnimationFrame(updateFades);
  }, [children, updateFades]);

  return (
    <div style={{ position: 'relative', overflow: 'hidden', maxHeight: '8rem' }}>
      {showTopFade && (
        <div className="absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white to-transparent z-10 pointer-events-none" />
      )}
      <div
        ref={scrollRef}
        onScroll={updateFades}
        style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem', padding: '0.25rem 0.375rem', maxHeight: '8rem', overflowY: 'auto' }}
      >
        {children}
      </div>
      {showBottomFade && (
        <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-white to-transparent z-10 pointer-events-none" />
      )}
    </div>
  );
}

// ============================================================================
// Inline Select (compact portal-based dropdown for value config)
// ============================================================================

function InlineSelect({ value, onChange, options, disabled, fontSize = '0.563rem', color }: {
  value: string;
  onChange: (val: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
  fontSize?: string;
  color?: string;
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const updatePos = useCallback(() => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const dropdownHeight = Math.min(options.length * 26 + 8, 180);
    const spaceBelow = window.innerHeight - rect.bottom - 8;
    setPos({
      top: spaceBelow < dropdownHeight ? rect.top - dropdownHeight - 2 : rect.bottom + 2,
      left: rect.left,
    });
  }, [options.length]);

  const selectedLabel = options.find(o => o.value === value)?.label || value;

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={e => { e.stopPropagation(); if (!disabled) { updatePos(); setOpen(!open); } }}
        style={{
          background: 'transparent', border: 'none', padding: 0,
          fontSize, color: disabled ? C.textGhost : (color || C.textMuted),
          cursor: disabled ? 'default' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.125rem',
          opacity: disabled ? 0.4 : 1,
        }}
      >
        {selectedLabel}
        <svg style={{ width: 7, height: 7, flexShrink: 0, transition: 'transform 0.15s ease', transform: open ? 'rotate(180deg)' : 'none' }} fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && createPortal(
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 9998 }} onClick={() => setOpen(false)} />
          <div style={{
            position: 'fixed', zIndex: 9999, top: pos.top, left: pos.left,
            maxHeight: 180, overflowY: 'auto',
            backgroundColor: 'white', borderRadius: '0.5rem',
            border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
            padding: '0.25rem', display: 'flex', flexDirection: 'column',
          }}>
            {options.map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={e => { e.stopPropagation(); onChange(opt.value); setOpen(false); }}
                style={{
                  textAlign: 'left', padding: '0.25rem 0.5rem',
                  fontSize: '0.625rem', borderRadius: '0.25rem', border: 'none',
                  backgroundColor: value === opt.value ? C.bgActive : 'transparent',
                  color: value === opt.value ? C.text : C.textMuted,
                  cursor: 'pointer', whiteSpace: 'nowrap',
                  transition: 'background-color 0.1s ease',
                }}
                onMouseEnter={e => { if (value !== opt.value) e.currentTarget.style.backgroundColor = C.bgHover; }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = value === opt.value ? C.bgActive : 'transparent'; }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>,
        document.body
      )}
    </>
  );
}
