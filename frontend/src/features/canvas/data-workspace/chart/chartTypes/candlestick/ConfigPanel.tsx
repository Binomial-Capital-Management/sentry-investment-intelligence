/**
 * CandlestickChartConfigPanel - Configuration UI for Candlestick Chart options
 */

import { CandlestickChartOptions } from './CandlestickChart';

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
  options: CandlestickChartOptions;
  onChange: (options: CandlestickChartOptions) => void;
}

export function CandlestickChartConfigPanel({ options, onChange }: Props) {
  const isClassic = options.upColor === '#22C55E' && options.downColor === '#EF4444';
  const isBlueOrange = options.upColor === '#3B82F6' && options.downColor === '#F97316';
  const isEmeraldViolet = options.upColor === '#10B981' && options.downColor === '#8B5CF6';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Candle Colors */}
      <div>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Candle Colors
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <div>
            <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Bullish (Up)</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
              <input
                type="color"
                value={options.upColor}
                onChange={(e) => onChange({
                  ...options,
                  upColor: e.target.value,
                  increasing: {
                    line: { color: e.target.value },
                    fillcolor: e.target.value,
                  }
                })}
                style={{
                  width: '2rem',
                  height: '1.5rem',
                  borderRadius: '0.25rem',
                  border: C.border,
                  cursor: 'pointer',
                }}
              />
              <span style={{ fontSize: '0.5rem', color: C.textGhost, fontFamily: 'monospace' }}>
                {options.upColor}
              </span>
            </div>
          </div>
          <div>
            <label style={{ fontSize: '0.5rem', color: C.textFaint }}>Bearish (Down)</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
              <input
                type="color"
                value={options.downColor}
                onChange={(e) => onChange({
                  ...options,
                  downColor: e.target.value,
                  decreasing: {
                    line: { color: e.target.value },
                    fillcolor: e.target.value,
                  }
                })}
                style={{
                  width: '2rem',
                  height: '1.5rem',
                  borderRadius: '0.25rem',
                  border: C.border,
                  cursor: 'pointer',
                }}
              />
              <span style={{ fontSize: '0.5rem', color: C.textGhost, fontFamily: 'monospace' }}>
                {options.downColor}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Line Width */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
          <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
            Wick Width
          </span>
          <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
            {options.lineWidth}px
          </span>
        </div>
        <input
          type="range"
          min={1}
          max={3}
          step={0.5}
          value={options.lineWidth}
          onChange={(e) => onChange({ ...options, lineWidth: Number(e.target.value) })}
          className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
          style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 30%)', marginTop: '0.125rem' }}>
          <span>1</span>
          <span>3</span>
        </div>
      </div>

      {/* Volume Section */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '0.5rem',
        }}>
          <span style={{
            fontSize: '0.563rem',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: C.textFaint,
          }}>
            Volume Bars
          </span>
          <button
            onClick={() => onChange({ ...options, showVolume: !options.showVolume })}
            style={{
              padding: '0.25rem 0.375rem', fontSize: '0.563rem', fontWeight: 500,
              borderRadius: '0.375rem', cursor: 'pointer', transition: 'all 0.1s ease',
              border: options.showVolume ? C.borderSel : C.border,
              backgroundColor: options.showVolume ? C.bgActive : 'transparent',
              color: options.showVolume ? C.text : C.textMuted,
            }}
          >
            {options.showVolume ? 'On' : 'Off'}
          </button>
        </div>

        {options.showVolume && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.563rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: C.textFaint }}>
                Opacity
              </span>
              <span style={{ fontSize: '0.625rem', fontWeight: 600, fontFamily: 'monospace', color: C.text, backgroundColor: 'hsl(30 3.3% 11.8% / 6%)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>
                {Math.round(options.volumeOpacity * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={10}
              max={100}
              value={options.volumeOpacity * 100}
              onChange={(e) => onChange({ ...options, volumeOpacity: Number(e.target.value) / 100 })}
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

      {/* Quick Presets */}
      <div style={{ borderTop: C.border, paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        <div style={{
          fontSize: '0.563rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: C.textFaint,
          marginBottom: '0.5rem',
        }}>
          Color Presets
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          <button
            onClick={() => onChange({
              ...options,
              upColor: '#22C55E',
              downColor: '#EF4444',
              increasing: { line: { color: '#22C55E' }, fillcolor: '#22C55E' },
              decreasing: { line: { color: '#EF4444' }, fillcolor: '#EF4444' },
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              border: isClassic ? C.borderSel : C.border,
              borderRadius: '0.25rem',
              background: isClassic ? C.bgActive : 'transparent',
              color: isClassic ? C.text : C.textMuted,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              transition: 'all 0.1s ease',
            }}
            onMouseEnter={(e) => { if (!isClassic) e.currentTarget.style.background = C.bgHover; }}
            onMouseLeave={(e) => { if (!isClassic) e.currentTarget.style.background = 'transparent'; }}
          >
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22C55E', display: 'inline-block' }} />
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#EF4444', display: 'inline-block' }} />
            Classic
          </button>
          <button
            onClick={() => onChange({
              ...options,
              upColor: '#3B82F6',
              downColor: '#F97316',
              increasing: { line: { color: '#3B82F6' }, fillcolor: '#3B82F6' },
              decreasing: { line: { color: '#F97316' }, fillcolor: '#F97316' },
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              border: isBlueOrange ? C.borderSel : C.border,
              borderRadius: '0.25rem',
              background: isBlueOrange ? C.bgActive : 'transparent',
              color: isBlueOrange ? C.text : C.textMuted,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              transition: 'all 0.1s ease',
            }}
            onMouseEnter={(e) => { if (!isBlueOrange) e.currentTarget.style.background = C.bgHover; }}
            onMouseLeave={(e) => { if (!isBlueOrange) e.currentTarget.style.background = 'transparent'; }}
          >
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#3B82F6', display: 'inline-block' }} />
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#F97316', display: 'inline-block' }} />
            Blue/Orange
          </button>
          <button
            onClick={() => onChange({
              ...options,
              upColor: '#10B981',
              downColor: '#8B5CF6',
              increasing: { line: { color: '#10B981' }, fillcolor: '#10B981' },
              decreasing: { line: { color: '#8B5CF6' }, fillcolor: '#8B5CF6' },
            })}
            style={{
              fontSize: '0.5rem',
              padding: '0.125rem 0.375rem',
              border: isEmeraldViolet ? C.borderSel : C.border,
              borderRadius: '0.25rem',
              background: isEmeraldViolet ? C.bgActive : 'transparent',
              color: isEmeraldViolet ? C.text : C.textMuted,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              transition: 'all 0.1s ease',
            }}
            onMouseEnter={(e) => { if (!isEmeraldViolet) e.currentTarget.style.background = C.bgHover; }}
            onMouseLeave={(e) => { if (!isEmeraldViolet) e.currentTarget.style.background = 'transparent'; }}
          >
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#8B5CF6', display: 'inline-block' }} />
            Emerald/Violet
          </button>
        </div>
      </div>
    </div>
  );
}
