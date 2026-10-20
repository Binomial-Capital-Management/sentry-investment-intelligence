/**
 * Radar Chart Configuration Panel
 */

import { RadarChartOptions } from './RadarChart';
import { CustomSelect } from '../../components/CustomSelect';

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
  options: RadarChartOptions;
  onChange: (options: RadarChartOptions) => void;
}

export function RadarChartConfigPanel({ options, onChange }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Normalization - Critical for radar charts */}
      <div>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Normalize (required for different scales)
        </div>
        <CustomSelect
          value={options.normalize}
          onChange={(v) => onChange({ ...options, normalize: v as any })}
          options={[
            { value: 'minmax', label: 'Min-Max (0 to 1)' },
            { value: 'zscore', label: 'Z-Score (σ from mean)' },
            { value: 'rank', label: 'Percentile Rank' },
            { value: 'none', label: 'None (raw values)' },
          ]}
        />
        <p style={{
          fontSize: '0.5rem',
          color: C.textGhost,
          fontStyle: 'italic',
          marginTop: '0.25rem',
        }}>
          Metrics like PE (20-40) and ROE (0.1-0.3) need normalization to compare
        </p>
      </div>

      {/* Fill Options */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Display
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
            <button
              onClick={() => onChange({ ...options, fill: options.fill === 'toself' ? 'none' : 'toself' })}
              style={{
                padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: options.fill === 'toself' ? C.borderSel : C.border,
                backgroundColor: options.fill === 'toself' ? C.bgActive : 'transparent',
                color: options.fill === 'toself' ? C.text : C.textMuted,
              }}
            >
              Fill polygon
            </button>
            <button
              onClick={() => onChange({ ...options, showValues: !options.showValues })}
              style={{
                padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: options.showValues ? C.borderSel : C.border,
                backgroundColor: options.showValues ? C.bgActive : 'transparent',
                color: options.showValues ? C.text : C.textMuted,
              }}
            >
              Show values on hover
            </button>
          </div>

          {options.fill === 'toself' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                  Fill Opacity
                </span>
                <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                  {(options.opacity * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={options.opacity}
                onChange={(e) => onChange({ ...options, opacity: parseFloat(e.target.value) })}
                className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
                style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
                <span>0%</span>
                <span>100%</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Presets */}
      {(() => {
        const isFilled = options.fill === 'toself' && options.opacity === 0.3 && options.normalize === 'minmax';
        const isLinesOnly = options.fill === 'none' && options.normalize === 'minmax';
        const isPercentile = options.fill === 'toself' && options.opacity === 0.2 && options.normalize === 'rank';
        return (
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Presets
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          <button
            onClick={() => onChange({
              ...options,
              fill: 'toself',
              opacity: 0.3,
              normalize: 'minmax',
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isFilled ? C.borderSel : C.border,
              backgroundColor: isFilled ? C.bgActive : 'transparent',
              color: isFilled ? C.text : C.textMuted,
            }}
          >
            Filled
          </button>
          <button
            onClick={() => onChange({
              ...options,
              fill: 'none',
              normalize: 'minmax',
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isLinesOnly ? C.borderSel : C.border,
              backgroundColor: isLinesOnly ? C.bgActive : 'transparent',
              color: isLinesOnly ? C.text : C.textMuted,
            }}
          >
            Lines Only
          </button>
          <button
            onClick={() => onChange({
              ...options,
              fill: 'toself',
              opacity: 0.2,
              normalize: 'rank',
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isPercentile ? C.borderSel : C.border,
              backgroundColor: isPercentile ? C.bgActive : 'transparent',
              color: isPercentile ? C.text : C.textMuted,
            }}
          >
            Percentile
          </button>
        </div>
      </div>
        );
      })()}

      {/* Help text */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic' }}>
          <strong>Tip:</strong> Select multiple Y-series fields (e.g., PE, PB, ROE) and group by symbol to compare companies across metrics.
        </div>
      </div>
    </div>
  );
}
