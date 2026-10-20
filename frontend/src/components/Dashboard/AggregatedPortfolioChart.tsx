import { useState, useEffect, useMemo } from 'react';
import Plot from 'react-plotly.js';
import { portfolioApiService, type PortfolioValueHistory, type Holding } from '@/services/portfolioApi';
import { RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';

interface AggregatedDataPoint {
  date: string;
  totalValue: number;
}

interface NormalizedHistoryPoint {
  date: string;
  value: number;
}

interface PortfolioTwrPoint {
  date: string;
  index: number;
}

interface AggregatedTwrPoint {
  date: string;
  twr: number;
}

const formatDateOnly = (isoString: string): string => {
  if (!isoString) return '';
  return isoString.split('T')[0];
};

const buildTimelineDates = (days: number): string[] => {
  if (days <= 0) return [];
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  const start = new Date(today);
  start.setUTCDate(start.getUTCDate() - Math.max(days - 1, 0));

  const dates: string[] = [];
  const cursor = new Date(start);
  while (cursor <= today) {
    dates.push(formatDateOnly(cursor.toISOString()));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return dates;
};

const aggregateHistories = (
  histories: NormalizedHistoryPoint[][],
  selectedRange: number,
): AggregatedDataPoint[] => {
  if (histories.length === 0) return [];

  const timelineDates = buildTimelineDates(selectedRange);
  if (timelineDates.length === 0) return [];

  const pointerState = histories.map(() => ({ index: -1, lastValue: 0 }));
  const aggregated: AggregatedDataPoint[] = [];

  timelineDates.forEach(date => {
    let dayTotal = 0;

    histories.forEach((series, idx) => {
      const pointer = pointerState[idx];

      // Advance pointer while next snapshot date is <= current date
      while (
        pointer.index + 1 < series.length &&
        series[pointer.index + 1].date <= date
      ) {
        pointer.index += 1;
        pointer.lastValue = series[pointer.index].value;
      }

      if (pointer.index >= 0 && series[pointer.index].date <= date) {
        dayTotal += pointer.lastValue;
      }
    });

    aggregated.push({ date, totalValue: dayTotal });
  });

  const firstPositiveIndex = aggregated.findIndex(point => point.totalValue > 0);
  if (firstPositiveIndex > 0) {
    return aggregated.slice(firstPositiveIndex);
  }
  return aggregated;
};

const getHoldingQuantity = (holding: Holding): number => {
  if (holding.lots && holding.lots.length > 0) {
    return holding.lots.reduce((sum, lot) => sum + (lot.quantity || 0), 0);
  }
  return holding.quantity || 0;
};

const getEndPriceForTicker = (
  ticker: string,
  endSnapshot: PortfolioValueHistory,
): number => {
  if (endSnapshot.prices_snapshot && typeof endSnapshot.prices_snapshot[ticker] === 'number') {
    return endSnapshot.prices_snapshot[ticker] || 0;
  }
  const holdingMatch = endSnapshot.holdings_snapshot?.find(h => h.ticker === ticker);
  if (holdingMatch && typeof holdingMatch.currentPrice === 'number') {
    return holdingMatch.currentPrice || 0;
  }
  return 0;
};

const estimateNetContribution = (
  startSnapshot: PortfolioValueHistory,
  endSnapshot: PortfolioValueHistory,
): number => {
  const startHoldings = startSnapshot.holdings_snapshot;
  if (!startHoldings || startHoldings.length === 0) {
    return 0;
  }

  let carryForwardValue = 0;
  startHoldings.forEach(holding => {
    const quantity = getHoldingQuantity(holding);
    if (!quantity) {
      return;
    }
    const endPrice = getEndPriceForTicker(holding.ticker, endSnapshot);
    carryForwardValue += quantity * endPrice;
  });

  return endSnapshot.total_value - carryForwardValue;
};

const buildPortfolioTwrSeries = (
  history: PortfolioValueHistory[],
): PortfolioTwrPoint[] => {
  if (history.length === 0) return [];
  const sorted = [...history].sort(
    (a, b) => new Date(a.snapshot_date).getTime() - new Date(b.snapshot_date).getTime(),
  );

  if (!sorted[0].total_value || sorted[0].total_value <= 0) {
    return [];
  }

  const series: PortfolioTwrPoint[] = [
    { date: formatDateOnly(sorted[0].snapshot_date), index: 1 },
  ];
  let index = 1;

  for (let i = 1; i < sorted.length; i += 1) {
    const startSnapshot = sorted[i - 1];
    const endSnapshot = sorted[i];
    const beginValue = startSnapshot.total_value || 0;
    if (beginValue <= 0) {
      continue;
    }
    const netContribution = estimateNetContribution(startSnapshot, endSnapshot);
    const adjustedEnding = endSnapshot.total_value - netContribution;
    const periodReturn = beginValue ? (adjustedEnding - beginValue) / beginValue : 0;
    index *= 1 + periodReturn;
    series.push({
      date: formatDateOnly(endSnapshot.snapshot_date),
      index,
    });
  }

  return series;
};

const aggregateTwrTimeline = (
  twrSeriesList: PortfolioTwrPoint[][],
  startValues: number[],
  selectedRange: number,
): AggregatedTwrPoint[] => {
  if (!twrSeriesList.length) {
    return [];
  }

  const timelineDates = buildTimelineDates(selectedRange);
  if (!timelineDates.length) {
    return [];
  }

  const pointerState = twrSeriesList.map(() => ({ index: -1, lastValue: 1 }));

  return timelineDates.map(date => {
    let numerator = 0;
    let denominator = 0;

    twrSeriesList.forEach((series, idx) => {
      const startValue = startValues[idx] || 0;
      if (startValue <= 0) {
        return;
      }
      const pointer = pointerState[idx];
      while (
        pointer.index + 1 < series.length &&
        series[pointer.index + 1].date <= date
      ) {
        pointer.index += 1;
        pointer.lastValue = series[pointer.index].index;
      }

      if (pointer.index >= 0 && series[pointer.index].date <= date) {
        numerator += startValue * pointer.lastValue;
        denominator += startValue;
      }
    });

    const twr = denominator > 0 ? (numerator / denominator - 1) * 100 : 0;
    return { date, twr };
  });
};

const AggregatedPortfolioChart = () => {
  const [aggregatedHistory, setAggregatedHistory] = useState<AggregatedDataPoint[]>([]);
  const [twrTimeline, setTwrTimeline] = useState<AggregatedTwrPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRange, setSelectedRange] = useState<number>(30);
  const [portfolioCount, setPortfolioCount] = useState<number>(0);
  const [viewMode, setViewMode] = useState<'twr' | 'value'>('twr'); // TWR or Total Value

  const timeRanges = [
    { label: '1W', days: 7 },
    { label: '1M', days: 30 },
    { label: '3M', days: 90 },
    { label: '6M', days: 180 },
    { label: '1Y', days: 365 },
  ];

  const fetchAggregatedHistory = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all portfolios
      const portfolios = await portfolioApiService.listPortfolios();
      setPortfolioCount(portfolios.length);

      if (portfolios.length === 0) {
        setAggregatedHistory([]);
        setLoading(false);
        return;
      }

      // Fetch history for each portfolio
      const historyPromises = portfolios.map(portfolio =>
        portfolioApiService.getValueHistory(portfolio.id, selectedRange),
      );

      const allHistories = await Promise.all(historyPromises);

      const normalizedSeries: NormalizedHistoryPoint[][] = [];
      const twrSeriesList: PortfolioTwrPoint[][] = [];
      const startValues: number[] = [];

      allHistories.forEach(history => {
        if (!history || history.length === 0) {
          return;
        }

        const sortedHistory = [...history].sort(
          (a, b) => new Date(a.snapshot_date).getTime() - new Date(b.snapshot_date).getTime(),
        );

        const normalizedPoints: NormalizedHistoryPoint[] = sortedHistory.map(entry => ({
          date: formatDateOnly(entry.snapshot_date),
          value: entry.total_value,
        }));

        if (normalizedPoints.length > 0) {
          normalizedSeries.push(normalizedPoints);
        }

        const startValue = sortedHistory[0].total_value || 0;
        if (startValue > 0) {
          const twrSeries = buildPortfolioTwrSeries(sortedHistory);
          if (twrSeries.length > 0) {
            twrSeriesList.push(twrSeries);
            startValues.push(startValue);
          }
        }
      });

      const aggregated = aggregateHistories(normalizedSeries, selectedRange);
      const aggregatedTwr = aggregateTwrTimeline(twrSeriesList, startValues, selectedRange);

      setAggregatedHistory(aggregated);
      setTwrTimeline(aggregatedTwr);
    } catch (err: any) {
      console.error('Failed to fetch aggregated portfolio history:', err);
      setError(err.message || 'Failed to load performance data');
      toast.error('Failed to load performance data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAggregatedHistory();
  }, [selectedRange]);

  // Calculate performance metrics based on aggregated value history
  const valueMetrics = useMemo(() => {
    if (aggregatedHistory.length === 0) return null;
    const startValue = aggregatedHistory[0].totalValue;
    const endValue = aggregatedHistory[aggregatedHistory.length - 1].totalValue;
    const valueChange = endValue - startValue;
    const valueChangePercent = startValue > 0 ? (valueChange / startValue) * 100 : 0;

    return {
      currentValue: endValue,
      startValue,
      valueChange,
      valueChangePercent,
      isPositive: valueChange >= 0,
    };
  }, [aggregatedHistory]);

  const finalTwr = twrTimeline.length > 0 ? twrTimeline[twrTimeline.length - 1].twr : 0;
  const metrics = valueMetrics ? { ...valueMetrics, twr: finalTwr } : null;

  // Prepare chart data based on view mode
  const chartData = useMemo(() => {
    if ((!aggregatedHistory.length && viewMode === 'value') || !metrics) return [];

    const positiveColor = '#10b981';
    const negativeColor = '#ef4444';
    const isValuePositive = metrics.isPositive ?? true;
    const isTwrPositive = finalTwr >= 0;

    if (viewMode === 'value') {
      if (aggregatedHistory.length === 0) return [];
      const dates = aggregatedHistory.map(h => h.date);
      const values = aggregatedHistory.map(h => h.totalValue);

      return [{
        x: dates,
        y: values,
        type: 'scatter' as const,
        mode: aggregatedHistory.length === 1 ? 'markers' as const : 'lines' as const,
        name: 'Total Portfolio Value',
        marker: {
          size: 6,
          color: '#FFFFFF',
          line: {
            color: isValuePositive ? positiveColor : negativeColor,
            width: 2,
          },
        },
        line: {
          color: isValuePositive ? positiveColor : negativeColor,
          width: 3,
          shape: 'spline' as const,
          smoothing: 1.3,
        },
        fill: 'tozeroy' as const,
        fillcolor: isValuePositive
          ? 'rgba(16, 185, 129, 0.08)'
          : 'rgba(239, 68, 68, 0.08)',
        hovertemplate: '<b>%{x|%b %d, %Y}</b><br>' +
                       'Total Value: $%{y:,.2f}<br>' +
                       '<extra></extra>',
      }];
    }

    if (twrTimeline.length === 0) return [];

    const twrDates = twrTimeline.map(point => point.date);
    const twrValues = twrTimeline.map(point => point.twr);

    return [{
      x: twrDates,
      y: twrValues,
      type: 'scatter' as const,
      mode: twrTimeline.length === 1 ? 'markers' as const : 'lines' as const,
      name: 'Time-Weighted Return',
      marker: {
        size: 6,
        color: '#FFFFFF',
        line: {
          color: isTwrPositive ? positiveColor : negativeColor,
          width: 2,
        },
      },
      line: {
        color: isTwrPositive ? positiveColor : negativeColor,
        width: 3,
        shape: 'spline' as const,
        smoothing: 1.3,
      },
      fill: 'tozeroy' as const,
      fillcolor: isTwrPositive
        ? 'rgba(16, 185, 129, 0.08)'
        : 'rgba(239, 68, 68, 0.08)',
      hovertemplate: '<b>%{x|%b %d, %Y}</b><br>' +
                     'TWR: %{y:.2f}%<br>' +
                     '<extra></extra>',
    }];
  }, [aggregatedHistory, metrics, viewMode, finalTwr, twrTimeline]);

  const layout = {
    autosize: true,
    height: 300,
    margin: { l: 65, r: 25, t: 20, b: 50 },
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
        color: '#9ca3af',
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
      tickformat: viewMode === 'value' ? '$,.0f' : '.2f',
      ticksuffix: viewMode === 'value' ? '' : '%',
      tickfont: {
        size: 11,
        color: '#6b7280',
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      fixedrange: false,
    },
    hovermode: 'x unified' as const,
    hoverlabel: {
      bgcolor: '#111827',
      bordercolor: 'rgba(0,0,0,0)',
      font: {
        size: 13,
        color: '#FFFFFF',
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
    },
    font: {
      family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      size: 12,
      color: '#374151',
    },
    showlegend: false,
  };

  const config = {
    displayModeBar: false,
    responsive: true,
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200">
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px',
        }}>
          <RefreshCw size={24} style={{ color: '#9ca3af', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: '14px', color: '#6b7280' }}>Loading performance data...</span>
        </div>
        <style>{`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  if (error || aggregatedHistory.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200 flex-col gap-3">
        <span className="text-sm text-gray-500">
          {error || (portfolioCount === 0 ? 'No portfolios available' : 'No performance data available yet')}
        </span>
        <button
          onClick={fetchAggregatedHistory}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header with metrics, tabs, and time range selector */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Aggregate Performance</h3>
          {metrics && (
            <div className="flex items-baseline gap-3 mt-1">
              {viewMode === 'value' ? (
                <>
                  <span className="text-2xl font-semibold text-gray-900">
                    ${metrics.currentValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                  </span>
                  <span className={`text-sm font-semibold ${metrics.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                    {metrics.isPositive ? '+' : ''}${Math.abs(metrics.valueChange).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    {' '}({metrics.isPositive ? '+' : ''}{metrics.valueChangePercent.toFixed(2)}%)
                  </span>
                </>
              ) : (
                <>
                  <span className="text-2xl font-semibold text-gray-900">
                    {metrics.isPositive ? '+' : ''}{metrics.twr.toFixed(2)}%
                  </span>
                  <span className="text-sm text-gray-500">Time-Weighted Return</span>
                </>
              )}
              <span className="text-xs text-gray-500">
                {portfolioCount} {portfolioCount === 1 ? 'portfolio' : 'portfolios'}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-4">
          {/* View Mode Tabs */}
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('twr')}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                viewMode === 'twr'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              TWR
            </button>
            <button
              onClick={() => setViewMode('value')}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                viewMode === 'value'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Total Value
            </button>
          </div>

          {/* Time range selector */}
          <div className="flex space-x-2">
            {timeRanges.map(range => (
              <button
                key={range.days}
                onClick={() => setSelectedRange(range.days)}
                className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                  selectedRange === range.days
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {range.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-white rounded-lg border border-gray-200 flex justify-start items-start">
        <Plot
          data={chartData}
          layout={layout}
          config={config}
          style={{ width: '100%' }}
          useResizeHandler={true}
        />
      </div>
    </div>
  );
};

export default AggregatedPortfolioChart;
