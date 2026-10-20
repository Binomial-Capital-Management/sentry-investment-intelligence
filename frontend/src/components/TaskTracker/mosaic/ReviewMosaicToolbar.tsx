import { useState, useRef, useEffect } from 'react';
import { LayoutGrid, RotateCcw, Plus, ChevronDown } from 'lucide-react';
import type { MosaicNode } from 'react-mosaic-component';
import type { ReviewTileId, ReviewPresetId } from './types';
import { REVIEW_TILE_IDS, REVIEW_TILE_TITLES } from './types';
import { REVIEW_LAYOUT_PRESETS } from './presets';

function collectLeaves(node: MosaicNode<ReviewTileId> | null): Set<ReviewTileId> {
  if (!node) return new Set();
  if (typeof node === 'string') return new Set([node]);
  return new Set([...collectLeaves(node.first), ...collectLeaves(node.second)]);
}

interface ReviewMosaicToolbarProps {
  currentNode: MosaicNode<ReviewTileId> | null;
  onNodeChange: (n: MosaicNode<ReviewTileId> | null) => void;
  activePreset: ReviewPresetId;
  onPresetChange: (id: ReviewPresetId) => void;
}

export default function ReviewMosaicToolbar({ currentNode, onNodeChange, activePreset, onPresetChange }: ReviewMosaicToolbarProps) {
  const [showAdd, setShowAdd] = useState(false);
  const addRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (addRef.current && !addRef.current.contains(e.target as Node)) setShowAdd(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const visible = collectLeaves(currentNode);
  const hidden  = REVIEW_TILE_IDS.filter(id => !visible.has(id));

  const base: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px',
    fontSize: '12px', fontWeight: '500', border: '1px solid #e5e7eb',
    borderRadius: '6px', background: '#fff', cursor: 'pointer',
    fontFamily: 'inherit', transition: 'all 0.15s',
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 16px', background: '#fff', borderBottom: '1px solid #e5e7eb', flexWrap: 'wrap', position: 'relative', zIndex: 100 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginRight: '8px' }}>
        <LayoutGrid size={14} style={{ color: '#6b7280' }} />
        <span style={{ fontSize: '11px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Layout</span>
      </div>

      <div style={{ display: 'flex', gap: '4px' }}>
        {Object.values(REVIEW_LAYOUT_PRESETS).map(p => (
          <button key={p.id} title={p.description}
            onClick={() => { onPresetChange(p.id); onNodeChange(p.node); }}
            style={{ ...base, borderColor: activePreset === p.id ? '#2563eb' : '#e5e7eb', background: activePreset === p.id ? '#eff6ff' : '#fff', color: activePreset === p.id ? '#2563eb' : '#6b7280' }}
            onMouseEnter={(e) => { if (activePreset !== p.id) { e.currentTarget.style.background = '#f9fafb'; e.currentTarget.style.borderColor = '#d1d5db'; } }}
            onMouseLeave={(e) => { if (activePreset !== p.id) { e.currentTarget.style.background = '#fff'; e.currentTarget.style.borderColor = '#e5e7eb'; } }}
          >{p.label}</button>
        ))}
      </div>

      <div style={{ width: '1px', height: '20px', background: '#e5e7eb', margin: '0 4px' }} />

      <div ref={addRef} style={{ position: 'relative', zIndex: 100 }}>
        <button onClick={() => setShowAdd(s => !s)} disabled={hidden.length === 0}
          style={{ ...base, color: hidden.length === 0 ? '#d1d5db' : '#6b7280', cursor: hidden.length === 0 ? 'not-allowed' : 'pointer' }}>
          <Plus size={12} />Add Panel<ChevronDown size={10} />
        </button>
        {showAdd && hidden.length > 0 && (
          <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: '4px', background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', zIndex: 200, minWidth: '180px', overflow: 'hidden' }}>
            {hidden.map(id => (
              <button key={id} onClick={() => { onNodeChange(currentNode ? { direction: 'row', first: currentNode, second: id, splitPercentage: 60 } : id); setShowAdd(false); }}
                style={{ width: '100%', padding: '8px 12px', fontSize: '12px', fontWeight: '500', border: 'none', background: 'transparent', color: '#374151', cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left', transition: 'background 0.1s' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#f3f4f6')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >{REVIEW_TILE_TITLES[id]}</button>
            ))}
          </div>
        )}
      </div>

      <button onClick={() => onNodeChange(REVIEW_LAYOUT_PRESETS[activePreset].node)} style={{ ...base, color: '#6b7280' }}
        onMouseEnter={(e) => { e.currentTarget.style.background = '#f9fafb'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = '#fff'; }}
      ><RotateCcw size={12} />Reset</button>
    </div>
  );
}
