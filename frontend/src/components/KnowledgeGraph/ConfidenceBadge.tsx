/**
 * Confidence indicator for auto-detection results
 * OpenAI-inspired design with clear visual feedback
 */

interface ConfidenceBadgeProps {
  confidence: number; // 0.0 to 1.0
  showPercentage?: boolean;
}

export default function ConfidenceBadge({ confidence, showPercentage = true }: ConfidenceBadgeProps) {
  const percentage = Math.round(confidence * 100);

  const getLevel = () => {
    if (confidence >= 0.9) return 'high';
    if (confidence >= 0.7) return 'medium';
    return 'low';
  };

  const level = getLevel();

  const styles = {
    high: {
      bg: 'bg-green-50',
      border: 'border-green-300',
      text: 'text-green-800',
      label: 'High',
    },
    medium: {
      bg: 'bg-amber-50',
      border: 'border-amber-300',
      text: 'text-amber-800',
      label: 'Medium',
    },
    low: {
      bg: 'bg-red-50',
      border: 'border-red-300',
      text: 'text-red-800',
      label: 'Low',
    },
  };

  const style = styles[level];

  return (
    <div className={`inline-flex items-center px-2 py-1 rounded border ${style.bg} ${style.border} ${style.text} text-xs font-medium`}>
      {showPercentage ? (
        <span>{percentage}%</span>
      ) : (
        <span>{style.label}</span>
      )}
    </div>
  );
}
