import { useState, useCallback } from 'react';
import { WorkspaceTab } from '../../stores/dataWorkspaceStore';
import { C, sectionHeader, mono } from './tokens';
import { Tooltip } from '@/features/canvas/shared/Tooltip';

interface GroupOption {
  id: string;
  name: string;
  datasets: any[];
}

interface Props {
  workspaceTabs: WorkspaceTab[];
  selectedDatasets: any[];
  setSelectedDatasets: React.Dispatch<React.SetStateAction<any[]>>;
  onSelectPivot: (tabId: string, sheetId: string, sheet: any) => void;
  onNewChart?: () => void;
}

function getDatasetKey(ds: any): string {
  return ds.id || ds.endpoint + ds.symbol;
}

function buildGroupOptions(tab: WorkspaceTab): GroupOption[] {
  const datasets = tab.datasets || [];
  if (datasets.length === 0) return [];

  const groups = tab.datasetGroups;
  if (groups && groups.length > 0) {
    return groups.map(g => ({
      id: g.id,
      name: g.name,
      datasets: datasets.filter(d => d.groupId === g.id),
    })).filter(g => g.datasets.length > 0);
  }

  return [{ id: '_all_', name: 'All Data', datasets }];
}

export default function SheetSelectionStep({
  workspaceTabs,
  selectedDatasets,
  setSelectedDatasets,
  onSelectPivot,
  onNewChart,
}: Props) {
  const dataTabs = workspaceTabs.filter(
    (t) => t.type !== 'pivot' && t.type !== 'chart' && t.datasets && t.datasets.length > 0
  );
  const pivotTabs = workspaceTabs.filter((t) => t.type === 'pivot' && t.pivotConfig);

  const groupOptions: GroupOption[] = dataTabs.flatMap(buildGroupOptions);

  const [open, setOpen] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const toggleGroupExpand = useCallback((id: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const toggleDataset = useCallback((ds: any) => {
    const key = getDatasetKey(ds);
    setSelectedDatasets(prev => {
      const exists = prev.some(d => getDatasetKey(d) === key);
      if (exists) return prev.filter(d => getDatasetKey(d) !== key);
      return [...prev, ds];
    });
  }, [setSelectedDatasets]);

  const totalIncluded = selectedDatasets.length;

  const hasData = groupOptions.length > 0 || pivotTabs.length > 0;

  if (!hasData) {
    return (
      <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
        <div style={{ fontSize: '0.688rem', color: C.textFaint, fontStyle: 'italic' }}>No data sources available</div>
        <div style={{ fontSize: '0.563rem', color: C.textGhost, marginTop: '0.25rem' }}>Add data first</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Dataset source picker — matches pivot's SourceGroupPicker */}
      {groupOptions.length > 0 && (
        <div>
          <div style={{ ...sectionHeader, marginBottom: '0.375rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            Source
            {onNewChart && (
              <Tooltip label="New chart">
                <button
                  onClick={onNewChart}
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
                color: totalIncluded > 0 ? C.text : C.textFaint,
                backgroundColor: 'white',
                cursor: 'pointer',
              }}
            >
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                {totalIncluded > 0 ? `${totalIncluded} selected` : 'Select datasets...'}
              </span>
              <svg
                style={{ width: 10, height: 10, color: C.textFaint, flexShrink: 0, transition: 'transform 0.15s ease', transform: open ? 'rotate(180deg)' : 'none' }}
                fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

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
                {groupOptions.map((g, gi) => {
                  const enabledCount = g.datasets.filter(ds => selectedDatasets.some(d => getDatasetKey(d) === getDatasetKey(ds))).length;
                  const isGroupExpanded = expandedGroups.has(g.id);
                  return (
                    <div key={g.id}>
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
                          color: C.textFaint,
                          background: 'none',
                          border: 'none',
                          borderRadius: '0.375rem',
                          cursor: 'pointer',
                          marginTop: gi !== 0 ? '0.25rem' : 0,
                          textAlign: 'left' as const,
                        }}
                        onMouseEnter={e => { e.currentTarget.style.backgroundColor = C.bgHover; }}
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
                            const checked = selectedDatasets.some(d => getDatasetKey(d) === key);
                            const sym = ds.symbol !== '_MARKET_' ? ds.symbol : 'Market';
                            return (
                              <button
                                key={key}
                                type="button"
                                onClick={() => toggleDataset(ds)}
                                style={{
                                  width: '100%',
                                  textAlign: 'left' as const,
                                  padding: '0.375rem 0.5rem',
                                  fontSize: '0.688rem',
                                  borderRadius: '0.5rem',
                                  border: 'none',
                                  backgroundColor: checked ? C.bgActive : 'transparent',
                                  opacity: checked ? 0.4 : 1,
                                  color: C.textMuted,
                                  cursor: 'pointer',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  gap: '0.5rem',
                                }}
                                onMouseEnter={e => { if (!checked) e.currentTarget.style.backgroundColor = C.bgHover; }}
                                onMouseLeave={e => { e.currentTarget.style.backgroundColor = checked ? C.bgActive : 'transparent'; }}
                              >
                                <span style={{ fontWeight: 500, fontFamily: mono, color: C.text }}>{sym}</span>
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, fontSize: '0.563rem', color: C.textFaint }}>
                                  {ds.endpoint}
                                </span>
                              </button>
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
      )}

      {/* Pivot tables */}
      {pivotTabs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem' }}>
          <div style={{ ...sectionHeader, fontSize: '0.5rem', marginBottom: '0.125rem', color: C.textGhost }}>Pivot Tables</div>
          {pivotTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => onSelectPivot(tab.id, tab.id, { pivotConfig: tab.pivotConfig, name: tab.name })}
              style={{
                width: '100%', textAlign: 'left' as const,
                padding: '0.375rem 0.5rem', fontSize: '0.688rem',
                borderRadius: '0.5rem', border: 'none',
                backgroundColor: 'transparent', color: C.textMuted,
                cursor: 'pointer', display: 'flex', alignItems: 'center',
                justifyContent: 'space-between', gap: '0.5rem',
                transition: 'all 0.1s ease',
              }}
              onMouseEnter={e => { e.currentTarget.style.backgroundColor = C.bgHover; }}
              onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            >
              <span style={{ fontWeight: 500, fontFamily: mono, color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{tab.name}</span>
              <span style={{ fontSize: '0.5rem', color: C.textFaint, flexShrink: 0 }}>
                {tab.pivotConfig?.values?.length || 0} val · {tab.pivotConfig?.rows?.length || 0} rows
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
