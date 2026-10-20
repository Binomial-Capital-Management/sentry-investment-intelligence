import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { usePortfolioStore } from '@stores/portfolioStore';
import TransactionHistoryTab from './TransactionHistoryTab';

const PortfolioTransactionsPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { savedPortfolios } = usePortfolioStore();

  const portfolio = savedPortfolios.find(p => p.id === id);

  if (!portfolio) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      }}>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
            Portfolio not found
          </h2>
          <button
            onClick={() => navigate('/portfolio')}
            style={{
              padding: '8px 16px',
              background: '#3B82F6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            Back to Portfolios
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      padding: '24px',
      maxWidth: '1400px',
      margin: '0 auto',
    }}>
      {/* Header with breadcrumb */}
      <div style={{ marginBottom: '24px' }}>
        <button
          onClick={() => navigate(`/portfolio/${id}`)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            background: 'transparent',
            border: '1px solid #E5E7EB',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '14px',
            color: '#6B7280',
            marginBottom: '16px',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#F3F4F6';
            e.currentTarget.style.borderColor = '#D1D5DB';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.borderColor = '#E5E7EB';
          }}
        >
          <ArrowLeft size={16} />
          Back to {portfolio.name}
        </button>

        <h1 style={{
          fontSize: '28px',
          fontWeight: '700',
          color: '#1F2937',
          marginBottom: '8px',
        }}>
          Transaction History
        </h1>
        <p style={{ fontSize: '14px', color: '#6B7280' }}>
          {portfolio.name} • Complete transaction audit trail
        </p>
      </div>

      {/* Transaction History Component */}
      <div style={{
        background: 'white',
        borderRadius: '8px',
        border: '1px solid #E5E7EB',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
      }}>
        <TransactionHistoryTab portfolioId={id!} />
      </div>
    </div>
  );
};

export default PortfolioTransactionsPage;
