/**
 * Summary card showing auto-detection results
 * OpenAI-inspired: Shows what was detected with confidence and quick actions
 */

import ConfidenceBadge from './ConfidenceBadge';

interface DetectionSummaryProps {
  headerCount: number;
  identifierCount: number;
  dataRowCount: number;
  confidence: number;
  onAccept: () => void;
  onAdjust: () => void;
}

export default function DetectionSummary({
  headerCount,
  identifierCount,
  dataRowCount,
  confidence,
  onAccept,
  onAdjust,
}: DetectionSummaryProps) {
  return (
    <div className="bg-white border border-slate-300 rounded p-3">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 mb-1.5">
            Auto-Detected Table Structure
          </h3>
          <div className="flex items-center gap-4 text-xs text-slate-600">
            <span><span className="font-semibold text-slate-900">{headerCount}</span> header{headerCount !== 1 ? 's' : ''}</span>
            <span className="text-slate-400">•</span>
            <span><span className="font-semibold text-slate-900">{identifierCount}</span> ID{identifierCount !== 1 ? 's' : ''}</span>
            <span className="text-slate-400">•</span>
            <span><span className="font-semibold text-slate-900">{dataRowCount}</span> rows</span>
          </div>
        </div>
        <ConfidenceBadge confidence={confidence} showPercentage={false} />
      </div>

      <div className="flex gap-2">
        <button
          onClick={onAccept}
          className="px-4 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium text-sm"
        >
          Confirm & Parse
        </button>
        <button
          onClick={onAdjust}
          className="px-4 py-1.5 bg-white border border-slate-300 text-slate-700 rounded hover:bg-slate-50 transition-colors font-medium text-sm"
        >
          Adjust Manually
        </button>
      </div>
    </div>
  );
}
