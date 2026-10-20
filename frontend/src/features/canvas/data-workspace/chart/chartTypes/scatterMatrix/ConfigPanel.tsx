/**
 * Configuration panel for Scatter Matrix charts
 */

import React from 'react';
import { ScatterMatrixChartOptions } from './ScatterMatrixChart';
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
  options: ScatterMatrixChartOptions;
  onChange: (options: Partial<ScatterMatrixChartOptions>) => void;
  availableFields?: string[];
}

export const ScatterMatrixChartConfigPanel: React.FC<Props> = ({
  options,
  onChange,
  availableFields = [],
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Diagonal Display */}
      <div>
        <label style={{ fontSize: '0.5rem', color: C.textFaint, display: 'block', marginBottom: '0.25rem' }}>
          Diagonal Display
        </label>
        <CustomSelect
          value={options.diagonalType}
          onChange={(v) => onChange({ diagonalType: v as any })}
          options={[
            { value: 'histogram', label: 'Histogram' },
            { value: 'box', label: 'Box Plot' },
            { value: 'none', label: 'None' },
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
          min="2"
          max="12"
          step="1"
          value={options.markerSize}
          onChange={(e) => onChange({ markerSize: Number(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>2</span>
          <span>12</span>
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
          min="0.1"
          max="1"
          step="0.1"
          value={options.markerOpacity}
          onChange={(e) => onChange({ markerOpacity: Number(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>10%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Show Upper Half */}
      <div>
        <button
          onClick={() => onChange({ showUpperHalf: !options.showUpperHalf })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.showUpperHalf ? C.borderSel : C.border,
            backgroundColor: options.showUpperHalf ? C.bgActive : 'transparent',
            color: options.showUpperHalf ? C.text : C.textMuted,
          }}
        >
          Show Upper Triangle
        </button>
      </div>

      {/* Color By Field */}
      {availableFields.length > 0 && (
        <div>
          <label style={{ fontSize: '0.5rem', color: C.textFaint, display: 'block', marginBottom: '0.25rem' }}>
            Color By (optional)
          </label>
          <CustomSelect
            value={options.colorByField || ''}
            onChange={(v) => onChange({ colorByField: v || null })}
            options={[
              { value: '', label: 'None (single color)' },
              ...availableFields.map(field => ({ value: field, label: field })),
            ]}
          />
        </div>
      )}

      {/* Info */}
      <div style={{
        fontSize: '0.5rem',
        color: C.textGhost,
        fontStyle: 'italic',
        padding: '0.5rem',
        borderRadius: '0.375rem',
        background: C.bgSubtle,
      }}>
        Select 2+ numeric Y-series fields to compare pairwise relationships.
        The diagonal shows distribution of each variable.
      </div>
    </div>
  );
};
