import { useState, ReactNode } from 'react';
import { ChartConfig } from '../../stores/dataWorkspaceStore';

const C = {
  text:       'hsl(60 2.5% 23.3%)',
  textMuted:  'hsl(60 2.5% 23.3% / 60%)',
  textFaint:  'hsl(60 2.5% 23.3% / 35%)',
  textGhost:  'hsl(60 2.5% 23.3% / 25%)',
  border:     '0.5px solid hsl(30 3.3% 11.8% / 10%)',
  borderSel:  '0.5px solid hsl(30 3.3% 11.8% / 15%)',
  bgActive:   'hsl(30 3.3% 11.8% / 8%)',
  bgHover:    'hsl(30 3.3% 11.8% / 5%)',
} as const;

const sectionHeader: React.CSSProperties = {
  fontSize: '0.563rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: C.textFaint,
};

interface Props {
  config: ChartConfig;
  availableFields: { field: string; type: 'numeric' | 'date' | 'string' }[];
  data: Record<string, any>[];
  onUpdate: (updates: Partial<ChartConfig>) => void;
  typeOptionsPanel?: ReactNode;
}

export function ChartOptionsPanel({
  config,
  onUpdate,
  typeOptionsPanel,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          height: 30,
          padding: '0.3rem 0.625rem',
          fontSize: '0.688rem',
          fontWeight: 500,
          textAlign: 'left' as const,
          border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
          borderRadius: '0.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.375rem',
          color: C.text,
          backgroundColor: 'white',
          cursor: 'pointer',
        }}
      >
        <span style={{ flex: 1 }}>Options</span>
        <svg
          style={{ width: 10, height: 10, color: C.textFaint, flexShrink: 0, transition: 'transform 0.15s ease', transform: open ? 'rotate(180deg)' : 'none' }}
          fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {/* Display toggles */}
          <div>
            <div style={{ ...sectionHeader, marginBottom: '0.375rem' }}>Display</div>
            <div style={{ display: 'flex', gap: '0.25rem' }}>
              {[
                { label: 'Legend', active: config.showLegend ?? true, toggle: () => onUpdate({ showLegend: !(config.showLegend ?? true) }) },
                { label: 'Grid', active: config.showGrid ?? true, toggle: () => onUpdate({ showGrid: !(config.showGrid ?? true) }) },
              ].map(({ label, active, toggle }) => (
                <button
                  key={label}
                  onClick={toggle}
                  style={{
                    flex: 1, padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                    borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                    border: active ? C.borderSel : C.border,
                    backgroundColor: active ? C.bgActive : 'transparent',
                    color: active ? C.text : C.textMuted,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Type-specific style options */}
          {typeOptionsPanel && (
            <div style={{ borderTop: C.border, paddingTop: '0.75rem' }}>
              <div style={{ ...sectionHeader, marginBottom: '0.375rem' }}>Style</div>
              {typeOptionsPanel}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
