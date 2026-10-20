/**
 * Scatter3DChartConfigPanel - Configuration UI for 3D Scatter options
 */

import type { Scatter3DChartOptions } from './Scatter3DChart';
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
  options: Scatter3DChartOptions;
  onChange: (options: Scatter3DChartOptions) => void;
  availableFields?: string[];
}

const COLOR_SCALES = [
  { value: 'Viridis', label: 'Viridis' },
  { value: 'Blues', label: 'Blues' },
  { value: 'Reds', label: 'Reds' },
  { value: 'Greens', label: 'Greens' },
  { value: 'RdYlBu', label: 'Red-Yellow-Blue' },
  { value: 'Spectral', label: 'Spectral' },
];

export function Scatter3DChartConfigPanel({ options, onChange, availableFields = [] }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div style={{
        fontSize: '0.563rem',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        color: C.textFaint,
      }}>
        3D Options
      </div>

      {/* Z-Axis Field */}
      <div>
        <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Z-Axis Field</label>
        <CustomSelect
          value={options.zAxis}
          onChange={(v) => onChange({ ...options, zAxis: v })}
          placeholder="Select field..."
          options={[
            { value: '', label: 'Select field...' },
            ...availableFields.map((field) => ({ value: field, label: field })),
          ]}
        />
      </div>

      {/* Marker Size */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Marker Size
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {options.markerSize}
          </span>
        </div>
        <input
          type="range"
          min={2}
          max={20}
          value={options.markerSize}
          onChange={(e) => onChange({ ...options, markerSize: Number(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>2</span>
          <span>20</span>
        </div>
      </div>

      {/* Marker Opacity */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Opacity
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {Math.round(options.markerOpacity * 100)}%
          </span>
        </div>
        <input
          type="range"
          min={10}
          max={100}
          value={options.markerOpacity * 100}
          onChange={(e) => onChange({ ...options, markerOpacity: Number(e.target.value) / 100 })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>10%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Color by field */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Color Mapping
        </div>

        <div>
          <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Color by Field</label>
          <CustomSelect
            value={options.colorByField || ''}
            onChange={(v) => onChange({ ...options, colorByField: v || null })}
            options={[
              { value: '', label: 'None (single color)' },
              ...availableFields.map((field) => ({ value: field, label: field })),
            ]}
          />
        </div>

        {options.colorByField && (
          <>
            <div style={{ marginTop: '0.5rem' }}>
              <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Color Scale</label>
              <CustomSelect
                value={options.colorScale}
                onChange={(v) => onChange({ ...options, colorScale: v as any })}
                options={COLOR_SCALES.map((scale) => ({ value: scale.value, label: scale.label }))}
              />
            </div>

            <div style={{ marginTop: '0.5rem' }}>
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
          </>
        )}
      </div>
    </div>
  );
}
