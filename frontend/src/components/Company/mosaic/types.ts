import type { MosaicNode } from 'react-mosaic-component';

export const COMPANY_TILE_IDS = [
  'chart',
  'symbolInfo',
  'profile',
  'financials',
  'sectorCompare',
] as const;

export type CompanyTileId = (typeof COMPANY_TILE_IDS)[number];

export const COMPANY_TILE_TITLES: Record<CompanyTileId, string> = {
  chart:         'Price Chart',
  symbolInfo:    'Symbol Info',
  profile:       'Company Profile',
  financials:    'Financials',
  sectorCompare: 'GICS Sector Compare',
};

export type CompanyPresetId = 'overview' | 'analysis' | 'chart';

export interface CompanyLayoutPreset {
  id: CompanyPresetId;
  label: string;
  description: string;
  node: MosaicNode<CompanyTileId>;
}
