/**
 * Box Plot Configuration Panel
 * Controls for box plot appearance and statistical options
 */

import { BoxPlotChartOptions } from './BoxPlotChart';
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
  options: BoxPlotChartOptions;
  onChange: (options: BoxPlotChartOptions) => void;
}

export function BoxPlotChartConfigPanel({ options, onChange }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Orientation */}
      <div>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Orientation
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.563rem', color: C.textMuted, cursor: 'pointer' }}>
            <input
              type="radio"
              checked={options.orientation === 'v'}
              onChange={() => onChange({ ...options, orientation: 'v' })}
              style={{ width: 12, height: 12 }}
            />
            Vertical
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.563rem', color: C.textMuted, cursor: 'pointer' }}>
            <input
              type="radio"
              checked={options.orientation === 'h'}
              onChange={() => onChange({ ...options, orientation: 'h' })}
              style={{ width: 12, height: 12 }}
            />
            Horizontal
          </label>
        </div>
      </div>

      {/* Points Display */}
      <div>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Show Points
        </div>
        <CustomSelect
          value={String(options.boxPoints)}
          onChange={(v) => {
            const boxPoints = v === 'false' ? false : v as 'all' | 'outliers' | 'suspectedoutliers';
            onChange({ ...options, boxPoints });
          }}
          options={[
            { value: 'outliers', label: 'Outliers only' },
            { value: 'suspectedoutliers', label: 'Suspected outliers' },
            { value: 'all', label: 'All points' },
            { value: 'false', label: 'None' },
          ]}
        />
      </div>

      {/* Statistical Options */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Statistics
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
          <button
            onClick={() => onChange({ ...options, boxMean: options.boxMean ? false : true })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.boxMean ? C.borderSel : C.border,
              backgroundColor: options.boxMean ? C.bgActive : 'transparent',
              color: options.boxMean ? C.text : C.textMuted,
            }}
          >
            Show mean
          </button>

          {options.boxMean && (
            <button
              onClick={() => onChange({ ...options, boxMean: options.boxMean === 'sd' ? true : 'sd' })}
              style={{
                padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: options.boxMean === 'sd' ? C.borderSel : C.border,
                backgroundColor: options.boxMean === 'sd' ? C.bgActive : 'transparent',
                color: options.boxMean === 'sd' ? C.text : C.textMuted,
              }}
            >
              Show +/-1 std dev
            </button>
          )}

          <button
            onClick={() => onChange({ ...options, notched: !options.notched })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.notched ? C.borderSel : C.border,
              backgroundColor: options.notched ? C.bgActive : 'transparent',
              color: options.notched ? C.text : C.textMuted,
            }}
          >
            Notched (95% CI of median)
          </button>
        </div>
      </div>

      {/* Quartile Method */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Quartile Method
        </div>
        <CustomSelect
          value={options.quartileMethod}
          onChange={(v) => onChange({ ...options, quartileMethod: v as any })}
          options={[
            { value: 'linear', label: 'Linear (default)' },
            { value: 'exclusive', label: 'Exclusive' },
            { value: 'inclusive', label: 'Inclusive' },
          ]}
        />
        <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic', marginTop: '0.25rem' }}>
          How quartiles are calculated
        </p>
      </div>

      {/* Point Spread (when showing points) */}
      {options.boxPoints && options.boxPoints !== false && (
        <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
            <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
              Point Spread (Jitter)
            </span>
            <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
              {options.jitter.toFixed(2)}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={options.jitter}
            onChange={(e) => onChange({ ...options, jitter: parseFloat(e.target.value) })}
            className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
            style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
            <span>0</span>
            <span>1</span>
          </div>
        </div>
      )}

      {/* Normalization */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Normalize (compare different scales)
        </div>
        <CustomSelect
          value={options.normalize}
          onChange={(v) => onChange({ ...options, normalize: v as any })}
          options={[
            { value: 'none', label: 'None (raw values)' },
            { value: 'zscore', label: 'Z-Score (sigma from mean)' },
            { value: 'minmax', label: 'Min-Max (0-100%)' },
            { value: 'percent', label: '% from mean' },
          ]}
        />
        <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic', marginTop: '0.25rem' }}>
          Use when comparing fields with different magnitudes (e.g., P/E vs Price)
        </p>
      </div>

      {/* Presets */}
      {(() => {
        const isStandard = options.boxPoints === 'outliers' && options.boxMean === true && options.notched === false && options.orientation === 'v';
        const isFullDetail = options.boxPoints === 'all' && options.boxMean === 'sd' && options.notched === false && options.jitter === 0.4 && options.orientation === 'v';
        const isCleanNotched = options.boxPoints === false && options.boxMean === true && options.notched === true && options.orientation === 'v';
        const isHorizontal = options.boxPoints === 'outliers' && options.boxMean === true && options.notched === false && options.orientation === 'h';
        return (
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Presets
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
          <button
            onClick={() => onChange({
              ...options,
              boxPoints: 'outliers',
              boxMean: true,
              notched: false,
              orientation: 'v',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isStandard ? C.borderSel : C.border, backgroundColor: isStandard ? C.bgActive : 'transparent', color: isStandard ? C.text : C.textMuted }}
          >
            Standard
          </button>
          <button
            onClick={() => onChange({
              ...options,
              boxPoints: 'all',
              boxMean: 'sd',
              notched: false,
              jitter: 0.4,
              orientation: 'v',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isFullDetail ? C.borderSel : C.border, backgroundColor: isFullDetail ? C.bgActive : 'transparent', color: isFullDetail ? C.text : C.textMuted }}
          >
            Full Detail
          </button>
          <button
            onClick={() => onChange({
              ...options,
              boxPoints: false,
              boxMean: true,
              notched: true,
              orientation: 'v',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isCleanNotched ? C.borderSel : C.border, backgroundColor: isCleanNotched ? C.bgActive : 'transparent', color: isCleanNotched ? C.text : C.textMuted }}
          >
            Clean + Notched
          </button>
          <button
            onClick={() => onChange({
              ...options,
              boxPoints: 'outliers',
              boxMean: true,
              notched: false,
              orientation: 'h',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isHorizontal ? C.borderSel : C.border, backgroundColor: isHorizontal ? C.bgActive : 'transparent', color: isHorizontal ? C.text : C.textMuted }}
          >
            Horizontal
          </button>
        </div>
      </div>
        );
      })()}
    </div>
  );
}
