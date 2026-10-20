import PortfolioPerformanceChart from '../PortfolioPerformanceChart';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';

export default function PerformanceTile() {
  const { portfolio } = usePortfolioDetail();

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#fff', padding: '8px' }}>
      <PortfolioPerformanceChart
        portfolioId={portfolio.id}
        portfolioName={portfolio.name}
      />
    </div>
  );
}
