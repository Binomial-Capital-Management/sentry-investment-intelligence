import { useState, useRef, useEffect } from 'react';
import { LayoutGrid, RotateCcw, Plus, ChevronDown } from 'lucide-react';
import type { MosaicNode } from 'react-mosaic-component';
import type { CompanyTileId, CompanyPresetId } from './types';
import { COMPANY_TILE_IDS, COMPANY_TILE_TITLES } from './types';
import { COMPANY_LAYOUT_PRESETS } from './presets';

function collectLeaves(node: MosaicNode<CompanyTileId> | null): Set<CompanyTileId> {
  if (!node) return new Set();
  if (typeof node === 'string') return new Set([node]);
  return new Set([...collectLeaves(node.first), ...collectLeaves(node.second)]);
}

interface CompanyMosaicToolbarProps {
  currentNode: MosaicNode<CompanyTileId> | null;
  onNodeChange: (node: MosaicNode<CompanyTileId> | null) => void;
  activePreset: CompanyPresetId;
  onPresetChange: (id: CompanyPresetId) => void;
}

export default function CompanyMosaicToolbar({
  currentNode,
  onNodeChange,
  activePreset,
  onPresetChange,
}: CompanyMosaicToolbarProps) {
  const [showAddMenu, setShowAddMenu] = useState(false);
  const addMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const visibleTiles = collectLeaves(currentNode);
  const hiddenTiles = COMPANY_TILE_IDS.filter(id => !visibleTiles.has(id));

  const handleAddTile = (tileId: CompanyTileId) => {
    if (!currentNode) {
      onNodeChange(tileId);
    } else {
      onNodeChange({
        direction: 'row',
        first: currentNode,
        second: tileId,
        splitPercentage: 75,
      });
    }
    setShowAddMenu(false);
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '6px 16px',
      background: '#fff',
      borderBottom: '1px solid #e5e7eb',
      flexWrap: 'wrap',
      position: 'relative',
      zIndex: 100,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginRight: '8px' }}>
        <LayoutGrid size={14} style={{ color: '#6b7280' }} />
        <span style={{ fontSize: '11px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Layout
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {Object.values(COMPANY_LAYOUT_PRESETS).map((preset) => (
          <button
            key={preset.id}
            onClick={() => { onPresetChange(preset.id); onNodeChange(preset.node); }}
            title={preset.description}
            style={{
              padding: '4px 10px',
              fontSize: '12px',
              fontWeight: '500',
              border: '1px solid',
              borderColor: activePreset === preset.id ? '#2563eb' : '#e5e7eb',
              borderRadius: '6px',
              background: activePreset === preset.id ? '#eff6ff' : '#fff',
              color: activePreset === preset.id ? '#2563eb' : '#6b7280',
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              if (activePreset !== preset.id) {
                e.currentTarget.style.background = '#f9fafb';
                e.currentTarget.style.borderColor = '#d1d5db';
              }
            }}
            onMouseLeave={(e) => {
              if (activePreset !== preset.id) {
                e.currentTarget.style.background = '#fff';
                e.currentTarget.style.borderColor = '#e5e7eb';
              }
            }}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div style={{ width: '1px', height: '20px', background: '#e5e7eb', margin: '0 4px' }} />

      <div ref={addMenuRef} style={{ position: 'relative', zIndex: 100 }}>
        <button
          onClick={() => setShowAddMenu(!showAddMenu)}
          disabled={hiddenTiles.length === 0}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '4px 10px',
            fontSize: '12px',
            fontWeight: '500',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            background: '#fff',
            color: hiddenTiles.length === 0 ? '#d1d5db' : '#6b7280',
            cursor: hiddenTiles.length === 0 ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit',
            transition: 'all 0.15s',
          }}
        >
          <Plus size={12} />
          Add Panel
          <ChevronDown size={10} />
        </button>

        {showAddMenu && hiddenTiles.length > 0 && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '4px',
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 50,
            minWidth: '160px',
            overflow: 'hidden',
          }}>
            {hiddenTiles.map((tileId) => (
              <button
                key={tileId}
                onClick={() => handleAddTile(tileId)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  fontSize: '12px',
                  fontWeight: '500',
                  border: 'none',
                  background: 'transparent',
                  color: '#374151',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  textAlign: 'left',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#f3f4f6')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                {COMPANY_TILE_TITLES[tileId]}
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        onClick={() => onNodeChange(COMPANY_LAYOUT_PRESETS[activePreset].node)}
        title="Reset to current preset layout"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          padding: '4px 10px',
          fontSize: '12px',
          fontWeight: '500',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          background: '#fff',
          color: '#6b7280',
          cursor: 'pointer',
          fontFamily: 'inherit',
          transition: 'all 0.15s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = '#f9fafb'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = '#fff'; }}
      >
        <RotateCcw size={12} />
        Reset
      </button>
    </div>
  );
}
