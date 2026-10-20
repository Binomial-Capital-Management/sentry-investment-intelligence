/**
 * BubbleChartConfigPanel - Configuration UI for Bubble Chart
 */

import { BubbleChartOptions } from './BubbleChart';
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

const COLOR_SCALES = [
  'Viridis', 'Plasma', 'Inferno', 'Magma', 'Cividis',
  'Blues', 'Greens', 'Reds', 'YlOrRd', 'RdBu', 'Spectral'
];

interface Props {
  options: BubbleChartOptions;
  onChange: (options: BubbleChartOptions) => void;
  availableFields?: string[];
}

export function BubbleChartConfigPanel({ options, onChange, availableFields = [] }: Props) {
  const isDefault = options.minSize === 8 && options.maxSize === 50 && options.opacity === 0.7;
  const isLarge = options.minSize === 15 && options.maxSize === 80 && options.opacity === 0.6;
  const isDense = options.minSize === 5 && options.maxSize === 30 && options.opacity === 0.8;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Size Field */}
      <div>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Size Field (required)
        </div>
        <CustomSelect
          value={options.sizeField}
          onChange={(v) => onChange({ ...options, sizeField: v })}
          placeholder="Select field..."
          options={availableFields.map(f => ({
            value: f,
            label: f,
          }))}
        />
        <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic', marginTop: '0.25rem' }}>
          This field determines bubble size
        </p>
      </div>

      {/* Size Range */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Bubble Size Range
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.625rem' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Min
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {options.minSize}px
              </span>
            </div>
            <input
              type="range"
              min={4}
              max={30}
              value={options.minSize}
              onChange={(e) => onChange({ ...options, minSize: parseInt(e.target.value) })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>4</span>
              <span>30</span>
            </div>
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Max
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {options.maxSize}px
              </span>
            </div>
            <input
              type="range"
              min={20}
              max={100}
              value={options.maxSize}
              onChange={(e) => onChange({ ...options, maxSize: parseInt(e.target.value) })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>20</span>
              <span>100</span>
            </div>
          </div>
        </div>
      </div>

      {/* Color Field (optional) */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Color By (optional)
        </div>
        <CustomSelect
          value={options.colorField || ''}
          onChange={(v) => onChange({ ...options, colorField: v || null })}
          options={[
            { value: '', label: 'Use series color' },
            ...availableFields.map(f => ({
              value: f,
              label: f,
            })),
          ]}
        />

        {options.colorField && (
          <div style={{ marginTop: '0.375rem', display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
            <CustomSelect
              value={options.colorScale}
              onChange={(v) => onChange({ ...options, colorScale: v })}
              options={COLOR_SCALES.map(s => ({
                value: s,
                label: s,
              }))}
            />
            <button
              onClick={() => onChange({ ...options, showColorbar: !options.showColorbar })}
              style={{
                padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: options.showColorbar ? C.borderSel : C.border,
                backgroundColor: options.showColorbar ? C.bgActive : 'transparent',
                color: options.showColorbar ? C.text : C.textMuted,
              }}
            >
              Show color bar
            </button>
          </div>
        )}
      </div>

      {/* Opacity */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Opacity
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {Math.round(options.opacity * 100)}%
          </span>
        </div>
        <input
          type="range"
          min={10}
          max={100}
          value={options.opacity * 100}
          onChange={(e) => onChange({ ...options, opacity: parseInt(e.target.value) / 100 })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>10%</span>
          <span>100%</span>
        </div>
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
              minSize: 8,
              maxSize: 50,
              opacity: 0.7,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isDefault ? C.borderSel : C.border, backgroundColor: isDefault ? C.bgActive : 'transparent', color: isDefault ? C.text : C.textMuted }}
          >
            Default
          </button>
          <button
            onClick={() => onChange({
              ...options,
              minSize: 15,
              maxSize: 80,
              opacity: 0.6,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isLarge ? C.borderSel : C.border, backgroundColor: isLarge ? C.bgActive : 'transparent', color: isLarge ? C.text : C.textMuted }}
          >
            Large
          </button>
          <button
            onClick={() => onChange({
              ...options,
              minSize: 5,
              maxSize: 30,
              opacity: 0.8,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isDense ? C.borderSel : C.border, backgroundColor: isDense ? C.bgActive : 'transparent', color: isDense ? C.text : C.textMuted }}
          >
            Dense
          </button>
        </div>
      </div>
    </div>
  );
}
