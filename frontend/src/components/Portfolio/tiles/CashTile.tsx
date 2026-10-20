import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';

export default function CashTile() {
  const { portfolio, setShowCashModal, totalValue } = usePortfolioDetail();

  const cash = Number(portfolio?.cash_balance || 0);
  const cashPct = totalValue > 0 ? (cash / totalValue) * 100 : 0;
  const hasByCurrency = portfolio?.metadata?.cash_by_currency &&
    Object.keys(portfolio.metadata.cash_by_currency).length > 0;

  return (
    <div style={{ height: '100%', background: '#fff', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 1, padding: '16px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '30px', fontWeight: '700', color: '#111827', fontVariantNumeric: 'tabular-nums', marginBottom: '4px' }}>
            ${cash >= 1e6 ? (cash / 1e6).toFixed(2) + 'M' : cash >= 1000 ? (cash / 1000).toFixed(1) + 'K' : cash.toFixed(0)}
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af', marginBottom: '16px' }}>
            {cashPct.toFixed(1)}% of portfolio
          </div>

          {hasByCurrency && (
            <div style={{ borderTop: '1px solid #f3f4f6', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {Object.entries(portfolio.metadata!.cash_by_currency!).map(([currency, amount]) => (
                <div key={currency} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '12px', color: '#6b7280', fontWeight: '500' }}>{currency}</span>
                  <span style={{ fontSize: '13px', fontWeight: '600', color: '#111827', fontVariantNumeric: 'tabular-nums' }}>
                    ${Number(amount).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={() => setShowCashModal(true)}
          style={{
            width: '100%',
            padding: '8px 12px',
            fontSize: '12px',
            fontWeight: '600',
            background: '#f3f4f6',
            color: '#374151',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            cursor: 'pointer',
            fontFamily: 'inherit',
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#e5e7eb'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = '#f3f4f6'; }}
        >
          Manage Cash
        </button>
      </div>
    </div>
  );
}
