import { RefreshCw, AlertTriangle } from 'lucide-react';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';
import { useFactorAnalysis } from '../hooks/useFactorAnalysis';

function Metric({
  label, value, color, small,
}: { label: string; value: string; color?: string; small?: boolean }) {
  return (
    <div style={{ background: '#fff', padding: small ? '8px 12px' : '11px 12px', display: 'flex', flexDirection: 'column' }}>
      <div style={{ fontSize: '9px', color: '#9ca3af', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '3px' }}>
        {label}
      </div>
      <div style={{ fontSize: small ? '13px' : '17px', fontWeight: '700', color: color ?? '#111827', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
    </div>
  );
}

export default function RiskAnalyticsTile() {
  const { portfolio, holdings } = usePortfolioDetail();
  const { data, loading, error, refresh, lastUpdated } = useFactorAnalysis(portfolio?.id);

  const fmtPct = (v: number | undefined) =>
    v === undefined || isNaN(v) ? '–' : `${(v * 100).toFixed(1)}%`;

  const fmtDollar = (v: number | undefined) => {
    if (v === undefined || isNaN(v)) return '–';
    if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
    if (v >= 1000) return `$${(v / 1000).toFixed(1)}K`;
    return `$${v.toFixed(0)}`;
  };

  const fmtNum = (v: number | undefined, dp = 2) =>
    v === undefined || isNaN(v) ? '–' : v.toFixed(dp);

  if (holdings.length < 2) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff', padding: '24px', textAlign: 'center' }}>
        <div>
          <AlertTriangle size={20} style={{ color: '#f59e0b', marginBottom: '8px' }} />
          <div style={{ fontSize: '13px', color: '#6b7280' }}>Add at least 2 positions</div>
        </div>
      </div>
    );
  }

  const v = data?.var;
  const b = data?.barra;

  const var95pct = v?.historical_95?.pct;
  const var95dollar = v?.historical_95?.dollar;
  const var99pct = v?.historical_99?.pct;
  const cvar95pct = v?.cvar_95?.pct;
  const annVol = v?.annual_vol;
  const sharpe = v?.sharpe_est;
  const skew = v?.skewness;
  const kurt = v?.kurtosis;
  const beta = b?.ex_ante_beta;
  const factorVol = b?.factor_risk;
  const specificVol = b?.specific_risk;
  const r2 = b?.mean_r_squared;

  return (
    <div style={{ height: '100%', background: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sub-header */}
      <div style={{ padding: '5px 12px', borderBottom: '1px solid #f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <span style={{ fontSize: '10px', color: '#9ca3af' }}>
          {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Click refresh to compute'}
        </span>
        <button
          onClick={refresh}
          disabled={loading}
          style={{ background: 'none', border: 'none', cursor: loading ? 'wait' : 'pointer', padding: '2px', color: '#9ca3af' }}
          title="Refresh risk metrics"
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
          Running factor analysis…
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto' }}>
          {/* Primary 2×2 grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', background: '#e5e7eb' }}>
            <Metric label="Ex Ante Beta" value={fmtNum(beta)} color={beta !== undefined ? (beta > 1.3 ? '#dc2626' : beta < 0.7 ? '#059669' : '#111827') : undefined} />
            <Metric label="Annual Vol" value={fmtPct(annVol)} />
            <Metric label="VaR (95%)" value={var95pct !== undefined ? `${fmtPct(var95pct)} · ${fmtDollar(var95dollar)}` : '–'} color="#dc2626" />
            <Metric label="CVaR (95%)" value={fmtPct(cvar95pct)} color="#dc2626" />
          </div>

          {/* Secondary row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1px', background: '#e5e7eb', borderTop: '1px solid #e5e7eb' }}>
            <Metric label="VaR (99%)" value={fmtPct(var99pct)} color="#dc2626" small />
            <Metric label="Sharpe" value={fmtNum(sharpe)} small />
            <Metric label="R²" value={r2 !== undefined ? `${(r2 * 100).toFixed(0)}%` : '–'} small />
          </div>

          {/* Distribution row */}
          {(skew !== undefined || kurt !== undefined) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', background: '#e5e7eb', borderTop: '1px solid #e5e7eb' }}>
              <Metric label="Skewness" value={fmtNum(skew, 3)} color={skew !== undefined && skew < -0.5 ? '#f59e0b' : undefined} small />
              <Metric label="Kurtosis" value={fmtNum(kurt, 2)} small />
            </div>
          )}

          {/* Factor vs specific risk */}
          {(factorVol !== undefined && specificVol !== undefined) && (
            <div style={{ padding: '10px 12px', borderTop: '1px solid #f3f4f6' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
                Risk Sources
              </div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <div>
                  <div style={{ fontSize: '9px', color: '#9ca3af' }}>Factor</div>
                  <div style={{ fontSize: '14px', fontWeight: '700', color: '#2563eb', fontVariantNumeric: 'tabular-nums' }}>{fmtPct(factorVol)}</div>
                </div>
                <div>
                  <div style={{ fontSize: '9px', color: '#9ca3af' }}>Specific</div>
                  <div style={{ fontSize: '14px', fontWeight: '700', color: '#7c3aed', fontVariantNumeric: 'tabular-nums' }}>{fmtPct(specificVol)}</div>
                </div>
              </div>
            </div>
          )}

          {!data && !loading && (
            <div style={{ padding: '24px', color: '#9ca3af', fontSize: '12px', textAlign: 'center' }}>
              No data yet — click refresh above to run analysis
            </div>
          )}
        </div>
      )}
    </div>
  );
}
