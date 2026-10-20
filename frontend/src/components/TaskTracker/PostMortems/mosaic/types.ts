import type { MosaicNode } from 'react-mosaic-component';

export const PM_TILE_IDS = ['metrics', 'transactions', 'chat'] as const;
export type PmTileId = (typeof PM_TILE_IDS)[number];

export const PM_TILE_TITLES: Record<PmTileId, string> = {
  metrics:      'Summary Metrics',
  transactions: 'Transactions',
  chat:         'AI Analysis',
};

export type PmPresetId = 'overview' | 'trades' | 'analysis';

export interface PmLayoutPreset {
  id: PmPresetId;
  label: string;
  description: string;
  node: MosaicNode<PmTileId>;
}
