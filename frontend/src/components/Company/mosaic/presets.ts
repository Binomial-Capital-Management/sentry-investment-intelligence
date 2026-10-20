import type { CompanyLayoutPreset, CompanyPresetId } from './types';

export const COMPANY_LAYOUT_PRESETS: Record<CompanyPresetId, CompanyLayoutPreset> = {
  overview: {
    id: 'overview',
    label: 'Overview',
    description: 'Chart + sector compare + symbol info + profile',
    node: {
      direction: 'row',
      first: {
        direction: 'column',
        first: 'chart',
        second: 'sectorCompare',
        splitPercentage: 55,
      },
      second: {
        direction: 'column',
        first: 'symbolInfo',
        second: 'profile',
        splitPercentage: 28,
      },
      splitPercentage: 65,
    },
  },

  analysis: {
    id: 'analysis',
    label: 'Analysis',
    description: 'Chart top, sector compare + financials below',
    node: {
      direction: 'column',
      first: 'chart',
      second: {
        direction: 'row',
        first: 'sectorCompare',
        second: 'financials',
        splitPercentage: 45,
      },
      splitPercentage: 55,
    },
  },

  chart: {
    id: 'chart',
    label: 'Chart',
    description: 'Full-screen price chart',
    node: 'chart',
  },
};

export const DEFAULT_COMPANY_PRESET_ID: CompanyPresetId = 'overview';
