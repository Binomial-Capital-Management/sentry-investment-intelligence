import { useCallback } from 'react';
import { Mosaic, MosaicWindow, updateTree, createRemoveUpdate } from 'react-mosaic-component';
import type { MosaicNode, MosaicBranch } from 'react-mosaic-component';
import { X, Maximize2 } from 'lucide-react';
import type { ReviewTileId } from './types';
import { REVIEW_TILE_TITLES } from './types';
import PostMortemsTile from '../tiles/PostMortemsTile';

const TILE_COMPONENTS: Record<ReviewTileId, React.ComponentType> = {
  postMortems: PostMortemsTile,
};

const btnStyle: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer', padding: '3px 4px',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: '#9ca3af', borderRadius: '3px', lineHeight: 1, transition: 'color 0.1s, background 0.1s',
};

interface ReviewMosaicProps {
  value: MosaicNode<ReviewTileId> | null;
  onChange: (n: MosaicNode<ReviewTileId> | null) => void;
}

export default function ReviewMosaic({ value, onChange }: ReviewMosaicProps) {
  const handleRemove = useCallback((path: MosaicBranch[]) => {
    if (!value) return;
    onChange(updateTree(value, [createRemoveUpdate(value, path)]));
  }, [value, onChange]);

  const handleExpand = useCallback((path: MosaicBranch[]) => {
    if (!value) return;
    let node: MosaicNode<ReviewTileId> = value;
    for (const b of path) {
      if (typeof node === 'string') break;
      node = node[b] as MosaicNode<ReviewTileId>;
    }
    if (typeof node === 'string') onChange(node);
  }, [value, onChange]);

  const renderTile = useCallback((id: ReviewTileId, path: MosaicBranch[]) => {
    const Comp = TILE_COMPONENTS[id];
    return (
      <MosaicWindow<ReviewTileId>
        path={path}
        title={REVIEW_TILE_TITLES[id]}
        renderToolbar={(_p, draggable) => (
          <div className="mosaic-window-toolbar" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '0 6px 0 10px', height: '30px',
            background: '#fafafa', borderBottom: '1px solid #e5e7eb',
            cursor: draggable ? 'grab' : 'default', userSelect: 'none',
          }}>
            <span style={{ fontSize: '10px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {REVIEW_TILE_TITLES[id]}
            </span>
            <div style={{ display: 'flex', gap: '1px' }}>
              <button style={btnStyle} title="Expand"
                onClick={(e) => { e.stopPropagation(); handleExpand(path); }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#f3f4f6'; e.currentTarget.style.color = '#374151'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = '#9ca3af'; }}
              ><Maximize2 size={11} /></button>
              <button style={btnStyle} title="Close panel"
                onClick={(e) => { e.stopPropagation(); handleRemove(path); }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#fee2e2'; e.currentTarget.style.color = '#dc2626'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = '#9ca3af'; }}
              ><X size={12} /></button>
            </div>
          </div>
        )}
      ><Comp /></MosaicWindow>
    );
  }, [handleRemove, handleExpand]);

  return (
    <Mosaic<ReviewTileId>
      renderTile={renderTile} value={value} onChange={onChange}
      className="portfolio-mosaic"
      zeroStateView={
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9ca3af', gap: '8px' }}>
          <span style={{ fontSize: '14px', fontWeight: '500' }}>No panels open</span>
          <span style={{ fontSize: '12px' }}>Use the toolbar above to add panels</span>
        </div>
      }
    />
  );
}
