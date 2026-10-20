import { useRef, useCallback } from 'react';
import { sentimentAccents, type Sentiment } from './metricCardStyles';

const S = {
  text:       'hsl(60 2.5% 23.3%)',
  textFaint:  'hsl(60 2.5% 23.3% / 35%)',
  textGhost:  'hsl(60 2.5% 23.3% / 25%)',
  textMuted:  'hsl(60 2.5% 23.3% / 60%)',
  border:     '0.5px solid hsl(30 3.3% 11.8% / 10%)',
  bgActive:   'hsl(30 3.3% 11.8% / 8%)',
} as const;

export interface NormalizedMetricCard {
  id: string;
  label: string;
  value: string;
  sentiment: Sentiment;
}

interface ToolMetricsPanelProps {
  cards: NormalizedMetricCard[];
  isOpen: boolean;
  height: number;
  onHeightChange: (h: number) => void;
  onClose: () => void;
}

export function ToolMetricsPanel({ cards, isOpen, height, onHeightChange, onClose }: ToolMetricsPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    const container = panelRef.current?.parentElement;
    if (!container) return;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const rect = container.getBoundingClientRect();
      const pct = ((rect.bottom - ev.clientY) / rect.height) * 100;
      onHeightChange(Math.max(20, Math.min(85, pct)));
    };
    const onUp = () => {
      dragging.current = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [onHeightChange]);

  const valueColor = (s: Sentiment) => {
    if (s === 'neutral') return S.text;
    return sentimentAccents[s]?.accent ?? S.text;
  };

  return (
    <div
      ref={panelRef}
      className="absolute bottom-0 left-0 right-0 z-30 bg-white flex flex-col shadow-[0_-4px_24px_rgba(0,0,0,0.08)] rounded-t-xl"
      style={{
        height: `${height}%`,
        borderTop: '1px solid hsl(30 3.3% 11.8% / 15%)',
        transform: isOpen ? 'translateY(0)' : 'translateY(100%)',
        transition: dragging.current ? 'none' : 'transform 0.3s ease-out',
      }}
    >
      {/* Header with resize handle */}
      <div className="flex-shrink-0 relative" style={{ height: 44, borderBottom: S.border }}>
        <div
          onMouseDown={onResizeStart}
          className="absolute top-0 left-0 right-0 flex justify-center pt-1.5 cursor-row-resize group z-10"
        >
          <div className="w-8 h-1 rounded-full transition-colors" style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }} />
        </div>
        <div className="h-full px-4 flex items-center justify-between">
          <span style={{ fontSize: '0.688rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint }}>Metrics</span>
          <button onClick={onClose} className="p-1 rounded transition-colors" style={{ color: S.textGhost }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = S.bgActive; e.currentTarget.style.color = S.textMuted; }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = S.textGhost; }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Content — table style matching pivot stats */}
      <div className="flex-1 overflow-y-auto overflow-x-auto min-h-0 p-4">
        <table className="w-full" style={{ fontSize: '0.688rem' }}>
          <thead>
            <tr style={{ borderBottom: S.border }}>
              {cards.map(c => (
                <th
                  key={c.id}
                  style={{
                    padding: '0.5rem 0.75rem',
                    textAlign: 'left',
                    fontWeight: 600,
                    fontSize: '0.6875rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: S.textFaint,
                  }}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {cards.map(c => (
                <td
                  key={c.id}
                  style={{
                    padding: '0.25rem 0.75rem 0.75rem',
                    fontWeight: 700,
                    fontSize: '1.5rem',
                    color: valueColor(c.sentiment),
                  }}
                >
                  {c.value}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
