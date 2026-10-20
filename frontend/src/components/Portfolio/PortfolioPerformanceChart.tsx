import { useState, useEffect, useMemo } from 'react';
import Plot from 'react-plotly.js';
import { portfolioApiService, type PortfolioValueHistory, type Holding } from '@/services/portfolioApi';
import { RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';

interface PortfolioPerformanceChartProps {
  portfolioId: string;
  portfolioName: string;
}

const formatDateOnly = (isoString: string): string => {
  if (!isoString) return '';
  return isoString.split('T')[0];
};

const getHoldingQuantity = (holding: Holding): number => {
  if (holding.lots && holding.lots.length > 0) {
    return holding.lots.reduce((sum, lot) => sum + (lot.quantity || 0), 0);
  }
  return holding.quantity || 0;
};

const getEndPriceForTicker = (
  ticker: string,
  snapshot: PortfolioValueHistory,
): number => {
  const prices = snapshot.prices_snapshot;
  if (prices && typeof prices[ticker] === 'number') {
    return prices[ticker] || 0;
  }
  const holdingMatch = snapshot.holdings_snapshot?.find((h) => h.ticker === ticker);
  if (holdingMatch && typeof holdingMatch.currentPrice === 'number') {
    return holdingMatch.currentPrice || 0;
  }
  return 0;
};

const estimateNetContribution = (
  startSnapshot: PortfolioValueHistory,
  endSnapshot: PortfolioValueHistory,
): number => {
  if (!startSnapshot.holdings_snapshot || startSnapshot.holdings_snapshot.length === 0) {
    return 0;
  }

  let carryForwardValue = 0;
  startSnapshot.holdings_snapshot.forEach((holding) => {
    const quantity = getHoldingQuantity(holding);
    if (!quantity) {
      return;
    }
    const endPrice = getEndPriceForTicker(holding.ticker, endSnapshot)
      || holding.currentPrice
      || 0;
    carryForwardValue += quantity * endPrice;
  });

  return endSnapshot.total_value - carryForwardValue;
};

const buildPortfolioTwrSeries = (
  history: PortfolioValueHistory[],
): { date: string; twr: number }[] => {
  if (!history || history.length === 0) {
    return [];
  }

  const sorted = [...history].sort(
    (a, b) => new Date(a.snapshot_date).getTime() - new Date(b.snapshot_date).getTime(),
  );

  if (!sorted[0].total_value || sorted[0].total_value <= 0) {
    return [];
  }

  const series: { date: string; twr: number }[] = [
    { date: formatDateOnly(sorted[0].snapshot_date), twr: 0 },
  ];
  let index = 1;

  for (let i = 1; i < sorted.length; i += 1) {
    const startSnapshot = sorted[i - 1];
    const endSnapshot = sorted[i];
    const beginValue = startSnapshot.total_value || 0;
    if (beginValue <= 0) {
      series.push({
        date: formatDateOnly(endSnapshot.snapshot_date),
        twr: (index - 1) * 100,
      });
      continue;
    }

    const hasSnapshots =
      startSnapshot.holdings_snapshot?.length &&
      endSnapshot.holdings_snapshot?.length;

    let periodReturn: number;
    if (hasSnapshots) {
      const netContribution = estimateNetContribution(startSnapshot, endSnapshot);
      const adjustedEnding = endSnapshot.total_value - netContribution;
      periodReturn = beginValue ? (adjustedEnding - beginValue) / beginValue : 0;
    } else {
      periodReturn = (endSnapshot.total_value - beginValue) / beginValue;
    }

    index *= 1 + periodReturn;
    series.push({
      date: formatDateOnly(endSnapshot.snapshot_date),
      twr: (index - 1) * 100,
    });
  }

  return series;
};

const PortfolioPerformanceChart = ({ portfolioId, portfolioName }: PortfolioPerformanceChartProps) => {
  const [history, setHistory] = useState<PortfolioValueHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRange, setSelectedRange] = useState<number>(30);

  const timeRanges = [
    { label: '1W', days: 7 },
    { label: '1M', days: 30 },
    { label: '3M', days: 90 },
    { label: '6M', days: 180 },
    { label: '1Y', days: 365 },
  ];

  const fetchHistory = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await portfolioApiService.getValueHistory(portfolioId, selectedRange);

      // Sort by date ascending for proper chart display
      const sorted = data.sort((a, b) =>
        new Date(a.snapshot_date).getTime() - new Date(b.snapshot_date).getTime(),
      );

      setHistory(sorted);
    } catch (err: any) {
      console.error('Failed to fetch portfolio history:', err);
      setError(err.message || 'Failed to load performance data');
      toast.error('Failed to load performance data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [portfolioId, selectedRange]);

  const twrSeries = useMemo(() => buildPortfolioTwrSeries(history), [history]);
  const finalTwr = twrSeries.length > 0 ? twrSeries[twrSeries.length - 1].twr : null;

  // Calculate performance metrics
  const metrics = useMemo(() => {
    if (history.length < 2) return null;

    const firstValue = history[0].total_value;
    const lastValue = history[history.length - 1].total_value;
    const change = lastValue - firstValue;
    const changePercent = (change / firstValue) * 100;

    return {
      currentValue: lastValue,
      startValue: firstValue,
      change,
      changePercent,
      isPositive: change >= 0,
    };
  }, [history]);

  // Prepare chart data
  const chartData = useMemo(() => {
    if (history.length === 0) return [];

    const dates = history.map(h => h.snapshot_date);
    const values = history.map(h => h.total_value);

    return [{
      x: dates,
      y: values,
      type: 'scatter' as const,
      mode: history.length === 1 ? 'markers' as const : 'lines' as const,
      name: portfolioName,
      line: {
        color: '#2563eb', // Institutional Blue
        width: 2,
        shape: 'spline' as const,
        smoothing: 0.5,
      },
      fill: 'tozeroy' as const,
      fillcolor: 'rgba(37, 99, 235, 0.05)', // Subtle Blue Fade
      hovertemplate: '<b>%{x|%b %d, %Y}</b><br>' +
                     '$%{y:,.2f}<br>' +
                     '<extra></extra>',
    }];
  }, [history, portfolioName, metrics]);

  const layout = {
    autosize: true,
    height: 340,
    margin: { l: 60, r: 20, t: 20, b: 40 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    xaxis: {
      showgrid: false,
      zeroline: false,
      showline: true,
      linewidth: 1,
      linecolor: '#e5e7eb',
      type: 'date' as const,
      tickfont: {
        size: 11,
        color: '#6b7280',
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      tickformat: '%b %d',
      hoverformat: '%B %d, %Y',
    },
    yaxis: {
      showgrid: true,
      gridcolor: '#f3f4f6',
      gridwidth: 1,
      zeroline: false,
      showline: false,
      tickformat: '$,.0f', // Standard currency format
      tickfont: {
        size: 11,
        color: '#6b7280',
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      fixedrange: false,
    },
    hovermode: 'x unified' as const,
    hoverlabel: {
      bgcolor: '#1f2937',
      bordercolor: 'transparent',
      font: {
        size: 13,
        color: '#FFFFFF',
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
    },
    showlegend: false,
  };

  const config = {
    displayModeBar: false,
    responsive: true,
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 mb-6 h-[400px] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="h-6 w-6 text-gray-400 animate-spin" />
          <span className="text-sm text-gray-500 font-medium">Loading performance data...</span>
        </div>
      </div>
    );
  }

  if (error || history.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 mb-6 h-[400px] flex flex-col items-center justify-center gap-4">
        <div className="bg-gray-50 rounded-full p-3">
          <RefreshCw className="h-6 w-6 text-gray-400" />
        </div>
        <span className="text-sm text-gray-500 font-medium">
          {error || 'No performance data available yet'}
        </span>
        <button
          onClick={fetchHistory}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm mb-6 overflow-hidden">
      {/* Modern Header */}
      <div className="px-6 py-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Portfolio Value</h3>
          {metrics && (
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-bold text-gray-900 tracking-tight">
                ${metrics.currentValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <div className={`flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium ${
                metrics.isPositive ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
              }`}>
                {metrics.isPositive ? '+' : ''}{metrics.changePercent.toFixed(2)}%
              </div>
            </div>
          )}
        </div>

        {/* Segmented Control Style Time Selector */}
        <div className="flex bg-gray-100/80 p-1 rounded-lg self-start sm:self-center">
          {timeRanges.map(range => (
            <button
              key={range.days}
              onClick={() => setSelectedRange(range.days)}
              className={`
                px-3 py-1.5 text-xs font-semibold rounded-md transition-all duration-200 ease-out
                ${selectedRange === range.days
                  ? 'bg-white text-gray-900 shadow-sm ring-1 ring-black/5'
                  : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'
                }
              `}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Area */}
      <div className="w-full">
        <Plot
          data={chartData}
          layout={layout}
          config={config}
          style={{ width: '100%', height: '340px' }}
          useResizeHandler={true}
        />
      </div>
    </div>
  );
};

export default PortfolioPerformanceChart;
