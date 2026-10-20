/**
 * BarChartConfigPanel - Configuration UI for Bar Chart options
 */

import { BarChartOptions } from './BarChart';
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
  options: BarChartOptions;
  onChange: (options: BarChartOptions) => void;
}

export function BarChartConfigPanel({ options, onChange }: Props) {
  const isComparison = options.orientation === 'v' && options.barMode === 'group' && options.showValues === true && options.gap === 0.2;
  const isStacked = options.orientation === 'v' && options.barMode === 'stack' && options.showValues === false && options.gap === 0.15;
  const isHorizontal = options.orientation === 'h' && options.barMode === 'group' && options.showValues === true && options.gap === 0.25;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Orientation */}
      <div>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Orientation
        </div>
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          <button
            onClick={() => onChange({ ...options, orientation: 'v' })}
            style={{
              flex: 1,
              padding: '0.25rem 0.375rem',
              fontSize: '0.563rem',
              fontWeight: 500,
              borderRadius: '0.375rem',
              border: options.orientation === 'v' ? C.borderSel : C.border,
              background: options.orientation === 'v' ? C.bgActive : 'transparent',
              color: options.orientation === 'v' ? C.text : C.textMuted,
              cursor: 'pointer',
              transition: 'all 0.1s ease',
            }}
          >
            Vertical
          </button>
          <button
            onClick={() => onChange({ ...options, orientation: 'h' })}
            style={{
              flex: 1,
              padding: '0.25rem 0.375rem',
              fontSize: '0.563rem',
              fontWeight: 500,
              borderRadius: '0.375rem',
              border: options.orientation === 'h' ? C.borderSel : C.border,
              background: options.orientation === 'h' ? C.bgActive : 'transparent',
              color: options.orientation === 'h' ? C.text : C.textMuted,
              cursor: 'pointer',
              transition: 'all 0.1s ease',
            }}
          >
            Horizontal
          </button>
        </div>
      </div>

      {/* Bar Mode */}
      <div>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Multiple Series Display
        </div>
        <CustomSelect
          value={options.barMode}
          onChange={(v) => onChange({ ...options, barMode: v as 'group' | 'stack' | 'overlay' })}
          options={[
            { value: 'group', label: 'Grouped (side by side)' },
            { value: 'stack', label: 'Stacked (cumulative)' },
            { value: 'overlay', label: 'Overlay (overlapping)' },
          ]}
        />
      </div>

      {/* Display Options */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Display
        </div>
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
          Show value labels on bars
        </button>
      </div>

      {/* Bar Sizing */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Bar Sizing
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Gap
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {(options.gap * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={0.5}
              step={0.05}
              value={options.gap}
              onChange={(e) => onChange({ ...options, gap: parseFloat(e.target.value) })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>0%</span>
              <span>50%</span>
            </div>
          </div>

          {options.barWidth !== undefined && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                  Bar Width
                </span>
                <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                  {(options.barWidth * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min={0.1}
                max={1}
                step={0.05}
                value={options.barWidth}
                onChange={(e) => onChange({ ...options, barWidth: parseFloat(e.target.value) })}
                className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
                style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
                <span>10%</span>
                <span>100%</span>
              </div>
            </div>
          )}
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
              orientation: 'v',
              barMode: 'group',
              showValues: true,
              gap: 0.2,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isComparison ? C.borderSel : C.border, backgroundColor: isComparison ? C.bgActive : 'transparent', color: isComparison ? C.text : C.textMuted }}
          >
            Comparison
          </button>
          <button
            onClick={() => onChange({
              ...options,
              orientation: 'v',
              barMode: 'stack',
              showValues: false,
              gap: 0.15,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isStacked ? C.borderSel : C.border, backgroundColor: isStacked ? C.bgActive : 'transparent', color: isStacked ? C.text : C.textMuted }}
          >
            Stacked
          </button>
          <button
            onClick={() => onChange({
              ...options,
              orientation: 'h',
              barMode: 'group',
              showValues: true,
              gap: 0.25,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isHorizontal ? C.borderSel : C.border, backgroundColor: isHorizontal ? C.bgActive : 'transparent', color: isHorizontal ? C.text : C.textMuted }}
          >
            Horizontal
          </button>
        </div>
      </div>
    </div>
  );
}
