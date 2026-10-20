import type { MosaicNode } from 'react-mosaic-component';

export const TILE_IDS = [
  'holdings',
  'performance',
  'transactions',
  'summary',
  'cash',
  'sectors',
  'weights',
  'riskAnalytics',
  'barraExposures',
  'pcaRisk',
  'factorTilts',
  'portfolioList',
] as const;

export type TileId = (typeof TILE_IDS)[number];

export const TILE_TITLES: Record<TileId, string> = {
  holdings: 'Holdings',
  performance: 'Performance',
  transactions: 'Transactions',
  summary: 'Portfolio Summary',
  cash: 'Cash Balance',
  sectors: 'Sector Allocation',
  weights: 'Portfolio Metrics',
  riskAnalytics: 'Risk Summary',
  barraExposures: 'Factor Exposures',
  pcaRisk: 'PCA Risk',
  factorTilts: 'Factor Tilts',
  portfolioList: 'Portfolios',
};

export type PresetId = 'overview' | 'trading' | 'analysis' | 'dashboard' | 'factor';

export interface LayoutPreset {
  id: PresetId;
  label: string;
  description: string;
  node: MosaicNode<TileId>;
}
