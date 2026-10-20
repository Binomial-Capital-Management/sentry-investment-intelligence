/**
 * CompatibilityBadge - Shows the compatibility group of a dataset/endpoint.
 * 
 * Visual indicator for data structure type, helping users understand
 * which datasets can be merged together.
 */

import React from 'react';
import { useCompatibilityGroupColors } from '@/hooks/useDatasetCompatibility';

interface CompatibilityBadgeProps {
  group: string;
  size?: 'sm' | 'md' | 'lg';
  showTooltip?: boolean;
}

const GROUP_LABELS: Record<string, string> = {
  'fiscal_period': 'Fiscal',
  'daily_series': 'Daily',
  'point_in_time': 'Snapshot',
  'event_list': 'Events',
  'market_wide': 'Market',
  'options': 'Options',
  'crypto': 'Crypto',
  'commodity': 'Commodity',
  'forex': 'Forex',
  'filing': 'Filing',
  'intraday': 'Intraday',
  'technical': 'Technical',
  'unknown': 'Unknown',
};

const GROUP_DESCRIPTIONS: Record<string, string> = {
  'fiscal_period': 'Quarterly/annual fiscal period data. Can merge with other fiscal datasets.',
  'daily_series': 'Daily price and trading data. Can merge with other daily series.',
  'point_in_time': 'Current snapshot data. Cannot be time-merged with historical data.',
  'event_list': 'Event-based records with specific dates. Can merge by event date.',
  'market_wide': 'Market-wide data not tied to specific tickers.',
  'options': 'Options chain and pricing data.',
  'crypto': 'Cryptocurrency market data.',
  'commodity': 'Commodity pricing and market data.',
  'forex': 'Foreign exchange rate data.',
  'filing': 'SEC filing documents and metadata.',
  'intraday': 'Intraday price data with minute/hour granularity.',
  'technical': 'Technical indicator time series.',
  'unknown': 'Unknown data structure.',
};

const SIZE_CLASSES = {
  sm: 'text-xs px-1.5 py-0.5',
  md: 'text-sm px-2 py-1',
  lg: 'text-base px-3 py-1.5',
};

export const CompatibilityBadge: React.FC<CompatibilityBadgeProps> = ({
  group,
  size = 'sm',
  showTooltip = true,
}) => {
  const { getColor } = useCompatibilityGroupColors();
  const colors = getColor(group);
  const label = GROUP_LABELS[group] || group;
  const description = GROUP_DESCRIPTIONS[group] || '';
  
  return (
    <span
      className={`
        inline-flex items-center font-medium rounded-full border
        ${colors.bg} ${colors.text} ${colors.border}
        ${SIZE_CLASSES[size]}
      `}
      title={showTooltip ? description : undefined}
    >
      {label}
    </span>
  );
};

/**
 * CompatibilityWarning - Compact inline warning when datasets are incompatible.
 */
interface CompatibilityWarningProps {
  tabGroup: string;
  newGroup: string;
  onDismiss?: () => void;
  onCreateNewSheet?: () => void;
}

export const CompatibilityWarning: React.FC<CompatibilityWarningProps> = ({
  tabGroup,
  newGroup,
  onDismiss,
  onCreateNewSheet,
}) => {
  const { getColor } = useCompatibilityGroupColors();
  const tabColors = getColor(tabGroup);
  const newColors = getColor(newGroup);
  
  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-amber-50/80 border border-amber-200/60 rounded-md text-xs">
      <svg className="w-4 h-4 text-amber-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <span className="text-amber-700">Different structure:</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${tabColors.bg} ${tabColors.text}`}>
          {GROUP_LABELS[tabGroup] || tabGroup}
        </span>
        <span className="text-amber-400">≠</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${newColors.bg} ${newColors.text}`}>
          {GROUP_LABELS[newGroup] || newGroup}
        </span>
      </div>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {onCreateNewSheet && (
          <button
            onClick={onCreateNewSheet}
            className="px-2 py-1 bg-slate-800 text-white text-[10px] font-medium rounded hover:bg-slate-700 transition-colors flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Sheet
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="p-1 text-amber-500 hover:text-amber-700 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};

/**
 * TabCompatibilityIndicator - Compact indicator for current sheet's data type.
 * (Kept for backward compat, use SheetCompatibilityIndicator)
 */
interface TabCompatibilityIndicatorProps {
  group: string | null;
}

export const TabCompatibilityIndicator: React.FC<TabCompatibilityIndicatorProps> = ({
  group,
}) => {
  if (!group || group === 'unknown') return null;
  
  const { getColor } = useCompatibilityGroupColors();
  const colors = getColor(group);
  
  return (
    <div 
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${colors.bg} ${colors.text} ${colors.border} border`}
      title={`This sheet contains ${GROUP_DESCRIPTIONS[group] || group} data`}
    >
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
      </svg>
      {GROUP_LABELS[group] || group}
    </div>
  );
};

// Alias for clarity
export const SheetCompatibilityIndicator = TabCompatibilityIndicator;

export default CompatibilityBadge;

