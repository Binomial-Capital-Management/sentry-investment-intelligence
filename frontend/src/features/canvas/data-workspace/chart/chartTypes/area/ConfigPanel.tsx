/**
 * AreaChartConfigPanel - Configuration UI for Area Chart
 */

import { AreaChartOptions } from './AreaChart';
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
  options: AreaChartOptions;
  onChange: (options: AreaChartOptions) => void;
}

export function AreaChartConfigPanel({ options, onChange }: Props) {
  const isSmooth = options.stackMode === 'none' && options.smoothing === true && options.fillOpacity === 0.3 && options.lineWidth === 2 && (options.normalize || 'none') === 'none';
  const isStacked = options.stackMode === 'stack' && options.smoothing === false && options.fillOpacity === 0.7 && options.lineWidth === 1 && (options.normalize || 'none') === 'none';
  const is100Fill = options.stackMode === 'percent' && options.smoothing === false && options.fillOpacity === 0.8 && options.lineWidth === 0 && (options.normalize || 'none') === 'none';
  const isNormalized = options.stackMode === 'none' && options.smoothing === true && options.fillOpacity === 0.4 && options.lineWidth === 2 && options.normalize === 'minmax';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Stack Mode */}
      <div>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Stack Mode
        </div>
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          {[
            { value: 'none', label: 'Overlay' },
            { value: 'stack', label: 'Stack' },
            { value: 'percent', label: '100%' },
          ].map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onChange({ ...options, stackMode: value as any })}
              style={{
                flex: 1,
                padding: '0.25rem 0.375rem',
                fontSize: '0.563rem',
                fontWeight: 500,
                borderRadius: '0.375rem',
                border: options.stackMode === value ? C.borderSel : C.border,
                background: options.stackMode === value ? C.bgActive : 'transparent',
                color: options.stackMode === value ? C.text : C.textMuted,
                cursor: 'pointer',
                transition: 'all 0.1s ease',
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic', marginTop: '0.25rem' }}>
          {options.stackMode === 'none' && 'Areas overlap (compare trends)'}
          {options.stackMode === 'stack' && 'Areas stacked (show totals)'}
          {options.stackMode === 'percent' && 'Normalized to 100% (show proportions)'}
        </p>
      </div>

      {/* Fill Opacity */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Fill Opacity
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {Math.round(options.fillOpacity * 100)}%
          </span>
        </div>
        <input
          type="range"
          min={10}
          max={100}
          value={options.fillOpacity * 100}
          onChange={(e) => onChange({ ...options, fillOpacity: parseInt(e.target.value) / 100 })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>10</span>
          <span>100</span>
        </div>
      </div>

      {/* Line Style */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Line Style
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Width
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {options.lineWidth}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={5}
              step={0.5}
              value={options.lineWidth}
              onChange={(e) => onChange({ ...options, lineWidth: parseFloat(e.target.value) })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>0</span>
              <span>5</span>
            </div>
          </div>
          <button
            onClick={() => onChange({ ...options, smoothing: !options.smoothing })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.smoothing ? C.borderSel : C.border,
              backgroundColor: options.smoothing ? C.bgActive : 'transparent',
              color: options.smoothing ? C.text : C.textMuted,
            }}
          >
            Smooth curves (spline)
          </button>
        </div>
      </div>

      {/* Markers */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Data Points
        </div>
        <button
          onClick={() => onChange({ ...options, showMarkers: !options.showMarkers })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.showMarkers ? C.borderSel : C.border,
            backgroundColor: options.showMarkers ? C.bgActive : 'transparent',
            color: options.showMarkers ? C.text : C.textMuted,
          }}
        >
          Show markers
        </button>
        {options.showMarkers && (
          <div style={{ marginTop: '0.375rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Size
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {options.markerSize}
              </span>
            </div>
            <input
              type="range"
              min={2}
              max={12}
              value={options.markerSize}
              onChange={(e) => onChange({ ...options, markerSize: parseInt(e.target.value) })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>2</span>
              <span>12</span>
            </div>
          </div>
        )}
      </div>

      {/* Normalization */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Normalize (compare different scales)
        </div>
        <CustomSelect
          value={options.normalize || 'none'}
          onChange={(v) => onChange({ ...options, normalize: v as any })}
          options={[
            { value: 'none', label: 'None (raw values)' },
            { value: 'zscore', label: 'Z-Score (sigma from mean)' },
            { value: 'minmax', label: 'Min-Max (0-100%)' },
            { value: 'percent', label: '% from mean' },
          ]}
        />
        <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic', marginTop: '0.25rem' }}>
          Use when comparing series with different magnitudes (e.g., TSM in TWD vs US companies in USD)
        </p>
      </div>

      {/* Presets */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Presets
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
          <button
            onClick={() => onChange({
              ...options,
              stackMode: 'none',
              smoothing: true,
              fillOpacity: 0.3,
              lineWidth: 2,
              normalize: 'none',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isSmooth ? C.borderSel : C.border, backgroundColor: isSmooth ? C.bgActive : 'transparent', color: isSmooth ? C.text : C.textMuted }}
          >
            Smooth
          </button>
          <button
            onClick={() => onChange({
              ...options,
              stackMode: 'stack',
              smoothing: false,
              fillOpacity: 0.7,
              lineWidth: 1,
              normalize: 'none',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isStacked ? C.borderSel : C.border, backgroundColor: isStacked ? C.bgActive : 'transparent', color: isStacked ? C.text : C.textMuted }}
          >
            Stacked
          </button>
          <button
            onClick={() => onChange({
              ...options,
              stackMode: 'percent',
              smoothing: false,
              fillOpacity: 0.8,
              lineWidth: 0,
              normalize: 'none',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: is100Fill ? C.borderSel : C.border, backgroundColor: is100Fill ? C.bgActive : 'transparent', color: is100Fill ? C.text : C.textMuted }}
          >
            100% Fill
          </button>
          <button
            onClick={() => onChange({
              ...options,
              stackMode: 'none',
              smoothing: true,
              fillOpacity: 0.4,
              lineWidth: 2,
              normalize: 'minmax',
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isNormalized ? C.borderSel : C.border, backgroundColor: isNormalized ? C.bgActive : 'transparent', color: isNormalized ? C.text : C.textMuted }}
          >
            Normalized
          </button>
        </div>
      </div>
    </div>
  );
}
