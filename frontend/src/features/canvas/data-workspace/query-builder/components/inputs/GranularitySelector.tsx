/**
 * GranularitySelector - UI for selecting target granularity when mixed granularities are detected
 * 
 * Shows when user selects endpoints with different time granularities
 * (e.g., quarterly financials + daily prices) and lets them choose
 * which granularity to align data to.
 */

import type { Granularity } from '@/features/canvas/types';

interface GranularitySelectorProps {
  granularitiesDetected: Granularity[];
  selectedGranularity: Granularity | null;
  onChange: (granularity: Granularity) => void;
  endpointsByGranularity?: Record<Granularity, string[]>;
}

// Order from finest to coarsest (for aggregation direction)
const GRANULARITY_ORDER: Granularity[] = ['intraday', 'daily', 'weekly', 'monthly', 'quarterly'];

// Granularities that can be selected as targets
const SELECTABLE_GRANULARITIES: Granularity[] = ['daily', 'weekly', 'monthly', 'quarterly'];

// Get human-readable granularity label
const getGranularityLabel = (granularity: Granularity): string => {
  const labels: Record<Granularity, string> = {
    snapshot: 'Snapshot (Point-in-time)',
    daily: 'Daily',
    weekly: 'Weekly',
    monthly: 'Monthly',
    quarterly: 'Quarterly',
    intraday: 'Intraday',
    event: 'Event-based',
    unknown: 'Unknown',
  };
  return labels[granularity] || granularity;
};

export default function GranularitySelector({
  granularitiesDetected,
  selectedGranularity,
  onChange,
  endpointsByGranularity,
}: GranularitySelectorProps) {
  // Filter to only show selectable granularities that are detected
  const availableGranularities = SELECTABLE_GRANULARITIES.filter(
    (g) => granularitiesDetected.includes(g) || 
    // Also include coarser granularities that data can be aggregated to
    GRANULARITY_ORDER.indexOf(g) > Math.min(...granularitiesDetected.map((d) => GRANULARITY_ORDER.indexOf(d)))
  );

  // Find which granularities would need aggregation
  const getAggregationInfo = (target: Granularity): string[] => {
    const targetIdx = GRANULARITY_ORDER.indexOf(target);
    return granularitiesDetected
      .filter((g) => GRANULARITY_ORDER.indexOf(g) < targetIdx && GRANULARITY_ORDER.indexOf(g) >= 0)
      .map((g) => getGranularityLabel(g));
  };

  if (granularitiesDetected.length <= 1) {
    return null;
  }

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-4">
      <div className="flex items-start gap-2 mb-3">
        <svg className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <div className="flex-1">
          <h4 className="font-medium text-amber-800">Mixed granularities detected</h4>
          <p className="text-sm text-amber-700 mt-1">
            Your selections include data at different time resolutions:
          </p>
          <ul className="text-sm text-amber-700 mt-2 space-y-1">
            {granularitiesDetected
              .filter((g) => GRANULARITY_ORDER.includes(g) || g === 'snapshot')
              .map((g) => (
                <li key={g} className="flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-amber-400" />
                  <span className="font-medium">{getGranularityLabel(g)}</span>
                  {endpointsByGranularity?.[g] && (
                    <span className="text-amber-600">
                      ({endpointsByGranularity[g].slice(0, 2).join(', ')}
                      {endpointsByGranularity[g].length > 2 && `, +${endpointsByGranularity[g].length - 2} more`})
                    </span>
                  )}
                </li>
              ))}
          </ul>
        </div>
      </div>

      <div className="mt-4">
        <label className="block text-sm font-medium text-amber-800 mb-2">
          Align data to:
        </label>
        <div className="flex flex-wrap gap-2">
          {availableGranularities.map((g) => {
            const isSelected = selectedGranularity === g;
            
            return (
              <button
                key={g}
                onClick={() => onChange(g)}
                className={`
                  px-3 py-2 rounded-md text-sm font-medium transition-colors
                  ${isSelected 
                    ? 'bg-amber-600 text-white' 
                    : 'bg-white text-amber-800 border border-amber-300 hover:border-amber-400 hover:bg-amber-50'}
                `}
              >
                {getGranularityLabel(g)}
              </button>
            );
          })}
        </div>
        
        {selectedGranularity && (
          <div className="mt-3 text-sm text-amber-700 flex items-center gap-2">
            <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {(() => {
              const aggNeeded = getAggregationInfo(selectedGranularity);
              if (aggNeeded.length > 0) {
                return `${aggNeeded.join(' and ')} data will be aggregated to ${getGranularityLabel(selectedGranularity).toLowerCase()}`;
              }
              return `Data will be aligned at ${getGranularityLabel(selectedGranularity).toLowerCase()} level`;
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
