import { usePostMortemDetail } from '../mosaic/PostMortemDetailContext';

export default function MetricsTile() {
  const { metrics, formatCurrency } = usePostMortemDetail();

  if (!metrics) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: '13px' }}>
        No metrics available
      </div>
    );
  }

  const cards = [
    { label: 'Total P&L',    value: `${metrics.totalPnL >= 0 ? '+' : ''}${formatCurrency(metrics.totalPnL)}`, color: metrics.totalPnL >= 0 ? '#107C10' : '#A4262C' },
    { label: 'Total Trades', value: String(metrics.totalTrades), color: '#323130' },
    { label: 'Wins',         value: String(metrics.wins),        color: '#107C10' },
    { label: 'Losses',       value: String(metrics.losses),      color: '#A4262C' },
    { label: 'Win Rate',     value: `${metrics.winRate.toFixed(1)}%`, color: '#323130' },
  ];

  return (
    <div style={{ height: '100%', padding: '12px 16px', display: 'flex', gap: '12px', alignItems: 'stretch', overflow: 'auto' }}>
      {cards.map((c) => (
        <div key={c.label} style={{
          flex: 1, minWidth: '100px',
          background: '#fff', borderRadius: '10px',
          border: '1px solid #E1DFDD',
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
          padding: '14px 16px',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        }}>
          <p style={{ fontSize: '10px', fontWeight: '700', color: '#605E5C', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
            {c.label}
          </p>
          <p style={{ fontSize: '22px', fontWeight: '700', color: c.color, margin: '6px 0 0', letterSpacing: '-0.5px' }}>
            {c.value}
          </p>
          {c.label === 'Win Rate' && (
            <div style={{ height: '3px', background: '#f3f4f6', borderRadius: '2px', marginTop: '6px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${metrics.winRate}%`, background: '#0078D4', borderRadius: '2px' }} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
