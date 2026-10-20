/**
 * ScatterChartConfigPanel - Configuration UI for Scatter Chart options
 * Separated to enable Fast Refresh compatibility
 */

import { ScatterChartOptions, RegressionType, RegressionConfig } from './ScatterChart';
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

// Regression type labels for display
const REGRESSION_TYPE_LABELS: Record<RegressionType, string> = {
  linear: 'Linear',
  polynomial: 'Polynomial',
  exponential: 'Exponential',
  logarithmic: 'Logarithmic',
};

// Default regression config
const DEFAULT_REGRESSION: RegressionConfig = {
  enabled: false,
  type: 'linear',
  degree: 2,
  showEquation: true,
  showR2: true,
};

interface Props {
  options: ScatterChartOptions;
  onChange: (options: ScatterChartOptions) => void;
}

export function ScatterChartConfigPanel({ options, onChange }: Props) {
  const regression = options.regression || DEFAULT_REGRESSION;

  const updateRegression = (updates: Partial<RegressionConfig>) => {
    onChange({
      ...options,
      regression: { ...regression, ...updates },
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
      <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
        Marker Style
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.625rem' }}>
        {/* Marker Shape */}
        <div>
          <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Shape</label>
          <CustomSelect
            value={options.markerShape}
            onChange={(v) => onChange({ ...options, markerShape: v as any })}
            options={[
              { value: 'circle', label: 'Circle' },
              { value: 'square', label: 'Square' },
              { value: 'diamond', label: 'Diamond' },
              { value: 'cross', label: 'Cross' },
              { value: 'x', label: 'X' },
            ]}
          />
        </div>

        {/* Marker Size */}
        <div>
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
            min={4}
            max={20}
            value={options.markerSize}
            onChange={(e) => onChange({ ...options, markerSize: Number(e.target.value) })}
            className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
            style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
            <span>4</span>
            <span>20</span>
          </div>
        </div>

        {/* Opacity */}
        <div style={{ gridColumn: 'span 2' }}>
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
      </div>

      {/* Toggles */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
        <button
          onClick={() => onChange({ ...options, jitter: !options.jitter })}
          style={{
            padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
            borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
            border: options.jitter ? C.borderSel : C.border,
            backgroundColor: options.jitter ? C.bgActive : 'transparent',
            color: options.jitter ? C.text : C.textMuted,
          }}
        >
          Jitter Points
        </button>
      </div>

      {/* Regression Section */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Regression Analysis
          </span>
          <button
            onClick={() => updateRegression({ enabled: !regression.enabled })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: regression.enabled ? C.borderSel : C.border,
              backgroundColor: regression.enabled ? C.bgActive : 'transparent',
              color: regression.enabled ? C.text : C.textMuted,
            }}
          >
            {regression.enabled ? 'On' : 'Off'}
          </button>
        </div>

        {regression.enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {/* Regression Type */}
            <div>
              <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Type</label>
              <CustomSelect
                value={regression.type}
                onChange={(v) => updateRegression({ type: v as RegressionType })}
                options={Object.entries(REGRESSION_TYPE_LABELS).map(([value, label]) => ({
                  value,
                  label,
                }))}
              />
            </div>

            {/* Polynomial Degree (only for polynomial type) */}
            {regression.type === 'polynomial' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                  <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                    Degree
                  </span>
                  <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                    {regression.degree}
                  </span>
                </div>
                <input
                  type="range"
                  min={2}
                  max={6}
                  value={regression.degree}
                  onChange={(e) => updateRegression({ degree: Number(e.target.value) })}
                  className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
                  style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
                  <span>2</span>
                  <span>6</span>
                </div>
              </div>
            )}

            {/* Display Options */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
              <button
                onClick={() => updateRegression({ showEquation: !regression.showEquation })}
                style={{
                  padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                  borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                  border: regression.showEquation ? C.borderSel : C.border,
                  backgroundColor: regression.showEquation ? C.bgActive : 'transparent',
                  color: regression.showEquation ? C.text : C.textMuted,
                }}
              >
                Equation
              </button>
              <button
                onClick={() => updateRegression({ showR2: !regression.showR2 })}
                style={{
                  padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
                  borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
                  border: regression.showR2 ? C.borderSel : C.border,
                  backgroundColor: regression.showR2 ? C.bgActive : 'transparent',
                  color: regression.showR2 ? C.text : C.textMuted,
                }}
              >
                R² Value
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
