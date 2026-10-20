import { Check, X, Lightbulb } from 'lucide-react';

interface DetectionResult {
  headerRows: number[];
  identifierColumns: number[];
  confidence: number;
  notes?: string;
}

interface DetectionSuggestionsProps {
  suggestions: DetectionResult | null;
  onAcceptAll: () => void;
  onReject: () => void;
  isLoading?: boolean;
}

export default function DetectionSuggestions({
  suggestions,
  onAcceptAll,
  onReject,
  isLoading = false,
}: DetectionSuggestionsProps) {
  if (isLoading) {
    return (
      <div className="institutional-card">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-[var(--sentry-blue)] border-t-transparent" />
          <p className="text-[var(--sentry-gray-600)]">
            Running auto-detection...
          </p>
        </div>
      </div>
    );
  }

  if (!suggestions) return null;

  const confidenceColor = suggestions.confidence >= 0.8
    ? 'text-green-600'
    : suggestions.confidence >= 0.5
      ? 'text-yellow-600'
      : 'text-red-600';

  return (
    <div className="institutional-card border-l-4 border-[var(--sentry-blue)]">
      <div className="flex items-start gap-3">
        <Lightbulb className="text-[var(--sentry-blue)] mt-1" size={24} />
        <div className="flex-1">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-semibold text-[var(--sentry-navy)]">
                Auto-Detection Results
              </h3>
              <p className="text-sm text-[var(--sentry-gray-600)] mt-1">
                Confidence: <span className={`font-semibold ${confidenceColor}`}>
                  {(suggestions.confidence * 100).toFixed(0)}%
                </span>
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={onAcceptAll}
                className="
                  flex items-center gap-2 px-4 py-2 rounded-md
                  bg-green-500 text-white hover:bg-green-600
                  transition-colors font-medium text-sm
                "
              >
                <Check size={16} />
                Accept All
              </button>
              <button
                onClick={onReject}
                className="
                  flex items-center gap-2 px-4 py-2 rounded-md
                  bg-[var(--sentry-gray-200)] text-[var(--sentry-navy)]
                  hover:bg-[var(--sentry-gray-300)]
                  transition-colors font-medium text-sm
                "
              >
                <X size={16} />
                Reject
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-[var(--sentry-gray-600)]">Header Rows:</span>
              <span className="font-mono text-[var(--sentry-navy)]">
                {suggestions.headerRows.length > 0
                  ? suggestions.headerRows.map(r => r + 1).join(', ')
                  : 'None detected'}
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-[var(--sentry-gray-600)]">Identifier Columns:</span>
              <span className="font-mono text-[var(--sentry-navy)]">
                {suggestions.identifierColumns.length > 0
                  ? suggestions.identifierColumns.map(c => String.fromCharCode(65 + c)).join(', ')
                  : 'None detected'}
              </span>
            </div>
            {suggestions.notes && (
              <div className="mt-3 p-2 bg-[var(--sentry-gray-100)] rounded text-sm text-[var(--sentry-gray-700)]">
                {suggestions.notes}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
