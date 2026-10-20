/**
 * HeatmapChartConfigPanel - Configuration UI for Heatmap Chart options
 */

import { HeatmapChartOptions, COLOR_SCALES, ColorScale } from './HeatmapChart';
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

const numberInputStyle: React.CSSProperties = {
  width: '100%',
  marginTop: '0.25rem',
  fontSize: '0.563rem',
  padding: '0.25rem 0.375rem',
  border: C.border,
  borderRadius: '0.375rem',
  color: C.text,
  backgroundColor: 'white',
};

interface Props {
  options: HeatmapChartOptions;
  onChange: (options: HeatmapChartOptions) => void;
  availableFields?: string[];
}

export function HeatmapChartConfigPanel({ options, onChange, availableFields = [] }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Mode Toggle */}
      <div>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Mode
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.5rem',
            fontSize: '0.563rem',
            color: C.textMuted,
            cursor: 'pointer',
          }}>
            <input
              type="radio"
              checked={options.correlationMode}
              onChange={() => onChange({ ...options, correlationMode: true })}
              style={{ width: 12, height: 12, marginTop: '0.1rem' }}
            />
            <div>
              <div style={{ fontWeight: 500, color: C.text }}>Correlation Matrix</div>
              <div style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic' }}>
                Compute correlations between Y-series (requires 2+ columns)
              </div>
            </div>
          </label>
          <label style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.5rem',
            fontSize: '0.563rem',
            color: C.textMuted,
            cursor: 'pointer',
          }}>
            <input
              type="radio"
              checked={!options.correlationMode}
              onChange={() => onChange({ ...options, correlationMode: false })}
              style={{ width: 12, height: 12, marginTop: '0.1rem' }}
            />
            <div>
              <div style={{ fontWeight: 500, color: C.text }}>Custom Matrix</div>
              <div style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic' }}>
                Map X, Y, Z fields manually
              </div>
            </div>
          </label>
        </div>
      </div>

      {/* Field Mapping (only for custom mode) */}
      {!options.correlationMode && availableFields.length > 0 && (
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
              <label style={{ fontSize: '0.5rem', color: C.textFaint }}>X Field</label>
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
              <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Y Field</label>
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
              <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Z Value</label>
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
        </div>
      )}

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
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
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
            <button
              onClick={() => onChange({ ...options, reverseScale: !options.reverseScale })}
              style={{
                alignSelf: 'flex-start',
                padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: options.reverseScale ? C.borderSel : C.border,
                backgroundColor: options.reverseScale ? C.bgActive : 'transparent',
                color: options.reverseScale ? C.text : C.textMuted,
              }}
            >
              Reverse
            </button>
          </div>

          {/* Color Range */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            <div>
              <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Min Value</label>
              <input
                type="number"
                value={options.zMin ?? ''}
                onChange={(e) => onChange({
                  ...options,
                  zMin: e.target.value ? parseFloat(e.target.value) : undefined
                })}
                placeholder="Auto"
                style={numberInputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Max Value</label>
              <input
                type="number"
                value={options.zMax ?? ''}
                onChange={(e) => onChange({
                  ...options,
                  zMax: e.target.value ? parseFloat(e.target.value) : undefined
                })}
                placeholder="Auto"
                style={numberInputStyle}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Display Options */}
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
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
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
            Show values in cells
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
            Show color bar
          </button>
        </div>

        {options.showValues && (
          <div style={{ marginTop: '0.5rem' }}>
            <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Number Format</label>
            <CustomSelect
              value={options.valueFormat}
              onChange={(v) => onChange({ ...options, valueFormat: v })}
              options={[
                { value: '.0f', label: 'Integer (0)' },
                { value: '.1f', label: '1 decimal (0.0)' },
                { value: '.2f', label: '2 decimals (0.00)' },
                { value: '.3f', label: '3 decimals (0.000)' },
                { value: '.0%', label: 'Percent (0%)' },
                { value: '.1%', label: 'Percent (0.0%)' },
                { value: '.2%', label: 'Percent (0.00%)' },
              ]}
            />
          </div>
        )}
      </div>

      {/* Cell Spacing */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Cell Spacing
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                X Gap
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {options.xGap}px
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={5}
              value={options.xGap}
              onChange={(e) => onChange({ ...options, xGap: parseInt(e.target.value) })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>0</span>
              <span>5</span>
            </div>
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Y Gap
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {options.yGap}px
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={5}
              value={options.yGap}
              onChange={(e) => onChange({ ...options, yGap: parseInt(e.target.value) })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>0</span>
              <span>5</span>
            </div>
          </div>
        </div>
      </div>

      {/* Presets */}
      {(() => {
        const isCorrelation = options.correlationMode === true && options.colorScale === 'RdBu' && options.reverseScale === true && options.zMin === -1 && options.zMax === 1 && options.showValues === true && options.valueFormat === '.2f';
        const isReturns = options.colorScale === 'RdYlGn' && options.reverseScale === false && options.zMin === undefined && options.zMax === undefined && options.showValues === true && options.valueFormat === '.1%';
        const isDensity = options.colorScale === 'Viridis' && options.reverseScale === false && options.zMin === undefined && options.zMax === undefined && options.showValues === false;
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
              correlationMode: true,
              colorScale: 'RdBu',
              reverseScale: true,
              zMin: -1,
              zMax: 1,
              showValues: true,
              valueFormat: '.2f',
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isCorrelation ? C.borderSel : C.border,
              backgroundColor: isCorrelation ? C.bgActive : 'transparent',
              color: isCorrelation ? C.text : C.textMuted,
            }}
          >
            Correlation
          </button>
          <button
            onClick={() => onChange({
              ...options,
              colorScale: 'RdYlGn',
              reverseScale: false,
              zMin: undefined,
              zMax: undefined,
              showValues: true,
              valueFormat: '.1%',
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isReturns ? C.borderSel : C.border,
              backgroundColor: isReturns ? C.bgActive : 'transparent',
              color: isReturns ? C.text : C.textMuted,
            }}
          >
            Returns
          </button>
          <button
            onClick={() => onChange({
              ...options,
              colorScale: 'Viridis',
              reverseScale: false,
              zMin: undefined,
              zMax: undefined,
              showValues: false,
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
              border: isDensity ? C.borderSel : C.border,
              backgroundColor: isDensity ? C.bgActive : 'transparent',
              color: isDensity ? C.text : C.textMuted,
            }}
          >
            Density
          </button>
        </div>
      </div>
        );
      })()}
    </div>
  );
}
