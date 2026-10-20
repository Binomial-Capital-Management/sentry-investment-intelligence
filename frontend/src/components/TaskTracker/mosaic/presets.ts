import type { ReviewLayoutPreset, ReviewPresetId } from './types';

export const REVIEW_LAYOUT_PRESETS: Record<ReviewPresetId, ReviewLayoutPreset> = {
  postMortems: {
    id: 'postMortems',
    label: 'Post-Mortems',
    description: 'Trade post-mortems and analysis',
    node: 'postMortems',
  },
};

export const DEFAULT_REVIEW_PRESET_ID: ReviewPresetId = 'postMortems';
