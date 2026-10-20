import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Plus } from 'lucide-react';
import { useDataWorkspaceStore } from '../../stores/dataWorkspaceStore';
import {
  selectDatasetGroups,
  selectActiveGroupId,
  selectActiveAnalysisGroupId,
  selectActivePivotGroupId,
  selectActiveChartGroupId,
  selectGroupsWithCounts,
} from '../../stores/selectors';

const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const TEXT_200 = '60 2.5% 23.3%';
const BORDER_200 = '30 3.3% 11.8%';

interface GroupPickerProps {
  /** Which active-group pointer to read/write. Defaults to 'sources'. */
  mode?: 'sources' | 'analysis' | 'pivot' | 'chart';
}

export function GroupPicker({ mode = 'sources' }: GroupPickerProps = {}) {
  const groups = useDataWorkspaceStore(selectDatasetGroups);
  const groupsWithCounts = useDataWorkspaceStore(selectGroupsWithCounts);
  const sourcesActiveId = useDataWorkspaceStore(selectActiveGroupId);
  const analysisActiveId = useDataWorkspaceStore(selectActiveAnalysisGroupId);
  const pivotActiveId = useDataWorkspaceStore(selectActivePivotGroupId);
  const chartActiveId = useDataWorkspaceStore(selectActiveChartGroupId);
  const activeGroupId = mode === 'analysis'
    ? analysisActiveId
    : mode === 'pivot'
      ? pivotActiveId
      : mode === 'chart'
        ? chartActiveId
        : sourcesActiveId;
  const setSourcesActive = useDataWorkspaceStore(s => s.setActiveGroup);
  const setAnalysisActive = useDataWorkspaceStore(s => s.setActiveAnalysisGroup);
  const setPivotActive = useDataWorkspaceStore(s => s.setActivePivotGroup);
  const setChartActive = useDataWorkspaceStore(s => s.setActiveChartGroup);
  const setActiveGroup = mode === 'analysis'
    ? setAnalysisActive
    : mode === 'pivot'
      ? setPivotActive
      : mode === 'chart'
        ? setChartActive
        : setSourcesActive;
  const createDatasetGroup = useDataWorkspaceStore(s => s.createDatasetGroup);

  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
        setNewName('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  useEffect(() => {
    if (creating && inputRef.current) {
      inputRef.current.focus();
    }
  }, [creating]);

  const activeGroup = groupsWithCounts.find(g => g.id === activeGroupId);
  const emptyLabel = mode === 'analysis' ? 'Analyses' : mode === 'pivot' ? 'Pivots' : mode === 'chart' ? 'Charts' : 'Data';
  const displayName = activeGroup?.name ?? (groups.length === 0 ? emptyLabel : 'Select group');
  const displayCount = mode === 'analysis'
    ? (activeGroup?.toolResultCount ?? 0)
    : mode === 'pivot'
      ? (activeGroup?.pivotResultCount ?? 0)
      : mode === 'chart'
        ? (activeGroup?.chartResultCount ?? 0)
        : (activeGroup?.datasetCount ?? 0);

  const handleCreate = () => {
    const name = newName.trim() || 'New Group';
    const newId = createDatasetGroup(name);
    setActiveGroup(newId);
    setCreating(false);
    setNewName('');
    setOpen(false);
  };

  return (
    <div style={{ padding: '0.375rem 1rem', display: 'flex', alignItems: 'center', gap: '0.375rem', fontFamily: FONT_UI }} ref={dropdownRef}>
      <span style={{ fontSize: '0.563rem', color: `hsl(${TEXT_200} / 35%)`, fontWeight: 500 }}>Add to:</span>

      <div className="relative" style={{ flex: 1 }}>
        <button
          onClick={() => setOpen(!open)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            padding: '0.25rem 0.5rem',
            fontSize: '0.625rem',
            fontWeight: 500,
            fontFamily: FONT_UI,
            color: `hsl(${TEXT_200})`,
            backgroundColor: `hsl(${BORDER_200} / 3%)`,
            border: `0.5px solid hsl(${BORDER_200} / 15%)`,
            borderRadius: '0.375rem',
            cursor: 'pointer',
            transition: 'all 0.1s ease',
            width: '100%',
          }}
        >
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{displayName}</span>
          {groups.length > 0 && (
            <span style={{ fontSize: '0.5rem', color: `hsl(${TEXT_200} / 30%)`, flexShrink: 0 }}>{displayCount}</span>
          )}
          {groups.length === 0 && (
            <span style={{ fontSize: '0.5rem', color: `hsl(${TEXT_200} / 30%)`, fontStyle: 'italic', flexShrink: 0 }}>new</span>
          )}
          <ChevronDown
            className={`transition-transform ${open ? 'rotate-180' : ''}`}
            style={{ width: 10, height: 10, color: `hsl(${TEXT_200} / 30%)`, flexShrink: 0, marginLeft: 'auto' }}
          />
        </button>

        {open && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            backgroundColor: '#fff',
            border: `0.5px solid hsl(${BORDER_200} / 20%)`,
            borderRadius: '0.75rem',
            boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
            zIndex: 20,
            padding: '0.25rem',
            maxHeight: 192,
            overflowY: 'auto',
            fontFamily: FONT_UI,
          }}>
            {groupsWithCounts.map(g => (
              <button
                key={g.id}
                onClick={() => {
                  setActiveGroup(g.id);
                  setOpen(false);
                }}
                className="ep-browser-item"
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '0.375rem 0.625rem',
                  fontSize: '0.625rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderRadius: '0.5rem',
                  border: 'none',
                  backgroundColor: g.id === activeGroupId ? `hsl(${BORDER_200} / 8%)` : 'transparent',
                  fontWeight: g.id === activeGroupId ? 600 : 400,
                  color: g.id === activeGroupId ? `hsl(${TEXT_200})` : `hsl(${TEXT_200} / 60%)`,
                  cursor: 'pointer',
                  transition: 'all 0.1s ease',
                  fontFamily: FONT_UI,
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.name}</span>
                <span style={{ fontSize: '0.5rem', color: `hsl(${TEXT_200} / 25%)`, flexShrink: 0, marginLeft: '0.5rem' }}>
                  {mode === 'analysis' ? g.toolResultCount : mode === 'pivot' ? g.pivotResultCount : mode === 'chart' ? g.chartResultCount : g.datasetCount}
                </span>
              </button>
            ))}

            {creating ? (
              <div style={{ padding: '0.375rem 0.625rem', borderTop: `0.5px solid hsl(${BORDER_200} / 10%)`, marginTop: '0.25rem', paddingTop: '0.5rem' }}>
                <input
                  ref={inputRef}
                  type="text"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleCreate();
                    if (e.key === 'Escape') { setCreating(false); setNewName(''); }
                  }}
                  placeholder="Group name"
                  style={{
                    width: '100%',
                    padding: '0.25rem 0.5rem',
                    fontSize: '0.625rem',
                    fontFamily: FONT_UI,
                    border: `0.5px solid hsl(${BORDER_200} / 20%)`,
                    borderRadius: '0.375rem',
                    outline: 'none',
                    color: `hsl(${TEXT_200})`,
                    marginBottom: '0.375rem',
                  }}
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                  <button
                    onClick={() => { setCreating(false); setNewName(''); }}
                    style={{
                      flex: 1, padding: '0.25rem 0', fontSize: '0.625rem', fontWeight: 500, fontFamily: FONT_UI,
                      color: `hsl(${TEXT_200} / 45%)`, background: 'none', border: 'none', borderRadius: '0.375rem', cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreate}
                    style={{
                      flex: 1, padding: '0.25rem 0', fontSize: '0.625rem', fontWeight: 500, fontFamily: FONT_UI,
                      color: `hsl(${TEXT_200})`, backgroundColor: `hsl(${BORDER_200} / 6%)`, border: `0.5px solid hsl(${BORDER_200} / 12%)`,
                      borderRadius: '0.375rem', cursor: 'pointer',
                    }}
                  >
                    Create
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setCreating(true)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '0.375rem 0.625rem',
                  fontSize: '0.625rem',
                  fontFamily: FONT_UI,
                  color: `hsl(${TEXT_200} / 40%)`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.375rem',
                  borderTop: `0.5px solid hsl(${BORDER_200} / 10%)`,
                  marginTop: '0.25rem',
                  paddingTop: '0.5rem',
                  background: 'none',
                  border: 'none',
                  borderRadius: '0.5rem',
                  cursor: 'pointer',
                }}
              >
                <Plus style={{ width: 12, height: 12 }} />
                New group
              </button>
            )}
          </div>
        )}
      </div>

    </div>
  );
}
