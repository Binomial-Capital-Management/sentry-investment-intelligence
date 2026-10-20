import type { MosaicNode } from 'react-mosaic-component';

export const REVIEW_TILE_IDS = ['postMortems'] as const;
export type ReviewTileId = (typeof REVIEW_TILE_IDS)[number];

export const REVIEW_TILE_TITLES: Record<ReviewTileId, string> = {
  postMortems: 'Trade Post-Mortems',
};

export type ReviewPresetId = 'postMortems';

export interface ReviewLayoutPreset {
  id: ReviewPresetId;
  label: string;
  description: string;
  node: MosaicNode<ReviewTileId>;
}
