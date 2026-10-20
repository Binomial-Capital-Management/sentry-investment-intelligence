import { useNavigate } from 'react-router-dom';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';

export default function SummaryTile() {
  const navigate = useNavigate();
  const { totalValue, holdingsValue, holdings, totalWeight, portfolio } = usePortfolioDetail();

  const cash = Number(portfolio?.cash_balance || 0);
  const cashPct = totalValue > 0 ? (cash / totalValue) * 100 : 0;
  const investedPct = totalValue > 0 ? (holdingsValue / totalValue) * 100 : 0;
  const balanced = Math.abs(totalWeight - 1.0) < 0.01;

  const fmtValue = (v: number) => {
    if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
    if (v >= 1000) return `$${(v / 1000).toFixed(1)}K`;
    return `$${v.toFixed(0)}`;
  };

  return (
    <div style={{ height: '100%', background: '#fff', display: 'flex', flexDirection: 'column' }}>
      {/* Big number */}
      <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid #f3f4f6' }}>
        <div style={{ fontSize: '28px', fontWeight: '700', color: '#111827', fontVariantNumeric: 'tabular-nums' }}>
          {fmtValue(totalValue)}
        </div>
        <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>Total Portfolio Value</div>
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', flex: 1 }}>
        <StatCell label="Positions" value={String(holdings.length)} />
        <StatCell label="Invested" value={`${investedPct.toFixed(0)}%`} />
        <StatCell label="Cash" value={fmtValue(cash)} sub={`${cashPct.toFixed(1)}%`} />
        <StatCell
          label="Status"
          value={balanced ? 'Balanced' : 'Review'}
          valueColor={balanced ? '#059669' : '#f59e0b'}
        />
      </div>

      {/* Links */}
      <div style={{ padding: '10px 16px', borderTop: '1px solid #f3f4f6', display: 'flex', gap: '8px' }}>
        <button
          onClick={() => navigate('/portfolio')}
          style={{ flex: 1, padding: '6px', fontSize: '11px', fontWeight: '500', background: 'none', border: '1px solid #e5e7eb', borderRadius: '5px', cursor: 'pointer', color: '#6b7280', fontFamily: 'inherit' }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#f9fafb'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'none'; }}
        >
          All Portfolios
        </button>
        {portfolio.is_default && (
          <div style={{ display: 'flex', alignItems: 'center', fontSize: '10px', color: '#059669', fontWeight: '600', padding: '0 8px', background: '#ecfdf5', borderRadius: '5px', border: '1px solid #d1fae5' }}>
            DEFAULT
          </div>
        )}
      </div>
    </div>
  );
}

function StatCell({ label, value, sub, valueColor }: { label: string; value: string; sub?: string; valueColor?: string }) {
  return (
    <div style={{ padding: '12px', borderRight: '1px solid #f3f4f6', borderBottom: '1px solid #f3f4f6' }}>
      <div style={{ fontSize: '10px', color: '#9ca3af', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
        {label}
      </div>
      <div style={{ fontSize: '17px', fontWeight: '700', color: valueColor || '#111827', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '10px', color: '#9ca3af', marginTop: '1px' }}>{sub}</div>}
    </div>
  );
}
