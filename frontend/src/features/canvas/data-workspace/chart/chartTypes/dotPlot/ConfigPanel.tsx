/**
 * Configuration panel for Dot Plot charts
 */

import React from 'react';
import { DotPlotChartOptions } from './DotPlotChart';
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
  options: DotPlotChartOptions;
  onChange: (options: Partial<DotPlotChartOptions>) => void;
}

export const DotPlotChartConfigPanel: React.FC<Props> = ({
  options,
  onChange,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Orientation */}
      <div>
        <label style={{ fontSize: '0.5rem', color: C.textFaint, display: 'block', marginBottom: '0.25rem' }}>
          Orientation
        </label>
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          <button
            onClick={() => onChange({ orientation: 'vertical' })}
            style={{
              flex: 1,
              padding: '0.25rem 0.375rem',
              fontSize: '0.563rem',
              fontWeight: 500,
              borderRadius: '0.375rem',
              border: options.orientation === 'vertical' ? C.borderSel : C.border,
              background: options.orientation === 'vertical' ? C.bgActive : 'transparent',
              color: options.orientation === 'vertical' ? C.text : C.textMuted,
              cursor: 'pointer',
              transition: 'all 0.1s ease',
            }}
          >
            Vertical
          </button>
          <button
            onClick={() => onChange({ orientation: 'horizontal' })}
            style={{
              flex: 1,
              padding: '0.25rem 0.375rem',
              fontSize: '0.563rem',
              fontWeight: 500,
              borderRadius: '0.375rem',
              border: options.orientation === 'horizontal' ? C.borderSel : C.border,
              background: options.orientation === 'horizontal' ? C.bgActive : 'transparent',
              color: options.orientation === 'horizontal' ? C.text : C.textMuted,
              cursor: 'pointer',
              transition: 'all 0.1s ease',
            }}
          >
            Horizontal
          </button>
        </div>
      </div>

      {/* Jitter Amount */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Jitter (spread)
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {Math.round(options.jitter * 100)}%
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="0.4"
          step="0.05"
          value={options.jitter}
          onChange={(e) => onChange({ jitter: Number(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>No jitter</span>
          <span>Max spread</span>
        </div>
      </div>

      {/* Marker Size */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Point Size
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {options.markerSize}
          </span>
        </div>
        <input
          type="range"
          min="4"
          max="16"
          step="1"
          value={options.markerSize}
          onChange={(e) => onChange({ markerSize: Number(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>4</span>
          <span>16</span>
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
          min="0.2"
          max="1"
          step="0.1"
          value={options.markerOpacity}
          onChange={(e) => onChange({ markerOpacity: Number(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>20%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Color Mode */}
      <div>
        <label style={{ fontSize: '0.5rem', color: C.textFaint, display: 'block', marginBottom: '0.25rem' }}>
          Color Mode
        </label>
        <CustomSelect
          value={options.colorMode}
          onChange={(v) => onChange({ colorMode: v as any })}
          options={[
            { value: 'series', label: 'By Series' },
            { value: 'gradient', label: 'By Value (gradient)' },
          ]}
        />
      </div>

      {/* Statistical Lines */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <label style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
        }}>
          Show Statistics
        </label>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
          <button
            onClick={() => onChange({ showMean: !options.showMean })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.showMean ? C.borderSel : C.border,
              backgroundColor: options.showMean ? C.bgActive : 'transparent',
              color: options.showMean ? C.text : C.textMuted,
            }}
          >
            Mean line
          </button>
          <button
            onClick={() => onChange({ showMedian: !options.showMedian })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.showMedian ? C.borderSel : C.border,
              backgroundColor: options.showMedian ? C.bgActive : 'transparent',
              color: options.showMedian ? C.text : C.textMuted,
            }}
          >
            Median line
          </button>
        </div>
      </div>

      {/* Info */}
      <div style={{
        fontSize: '0.5rem',
        color: C.textGhost,
        fontStyle: 'italic',
        padding: '0.5rem',
        borderRadius: '0.375rem',
        background: C.bgSubtle,
      }}>
        Dot plots show individual data points per category. Use jitter to
        spread overlapping points. Good for small-medium datasets.
      </div>
    </div>
  );
};
