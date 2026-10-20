import { useNavigate, useParams } from 'react-router-dom';
import { usePortfolioStore } from '@stores/portfolioStore';
import { Star } from 'lucide-react';

export default function PortfolioListTile() {
  const navigate = useNavigate();
  const { id: currentId } = useParams<{ id: string }>();
  const { savedPortfolios = [] } = usePortfolioStore();

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#fff' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb', background: '#f9fafb' }}>
        <span style={{ fontSize: '11px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          All Portfolios ({savedPortfolios.length})
        </span>
      </div>
      <div>
        {savedPortfolios.map((p) => (
          <button
            key={p.id}
            onClick={() => navigate(`/portfolio/${p.id}`)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 16px',
              border: 'none',
              borderBottom: '1px solid #f3f4f6',
              background: p.id === currentId ? '#eff6ff' : 'transparent',
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { if (p.id !== currentId) e.currentTarget.style.background = '#f9fafb'; }}
            onMouseLeave={(e) => { if (p.id !== currentId) e.currentTarget.style.background = 'transparent'; }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {p.is_default && <Star size={12} style={{ color: '#f59e0b', fill: '#f59e0b' }} />}
              <span style={{
                fontSize: '13px',
                fontWeight: p.id === currentId ? '600' : '500',
                color: p.id === currentId ? '#2563eb' : '#374151',
              }}>
                {p.name}
              </span>
            </div>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>
              {p.tickers?.length || 0} pos
            </span>
          </button>
        ))}
        {savedPortfolios.length === 0 && (
          <div style={{ padding: '24px 16px', textAlign: 'center', color: '#9ca3af', fontSize: '13px' }}>
            No portfolios yet
          </div>
        )}
      </div>
    </div>
  );
}
