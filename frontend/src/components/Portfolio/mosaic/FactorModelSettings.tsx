import { useRef, useState, useEffect } from 'react';
import { Settings, RotateCcw, X } from 'lucide-react';
import { useFactorModelConfig, ALL_STYLE_FACTORS, DEFAULT_CONFIG } from '../hooks/useFactorModelConfig';
import type { StyleFactor } from '../hooks/useFactorModelConfig';

const PERIOD_OPTIONS = [
  { value: '6mo', label: '6 Months' },
  { value: '1y', label: '1 Year' },
  { value: '2y', label: '2 Years' },
] as const;

const BENCHMARK_OPTIONS = [
  { value: 'SPY',  label: 'SPY — S&P 500' },
  { value: 'QQQ',  label: 'QQQ — Nasdaq 100' },
  { value: 'IWM',  label: 'IWM — Russell 2000' },
  { value: 'DIA',  label: 'DIA — Dow Jones' },
  { value: 'EFA',  label: 'EFA — MSCI EAFE' },
  { value: 'EEM',  label: 'EEM — EM Equities' },
  { value: 'AGG',  label: 'AGG — US Agg Bond' },
  { value: 'custom', label: 'Custom…' },
];

function Slider({
  label, value, min, max, step = 1, unit = '', onChange, hint,
}: {
  label: string; value: number; min: number; max: number; step?: number;
  unit?: string; onChange: (v: number) => void; hint?: string;
}) {
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <label style={{ fontSize: '11px', fontWeight: '600', color: '#374151' }}>{label}</label>
        <span style={{ fontSize: '11px', fontWeight: '700', color: '#2563eb', fontVariantNumeric: 'tabular-nums' }}>
          {value}{unit}
        </span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{ width: '100%', accentColor: '#2563eb', cursor: 'pointer' }}
      />
      {hint && <div style={{ fontSize: '9px', color: '#9ca3af', marginTop: '2px' }}>{hint}</div>}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', marginBottom: '6px' }}>
      <div
        onClick={() => onChange(!checked)}
        style={{
          width: '32px', height: '18px', borderRadius: '9px',
          background: checked ? '#2563eb' : '#d1d5db',
          position: 'relative', transition: 'background 0.15s', flexShrink: 0,
        }}
      >
        <div style={{
          position: 'absolute', top: '2px',
          left: checked ? '16px' : '2px',
          width: '14px', height: '14px', borderRadius: '50%',
          background: '#fff', transition: 'left 0.15s',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        }} />
      </div>
      <span style={{ fontSize: '11px', color: '#374151', fontWeight: '500' }}>{label}</span>
    </label>
  );
}

