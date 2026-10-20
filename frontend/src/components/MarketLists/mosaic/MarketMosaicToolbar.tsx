import { useState, useRef, useEffect } from 'react';
import { LayoutGrid, RotateCcw, Plus, ChevronDown } from 'lucide-react';
import type { MosaicNode } from 'react-mosaic-component';
import type { MarketTileId, MarketPresetId } from './types';
import { MARKET_TILE_IDS, MARKET_TILE_TITLES } from './types';
import { MARKET_LAYOUT_PRESETS } from './presets';

function collectLeaves(node: MosaicNode<MarketTileId> | null): Set<MarketTileId> {
  if (!node) return new Set();
  if (typeof node === 'string') return new Set([node]);
  return new Set([...collectLeaves(node.first), ...collectLeaves(node.second)]);
}

interface MarketMosaicToolbarProps {
  currentNode: MosaicNode<MarketTileId> | null;
  onNodeChange: (node: MosaicNode<MarketTileId> | null) => void;
  activePreset: MarketPresetId;
  onPresetChange: (id: MarketPresetId) => void;
}

export default function MarketMosaicToolbar({
  currentNode,
  onNodeChange,
  activePreset,
  onPresetChange,
}: MarketMosaicToolbarProps) {
  const [showAddMenu, setShowAddMenu] = useState(false);
  const addMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const visible  = collectLeaves(currentNode);
  const hidden   = MARKET_TILE_IDS.filter(id => !visible.has(id));

  const handleAdd = (id: MarketTileId) => {
    onNodeChange(currentNode
      ? { direction: 'row', first: currentNode, second: id, splitPercentage: 65 }
      : id
    );
    setShowAddMenu(false);
  };

  const btnBase: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '4px',
    padding: '4px 10px', fontSize: '12px', fontWeight: '500',
    border: '1px solid #e5e7eb', borderRadius: '6px',
    background: '#fff', cursor: 'pointer', fontFamily: 'inherit',
    transition: 'all 0.15s',
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '8px',
      padding: '6px 16px', background: '#fff',
      borderBottom: '1px solid #e5e7eb',
      flexWrap: 'wrap', position: 'relative', zIndex: 100,
    }}>
      {/* Label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginRight: '8px' }}>
        <LayoutGrid size={14} style={{ color: '#6b7280' }} />
        <span style={{ fontSize: '11px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Layout
        </span>
      </div>

      {/* Presets */}
      <div style={{ display: 'flex', gap: '4px' }}>
        {Object.values(MARKET_LAYOUT_PRESETS).map((preset) => (
          <button
            key={preset.id}
            onClick={() => { onPresetChange(preset.id); onNodeChange(preset.node); }}
            title={preset.description}
            style={{
              ...btnBase,
              borderColor: activePreset === preset.id ? '#2563eb' : '#e5e7eb',
              background:  activePreset === preset.id ? '#eff6ff'  : '#fff',
              color:       activePreset === preset.id ? '#2563eb'  : '#6b7280',
            }}
            onMouseEnter={(e) => {
              if (activePreset !== preset.id) {
                e.currentTarget.style.background   = '#f9fafb';
                e.currentTarget.style.borderColor  = '#d1d5db';
              }
            }}
            onMouseLeave={(e) => {
              if (activePreset !== preset.id) {
                e.currentTarget.style.background   = '#fff';
                e.currentTarget.style.borderColor  = '#e5e7eb';
              }
            }}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div style={{ width: '1px', height: '20px', background: '#e5e7eb', margin: '0 4px' }} />

      {/* Add panel */}
      <div ref={addMenuRef} style={{ position: 'relative', zIndex: 100 }}>
        <button
          onClick={() => setShowAddMenu(s => !s)}
          disabled={hidden.length === 0}
          style={{
            ...btnBase,
            color: hidden.length === 0 ? '#d1d5db' : '#6b7280',
            cursor: hidden.length === 0 ? 'not-allowed' : 'pointer',
          }}
        >
          <Plus size={12} />
          Add Panel
          <ChevronDown size={10} />
        </button>

        {showAddMenu && hidden.length > 0 && (
          <div style={{
            position: 'absolute', top: '100%', left: 0, marginTop: '4px',
            background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)', zIndex: 200,
            minWidth: '180px', overflow: 'hidden',
          }}>
            {hidden.map((id) => (
              <button
                key={id}
                onClick={() => handleAdd(id)}
                style={{
                  width: '100%', padding: '8px 14px', fontSize: '12px', fontWeight: '500',
                  border: 'none', background: 'transparent', color: '#374151',
                  cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#f3f4f6')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                {MARKET_TILE_TITLES[id]}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Reset */}
      <button
        onClick={() => onNodeChange(MARKET_LAYOUT_PRESETS[activePreset].node)}
        style={{ ...btnBase, color: '#6b7280' }}
        onMouseEnter={(e) => { e.currentTarget.style.background = '#f9fafb'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = '#fff'; }}
        title="Reset to current preset"
      >
        <RotateCcw size={12} />
        Reset
      </button>
    </div>
  );
}
