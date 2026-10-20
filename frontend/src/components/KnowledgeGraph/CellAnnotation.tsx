/**
 * Inline badge/chip component for cell annotations
 * Shows whether a cell is a header or identifier
 */

interface CellAnnotationProps {
  type: 'header' | 'identifier';
  onRemove?: () => void;
  tooltip?: string;
}

export default function CellAnnotation({ type, onRemove, tooltip }: CellAnnotationProps) {
  const styles = type === 'header'
    ? {
        bg: 'bg-green-600',
        hoverBg: 'hover:bg-green-700',
        text: 'text-white',
        label: 'H',
      }
    : {
        bg: 'bg-blue-600',
        hoverBg: 'hover:bg-blue-700',
        text: 'text-white',
        label: 'ID',
      };

  return (
    <div
      className={`inline-flex items-center px-1.5 py-0.5 rounded ${styles.bg} ${styles.text} text-[9px] font-semibold cursor-pointer ${styles.hoverBg} transition-colors`}
      onClick={(e) => {
        e.stopPropagation();
        onRemove?.();
      }}
      title={tooltip || `Click to remove ${type}`}
    >
      <span>{styles.label}</span>
      {onRemove && <span className="ml-0.5 opacity-80">×</span>}
    </div>
  );
}
