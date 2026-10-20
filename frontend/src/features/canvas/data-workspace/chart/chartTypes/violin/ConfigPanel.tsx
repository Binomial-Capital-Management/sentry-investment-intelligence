/**
 * Violin Chart Configuration Panel
 * Controls for violin plot appearance and KDE options
 */

import { ViolinChartOptions } from './ViolinChart';
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
  options: ViolinChartOptions;
  onChange: (options: ViolinChartOptions) => void;
}

export function ViolinChartConfigPanel({ options, onChange }: Props) {
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

      {/* Violin Side */}
      <div>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Violin Shape
        </div>
        <CustomSelect
          value={options.side}
          onChange={(v) => onChange({ ...options, side: v as any })}
          options={[
            { value: 'both', label: 'Full (both sides)' },
            { value: 'positive', label: 'Half (positive side)' },
            { value: 'negative', label: 'Half (negative side)' },
          ]}
        />
        <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic', marginTop: '0.25rem' }}>
          Half violins are useful for comparing two groups
        </p>
      </div>

      {/* Inner Display */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Inside Violin
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
          <button
            onClick={() => onChange({ ...options, box: !options.box })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.box ? C.borderSel : C.border,
              backgroundColor: options.box ? C.bgActive : 'transparent',
              color: options.box ? C.text : C.textMuted,
            }}
          >
            Show box plot
          </button>
          <button
            onClick={() => onChange({ ...options, meanline: !options.meanline })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.meanline ? C.borderSel : C.border,
              backgroundColor: options.meanline ? C.bgActive : 'transparent',
              color: options.meanline ? C.text : C.textMuted,
            }}
          >
            Show mean line
          </button>
        </div>
      </div>

      {/* Points Display */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Show Points
        </div>
        <CustomSelect
          value={String(options.points)}
          onChange={(v) => {
            const points = v === 'false' ? false : v as 'all' | 'outliers' | 'suspectedoutliers';
            onChange({ ...options, points });
          }}
          options={[
            { value: 'false', label: 'None' },
            { value: 'outliers', label: 'Outliers only' },
            { value: 'suspectedoutliers', label: 'Suspected outliers' },
            { value: 'all', label: 'All points' },
          ]}
        />

        {/* Point Jitter */}
        {options.points && options.points !== false && (
          <div style={{ marginTop: '0.375rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Jitter
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
      </div>

      {/* Scale Mode */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Scale Mode
        </div>
        <CustomSelect
          value={options.scaleMode}
          onChange={(v) => onChange({ ...options, scaleMode: v as any })}
          options={[
            { value: 'width', label: 'Same width' },
            { value: 'count', label: 'By sample count' },
          ]}
        />
        <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic', marginTop: '0.25rem' }}>
          "By count" makes width proportional to sample size
        </p>
      </div>

      {/* Bandwidth Control */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            KDE Bandwidth
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {options.bandwidth === 0 ? 'Auto' : options.bandwidth.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={2}
          step={0.1}
          value={options.bandwidth}
          onChange={(e) => onChange({ ...options, bandwidth: parseFloat(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>0</span>
          <span>2</span>
        </div>
        <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic', marginTop: '0.25rem' }}>
          0 = auto. Higher = smoother curve
        </p>
      </div>

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
        const isStandard = options.side === 'both' && options.box === true && options.meanline === true && options.points === false && options.orientation === 'v';
        const isWithPoints = options.side === 'both' && options.box === false && options.meanline === true && options.points === 'all' && options.jitter === 0.4 && options.orientation === 'v';
        const isHalfViolin = options.side === 'positive' && options.box === true && options.meanline === false && options.points === false && options.orientation === 'v';
        const isClean = options.side === 'both' && options.box === false && options.meanline === true && options.points === false && options.bandwidth === 0 && options.orientation === 'v';
        return (
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Presets
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
          <button
            onClick={() => onChange({
              ...options,
              side: 'both',
              box: true,
              meanline: true,
              points: false,
              orientation: 'v',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isStandard ? C.borderSel : C.border, backgroundColor: isStandard ? C.bgActive : 'transparent', color: isStandard ? C.text : C.textMuted }}
          >
            Standard
          </button>
          <button
            onClick={() => onChange({
              ...options,
              side: 'both',
              box: false,
              meanline: true,
              points: 'all',
              jitter: 0.4,
              orientation: 'v',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isWithPoints ? C.borderSel : C.border, backgroundColor: isWithPoints ? C.bgActive : 'transparent', color: isWithPoints ? C.text : C.textMuted }}
          >
            With Points
          </button>
          <button
            onClick={() => onChange({
              ...options,
              side: 'positive',
              box: true,
              meanline: false,
              points: false,
              orientation: 'v',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isHalfViolin ? C.borderSel : C.border, backgroundColor: isHalfViolin ? C.bgActive : 'transparent', color: isHalfViolin ? C.text : C.textMuted }}
          >
            Half Violin
          </button>
          <button
            onClick={() => onChange({
              ...options,
              side: 'both',
              box: false,
              meanline: true,
              points: false,
              bandwidth: 0,
              orientation: 'v',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isClean ? C.borderSel : C.border, backgroundColor: isClean ? C.bgActive : 'transparent', color: isClean ? C.text : C.textMuted }}
          >
            Clean
          </button>
        </div>
      </div>
        );
      })()}
    </div>
  );
}
