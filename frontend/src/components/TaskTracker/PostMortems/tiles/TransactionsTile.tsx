import { usePostMortemDetail } from '../mosaic/PostMortemDetailContext';

export default function TransactionsTile() {
  const { postmortem, formatCurrency, formatDate } = usePostMortemDetail();

  if (!postmortem || postmortem.transactions.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: '13px' }}>
        No transactions attached
      </div>
    );
  }

  const thStyle: React.CSSProperties = {
    padding: '10px 14px', fontSize: '10px', fontWeight: '700',
    color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.06em',
    textAlign: 'left', whiteSpace: 'nowrap', position: 'sticky', top: 0,
    background: '#f9fafb', borderBottom: '1px solid #e5e7eb',
  };

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
        <thead>
          <tr>
            {['Portfolio','Date','Ticker','Type','Qty','Price','Value','Realized'].map(h => (
              <th key={h} style={{ ...thStyle, textAlign: h === 'Qty' || h === 'Price' || h === 'Value' || h === 'Realized' ? 'right' : 'left' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {postmortem.transactions.map((tx) => {
            const isBuy = tx.transaction_type === 'BUY';
            return (
              <tr key={tx.id} style={{ borderBottom: '1px solid #f3f4f6', transition: 'background 0.1s' }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = '#f9fafb'; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = ''; }}
              >
                <td style={{ padding: '10px 14px', fontWeight: '500', color: '#111827', whiteSpace: 'nowrap' }}>{tx.portfolio_name}</td>
                <td style={{ padding: '10px 14px', color: '#6b7280', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{formatDate(tx.transaction_date)}</td>
                <td style={{ padding: '10px 14px', fontWeight: '700', color: '#111827' }}>{tx.ticker}</td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{
                    fontSize: '9px', fontWeight: '700', textTransform: 'uppercase',
                    padding: '2px 6px', borderRadius: '4px',
                    background: isBuy ? '#f3f4f6' : '#ecfdf5',
                    color: isBuy ? '#374151' : '#059669',
                    border: `1px solid ${isBuy ? '#e5e7eb' : '#a7f3d0'}`,
                  }}>{isBuy ? 'BUY' : 'SELL'}</span>
                </td>
                <td style={{ padding: '10px 14px', textAlign: 'right', fontFamily: 'monospace', color: '#111827' }}>{tx.quantity.toLocaleString()}</td>
                <td style={{ padding: '10px 14px', textAlign: 'right', fontFamily: 'monospace', color: '#111827' }}>{formatCurrency(tx.price)}</td>
                <td style={{ padding: '10px 14px', textAlign: 'right', fontFamily: 'monospace', color: '#111827' }}>
                  {isBuy ? '-' : '+'}{formatCurrency(Math.abs(tx.total_amount))}
                </td>
                <td style={{ padding: '10px 14px', textAlign: 'right', fontFamily: 'monospace' }}>
                  {tx.realized_gain_loss != null ? (
                    <span style={{ color: tx.realized_gain_loss >= 0 ? '#059669' : '#dc2626', fontWeight: '600' }}>
                      {tx.realized_gain_loss >= 0 ? '+' : ''}{formatCurrency(tx.realized_gain_loss)}
                    </span>
                  ) : <span style={{ color: '#9ca3af' }}>—</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