export default function FactorModelSettings() {
  const { config, update, reset } = useFactorModelConfig();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  const knownBenchmarks = BENCHMARK_OPTIONS.map(o => o.value).filter(v => v !== 'custom');
  const isCustomBenchmark = !knownBenchmarks.includes(config.benchmark);
  const [showCustomInput, setShowCustomInput] = useState(isCustomBenchmark);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!panelRef.current?.contains(e.target as Node) && !btnRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const toggleFactor = (f: StyleFactor) => {
    const has = config.styleFactors.includes(f);
    if (has && config.styleFactors.length <= 1) return; // keep at least one
    update({ styleFactors: has ? config.styleFactors.filter(x => x !== f) : [...config.styleFactors, f] });
  };

  const isDefault = JSON.stringify(config) === JSON.stringify(DEFAULT_CONFIG);

  return (
    <div style={{ position: 'relative' }}>
      <button
        ref={btnRef}
        onClick={() => setOpen(v => !v)}
        title="Factor model settings"
        style={{
          display: 'flex', alignItems: 'center', gap: '4px',
          padding: '4px 8px', borderRadius: '5px', border: '1px solid',
          borderColor: open ? '#2563eb' : '#e5e7eb',
          background: open ? '#eff6ff' : '#fff',
          color: open ? '#2563eb' : '#6b7280',
          fontSize: '10px', fontWeight: '600', cursor: 'pointer',
          transition: 'all 0.15s',
          whiteSpace: 'nowrap',
        }}
      >
        <Settings size={11} />
        Factor Settings
        {!isDefault && <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#2563eb', flexShrink: 0 }} />}
      </button>

      {open && (
        <div
          ref={panelRef}
          style={{
            position: 'absolute', top: 'calc(100% + 6px)', right: 0,
            width: '320px', background: '#fff',
            border: '1px solid #e5e7eb', borderRadius: '10px',
            boxShadow: '0 10px 40px rgba(0,0,0,0.12)',
            zIndex: 1000, overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{ padding: '12px 14px', borderBottom: '1px solid #f3f4f6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '12px', fontWeight: '700', color: '#111827' }}>Factor Model Settings</span>
            <div style={{ display: 'flex', gap: '4px' }}>
              {!isDefault && (
                <button
                  onClick={reset}
                  title="Reset to defaults"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: '2px' }}
                >
                  <RotateCcw size={13} />
                </button>
              )}
              <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: '2px' }}>
                <X size={13} />
              </button>
            </div>
          </div>

          <div style={{ padding: '14px', maxHeight: '80vh', overflowY: 'auto' }}>
            {/* Data window */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '6px' }}>
                Data Window
              </div>
              <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
                {PERIOD_OPTIONS.map(p => (
                  <button
                    key={p.value}
                    onClick={() => update({ period: p.value })}
                    style={{
                      flex: 1, padding: '5px', fontSize: '11px', fontWeight: '600',
                      borderRadius: '5px', border: '1px solid',
                      borderColor: config.period === p.value ? '#2563eb' : '#e5e7eb',
                      background: config.period === p.value ? '#eff6ff' : '#fff',
                      color: config.period === p.value ? '#2563eb' : '#6b7280',
                      cursor: 'pointer',
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div>
                <label style={{ fontSize: '10px', color: '#374151', fontWeight: '600', display: 'block', marginBottom: '4px' }}>Benchmark</label>
                <select
                  value={showCustomInput ? 'custom' : config.benchmark}
                  onChange={e => {
                    if (e.target.value === 'custom') {
                      setShowCustomInput(true);
                    } else {
                      setShowCustomInput(false);
                      update({ benchmark: e.target.value });
                    }
                  }}
                  style={{
                    width: '100%', padding: '5px 8px', fontSize: '11px',
                    border: '1px solid #e5e7eb', borderRadius: '5px',
                    background: '#fff', color: '#111827', cursor: 'pointer',
                    appearance: 'auto',
                  }}
                >
                  {BENCHMARK_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                {showCustomInput && (
                  <input
                    autoFocus
                    value={config.benchmark}
                    onChange={e => update({ benchmark: e.target.value.toUpperCase().trim() })}
                    placeholder="e.g. ACWI"
                    style={{
                      width: '100%', marginTop: '6px', padding: '5px 8px',
                      fontSize: '11px', border: '1px solid #2563eb', borderRadius: '5px',
                      boxSizing: 'border-box', outline: 'none',
                    }}
                  />
                )}
              </div>
            </div>

            {/* Style factors */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '6px' }}>
                Style Factors
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '4px' }}>
                {ALL_STYLE_FACTORS.map(f => {
                  const active = config.styleFactors.includes(f);
                  return (
                    <button
                      key={f}
                      onClick={() => toggleFactor(f)}
                      style={{
                        padding: '3px 8px', fontSize: '10px', fontWeight: '600',
                        borderRadius: '4px', border: '1px solid',
                        borderColor: active ? '#2563eb' : '#e5e7eb',
                        background: active ? '#eff6ff' : '#f9fafb',
                        color: active ? '#2563eb' : '#6b7280',
                        cursor: 'pointer',
                      }}
                    >
                      {f}
                    </button>
                  );
                })}
              </div>
              <Toggle label="Include GICS Sector Dummies" checked={config.includeSectors} onChange={v => update({ includeSectors: v })} />
            </div>

            {/* Windows */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '8px' }}>
                Estimation Windows
              </div>
              <Slider
                label="Volatility Window"
                value={config.volWindow} min={20} max={252} unit="d"
                onChange={v => update({ volWindow: v })}
                hint="Days of returns used for the Volatility factor"
              />
              <Slider
                label="Beta Window"
                value={config.betaWindow} min={60} max={756} step={21} unit="d"
                onChange={v => update({ betaWindow: v })}
                hint="OLS beta lookback vs benchmark"
              />
            </div>

            {/* Covariance */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '8px' }}>
                Factor Covariance
              </div>
              <Slider
                label="EWA Half-Life"
                value={config.ewaHalfLife} min={10} max={504} step={5} unit="d"
                onChange={v => update({ ewaHalfLife: v })}
                hint="Exponential weighting decay. Shorter = more reactive to recent returns"
              />
              <Slider
                label="Newey-West Lags"
                value={config.nwLags} min={0} max={20} unit=""
                onChange={v => update({ nwLags: v })}
                hint="Autocorrelation correction lags (0 = no correction)"
              />
              <Slider
                label="Specific Risk Shrinkage"
                value={config.shrinkage} min={0} max={0.5} step={0.01} unit=""
                onChange={v => update({ shrinkage: v })}
                hint="Bayesian pull of idiosyncratic variances toward cross-sectional mean"
              />
            </div>

            {/* PCA */}
            <div>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '8px' }}>
                PCA
              </div>
              <Slider
                label="Components to Return"
                value={config.pcaN} min={2} max={20} unit=""
                onChange={v => update({ pcaN: v })}
                hint="Number of principal components shown in the PCA Risk tile"
              />
            </div>
          </div>

          {/* Footer note */}
          <div style={{ padding: '8px 14px', borderTop: '1px solid #f3f4f6', fontSize: '9px', color: '#9ca3af', background: '#fafafa' }}>
            Changes invalidate the 10-min cache and trigger a fresh compute.
          </div>
        </div>
      )}
    </div>
  );
}
