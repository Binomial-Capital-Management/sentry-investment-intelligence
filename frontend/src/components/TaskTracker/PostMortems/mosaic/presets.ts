import type { PmLayoutPreset, PmPresetId } from './types';

export const PM_LAYOUT_PRESETS: Record<PmPresetId, PmLayoutPreset> = {
  overview: {
    id: 'overview',
    label: 'Overview',
    description: 'Metrics + trades on the left, AI analysis on the right',
    node: {
      direction: 'row',
      first: {
        direction: 'column',
        first: 'metrics',
        second: 'transactions',
        splitPercentage: 22,
      },
      second: 'chat',
      splitPercentage: 60,
    },
  },
  trades: {
    id: 'trades',
    label: 'Trades',
    description: 'Metrics + transactions only',
    node: {
      direction: 'column',
      first: 'metrics',
      second: 'transactions',
      splitPercentage: 22,
    },
  },
  analysis: {
    id: 'analysis',
    label: 'Analysis',
    description: 'Transactions + AI analysis side by side',
    node: {
      direction: 'row',
      first: 'transactions',
      second: 'chat',
      splitPercentage: 45,
    },
  },
};

export const DEFAULT_PM_PRESET_ID: PmPresetId = 'overview';
