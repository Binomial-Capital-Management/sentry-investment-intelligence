/**
 * Surface3DChartConfigPanel - Configuration UI for 3D Surface Chart
 *
 * Select X, Y, Z fields - surface connects all points via triangulation
 */

import { Surface3DChartOptions, COLOR_SCALES } from './Surface3DChart';
import { ColorScale } from '../heatmap/HeatmapChart';
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
  options: Surface3DChartOptions;
  onChange: (options: Surface3DChartOptions) => void;
  availableFields?: string[];
}

export function Surface3DChartConfigPanel({ options, onChange, availableFields = [] }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Field Mapping */}
      <div>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Field Mapping
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
          <div>
            <label style={{ fontSize: '0.5rem', color: C.textFaint }}>X</label>
            <CustomSelect
              value={options.xField}
              onChange={(v) => onChange({ ...options, xField: v })}
              placeholder="Select..."
              options={[
                { value: '', label: 'Select...' },
                ...availableFields.map(f => ({ value: f, label: f })),
              ]}
            />
          </div>
          <div>
            <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Y</label>
            <CustomSelect
              value={options.yField}
              onChange={(v) => onChange({ ...options, yField: v })}
              placeholder="Select..."
              options={[
                { value: '', label: 'Select...' },
                ...availableFields.map(f => ({ value: f, label: f })),
              ]}
            />
          </div>
          <div>
            <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Z (height)</label>
            <CustomSelect
              value={options.zField}
              onChange={(v) => onChange({ ...options, zField: v })}
              placeholder="Select..."
              options={[
                { value: '', label: 'Select...' },
                ...availableFields.map(f => ({ value: f, label: f })),
              ]}
            />
          </div>
        </div>
        <p style={{
          fontSize: '0.5rem',
          color: C.textGhost,
          fontStyle: 'italic',
          marginTop: '0.5rem',
        }}>
          Surface connects all points using triangulation (mesh3d)
        </p>
      </div>

      {/* Color Scale */}
      <div>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Color Scale
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
          <div>
            <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Scale</label>
            <CustomSelect
              value={options.colorScale}
              onChange={(v) => onChange({ ...options, colorScale: v as ColorScale })}
              options={COLOR_SCALES.map(s => ({
                value: s.id,
                label: s.name,
                group: s.type === 'sequential' ? 'Sequential' : 'Diverging',
              }))}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: '0.125rem', gap: '0.25rem' }}>
            <button
              onClick={() => onChange({ ...options, reverseScale: !options.reverseScale })}
              style={{
                padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: options.reverseScale ? C.borderSel : C.border,
                backgroundColor: options.reverseScale ? C.bgActive : 'transparent',
                color: options.reverseScale ? C.text : C.textMuted,
              }}
            >
              Reverse
            </button>
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
              Bar
            </button>
          </div>
        </div>
      </div>

      {/* Surface Appearance */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Surface
        </div>
        <div>
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
      </div>

      {/* Presets */}
      {(() => {
        const isDefault = options.colorScale === 'Viridis' && options.opacity === 0.9;
        const isPlasma = options.colorScale === 'Plasma' && options.opacity === 0.85;
        const isDiverging = options.colorScale === 'RdBu' && options.opacity === 0.9;
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
              colorScale: 'Viridis',
              opacity: 0.9,
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isDefault ? C.borderSel : C.border,
              backgroundColor: isDefault ? C.bgActive : 'transparent',
              color: isDefault ? C.text : C.textMuted,
            }}
          >
            Default
          </button>
          <button
            onClick={() => onChange({
              ...options,
              colorScale: 'Plasma',
              opacity: 0.85,
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isPlasma ? C.borderSel : C.border,
              backgroundColor: isPlasma ? C.bgActive : 'transparent',
              color: isPlasma ? C.text : C.textMuted,
            }}
          >
            Plasma
          </button>
          <button
            onClick={() => onChange({
              ...options,
              colorScale: 'RdBu',
              opacity: 0.9,
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isDiverging ? C.borderSel : C.border,
              backgroundColor: isDiverging ? C.bgActive : 'transparent',
              color: isDiverging ? C.text : C.textMuted,
            }}
          >
            Diverging
          </button>
        </div>
      </div>
        );
      })()}
    </div>
  );
}
