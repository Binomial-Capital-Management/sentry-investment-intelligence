import { useState, useRef, useCallback, memo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { lazy, Suspense, useMemo } from 'react';
const Plot = lazy(() => import('react-plotly.js'));
import type { ChartData } from '@/types';

interface ChartFrameProps {
  chart: ChartData;
  title?: string;
  kpis?: Array<{
    label: string;
    value: string | number;
    change?: number;
    unit?: string;
  }>;
  onExport?: (format: 'png' | 'svg' | 'json') => void;
  onFullscreen?: () => void;
  controls?: {
    timeRange?: boolean;
    chartType?: boolean;
    indicators?: boolean;
  };
}

const ChartFrame = memo(({
  chart,
  title,
  kpis,
  onExport,
  onFullscreen,
  controls = {},
}: ChartFrameProps) => {
  const [showControls, setShowControls] = useState(false);
  const [selectedTimeRange, setSelectedTimeRange] = useState('1M');
  const [hoveredKpi, setHoveredKpi] = useState<number | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<HTMLDivElement>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setShowExportMenu(false);
      }
    };

    if (showExportMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showExportMenu]);

  const timeRanges = ['1D', '1W', '1M', '3M', '6M', '1Y', 'YTD', 'ALL'];

  const handleExport = useCallback(async (format: 'png' | 'svg' | 'json') => {
    if (onExport) {
      onExport(format);
      return;
    }

    // Default export implementation
    const plotElement = plotRef.current?.querySelector('.js-plotly-plot') as HTMLElement;

    if (format === 'json') {
      // Export data as JSON
      const jsonData = {
        data: chart.plotly?.data || chart.data || [],
        layout: chart.plotly?.layout || chart.layout || {},
      };
      const blob = new Blob([JSON.stringify(jsonData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title || 'chart'}-data.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      return;
    }

    if (plotElement) {
      try {
        // Find the SVG element inside the Plotly chart
        const svgElement = plotElement.querySelector('svg.main-svg') as SVGSVGElement;

        if (!svgElement) {
          console.error('SVG element not found in chart');
          setShowExportMenu(false);
          return;
        }

        if (format === 'svg') {
          // Export as SVG directly
          const svgData = new XMLSerializer().serializeToString(svgElement);
          const blob = new Blob([svgData], { type: 'image/svg+xml' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `${title || 'chart'}.svg`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        } else if (format === 'png') {
          // Convert SVG to PNG using canvas
          const svgData = new XMLSerializer().serializeToString(svgElement);
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          const img = new Image();

          // Get dimensions from SVG
          const bbox = svgElement.getBoundingClientRect();
          const scale = 2; // High resolution
          canvas.width = bbox.width * scale;
          canvas.height = bbox.height * scale;

          const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
          const svgUrl = URL.createObjectURL(svgBlob);

          img.onload = () => {
            if (ctx) {
              ctx.fillStyle = 'white';
              ctx.fillRect(0, 0, canvas.width, canvas.height);
              ctx.scale(scale, scale);
              ctx.drawImage(img, 0, 0);
            }
            URL.revokeObjectURL(svgUrl);

            canvas.toBlob((blob) => {
              if (blob) {
                const pngUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = pngUrl;
                a.download = `${title || 'chart'}.png`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(pngUrl);
              }
            }, 'image/png');
          };

          img.onerror = () => {
            console.error('Failed to load SVG for PNG conversion');
            URL.revokeObjectURL(svgUrl);
          };

          img.src = svgUrl;
        }
      } catch (error) {
        console.error('Failed to export chart:', error);
      }
    } else {
      console.warn('Plot element not found');
    }

    setShowExportMenu(false);
  }, [onExport, chart, title]);

  const handleFullscreen = useCallback(() => {
    if (onFullscreen) {
      onFullscreen();
    } else if (isFullscreen) {
      document.exitFullscreen?.();
    } else if (chartRef.current?.requestFullscreen) {
      chartRef.current.requestFullscreen();
    }
  }, [onFullscreen, isFullscreen]);

  // Listen for fullscreen changes (e.g., user presses Escape)
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Prepare plotly props once
  const defaultConfig = useMemo(() => ({
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['sendDataToCloud'],
    responsive: true,
  }), []);

  const computedLayout = useMemo(() => ({
    ...chart.layout,
    paper_bgcolor: '#FFFFFF',
    plot_bgcolor: '#FAFBFC',
    font: {
      family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#0F172A',
    },
  }), [chart.layout]);

  return (
    <motion.div
      ref={chartRef}
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`chart-frame overflow-hidden ${isFullscreen ? '' : 'bg-white rounded-lg border border-gray-200'}`}
      style={{
        position: 'relative',
        ...(isFullscreen && {
          display: 'flex',
          flexDirection: 'column' as const,
          height: '100vh',
          width: '100vw',
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)',
        }),
      }}
    >
      {/* Header */}
      <div
        className="chart-header"
        style={{
          padding: isFullscreen ? '20px 32px' : '12px 16px',
          borderBottom: isFullscreen ? '1px solid rgba(255,255,255,0.1)' : '1px solid var(--border-default)',
          background: isFullscreen ? 'rgba(0,0,0,0.3)' : 'color-mix(in oklab, var(--bg-surface), white 1%)',
          backdropFilter: isFullscreen ? 'blur(12px)' : 'none',
          flexShrink: 0,
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {title && (
              <h3 style={{
                fontSize: isFullscreen ? '20px' : 'var(--fs-14)',
                fontWeight: isFullscreen ? '600' : 'var(--fw-semibold)',
                color: isFullscreen ? '#ffffff' : 'var(--text-primary)',
                margin: 0,
                letterSpacing: isFullscreen ? '-0.02em' : 'normal',
              }}>
                {title}
              </h3>
            )}

            {/* Time Range Selector */}
            {controls.timeRange && (
              <div
                className="time-range-selector"
                style={{
                  display: 'flex',
                  gap: '2px',
                  padding: '2px',
                  borderRadius: 'var(--radius-base)',
                  background: 'color-mix(in oklab, var(--bg-subtle), white 3%)',
                }}
              >
                {timeRanges.map((range) => (
                  <button
                    key={range}
                    onClick={() => setSelectedTimeRange(range)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 'var(--radius-sm)',
                      border: 'none',
                      background: selectedTimeRange === range
                        ? 'color-mix(in oklab, var(--accent), black 70%)'
                        : 'transparent',
                      color: selectedTimeRange === range
                        ? 'var(--accent)'
                        : 'var(--text-muted)',
                      fontSize: 'var(--fs-11)',
                      fontWeight: 'var(--fw-medium)',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    {range}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Chart Controls */}
          <div className="flex items-center gap-2">
            {/* Settings */}
            {Object.keys(controls).length > 0 && (
              <button
                onClick={() => setShowControls(!showControls)}
                className="chart-control-button"
                title="Chart settings"
                style={{
                  padding: isFullscreen ? '10px' : '6px',
                  borderRadius: isFullscreen ? '8px' : 'var(--radius-base)',
                  background: isFullscreen
                    ? 'rgba(255,255,255,0.1)'
                    : showControls
                      ? 'color-mix(in oklab, var(--bg-subtle), white 6%)'
                      : 'transparent',
                  border: isFullscreen ? '1px solid rgba(255,255,255,0.2)' : 'none',
                  color: isFullscreen ? '#ffffff' : 'var(--text-muted)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <svg width={isFullscreen ? "18" : "16"} height={isFullscreen ? "18" : "16"} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
            )}

            {/* Fullscreen */}
            <button
              onClick={handleFullscreen}
              className="chart-control-button"
              title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
              style={{
                padding: isFullscreen ? '10px' : '6px',
                borderRadius: isFullscreen ? '8px' : 'var(--radius-base)',
                background: isFullscreen ? 'rgba(255,255,255,0.15)' : 'transparent',
                border: isFullscreen ? '1px solid rgba(255,255,255,0.3)' : 'none',
                color: isFullscreen ? '#ffffff' : 'var(--text-muted)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              <svg width={isFullscreen ? "18" : "16"} height={isFullscreen ? "18" : "16"} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {isFullscreen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 9V4H4m0 0v5m0-5l5 5m6-5h5m0 0v5m0-5l-5 5M9 15v5H4m0 0v-5m0 5l5-5m6 5h5m0 0v-5m0 5l-5-5" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l4 4m12-4h-4m4 0v4m0-4l-4 4M4 16v4m0 0h4m-4 0l4-4m12 4h-4m4 0v-4m0 4l-4-4" />
                )}
              </svg>
            </button>

            {/* Export Menu */}
            <div className="relative" ref={exportMenuRef}>
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                className="chart-control-button"
                title="Export"
                style={{
                  padding: isFullscreen ? '10px' : '6px',
                  borderRadius: isFullscreen ? '8px' : 'var(--radius-base)',
                  background: isFullscreen
                    ? 'rgba(255,255,255,0.1)'
                    : showExportMenu
                      ? 'color-mix(in oklab, var(--bg-subtle), white 6%)'
                      : 'transparent',
                  border: isFullscreen ? '1px solid rgba(255,255,255,0.2)' : 'none',
                  color: isFullscreen ? '#ffffff' : 'var(--text-muted)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <svg width={isFullscreen ? "18" : "16"} height={isFullscreen ? "18" : "16"} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </button>
              {/* Export dropdown */}
              <AnimatePresence>
                {showExportMenu && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.96 }}
                    transition={{ duration: 0.15, ease: [0.4, 0, 0.2, 1] }}
                    style={{
                      position: 'absolute',
                      top: '100%',
                      right: 0,
                      marginTop: '8px',
                      background: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: '12px',
                      boxShadow: '0 10px 40px -10px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.05)',
                      minWidth: '160px',
                      zIndex: 50,
                      overflow: 'hidden',
                      padding: '6px',
                    }}
                  >
                    {/* Header */}
                    <div style={{
                      padding: '8px 10px 6px',
                      fontSize: '10px',
                      fontWeight: '600',
                      color: '#94a3b8',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                    }}>
                      Export As
                    </div>
                    
                    <button
                      onClick={() => handleExport('png')}
                      className="export-menu-item"
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        background: 'transparent',
                        border: 'none',
                        textAlign: 'left',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: '#334155',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        borderRadius: '8px',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '6px',
                        background: 'linear-gradient(135deg, #ec4899 0%, #f472b6 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2">
                          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                          <circle cx="8.5" cy="8.5" r="1.5"/>
                          <polyline points="21,15 16,10 5,21"/>
                        </svg>
                      </div>
                      <div>
                        <div>PNG Image</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', fontWeight: '400' }}>Raster format</div>
                      </div>
                    </button>
                    
                    <button
                      onClick={() => handleExport('svg')}
                      className="export-menu-item"
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        background: 'transparent',
                        border: 'none',
                        textAlign: 'left',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: '#334155',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        borderRadius: '8px',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '6px',
                        background: 'linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                          <polyline points="14,2 14,8 20,8"/>
                        </svg>
                      </div>
                      <div>
                        <div>SVG Vector</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', fontWeight: '400' }}>Scalable format</div>
                      </div>
                    </button>
                    
                    {/* Divider */}
                    <div style={{ height: '1px', background: '#e2e8f0', margin: '6px 0' }} />
                    
                    <button
                      onClick={() => handleExport('json')}
                      className="export-menu-item"
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        background: 'transparent',
                        border: 'none',
                        textAlign: 'left',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: '#334155',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        borderRadius: '8px',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '6px',
                        background: 'linear-gradient(135deg, #0ea5e9 0%, #38bdf8 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                          <polyline points="14,2 14,8 20,8"/>
                          <line x1="16" y1="13" x2="8" y2="13"/>
                          <line x1="16" y1="17" x2="8" y2="17"/>
                        </svg>
                      </div>
                      <div>
                        <div>JSON Data</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', fontWeight: '400' }}>Raw chart data</div>
                      </div>
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* Controls Panel */}
        <AnimatePresence>
          {showControls && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="controls-panel"
              style={{
                marginTop: '12px',
                paddingTop: '12px',
                borderTop: '1px solid var(--border-default)',
              }}
            >
              <div className="flex gap-4">
                {controls.chartType && (
                  <div className="control-group">
                    <label style={{ fontSize: 'var(--fs-11)', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                      Chart Type
                    </label>
                    <select
                      style={{
                        padding: '4px 8px',
                        borderRadius: 'var(--radius-base)',
                        background: 'color-mix(in oklab, var(--bg-subtle), white 3%)',
                        border: '1px solid var(--border-default)',
                        color: 'var(--text-primary)',
                        fontSize: 'var(--fs-12)',
                        cursor: 'pointer',
                      }}
                    >
                      <option>Line</option>
                      <option>Bar</option>
                      <option>Candlestick</option>
                      <option>Area</option>
                    </select>
                  </div>
                )}

                {controls.indicators && (
                  <div className="control-group">
                    <label style={{ fontSize: 'var(--fs-11)', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                      Indicators
                    </label>
                    <div className="flex gap-2">
                      {['MA20', 'MA50', 'RSI', 'MACD'].map((indicator) => (
                        <label
                          key={indicator}
                          className="indicator-toggle"
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '4px 8px',
                            borderRadius: 'var(--radius-base)',
                            background: 'color-mix(in oklab, var(--bg-subtle), white 3%)',
                            fontSize: 'var(--fs-11)',
                            cursor: 'pointer',
                          }}
                        >
                          <input type="checkbox" style={{ width: '12px', height: '12px' }} />
                          <span style={{ color: 'var(--text-secondary)' }}>{indicator}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* KPIs Bar */}
      {kpis && kpis.length > 0 && (
        <div
          className="kpis-bar"
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border-default)',
            background: 'color-mix(in oklab, var(--bg-subtle), white 2%)',
            display: 'flex',
            gap: '24px',
            overflowX: 'auto',
          }}
        >
          {kpis.map((kpi, index) => (
            <motion.div
              key={index}
              className="kpi-item"
              onMouseEnter={() => setHoveredKpi(index)}
              onMouseLeave={() => setHoveredKpi(null)}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                minWidth: '100px',
                position: 'relative',
                cursor: 'pointer',
                transform: hoveredKpi === index ? 'translateY(-2px)' : 'translateY(0)',
                transition: 'transform 0.2s ease',
              }}
            >
              <span
                style={{
                  fontSize: 'var(--fs-11)',
                  color: 'var(--text-muted)',
                  letterSpacing: '0.05em',
                }}
              >
                {kpi.label}
              </span>
              <div className="flex items-baseline gap-2">
                <span
                  style={{
                    fontSize: 'var(--fs-18)',
                    fontWeight: 'var(--fw-semibold)',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {kpi.value}
                </span>
                {kpi.unit && (
                  <span style={{ fontSize: 'var(--fs-12)', color: 'var(--text-muted)' }}>
                    {kpi.unit}
                  </span>
                )}
                {kpi.change !== undefined && (
                  <span
                    style={{
                      fontSize: 'var(--fs-11)',
                      color: kpi.change > 0 ? 'var(--success)' : kpi.change < 0 ? 'var(--danger)' : 'var(--text-muted)',
                      fontWeight: 'var(--fw-medium)',
                    }}
                  >
                    {kpi.change > 0 ? '↑' : kpi.change < 0 ? '↓' : '—'} {Math.abs(kpi.change)}%
                  </span>
                )}
              </div>

              {/* Hover indicator */}
              {hoveredKpi === index && (
                <motion.div
                  layoutId="kpi-hover"
                  className="kpi-hover-indicator"
                  style={{
                    position: 'absolute',
                    bottom: '-2px',
                    left: 0,
                    right: 0,
                    height: '2px',
                    background: 'var(--accent)',
                    borderRadius: 'var(--radius-full)',
                  }}
                />
              )}
            </motion.div>
          ))}
        </div>
      )}

      {/* Chart Container */}
      <div
        ref={plotRef}
        className="chart-container"
        style={{
          padding: isFullscreen ? '32px 48px' : '16px',
          background: isFullscreen ? 'transparent' : 'var(--bg-void)',
          minHeight: isFullscreen ? 'auto' : '400px',
          flex: isFullscreen ? 1 : 'none',
          display: isFullscreen ? 'flex' : 'block',
          flexDirection: 'column',
          transition: 'min-height 0.3s ease',
          overflow: 'hidden',
        }}
      >
        {/* Fullscreen chart wrapper with card styling */}
        <div style={{
          flex: isFullscreen ? 1 : 'none',
          background: isFullscreen ? 'rgba(255,255,255,0.98)' : 'transparent',
          borderRadius: isFullscreen ? '16px' : 0,
          boxShadow: isFullscreen ? '0 25px 50px -12px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255,255,255,0.1)' : 'none',
          padding: isFullscreen ? '24px' : 0,
          display: 'flex',
          flexDirection: 'column',
        }}>
          <Suspense fallback={<div className="text-sm" style={{ color: isFullscreen ? '#64748b' : 'var(--text-secondary)' }}>Loading chart…</div>}>
            <Plot
              data={chart.plotly?.data || chart.data || []}
              layout={{
                ...(chart.plotly?.layout || computedLayout),
                width: undefined,
                autosize: true,
                height: isFullscreen ? undefined : 400,
                paper_bgcolor: isFullscreen ? '#ffffff' : 'transparent',
                plot_bgcolor: isFullscreen ? '#fafbfc' : 'transparent',
                margin: isFullscreen ? { t: 60, r: 40, b: 60, l: 60 } : undefined,
                font: {
                  family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  color: isFullscreen ? '#1e293b' : 'var(--text-secondary)',
                  size: isFullscreen ? 13 : 12,
                },
                title: isFullscreen ? {
                  text: title || '',
                  font: { size: 18, color: '#0f172a', family: 'Inter, sans-serif' },
                  x: 0.5,
                  xanchor: 'center',
                } : undefined,
                xaxis: {
                  ...chart.layout?.xaxis,
                  gridcolor: isFullscreen ? '#e2e8f0' : 'var(--border-subtle)',
                  zerolinecolor: isFullscreen ? '#cbd5e1' : 'var(--border-default)',
                  linecolor: isFullscreen ? '#e2e8f0' : undefined,
                  tickfont: { size: isFullscreen ? 12 : 11 },
                },
                yaxis: {
                  ...chart.layout?.yaxis,
                  gridcolor: isFullscreen ? '#e2e8f0' : 'var(--border-subtle)',
                  zerolinecolor: isFullscreen ? '#cbd5e1' : 'var(--border-default)',
                  linecolor: isFullscreen ? '#e2e8f0' : undefined,
                  tickfont: { size: isFullscreen ? 12 : 11 },
                },
                legend: isFullscreen ? {
                  bgcolor: 'rgba(255,255,255,0.9)',
                  bordercolor: '#e2e8f0',
                  borderwidth: 1,
                  font: { size: 12 },
                } : undefined,
              }}
              config={{
                ...defaultConfig,
                ...chart.config,
                displayModeBar: isFullscreen ? 'hover' : false,
                modeBarButtonsToRemove: ['sendDataToCloud', 'select2d', 'lasso2d', 'hoverClosestCartesian', 'hoverCompareCartesian', 'toggleSpikelines'],
                scrollZoom: true,
                toImageButtonOptions: {
                  format: 'png',
                  filename: title || 'chart',
                  height: 800,
                  width: 1200,
                  scale: 2,
                },
              }}
              className="w-full"
              style={{ flex: isFullscreen ? 1 : 'none', minHeight: isFullscreen ? 'calc(100vh - 200px)' : 'auto' }}
              useResizeHandler
            />
          </Suspense>
        </div>
      </div>

      {/* Footer Actions - hidden in fullscreen */}
      {!isFullscreen && (
      <div
        className="chart-footer"
        style={{
          padding: '8px 16px',
          borderTop: '1px solid var(--border-default)',
          background: 'color-mix(in oklab, var(--bg-surface), white 1%)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 'var(--fs-11)', color: 'var(--text-muted)' }}>
            Last updated: {new Date().toLocaleTimeString()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExport('json')}
            className="export-button"
            style={{
              padding: '4px 8px',
              borderRadius: 'var(--radius-base)',
              background: 'transparent',
              border: '1px solid var(--border-default)',
              color: 'var(--text-secondary)',
              fontSize: 'var(--fs-11)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            Export Data
          </button>
        </div>
      </div>
      )}

      {/* Hover styles */}
      <style>{`
        .chart-control-button:hover {
          background: color-mix(in oklab, var(--bg-subtle), white 6%) !important;
          color: var(--text-primary) !important;
        }
        
        .export-button:hover {
          background: color-mix(in oklab, var(--bg-subtle), white 3%) !important;
          border-color: var(--border-strong) !important;
        }
        
        .indicator-toggle:hover {
          background: color-mix(in oklab, var(--bg-subtle), white 5%) !important;
        }
        
        .export-menu-item:hover {
          background: #f1f5f9 !important;
        }

        /* Hide Plotly modebar completely - we have our own controls */
        .chart-frame .modebar {
          display: none !important;
        }
        
        /* Show modebar only in fullscreen on hover */
        .chart-frame:fullscreen .modebar {
          display: flex !important;
          background: transparent !important;
          right: 24px !important;
          top: auto !important;
          bottom: 24px !important;
        }
        
        .chart-frame:fullscreen .modebar-group {
          background: rgba(15, 23, 42, 0.95) !important;
          backdrop-filter: blur(12px) !important;
          border: 1px solid rgba(255, 255, 255, 0.15) !important;
          border-radius: 10px !important;
          padding: 6px !important;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
          margin-left: 6px !important;
        }
        
        .chart-frame:fullscreen .modebar-btn {
          color: rgba(255, 255, 255, 0.8) !important;
          padding: 8px !important;
        }
        
        .chart-frame:fullscreen .modebar-btn:hover {
          color: #ffffff !important;
          background: rgba(255, 255, 255, 0.15) !important;
          border-radius: 6px !important;
        }
        
        .chart-frame:fullscreen .modebar-btn.active {
          color: #60a5fa !important;
        }
        
        .chart-frame:fullscreen .modebar-btn path {
          fill: currentColor !important;
        }
      `}</style>
    </motion.div>
  );
});

ChartFrame.displayName = 'ChartFrame';

export default ChartFrame;
