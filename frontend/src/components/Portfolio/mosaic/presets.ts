import type { LayoutPreset } from './types';

export const LAYOUT_PRESETS: Record<string, LayoutPreset> = {
  overview: {
    id: 'overview',
    label: 'Overview',
    description: 'Holdings with summary and risk sidebar',
    node: {
      direction: 'row',
      first: 'holdings',
      second: {
        direction: 'column',
        first: 'summary',
        second: {
          direction: 'column',
          first: 'riskAnalytics',
          second: 'sectors',
          splitPercentage: 55,
        },
        splitPercentage: 25,
      },
      splitPercentage: 62,
    },
  },

  trading: {
    id: 'trading',
    label: 'Trading',
    description: 'Holdings and transactions with cash view',
    node: {
      direction: 'row',
      first: {
        direction: 'column',
        first: 'holdings',
        second: 'transactions',
        splitPercentage: 60,
      },
      second: {
        direction: 'column',
        first: 'summary',
        second: 'cash',
        splitPercentage: 50,
      },
      splitPercentage: 72,
    },
  },

  analysis: {
    id: 'analysis',
    label: 'Risk',
    description: 'Risk analytics with factor exposures and performance',
    node: {
      direction: 'row',
      first: {
        direction: 'column',
        first: 'riskAnalytics',
        second: 'sectors',
        splitPercentage: 55,
      },
      second: {
        direction: 'column',
        first: 'performance',
        second: 'weights',
        splitPercentage: 60,
      },
      splitPercentage: 40,
    },
  },

  factor: {
    id: 'factor',
    label: 'Factor',
    description: 'Barra factor model, PCA risk and active tilts vs benchmark',
    node: {
      direction: 'column',
      first: {
        direction: 'row',
        first: 'riskAnalytics',
        second: 'barraExposures',
        splitPercentage: 38,
      },
      second: {
        direction: 'row',
        first: 'pcaRisk',
        second: 'factorTilts',
        splitPercentage: 50,
      },
      splitPercentage: 45,
    },
  },

  dashboard: {
    id: 'dashboard',
    label: 'Dashboard',
    description: 'Full overview with all key panels',
    node: {
      direction: 'column',
      first: {
        direction: 'row',
        first: 'holdings',
        second: {
          direction: 'row',
          first: 'riskAnalytics',
          second: 'sectors',
          splitPercentage: 55,
        },
        splitPercentage: 55,
      },
      second: {
        direction: 'row',
        first: 'performance',
        second: {
          direction: 'row',
          first: 'weights',
          second: 'summary',
          splitPercentage: 55,
        },
        splitPercentage: 55,
      },
      splitPercentage: 55,
    },
  },
};

export const DEFAULT_PRESET_ID = 'overview';
