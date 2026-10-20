import { RefreshCw } from 'lucide-react';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';
import { useFactorAnalysis } from '../hooks/useFactorAnalysis';
import type { TiltEntry } from '../hooks/useFactorAnalysis';

const STYLE_ORDER = ['Momentum', 'Size', 'Value', 'Quality', 'Volatility', 'Beta'];

function TiltBar({ factor, tilt }: { factor: string; tilt: TiltEntry }) {
  const active = tilt.active;
  const maxBar = 2.0;
  const pct = Math.min(Math.abs(active) / maxBar, 1) * 100;
  const isPos = active >= 0;

  const color = isPos ? '#059669' : '#dc2626';
  const label = factor.replace(/_/g, ' ');

  return (
    <div style={{ padding: '4px 0', borderBottom: '1px solid #f9fafb' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
        <span style={{ fontSize: '11px', fontWeight: '600', color: '#374151' }}>{label}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '10px', color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>
            {tilt.portfolio.toFixed(2)} vs {tilt.benchmark.toFixed(2)}
          </span>
          <span style={{
            fontSize: '11px', fontWeight: '700', color,
            fontVariantNumeric: 'tabular-nums', width: '44px', textAlign: 'right',
          }}>
            {isPos ? '+' : ''}{active.toFixed(2)}
          </span>
        </div>
      </div>
      {/* Diverging bar centered at 0 */}
      <div style={{ position: 'relative', height: '8px', background: '#f3f4f6', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{
          position: 'absolute',
          top: 0,
          height: '100%',
          width: `${pct / 2}%`,
          background: color,
          borderRadius: '4px',
          left: isPos ? '50%' : 'auto',
          right: isPos ? 'auto' : '50%',
          opacity: 0.85,
          transition: 'width 0.3s',
        }} />
        {/* Center line */}
        <div style={{ position: 'absolute', left: '50%', top: 0, width: '1px', height: '100%', background: '#d1d5db' }} />
      </div>
    </div>
  );
}

export default function FactorTiltsTile() {
  const { portfolio } = usePortfolioDetail();
  const { data, loading, error, refresh, lastUpdated } = useFactorAnalysis(portfolio?.id);

  const tilts = data?.tilts;
  const activeTilts = tilts?.active_tilts ?? {};
  const benchmark = tilts?.benchmark ?? 'SPY';
  const te = tilts?.tracking_error_est;
  const afr = tilts?.active_factor_risk;

  // Sort: style factors first in defined order, then sectors
  const styleTilts = STYLE_ORDER
    .filter(f => f in activeTilts)
    .map(f => ({ factor: f, tilt: activeTilts[f] }));

  const sectorTilts = Object.entries(activeTilts)
    .filter(([k]) => !STYLE_ORDER.includes(k))
    .sort(([, a], [, b]) => Math.abs(b.active) - Math.abs(a.active))
    .map(([k, v]) => ({ factor: k, tilt: v }));

  return (
    <div style={{ height: '100%', background: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sub-header */}
      <div style={{ padding: '6px 12px', borderBottom: '1px solid #f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <span style={{ fontSize: '10px', color: '#6b7280' }}>
          Active tilts vs <strong style={{ color: '#111827' }}>{benchmark}</strong>
        </span>
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
          Computing tilts…
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto', padding: '6px 12px' }}>

          {/* Axis hint */}
          {styleTilts.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={{ fontSize: '8px', color: '#ef4444' }}>◀ Under-weight</span>
              <span style={{ fontSize: '8px', color: '#9ca3af' }}>Active Tilt</span>
              <span style={{ fontSize: '8px', color: '#059669' }}>Over-weight ▶</span>
            </div>
          )}

          {/* Style factor tilts */}
          {styleTilts.length > 0 && (
            <div style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>
                Style
              </div>
              {styleTilts.map(({ factor, tilt }) => (
                <TiltBar key={factor} factor={factor} tilt={tilt} />
              ))}
            </div>
          )}

          {/* Sector tilts */}
          {sectorTilts.length > 0 && (
            <div>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>
                Sector
              </div>
              {sectorTilts.map(({ factor, tilt }) => (
                <TiltBar key={factor} factor={factor} tilt={tilt} />
              ))}
            </div>
          )}

          {!data && !loading && (
            <div style={{ color: '#9ca3af', fontSize: '12px', textAlign: 'center', marginTop: '24px' }}>
              No data — click refresh
            </div>
          )}
        </div>
      )}

      {/* Footer stats */}
      {(te !== undefined || afr !== undefined) && (
        <div style={{ padding: '6px 12px', borderTop: '1px solid #f3f4f6', display: 'flex', gap: '16px', flexShrink: 0 }}>
          {te !== undefined && (
            <div>
              <div style={{ fontSize: '9px', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Tracking Error Est.</div>
              <div style={{ fontSize: '13px', fontWeight: '700', color: '#111827', fontVariantNumeric: 'tabular-nums' }}>
                {(te * 100).toFixed(1)}%
              </div>
            </div>
          )}
          {afr !== undefined && (
            <div>
              <div style={{ fontSize: '9px', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Active Factor Risk</div>
              <div style={{ fontSize: '13px', fontWeight: '700', color: '#111827', fontVariantNumeric: 'tabular-nums' }}>
                {(afr * 100).toFixed(1)}%
              </div>
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
