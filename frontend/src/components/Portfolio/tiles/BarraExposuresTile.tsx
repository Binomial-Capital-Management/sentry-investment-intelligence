import { RefreshCw } from 'lucide-react';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';
import { useFactorAnalysis } from '../hooks/useFactorAnalysis';

const STYLE_FACTORS = ['Momentum', 'Size', 'Value', 'Quality', 'Volatility', 'Beta'];
const SECTOR_FACTORS = [
  'Technology', 'Healthcare', 'Financials', 'Consumer_Disc', 'Consumer_Staples',
  'Industrials', 'Energy', 'Materials', 'Utilities', 'Real_Estate', 'Communications',
];

function barColor(v: number): string {
  return v >= 0 ? '#2563eb' : '#ef4444';
}

function ExposureBar({ label, value, maxAbs }: { label: string; value: number; maxAbs: number }) {
  const pct = maxAbs > 0 ? Math.min(Math.abs(value) / maxAbs, 1) * 100 : 0;
  const isPos = value >= 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '3px 0' }}>
      <span style={{ width: '110px', fontSize: '11px', color: '#374151', fontWeight: '500', flexShrink: 0, textAlign: 'right' }}>
        {label.replace(/_/g, ' ')}
      </span>
      <div style={{ flex: 1, position: 'relative', height: '14px', background: '#f3f4f6', borderRadius: '3px', overflow: 'hidden' }}>
        <div style={{
          position: 'absolute',
          top: 0,
          height: '100%',
          width: `${pct}%`,
          background: barColor(value),
          borderRadius: '3px',
          left: isPos ? '0' : 'auto',
          right: isPos ? 'auto' : '0',
          opacity: 0.85,
        }} />
      </div>
      <span style={{
        width: '44px', textAlign: 'right', fontSize: '11px', fontWeight: '700',
        color: barColor(value), fontVariantNumeric: 'tabular-nums',
      }}>
        {value.toFixed(2)}
      </span>
    </div>
  );
}

export default function BarraExposuresTile() {
  const { portfolio } = usePortfolioDetail();
  const { data, loading, error, refresh, lastUpdated } = useFactorAnalysis(portfolio?.id);

  const exposures = data?.barra?.portfolio_exposures ?? {};
  const contributions = data?.barra?.factor_contributions ?? {};
  const sysP = data?.barra?.systematic_pct ?? 0;
  const idioP = data?.barra?.idiosyncratic_pct ?? 0;
  const r2 = data?.barra?.mean_r_squared ?? 0;
  const exAnteBeta = data?.barra?.ex_ante_beta;
  const exAnteVol = data?.barra?.ex_ante_vol;

  const styleExps = STYLE_FACTORS.map(f => ({ f, v: exposures[f] ?? 0 })).filter(x => Math.abs(x.v) > 0.01);
  const sectorExps = SECTOR_FACTORS.map(f => ({ f, v: exposures[f] ?? 0 })).filter(x => x.v > 0.01)
    .sort((a, b) => b.v - a.v).slice(0, 6);

  const styleMax = Math.max(...styleExps.map(x => Math.abs(x.v)), 0.1);
  const sectorMax = Math.max(...sectorExps.map(x => x.v), 0.1);

  // Top factor contributions (excl. specific)
  const topContribs = Object.entries(contributions)
    .filter(([k]) => k !== 'Specific')
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <div style={{ height: '100%', background: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sub-header */}
      <div style={{ padding: '6px 12px', borderBottom: '1px solid #f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          {exAnteBeta !== undefined && (
            <span style={{ fontSize: '10px', color: '#6b7280' }}>
              β <strong style={{ color: '#111827' }}>{exAnteBeta.toFixed(2)}</strong>
            </span>
          )}
          {exAnteVol !== undefined && (
            <span style={{ fontSize: '10px', color: '#6b7280' }}>
              σ <strong style={{ color: '#111827' }}>{(exAnteVol * 100).toFixed(1)}%</strong>
            </span>
          )}
          {r2 > 0 && (
            <span style={{ fontSize: '10px', color: '#6b7280' }}>
              R² <strong style={{ color: '#111827' }}>{(r2 * 100).toFixed(0)}%</strong>
            </span>
          )}
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          style={{ background: 'none', border: 'none', cursor: loading ? 'wait' : 'pointer', padding: '2px', color: '#9ca3af' }}
          title="Refresh"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div style={{ padding: '8px 12px', fontSize: '11px', color: '#dc2626', background: '#fef2f2', flexShrink: 0 }}>
          {error}
        </div>
      )}

      {loading && !data ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: '12px' }}>
          Running factor model…
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto', padding: '8px 12px' }}>

          {/* Style factors */}
          {styleExps.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>
                Style Exposures
              </div>
              {styleExps.map(({ f, v }) => (
                <ExposureBar key={f} label={f} value={v} maxAbs={styleMax} />
              ))}
            </div>
          )}

          {/* Sector weights */}
          {sectorExps.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>
                Sector Weights
              </div>
              {sectorExps.map(({ f, v }) => (
                <ExposureBar key={f} label={f} value={v} maxAbs={sectorMax} />
              ))}
            </div>
          )}

          {/* Risk decomposition */}
          {(sysP > 0 || idioP > 0) && (
            <div style={{ borderTop: '1px solid #f3f4f6', paddingTop: '8px' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
                Risk Decomposition
              </div>
              <div style={{ height: '12px', borderRadius: '6px', background: '#f3f4f6', overflow: 'hidden', marginBottom: '4px' }}>
                <div style={{ height: '100%', width: `${sysP * 100}%`, background: '#2563eb', borderRadius: '6px 0 0 6px' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#6b7280' }}>
                <span><span style={{ color: '#2563eb', fontWeight: '700' }}>{(sysP * 100).toFixed(0)}%</span> Systematic</span>
                <span><span style={{ color: '#9ca3af', fontWeight: '700' }}>{(idioP * 100).toFixed(0)}%</span> Idiosyncratic</span>
              </div>

              {topContribs.length > 0 && (
                <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  {topContribs.map(([factor, contrib]) => (
                    <div key={factor} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px' }}>
                      <span style={{ color: '#374151' }}>{factor.replace(/_/g, ' ')}</span>
                      <span style={{ fontWeight: '600', color: '#111827', fontVariantNumeric: 'tabular-nums' }}>
                        {(contrib * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {!data && !loading && (
            <div style={{ color: '#9ca3af', fontSize: '12px', textAlign: 'center', marginTop: '24px' }}>
              No data — click refresh to run analysis
            </div>
          )}
        </div>
      )}

      {lastUpdated && (
        <div style={{ padding: '4px 12px', borderTop: '1px solid #f9fafb', fontSize: '9px', color: '#d1d5db', flexShrink: 0 }}>
          Updated {lastUpdated.toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
