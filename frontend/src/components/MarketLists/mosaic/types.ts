import type { MosaicNode } from 'react-mosaic-component';

export const MARKET_TILE_IDS = [
  'stocksHeatmap',
  'cryptoHeatmap',
  'etfHeatmap',
  'stockScreener',
  'forexScreener',
  'cryptoScreener',
  'chart',
  'annotations',
] as const;

export type MarketTileId = (typeof MARKET_TILE_IDS)[number];

export const MARKET_TILE_TITLES: Record<MarketTileId, string> = {
  stocksHeatmap:  'Stocks Heatmap',
  cryptoHeatmap:  'Crypto Heatmap',
  etfHeatmap:     'ETF Heatmap',
  stockScreener:  'Stock Screener',
  forexScreener:  'Forex Screener',
  cryptoScreener: 'Crypto Screener',
  chart:          'Technical Chart',
  annotations:    'Annotation Tool',
};

export type MarketPresetId = 'equities' | 'crypto' | 'research' | 'global';

export interface MarketLayoutPreset {
  id: MarketPresetId;
  label: string;
  description: string;
  node: MosaicNode<MarketTileId>;
}
