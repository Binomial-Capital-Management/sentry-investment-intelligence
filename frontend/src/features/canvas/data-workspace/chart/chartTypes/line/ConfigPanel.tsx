/**
 * LineChartConfigPanel - Configuration UI for Line Chart options
 * Separated to enable Fast Refresh compatibility
 */

import type { LineChartOptions } from './LineChart';
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
  options: LineChartOptions;
  onChange: (options: LineChartOptions) => void;
}

export function LineChartConfigPanel({ options, onChange }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem', borderTop: C.border, paddingTop: '0.5rem' }}>
      <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
        Line Options
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.625rem' }}>
        {/* Line Style */}
        <div>
          <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Style</label>
          <CustomSelect
            value={options.lineStyle}
            onChange={(v) => onChange({ ...options, lineStyle: v as any })}
            options={[
              { value: 'solid', label: 'Solid' },
              { value: 'dash', label: 'Dashed' },
              { value: 'dot', label: 'Dotted' },
              { value: 'dashdot', label: 'Dash-Dot' },
            ]}
          />
        </div>

        {/* Line Width */}
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
            min={1}
            max={5}
            value={options.lineWidth}
            onChange={(e) => onChange({ ...options, lineWidth: Number(e.target.value) })}
            className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
            style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
            <span>1</span>
            <span>5</span>
          </div>
        </div>
      </div>

      {/* Toggles */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
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
          Smooth
        </button>
        <button
          onClick={() => onChange({ ...options, fillArea: !options.fillArea })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.fillArea ? C.borderSel : C.border,
            backgroundColor: options.fillArea ? C.bgActive : 'transparent',
            color: options.fillArea ? C.text : C.textMuted,
          }}
        >
          Fill Area
        </button>
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
          Show Points
        </button>
        <button
          onClick={() => onChange({ ...options, connectGaps: !options.connectGaps })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.connectGaps ? C.borderSel : C.border,
            backgroundColor: options.connectGaps ? C.bgActive : 'transparent',
            color: options.connectGaps ? C.text : C.textMuted,
          }}
        >
          Connect Gaps
        </button>
      </div>
    </div>
  );
}
