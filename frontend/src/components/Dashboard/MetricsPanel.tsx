import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { RiskMetrics } from '@/types';

interface MetricGroup {
  id: string;
  label: string;
  metrics: Array<{
    key: string;
    label: string;
    value: number | string;
    unit?: string;
    description?: string;
    status?: 'good' | 'warning' | 'critical';
    benchmark?: number;
  }>;
}

interface MetricsPanelProps {
  metrics: RiskMetrics;
  layout?: 'grid' | 'list' | 'compact';
  onMetricClick?: (key: string, value: any) => void;
  showBenchmarks?: boolean;
  showTrends?: boolean;
}

const MetricsPanel = ({
  metrics,
  layout = 'grid',
  onMetricClick,
  showBenchmarks = true,
  showTrends = false,
}: MetricsPanelProps) => {
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'absolute' | 'relative'>('absolute');

  // Organize metrics into groups
  const metricGroups = useMemo<MetricGroup[]>(() => {
    const groups: MetricGroup[] = [
      {
        id: 'risk',
        label: 'Risk Metrics',
        metrics: [],
      },
      {
        id: 'performance',
        label: 'Performance',
        metrics: [],
      },
      {
        id: 'portfolio',
        label: 'Portfolio Stats',
        metrics: [],
      },
    ];

    // Categorize metrics
    Object.entries(metrics).forEach(([key, value]) => {
      if (typeof value !== 'number') return;

      const metric = {
        key,
        label: formatMetricLabel(key),
        value: formatMetricValue(key, value),
        unit: getMetricUnit(key),
        description: getMetricDescription(key),
        status: getMetricStatus(key, value),
        benchmark: getBenchmark(key),
      };

      // Assign to appropriate group
      if (key.includes('var') || key.includes('cvar') || key.includes('volatility') || key.includes('drawdown')) {
        groups[0].metrics.push(metric);
      } else if (key.includes('sharpe') || key.includes('sortino') || key.includes('return')) {
        groups[1].metrics.push(metric);
      } else {
        groups[2].metrics.push(metric);
      }
    });

    return groups.filter(g => g.metrics.length > 0);
  }, [metrics]);

  function formatMetricLabel(key: string): string {
    const labels: Record<string, string> = {
      var_95: 'VaR 95%',
      var_99: 'VaR 99%',
      cvar_95: 'CVaR 95%',
      cvar_99: 'CVaR 99%',
      volatility: 'Volatility',
      sharpe_ratio: 'Sharpe Ratio',
      sortino_ratio: 'Sortino Ratio',
      max_drawdown: 'Max Drawdown',
      expected_return: 'Expected Return',
      beta: 'Beta',
      alpha: 'Alpha',
      correlation: 'Correlation',
    };
    return labels[key] || key.split('_').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ');
  }

  function formatMetricValue(key: string, value: number): string {
    if (key.includes('ratio')) return value.toFixed(2);
    if (key.includes('var') || key.includes('cvar') || key.includes('return') || key.includes('volatility')) {
      return `${(value * 100).toFixed(2)}%`;
    }
    if (key.includes('drawdown')) return `${(value * 100).toFixed(2)}%`;
    return value.toFixed(4);
  }

  function getMetricUnit(key: string): string {
    if (key.includes('ratio')) return '';
    if (key.includes('days')) return 'days';
    if (key.includes('count')) return '';
    return '';
  }

  function getMetricDescription(key: string): string {
    const descriptions: Record<string, string> = {
      var_95: 'Maximum loss expected with 95% confidence',
      var_99: 'Maximum loss expected with 99% confidence',
      cvar_95: 'Expected loss beyond VaR 95%',
      cvar_99: 'Expected loss beyond VaR 99%',
      volatility: 'Annualized standard deviation of returns',
      sharpe_ratio: 'Risk-adjusted return metric',
      sortino_ratio: 'Downside risk-adjusted return',
      max_drawdown: 'Largest peak-to-trough decline',
    };
    return descriptions[key] || '';
  }

  function getMetricStatus(key: string, value: number): 'good' | 'warning' | 'critical' {
    if (key === 'sharpe_ratio') {
      if (value > 1) return 'good';
      if (value > 0.5) return 'warning';
      return 'critical';
    }
    if (key.includes('var') || key.includes('cvar')) {
      if (Math.abs(value) < 0.05) return 'good';
      if (Math.abs(value) < 0.1) return 'warning';
      return 'critical';
    }
    if (key === 'volatility') {
      if (value < 0.15) return 'good';
      if (value < 0.25) return 'warning';
      return 'critical';
    }
    return 'good';
  }

  function getBenchmark(key: string): number | undefined {
    const benchmarks: Record<string, number> = {
      sharpe_ratio: 1.0,
      sortino_ratio: 1.5,
      volatility: 0.16, // S&P 500 historical
      var_95: -0.05,
      var_99: -0.08,
    };
    return benchmarks[key];
  }

  const getStatusColor = (status?: 'good' | 'warning' | 'critical') => {
    switch (status) {
      case 'good': return 'var(--success)';
      case 'warning': return 'var(--warning)';
      case 'critical': return 'var(--danger)';
      default: return 'var(--text-secondary)';
    }
  };

  const renderMetricCard = (metric: MetricGroup['metrics'][0], _groupId: string) => (
    <motion.div
      key={metric.key}
      layoutId={`metric-${metric.key}`}
      className="metric-card"
      onClick={() => {
        setSelectedMetric(metric.key);
        onMetricClick?.(metric.key, metrics[metric.key]);
      }}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      style={{
        padding: layout === 'compact' ? '8px' : '12px',
        borderRadius: 'var(--radius-md)',
        background: selectedMetric === metric.key
          ? 'color-mix(in oklab, var(--accent), black 85%)'
          : 'color-mix(in oklab, var(--bg-subtle), white 2%)',
        boxShadow: '0 0 0 1px var(--border-default) inset',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Status Indicator */}
      <div
        className="status-bar"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '2px',
          background: getStatusColor(metric.status),
          opacity: 0.8,
        }}
      />

      {/* Metric Content */}
      <div className="metric-content">
        <div className="flex items-center justify-between mb-1">
          <span
            style={{
              fontSize: 'var(--fs-11)',
              color: 'var(--text-muted)',
              letterSpacing: '0.05em',
            }}
          >
            {metric.label}
          </span>
          {metric.status && (
            <span
              className="status-dot"
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: getStatusColor(metric.status),
              }}
            />
          )}
        </div>

        <div className="flex items-baseline gap-2">
          <span
            style={{
              fontSize: layout === 'compact' ? 'var(--fs-16)' : 'var(--fs-24)',
              fontWeight: 'var(--fw-semibold)',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {metric.value}
          </span>
          {metric.unit && (
            <span style={{ fontSize: 'var(--fs-12)', color: 'var(--text-muted)' }}>
              {metric.unit}
            </span>
          )}
        </div>

        {/* Benchmark Comparison */}
        {showBenchmarks && metric.benchmark !== undefined && (
          <div
            className="benchmark-comparison"
            style={{
              marginTop: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span style={{ fontSize: 'var(--fs-11)', color: 'var(--text-muted)' }}>
              Benchmark:
            </span>
            <span style={{ fontSize: 'var(--fs-11)', color: 'var(--text-secondary)' }}>
              {metric.benchmark}
            </span>
            {typeof metrics[metric.key] === 'number' && (
              <span
                style={{
                  fontSize: 'var(--fs-11)',
                  color: metrics[metric.key] > metric.benchmark ? 'var(--success)' : 'var(--danger)',
                }}
              >
                ({metrics[metric.key] > metric.benchmark ? '+' : ''}{((metrics[metric.key] - metric.benchmark) / metric.benchmark * 100).toFixed(1)}%)
              </span>
            )}
          </div>
        )}

        {/* Description on hover */}
        {metric.description && layout !== 'compact' && (
          <AnimatePresence>
            {selectedMetric === metric.key && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="metric-description"
                style={{
                  marginTop: '8px',
                  paddingTop: '8px',
                  borderTop: '1px solid var(--border-default)',
                  fontSize: 'var(--fs-11)',
                  color: 'var(--text-secondary)',
                  lineHeight: 'var(--lh-11)',
                }}
              >
                {metric.description}
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>

      {/* Trend Indicator (mock) */}
      {showTrends && (
        <div
          className="trend-indicator"
          style={{
            position: 'absolute',
            bottom: '8px',
            right: '8px',
            opacity: 0.3,
          }}
        >
          <svg width="32" height="16">
            <polyline
              points="0,14 8,12 16,8 24,10 32,6"
              fill="none"
              stroke={getStatusColor(metric.status)}
              strokeWidth="1"
            />
          </svg>
        </div>
      )}
    </motion.div>
  );

  return (
    <div className="metrics-panel">
      {/* Panel Header */}
      <div
        className="panel-header"
        style={{
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <h3 style={{
          fontSize: 'var(--fs-16)',
          fontWeight: 'var(--fw-semibold)',
          color: 'var(--text-primary)',
          margin: 0,
        }}>
          Portfolio Metrics
        </h3>

        {/* View Controls */}
        <div className="flex items-center gap-2">
          {/* Layout Toggle */}
          <div
            className="layout-toggle"
            style={{
              display: 'flex',
              gap: '2px',
              padding: '2px',
              borderRadius: 'var(--radius-base)',
              background: 'color-mix(in oklab, var(--bg-subtle), white 3%)',
            }}
          >
            {(['grid', 'list', 'compact'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => {}}
                style={{
                  padding: '4px 8px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  background: layout === mode
                    ? 'color-mix(in oklab, var(--accent), black 70%)'
                    : 'transparent',
                  color: layout === mode
                    ? 'var(--accent)'
                    : 'var(--text-muted)',
                  fontSize: 'var(--fs-11)',
                  fontWeight: 'var(--fw-medium)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  textTransform: 'capitalize',
                }}
              >
                {mode}
              </button>
            ))}
          </div>

          {/* View Mode Toggle */}
          <button
            onClick={() => setViewMode(viewMode === 'absolute' ? 'relative' : 'absolute')}
            style={{
              padding: '4px 8px',
              borderRadius: 'var(--radius-base)',
              background: 'color-mix(in oklab, var(--bg-subtle), white 3%)',
              border: 'none',
              color: 'var(--text-secondary)',
              fontSize: 'var(--fs-11)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            {viewMode === 'absolute' ? 'Absolute' : 'Relative'} Values
          </button>
        </div>
      </div>

      {/* Metrics Groups */}
      <div className="metrics-groups">
        {metricGroups.map((group) => (
          <div key={group.id} className="metric-group" style={{ marginBottom: '24px' }}>
            {/* Group Header */}
            <button
              onClick={() => setExpandedGroup(expandedGroup === group.id ? null : group.id)}
              className="group-header"
              style={{
                width: '100%',
                padding: '8px 12px',
                marginBottom: '12px',
                borderRadius: 'var(--radius-md)',
                background: 'color-mix(in oklab, var(--bg-subtle), white 1%)',
                boxShadow: '0 0 0 1px var(--border-default) inset',
                border: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              <div className="flex items-center gap-2">
                <span style={{
                  fontSize: 'var(--fs-13)',
                  fontWeight: 'var(--fw-medium)',
                  color: 'var(--text-primary)',
                }}>
                  {group.label}
                </span>
                <span style={{
                  padding: '2px 6px',
                  borderRadius: 'var(--radius-base)',
                  background: 'color-mix(in oklab, var(--accent), black 80%)',
                  fontSize: 'var(--fs-11)',
                  color: 'var(--accent)',
                }}>
                  {group.metrics.length}
                </span>
              </div>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{
                  color: 'var(--text-muted)',
                  transform: expandedGroup === group.id ? 'rotate(180deg)' : 'rotate(0)',
                  transition: 'transform 0.2s ease',
                }}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Group Metrics */}
            <AnimatePresence>
              {(expandedGroup === null || expandedGroup === group.id) && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="group-metrics"
                  style={{
                    display: layout === 'list' ? 'flex' : 'grid',
                    flexDirection: layout === 'list' ? 'column' : undefined,
                    gridTemplateColumns: layout === 'grid'
                      ? 'repeat(auto-fill, minmax(200px, 1fr))'
                      : layout === 'compact'
                      ? 'repeat(auto-fill, minmax(150px, 1fr))'
                      : undefined,
                    gap: '12px',
                  }}
                >
                  {group.metrics.map((metric) => renderMetricCard(metric, group.id))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MetricsPanel;
