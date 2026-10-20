import ChartFrame from './ChartFrame';
import type { ChartData } from '@/types';

interface PlotlyChartProps {
  chart: ChartData;
}

const PlotlyChart = ({ chart }: PlotlyChartProps) => {
  // Extract KPIs from chart data if available
  const kpis = chart.kpis || [];

  return (
    <ChartFrame
      chart={chart}
      title={chart.title || 'Analysis'}
      kpis={kpis}
    />
  );
};

export default PlotlyChart;
