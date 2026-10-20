import { useCallback } from 'react';
import { Mosaic, MosaicWindow, updateTree, createRemoveUpdate } from 'react-mosaic-component';
import type { MosaicNode, MosaicBranch } from 'react-mosaic-component';
import { X, Maximize2 } from 'lucide-react';
import type { TileId } from './types';
import { TILE_TITLES } from './types';

import HoldingsTile from '../tiles/HoldingsTile';
import PerformanceTile from '../tiles/PerformanceTile';
import TransactionsTile from '../tiles/TransactionsTile';
import SummaryTile from '../tiles/SummaryTile';
import CashTile from '../tiles/CashTile';
import SectorsTile from '../tiles/SectorsTile';
import WeightsTile from '../tiles/WeightsTile';
import RiskAnalyticsTile from '../tiles/RiskAnalyticsTile';
import BarraExposuresTile from '../tiles/BarraExposuresTile';
import PCARiskTile from '../tiles/PCARiskTile';
import FactorTiltsTile from '../tiles/FactorTiltsTile';
import PortfolioListTile from '../tiles/PortfolioListTile';

const TILE_COMPONENTS: Record<TileId, React.ComponentType> = {
  holdings: HoldingsTile,
  performance: PerformanceTile,
  transactions: TransactionsTile,
  summary: SummaryTile,
  cash: CashTile,
  sectors: SectorsTile,
  weights: WeightsTile,
  riskAnalytics: RiskAnalyticsTile,
  barraExposures: BarraExposuresTile,
  pcaRisk: PCARiskTile,
  factorTilts: FactorTiltsTile,
  portfolioList: PortfolioListTile,
};

interface PortfolioMosaicProps {
  value: MosaicNode<TileId> | null;
  onChange: (node: MosaicNode<TileId> | null) => void;
}

const toolbarBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: '3px 4px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: '#9ca3af',
  borderRadius: '3px',
  lineHeight: 1,
  transition: 'color 0.1s, background 0.1s',
};

export default function PortfolioMosaic({ value, onChange }: PortfolioMosaicProps) {
  const handleRemove = useCallback((path: MosaicBranch[]) => {
    if (!value) return;
    const newNode = updateTree(value, [createRemoveUpdate(value, path)]);
    onChange(newNode);
  }, [value, onChange]);

  const handleExpand = useCallback((path: MosaicBranch[]) => {
    if (!value) return;
    let node: MosaicNode<TileId> = value;
    for (const branch of path) {
      if (typeof node === 'string') break;
      node = node[branch] as MosaicNode<TileId>;
    }
    if (typeof node === 'string') onChange(node);
  }, [value, onChange]);

  const renderTile = useCallback((id: TileId, path: MosaicBranch[]) => {
    const TileComponent = TILE_COMPONENTS[id];

    return (
      <MosaicWindow<TileId>
        path={path}
        title={TILE_TITLES[id]}
        renderToolbar={(_props, draggable) => (
          <div
            className="mosaic-window-toolbar"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 6px 0 10px',
              height: '30px',
              background: '#fafafa',
              borderBottom: '1px solid #e5e7eb',
              cursor: draggable ? 'grab' : 'default',
              userSelect: 'none',
            }}
          >
            <span style={{
              fontSize: '10px',
              fontWeight: '700',
              color: '#9ca3af',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}>
              {TILE_TITLES[id]}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1px' }}>
              <button
                style={toolbarBtnStyle}
                title="Expand"
                onClick={(e) => { e.stopPropagation(); handleExpand(path); }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#f3f4f6'; e.currentTarget.style.color = '#374151'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = '#9ca3af'; }}
              >
                <Maximize2 size={11} />
              </button>
              <button
                style={toolbarBtnStyle}
                title="Close panel"
                onClick={(e) => { e.stopPropagation(); handleRemove(path); }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#fee2e2'; e.currentTarget.style.color = '#dc2626'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = '#9ca3af'; }}
              >
                <X size={12} />
              </button>
            </div>
          </div>
        )}
      >
        <TileComponent />
      </MosaicWindow>
    );
  }, [handleRemove, handleExpand]);

  return (
    <Mosaic<TileId>
      renderTile={renderTile}
      value={value}
      onChange={onChange}
      className="portfolio-mosaic"
      zeroStateView={
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: '#9ca3af',
          gap: '8px',
        }}>
          <span style={{ fontSize: '14px', fontWeight: '500' }}>No panels open</span>
          <span style={{ fontSize: '12px' }}>Select a layout preset from the toolbar above</span>
        </div>
      }
    />
  );
}
