/**
 * PieChartConfigPanel - Configuration UI for Pie/Donut Chart
 */

import { PieChartOptions } from './PieChart';
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
  options: PieChartOptions;
  onChange: (options: PieChartOptions) => void;
}

export function PieChartConfigPanel({ options, onChange }: Props) {
  const isClassicPie = options.donutHole === 0 && options.showPercent === true && options.labelPosition === 'outside' && options.pull === 0;
  const isDonut = options.donutHole === 0.5 && options.showPercent === true && options.labelPosition === 'inside' && options.pull === 0;
  const isExploded = options.donutHole === 0 && options.showPercent === true && options.labelPosition === 'outside' && options.pull === 0.05;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Chart Style */}
      <div>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Chart Style
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Donut Hole
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {Math.round(options.donutHole * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={80}
              value={options.donutHole * 100}
              onChange={(e) => onChange({ ...options, donutHole: parseInt(e.target.value) / 100 })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>0%</span>
              <span>80%</span>
            </div>
          </div>
          <p style={{ fontSize: '0.5rem', color: C.textGhost, fontStyle: 'italic' }}>
            {options.donutHole === 0 ? 'Pie chart' : options.donutHole < 0.4 ? 'Thin donut' : 'Donut chart'}
          </p>
        </div>
      </div>

      {/* Labels */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Labels
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.5rem', color: C.textFaint, width: '3.5rem' }}>Position</label>
            <CustomSelect
              value={options.labelPosition}
              onChange={(v) => onChange({ ...options, labelPosition: v as any })}
              options={[
                { value: 'inside', label: 'Inside' },
                { value: 'outside', label: 'Outside' },
                { value: 'none', label: 'Hidden' },
              ]}
            />
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
            <button
              onClick={() => onChange({ ...options, showPercent: !options.showPercent })}
              style={{
                padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                border: options.showPercent ? C.borderSel : C.border,
                backgroundColor: options.showPercent ? C.bgActive : 'transparent',
                color: options.showPercent ? C.text : C.textMuted,
              }}
            >
              Show percentages
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
              Show values
            </button>
          </div>
        </div>
      </div>

      {/* Layout */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint, marginBottom: '0.375rem' }}>
          Layout
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
          <button
            onClick={() => onChange({ ...options, sortByValue: !options.sortByValue })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.sortByValue ? C.borderSel : C.border,
              backgroundColor: options.sortByValue ? C.bgActive : 'transparent',
              color: options.sortByValue ? C.text : C.textMuted,
            }}
          >
            Sort by value (largest first)
          </button>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Rotation
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {options.rotation}&deg;
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={360}
              value={options.rotation}
              onChange={(e) => onChange({ ...options, rotation: parseInt(e.target.value) })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>0&deg;</span>
              <span>360&deg;</span>
            </div>
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Explode
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {Math.round(options.pull * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={20}
              value={options.pull * 100}
              onChange={(e) => onChange({ ...options, pull: parseInt(e.target.value) / 100 })}
              className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
              <span>0%</span>
              <span>20%</span>
            </div>
          </div>
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
              donutHole: 0,
              showPercent: true,
              labelPosition: 'outside',
              pull: 0,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isClassicPie ? C.borderSel : C.border, backgroundColor: isClassicPie ? C.bgActive : 'transparent', color: isClassicPie ? C.text : C.textMuted }}
          >
            Classic Pie
          </button>
          <button
            onClick={() => onChange({
              ...options,
              donutHole: 0.5,
              showPercent: true,
              labelPosition: 'inside',
              pull: 0,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isDonut ? C.borderSel : C.border, backgroundColor: isDonut ? C.bgActive : 'transparent', color: isDonut ? C.text : C.textMuted }}
          >
            Donut
          </button>
          <button
            onClick={() => onChange({
              ...options,
              donutHole: 0,
              showPercent: true,
              labelPosition: 'outside',
              pull: 0.05,
            })}
            style={{ fontSize: '0.5rem', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', cursor: 'pointer', transition: 'all 0.1s ease', border: isExploded ? C.borderSel : C.border, backgroundColor: isExploded ? C.bgActive : 'transparent', color: isExploded ? C.text : C.textMuted }}
          >
            Exploded
          </button>
        </div>
      </div>
    </div>
  );
}
