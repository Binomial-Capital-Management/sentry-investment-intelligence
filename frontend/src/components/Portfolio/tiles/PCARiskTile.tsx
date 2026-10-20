import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';
import { useFactorAnalysis } from '../hooks/useFactorAnalysis';
import type { PcaComponent } from '../hooks/useFactorAnalysis';

const COLORS = ['#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626', '#0891b2', '#be185d', '#65a30d'];

function ScreeBar({ pc, varExp, cumulative, maxVar, isSelected, onClick }: {
  pc: number; varExp: number; cumulative: number; maxVar: number;
  isSelected: boolean; onClick: () => void;
}) {
  const height = maxVar > 0 ? (varExp / maxVar) * 100 : 0;
  return (
    <div
      onClick={onClick}
      title={`PC${pc}: ${(varExp * 100).toFixed(1)}% explained (cumulative: ${(cumulative * 100).toFixed(1)}%)`}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px', cursor: 'pointer', flex: 1 }}
    >
      <div style={{ width: '100%', height: '60px', display: 'flex', alignItems: 'flex-end', justifyContent: 'center' }}>
        <div style={{
          width: '80%',
          height: `${height}%`,
          minHeight: '2px',
          background: isSelected ? (COLORS[pc - 1] ?? '#2563eb') : '#e5e7eb',
          borderRadius: '2px 2px 0 0',
          transition: 'background 0.15s',
        }} />
      </div>
      <span style={{ fontSize: '9px', color: isSelected ? '#374151' : '#9ca3af', fontWeight: isSelected ? '700' : '400' }}>
        PC{pc}
      </span>
    </div>
  );
}

export default function PCARiskTile() {
  const { portfolio } = usePortfolioDetail();
  const { data, loading, error, refresh, lastUpdated } = useFactorAnalysis(portfolio?.id);
  const [selectedPc, setSelectedPc] = useState(1);

  const pca = data?.pca;
  const components = pca?.components ?? [];
  const n80 = pca?.n_components_80pct ?? 0;

  const displayComponents = components.slice(0, 8);
  const maxVar = Math.max(...displayComponents.map(c => c.variance_explained), 0.01);
  const selected: PcaComponent | undefined = displayComponents.find(c => c.pc === selectedPc);

  return (
    <div style={{ height: '100%', background: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sub-header */}
      <div style={{ padding: '6px 12px', borderBottom: '1px solid #f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {n80 > 0 && (
            <span style={{ fontSize: '10px', color: '#6b7280' }}>
              <strong style={{ color: '#111827' }}>{n80}</strong> PCs explain 80%
            </span>
          )}
          {data?.n_assets && (
            <span style={{ fontSize: '10px', color: '#9ca3af' }}>{data.n_assets} assets</span>
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
          Running PCA…
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>

          {/* Scree plot */}
          {displayComponents.length > 0 && (
            <div>
              <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
                Variance Explained — click a bar to inspect
              </div>
              <div style={{ display: 'flex', gap: '2px', alignItems: 'flex-end' }}>
                {displayComponents.map(c => (
                  <ScreeBar
                    key={c.pc}
                    pc={c.pc}
                    varExp={c.variance_explained}
                    cumulative={c.cumulative}
                    maxVar={maxVar}
                    isSelected={c.pc === selectedPc}
                    onClick={() => setSelectedPc(c.pc)}
                  />
                ))}
              </div>
              <div style={{ display: 'flex', gap: '2px', marginTop: '2px' }}>
                {displayComponents.map(c => (
                  <div key={c.pc} style={{ flex: 1, textAlign: 'center', fontSize: '8px', color: '#9ca3af' }}>
                    {(c.variance_explained * 100).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Selected PC detail */}
          {selected && (
            <div style={{ borderTop: '1px solid #f3f4f6', paddingTop: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <div style={{ fontSize: '9px', fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  PC{selected.pc} Top Loadings
                </div>
                <div style={{ fontSize: '10px', color: '#6b7280' }}>
                  Portfolio exp: <strong style={{ color: '#111827' }}>{selected.portfolio_exposure.toFixed(3)}</strong>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                {selected.top_loadings.map((l, i) => {
                  const pct = Math.min(Math.abs(l.loading) * 400, 100);
                  const isPos = l.loading >= 0;
                  return (
                    <div key={l.ticker} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '44px', fontSize: '10px', fontWeight: '600', color: '#374151', textAlign: 'right' }}>{l.ticker}</span>
                      <div style={{ flex: 1, height: '10px', background: '#f3f4f6', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{
                          height: '100%',
                          width: `${pct}%`,
                          background: isPos ? (COLORS[i % COLORS.length] ?? '#2563eb') : '#ef4444',
                          borderRadius: '3px',
                          opacity: 0.8,
                        }} />
                      </div>
                      <span style={{ width: '48px', fontSize: '10px', fontWeight: '600', color: isPos ? '#374151' : '#ef4444', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                        {l.loading.toFixed(3)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {!data && !loading && (
            <div style={{ color: '#9ca3af', fontSize: '12px', textAlign: 'center', marginTop: '24px' }}>
              No data — click refresh to run PCA
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
