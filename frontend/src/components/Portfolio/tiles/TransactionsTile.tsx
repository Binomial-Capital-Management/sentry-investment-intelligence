import TransactionHistoryTab from '../TransactionHistoryTab';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';

export default function TransactionsTile() {
  const { portfolio } = usePortfolioDetail();

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#fff', padding: '16px' }}>
      <TransactionHistoryTab portfolioId={portfolio.id} />
    </div>
  );
}
