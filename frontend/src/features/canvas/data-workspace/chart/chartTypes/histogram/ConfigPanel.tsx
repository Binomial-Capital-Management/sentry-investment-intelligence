/**
 * HistogramChartConfigPanel - Configuration UI for Histogram options
 */

import type { HistogramChartOptions } from './HistogramChart';

const C = {
  text:       'hsl(60 2.5% 23.3%)',
  textMuted:  'hsl(60 2.5% 23.3% / 60%)',
  textFaint:  'hsl(60 2.5% 23.3% / 35%)',
  textGhost:  'hsl(60 2.5% 23.3% / 25%)',
  border:     '0.5px solid hsl(30 3.3% 11.8% / 10%)',
  borderSel:  '0.5px solid hsl(30 3.3% 11.8% / 15%)',
  bgActive:   'hsl(30 3.3% 11.8% / 8%)',
  bgSubtle:   'hsl(30 3.3% 11.8% / 3%)',
  bgHover:    'hsl(30 3.3% 11.8% / 5%)',
};

interface Props {
  options: HistogramChartOptions;
  onChange: (options: HistogramChartOptions) => void;
}

export function HistogramChartConfigPanel({ options, onChange }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div style={{
        fontSize: '0.563rem',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        color: C.textFaint,
      }}>
        Distribution Options
      </div>

      {/* Bins */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Bins
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {options.bins}
          </span>
        </div>
        <input
          type="range"
          min={5}
          max={100}
          value={options.bins}
          onChange={(e) => onChange({ ...options, bins: Number(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>5</span>
          <span>100</span>
        </div>
      </div>

      {/* Opacity */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Opacity
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {Math.round(options.barOpacity * 100)}%
          </span>
        </div>
        <input
          type="range"
          min={10}
          max={100}
          value={options.barOpacity * 100}
          onChange={(e) => onChange({ ...options, barOpacity: Number(e.target.value) / 100 })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>10%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Toggles */}
      <div style={{
        borderTop: C.border,
        paddingTop: '0.5rem',
        marginTop: '0.25rem',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.25rem',
      }}>
        <button
          onClick={() => onChange({ ...options, normalize: !options.normalize })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.normalize ? C.borderSel : C.border,
            backgroundColor: options.normalize ? C.bgActive : 'transparent',
            color: options.normalize ? C.text : C.textMuted,
          }}
        >
          Normalize (density)
        </button>
        <button
          onClick={() => onChange({ ...options, showKDE: !options.showKDE })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.showKDE ? C.borderSel : C.border,
            backgroundColor: options.showKDE ? C.bgActive : 'transparent',
            color: options.showKDE ? C.text : C.textMuted,
          }}
        >
          Show KDE curve
        </button>
        <button
          onClick={() => onChange({ ...options, showMean: !options.showMean })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.showMean ? C.borderSel : C.border,
            backgroundColor: options.showMean ? C.bgActive : 'transparent',
            color: options.showMean ? C.text : C.textMuted,
          }}
        >
          Show mean line
        </button>
        <button
          onClick={() => onChange({ ...options, showMedian: !options.showMedian })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.showMedian ? C.borderSel : C.border,
            backgroundColor: options.showMedian ? C.bgActive : 'transparent',
            color: options.showMedian ? C.text : C.textMuted,
          }}
        >
          Show median line
        </button>
      </div>
    </div>
  );
}
