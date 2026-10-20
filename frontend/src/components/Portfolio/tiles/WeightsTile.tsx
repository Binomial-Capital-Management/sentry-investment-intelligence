import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';

export default function WeightsTile() {
  const { portfolio, holdings, totalWeight, totalValue, holdingsValue } = usePortfolioDetail();

  const cashBalance = Number(portfolio?.cash_balance || 0);
  const cashPct = totalValue > 0 ? (cashBalance / totalValue) * 100 : 0;
  const holdingsPct = totalValue > 0 ? (holdingsValue / totalValue) * 100 : 0;
  const avgWeight = holdings.length > 0 ? holdingsPct / holdings.length : 0;

  const metrics = [
    { label: 'Weight Balance', value: `${(totalWeight * 100).toFixed(1)}%`, sub: Math.abs(totalWeight - 1.0) < 0.001 ? 'Fully invested' : cashPct > 1 ? `${cashPct.toFixed(1)}% cash` : 'Needs rebalancing', color: Math.abs(totalWeight - 1.0) < 0.001 ? '#059669' : '#f59e0b' },
    { label: 'Avg Weight', value: `${avgWeight.toFixed(1)}%`, sub: `Per position (${holdings.length})`, color: '#3b82f6' },
    { label: 'Cash', value: `$${cashBalance >= 1000 ? (cashBalance / 1000).toFixed(1) + 'K' : cashBalance.toFixed(0)}`, sub: `${cashPct.toFixed(1)}% of portfolio`, color: '#8b5cf6' },
    { label: 'Holdings Value', value: `$${holdingsValue >= 1e6 ? (holdingsValue / 1e6).toFixed(2) + 'M' : (holdingsValue / 1000).toFixed(1) + 'K'}`, sub: `${holdingsPct.toFixed(1)}% of portfolio`, color: '#10b981' },
  ];

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#fff' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', background: '#e5e7eb', height: '100%' }}>
        {metrics.map((m) => (
          <div key={m.label} style={{ background: '#fff', padding: '14px 16px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ fontSize: '10px', color: '#9ca3af', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
              {m.label}
            </div>
            <div style={{ fontSize: '20px', fontWeight: '700', color: '#111827', fontVariantNumeric: 'tabular-nums' }}>
              {m.value}
            </div>
            <div style={{ fontSize: '10px', color: '#9ca3af', marginTop: '3px' }}>
              {m.sub}
            </div>
          </div>
        ))}
      </div>
      {portfolio.updated_at && (
        <div style={{ padding: '6px 16px', borderTop: '1px solid #e5e7eb', fontSize: '10px', color: '#9ca3af', textAlign: 'center', background: '#fafafa' }}>
          Updated {new Date(portfolio.updated_at).toLocaleDateString()}
        </div>
      )}
    </div>
  );
}
