import type { MarketLayoutPreset, MarketPresetId } from './types';

export const MARKET_LAYOUT_PRESETS: Record<MarketPresetId, MarketLayoutPreset> = {
  equities: {
    id: 'equities',
    label: 'Equities',
    description: 'Stocks heatmap + stock screener',
    node: {
      direction: 'row',
      first: 'stocksHeatmap',
      second: 'stockScreener',
      splitPercentage: 55,
    },
  },

  crypto: {
    id: 'crypto',
    label: 'Crypto',
    description: 'Crypto heatmap + crypto screener',
    node: {
      direction: 'row',
      first: 'cryptoHeatmap',
      second: 'cryptoScreener',
      splitPercentage: 55,
    },
  },

  research: {
    id: 'research',
    label: 'Research',
    description: 'Chart + screener + ETF heatmap',
    node: {
      direction: 'row',
      first: 'chart',
      second: {
        direction: 'column',
        first: 'stockScreener',
        second: 'etfHeatmap',
        splitPercentage: 55,
      },
      splitPercentage: 60,
    },
  },

  global: {
    id: 'global',
    label: 'Global',
    description: 'Stocks heatmap + forex screener',
    node: {
      direction: 'row',
      first: 'stocksHeatmap',
      second: 'forexScreener',
      splitPercentage: 55,
    },
  },
};

export const DEFAULT_MARKET_PRESET_ID: MarketPresetId = 'equities';
