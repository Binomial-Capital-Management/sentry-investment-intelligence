import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { FieldInfo, DescriptiveStats, CorrelationResult, StatisticalTestResult, TEST_OPTIONS } from '../types';

const S = {
  text:       'hsl(60 2.5% 23.3%)',
  textMuted:  'hsl(60 2.5% 23.3% / 60%)',
  textFaint:  'hsl(60 2.5% 23.3% / 35%)',
  textGhost:  'hsl(60 2.5% 23.3% / 25%)',
  border:     '0.5px solid hsl(30 3.3% 11.8% / 10%)',
  bgActive:   'hsl(30 3.3% 11.8% / 8%)',
} as const;

const selectStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.375rem 0.5rem',
  fontSize: '0.688rem',
  border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
  borderRadius: '0.5rem',
  outline: 'none',
  color: S.text,
  backgroundColor: 'white',
};

const btnStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.375rem 0.75rem',
  borderRadius: '0.5rem',
  border: 'none',
  fontSize: '0.688rem',
  fontWeight: 500,
  backgroundColor: 'hsl(60 2.5% 23.3% / 85%)',
  color: 'white',
};

function StatsSelect({ value, onChange, options, placeholder = 'Select...' }: {
  value: string;
  onChange: (val: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });

  const updatePos = useCallback(() => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const dropdownHeight = Math.min(options.length * 30 + 8, 220);
    const spaceBelow = window.innerHeight - rect.bottom - 8;
    const flipUp = spaceBelow < dropdownHeight;
    setPos({
      top: flipUp ? rect.top - dropdownHeight - 4 : rect.bottom + 4,
      left: rect.left,
      width: rect.width,
    });
  }, [options.length]);

  const selectedLabel = options.find(o => o.value === value)?.label || placeholder;

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={() => { updatePos(); setOpen(!open); }}
        style={{
          ...selectStyle,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.25rem',
          cursor: 'pointer', textAlign: 'left',
        }}
      >
        <span style={{ color: value ? S.text : S.textGhost, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedLabel}</span>
        <svg style={{ width: 10, height: 10, color: S.textFaint, flexShrink: 0, transition: 'transform 0.15s ease', transform: open ? 'rotate(180deg)' : 'none' }}
          fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && createPortal(
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 9998 }} onClick={() => setOpen(false)} />
          <div style={{
            position: 'fixed', zIndex: 9999, top: pos.top, left: pos.left, width: pos.width,
            maxHeight: 220, overflowY: 'auto',
            backgroundColor: 'white', borderRadius: '0.75rem',
            border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
            padding: '0.25rem',
          }}>
            {options.map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => { onChange(opt.value); setOpen(false); }}
                style={{
                  width: '100%', textAlign: 'left', padding: '0.375rem 0.5rem',
                  fontSize: '0.688rem', borderRadius: '0.375rem', border: 'none',
                  backgroundColor: value === opt.value ? S.bgActive : 'transparent',
                  color: value === opt.value ? S.text : S.textMuted,
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.375rem',
                  transition: 'background-color 0.1s ease',
                }}
                onMouseEnter={e => { if (value !== opt.value) e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 5%)'; }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = value === opt.value ? S.bgActive : 'transparent'; }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>,
        document.body
      )}
    </>
  );
}

interface RegressionResult {
  x_field: string;
  y_field: string;
  slope: number;
  intercept: number;
  r_squared: number;
  adj_r_squared: number;
  std_error: number;
  p_value: number;
}

interface DistributionData {
  field: string;
  histogram_bins: number[];
  histogram_counts: number[];
  quartiles: Record<string, number>;
  outliers: number[];
}

interface PivotStatsPanelProps {
  activeStatsTab: 'descriptive' | 'correlation' | 'regression' | 'distribution' | 'tests';
  isOpen: boolean;
  height: number;
  onHeightChange: (h: number) => void;
  onClose: () => void;
  descriptiveStats: DescriptiveStats[];
  correlationResult: CorrelationResult | null;
  distributionData: DistributionData[];
  fields: FieldInfo[];
  regressionX: string;
  setRegressionX: (field: string) => void;
  regressionY: string;
  setRegressionY: (field: string) => void;
  regressionResult: RegressionResult | null;
  regressionLoading: boolean;
  runRegression: () => void;
  selectedTest: string;
  setSelectedTest: (test: string) => void;
  testFieldA: string;
  setTestFieldA: (field: string) => void;
  testFieldB: string;
  setTestFieldB: (field: string) => void;
  testGroupBy: string;
  setTestGroupBy: (field: string) => void;
  testPopulationMean: string;
  setTestPopulationMean: (value: string) => void;
  testResult: StatisticalTestResult | null;
  testLoading: boolean;
  runTest: () => void;
}

const TAB_LABELS: Record<string, string> = {
  descriptive: 'Descriptive',
  correlation: 'Correlation',
  regression: 'Regression',
  distribution: 'Distribution',
  tests: 'Tests',
};

export function PivotStatsPanel({
  activeStatsTab,
  isOpen,
  height,
  onHeightChange,
  onClose,
  descriptiveStats,
  correlationResult,
  distributionData,
  fields,
  regressionX,
  setRegressionX,
  regressionY,
  setRegressionY,
  regressionResult,
  regressionLoading,
  runRegression,
  selectedTest,
  setSelectedTest,
  testFieldA,
  setTestFieldA,
  testFieldB,
  setTestFieldB,
  testGroupBy,
  setTestGroupBy,
  testPopulationMean,
  setTestPopulationMean,
  testResult,
  testLoading,
  runTest,
}: PivotStatsPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    const container = panelRef.current?.parentElement;
    if (!container) return;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const rect = container.getBoundingClientRect();
      const pct = ((rect.bottom - ev.clientY) / rect.height) * 100;
      onHeightChange(Math.max(20, Math.min(85, pct)));
    };
    const onUp = () => {
      dragging.current = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [onHeightChange]);

  return (
    <div
      ref={panelRef}
      className="absolute bottom-0 left-0 right-0 z-30 bg-white flex flex-col shadow-[0_-4px_24px_rgba(0,0,0,0.08)] rounded-t-xl"
      style={{
        height: `${height}%`,
        borderTop: '1px solid hsl(30 3.3% 11.8% / 15%)',
        transform: isOpen ? 'translateY(0)' : 'translateY(100%)',
        transition: dragging.current ? 'none' : 'transform 0.3s ease-out',
      }}
    >
      {/* Header with resize handle */}
      <div className="flex-shrink-0 relative" style={{ height: 44, borderBottom: S.border }}>
        <div
          onMouseDown={onResizeStart}
          className="absolute top-0 left-0 right-0 flex justify-center pt-1.5 cursor-row-resize group z-10"
        >
          <div className="w-8 h-1 rounded-full transition-colors" style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 12%)' }} />
        </div>
        <div className="h-full px-4 flex items-center justify-between">
          <span style={{ fontSize: '0.688rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint }}>{TAB_LABELS[activeStatsTab] || activeStatsTab}</span>
          <button onClick={onClose} className="p-1 rounded transition-colors" style={{ color: S.textGhost }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = S.bgActive; e.currentTarget.style.color = S.textMuted; }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = S.textGhost; }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto overflow-x-auto min-h-0 p-4">
        {activeStatsTab === 'descriptive' && (
          <div>
            {descriptiveStats.length === 0 ? (
              <div style={{ textAlign: 'center', fontSize: '0.688rem', color: S.textGhost, padding: '2rem 0' }}>No numeric fields to analyze</div>
            ) : (
              <table className="w-full" style={{ fontSize: '0.688rem' }}>
                <thead>
                  <tr style={{ borderBottom: S.border }}>
                    {['Field', 'Count', 'Mean', 'Median', 'Std', 'Min', 'Max', 'Q1', 'Q3'].map((h, i) => (
                      <th key={h} style={{ padding: '0.375rem 0.5rem', textAlign: i === 0 ? 'left' : 'right', fontWeight: 600, fontSize: '0.563rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {descriptiveStats.map(stat => (
                    <tr key={stat.field} style={{ borderBottom: S.border }}>
                      <td style={{ padding: '0.375rem 0.5rem', fontWeight: 500, color: S.text, fontFamily: "'SF Mono', monospace" }}>{stat.field}</td>
                      <td style={{ padding: '0.375rem 0.5rem', textAlign: 'right', color: S.textMuted }}>{stat.count ?? '-'}</td>
                      <td style={{ padding: '0.375rem 0.5rem', textAlign: 'right', color: S.textMuted, fontFamily: "'SF Mono', monospace" }}>{stat.mean != null ? stat.mean.toFixed(2) : '-'}</td>
                      <td style={{ padding: '0.375rem 0.5rem', textAlign: 'right', color: S.textMuted, fontFamily: "'SF Mono', monospace" }}>{stat.median != null ? stat.median.toFixed(2) : '-'}</td>
                      <td style={{ padding: '0.375rem 0.5rem', textAlign: 'right', color: S.textMuted, fontFamily: "'SF Mono', monospace" }}>{stat.std != null ? stat.std.toFixed(2) : '-'}</td>
                      <td style={{ padding: '0.375rem 0.5rem', textAlign: 'right', color: S.textMuted, fontFamily: "'SF Mono', monospace" }}>{stat.min != null ? stat.min.toFixed(2) : '-'}</td>
                      <td style={{ padding: '0.375rem 0.5rem', textAlign: 'right', color: S.textMuted, fontFamily: "'SF Mono', monospace" }}>{stat.max != null ? stat.max.toFixed(2) : '-'}</td>
                      <td style={{ padding: '0.375rem 0.5rem', textAlign: 'right', color: S.textMuted, fontFamily: "'SF Mono', monospace" }}>{stat.q1 != null ? stat.q1.toFixed(2) : '-'}</td>
                      <td style={{ padding: '0.375rem 0.5rem', textAlign: 'right', color: S.textMuted, fontFamily: "'SF Mono', monospace" }}>{stat.q3 != null ? stat.q3.toFixed(2) : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
        
        {activeStatsTab === 'correlation' && (
          <div>
            {!correlationResult || correlationResult.fields.length < 2 ? (
              <div style={{ textAlign: 'center', fontSize: '0.688rem', color: S.textGhost, padding: '2rem 0' }}>Need at least 2 numeric fields for correlation</div>
            ) : (
              <table className="w-full" style={{ fontSize: '0.688rem' }}>
                <thead>
                  <tr style={{ borderBottom: S.border }}>
                    <th style={{ padding: '0.375rem 0.5rem' }}></th>
                    {correlationResult.fields.map(field => (
                      <th key={field} style={{ padding: '0.375rem 0.5rem', textAlign: 'center', fontWeight: 600, fontSize: '0.563rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint, maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {field}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {correlationResult.fields.map((field, i) => (
                    <tr key={field} style={{ borderBottom: S.border }}>
                      <td style={{ padding: '0.375rem 0.5rem', fontWeight: 500, color: S.text, fontFamily: "'SF Mono', monospace", maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{field}</td>
                      {correlationResult.matrix[i].map((corr, j) => {
                        const safeCorr = corr ?? 0;
                        const absCorr = Math.abs(safeCorr);
                        const bg = i === j ? S.bgActive :
                          absCorr > 0.7 ? (safeCorr > 0 ? 'hsl(150 40% 92%)' : 'hsl(0 60% 93%)') :
                          absCorr > 0.4 ? (safeCorr > 0 ? 'hsl(150 40% 96%)' : 'hsl(0 60% 97%)') : 'transparent';
                        return (
                          <td key={j} style={{ padding: '0.375rem 0.5rem', textAlign: 'center', backgroundColor: bg, fontFamily: "'SF Mono', monospace", color: S.textMuted }}>
                            {corr != null ? safeCorr.toFixed(2) : '-'}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
        
        {activeStatsTab === 'regression' && (
          <div style={{ display: 'flex', gap: '1.5rem' }}>
            <div style={{ width: '14rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint, marginBottom: '0.25rem' }}>X Variable</div>
                <StatsSelect value={regressionX} onChange={setRegressionX} placeholder="Select field..."
                  options={fields.filter(f => f.can_aggregate).map(f => ({ value: f.name, label: f.name }))} />
              </div>
              <div>
                <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint, marginBottom: '0.25rem' }}>Y Variable</div>
                <StatsSelect value={regressionY} onChange={setRegressionY} placeholder="Select field..."
                  options={fields.filter(f => f.can_aggregate && f.name !== regressionX).map(f => ({ value: f.name, label: f.name }))} />
              </div>
              <button onClick={runRegression} disabled={!regressionX || !regressionY || regressionLoading}
                style={{ ...btnStyle, opacity: (!regressionX || !regressionY || regressionLoading) ? 0.4 : 1, cursor: (!regressionX || !regressionY || regressionLoading) ? 'not-allowed' : 'pointer' }}>
                {regressionLoading ? 'Computing...' : 'Run Regression'}
              </button>
            </div>
            <div style={{ flex: 1 }}>
              {regressionResult ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.813rem', fontWeight: 600, color: S.text, fontFamily: "'SF Mono', monospace" }}>
                      {regressionResult.y_field} = β × {regressionResult.x_field} + α
                    </span>
                    <span style={{ fontSize: '0.625rem', fontWeight: 600, padding: '0.125rem 0.5rem', borderRadius: '0.375rem',
                      backgroundColor: regressionResult.r_squared > 0.7 ? 'hsl(150 40% 92%)' : regressionResult.r_squared > 0.4 ? 'hsl(40 80% 92%)' : S.bgActive,
                      color: regressionResult.r_squared > 0.7 ? 'hsl(150 40% 35%)' : regressionResult.r_squared > 0.4 ? 'hsl(40 80% 35%)' : S.textMuted,
                    }}>
                      R² = {(regressionResult.r_squared * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    {[
                      { label: 'Slope (β)', value: regressionResult.slope.toFixed(4), sub: 'Change in Y per unit X' },
                      { label: 'Intercept (α)', value: regressionResult.intercept.toFixed(4), sub: 'Y when X = 0' },
                      { label: 'R² (Fit)', value: regressionResult.r_squared.toFixed(4), sub: 'Variance explained' },
                      { label: 'P-Value', value: regressionResult.p_value.toFixed(6), sub: regressionResult.p_value < 0.05 ? 'Significant' : 'Not significant' },
                    ].map(card => (
                      <div key={card.label} style={{ padding: '0.75rem', borderRadius: '0.5rem', border: S.border }}>
                        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint }}>{card.label}</div>
                        <div style={{ fontSize: '1rem', fontWeight: 600, fontFamily: "'SF Mono', monospace", color: S.text, marginTop: '0.125rem' }}>{card.value}</div>
                        <div style={{ fontSize: '0.563rem', color: S.textGhost, marginTop: '0.125rem' }}>{card.sub}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: '0.688rem', color: S.textMuted, borderTop: S.border, paddingTop: '0.75rem' }}>
                    For every 1 unit increase in {regressionResult.x_field},{' '}
                    {regressionResult.y_field} changes by {regressionResult.slope > 0 ? '+' : ''}{regressionResult.slope.toFixed(4)} units.
                    The model explains {(regressionResult.r_squared * 100).toFixed(1)}% of the variance.
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: '0.688rem', color: S.textGhost }}>
                  Select X and Y variables to run linear regression
                </div>
              )}
            </div>
          </div>
        )}
        
        {activeStatsTab === 'distribution' && (
          <div className="space-y-4">
            {distributionData.length === 0 ? (
              <div className="text-center text-slate-400 text-xs py-4">No distribution data available</div>
            ) : (
              distributionData.slice(0, 6).map(dist => {
                const maxCount = Math.max(...dist.histogram_counts, 1);
                const totalCount = dist.histogram_counts.reduce((a, b) => a + b, 0);
                const min = dist.histogram_bins[0] ?? 0;
                const max = dist.histogram_bins[dist.histogram_bins.length - 1] ?? 1;
                const range = max - min || 1;
                const q1 = dist.quartiles?.q1 ?? min;
                const q2 = dist.quartiles?.q2 ?? (min + max) / 2;
                const q3 = dist.quartiles?.q3 ?? max;
                const iqr = q3 - q1;
                
                // Calculate positions as percentages
                const q1Pos = ((q1 - min) / range) * 100;
                const q2Pos = ((q2 - min) / range) * 100;
                const q3Pos = ((q3 - min) / range) * 100;
                const boxWidth = q3Pos - q1Pos;
                
                // Determine skewness direction
                const skewDirection = q2 < (q1 + q3) / 2 ? 'left' : q2 > (q1 + q3) / 2 ? 'right' : 'symmetric';
                
                return (
                  <div key={dist.field} className="bg-slate-50 rounded-lg p-3">
                    {/* Header with field name and summary stats */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-700">{dist.field}</span>
                        <span className="text-[10px] text-slate-400">n={totalCount}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {dist.outliers?.length > 0 && (
                          <span className="px-1.5 py-0.5 text-[10px] bg-amber-100 text-amber-700 rounded">
                            {dist.outliers.length} outlier{dist.outliers.length > 1 ? 's' : ''}
                          </span>
                        )}
                        <span className={`px-1.5 py-0.5 text-[10px] rounded ${
                          skewDirection === 'symmetric' ? 'bg-emerald-100 text-emerald-700' :
                          skewDirection === 'left' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                        }`}>
                          {skewDirection === 'symmetric' ? '⟷ Symmetric' : skewDirection === 'left' ? '← Left skew' : '→ Right skew'}
                        </span>
                      </div>
                    </div>
                    
                    {/* Box Plot */}
                    <div className="relative h-6 mb-3">
                      {/* Whisker line (min to max) */}
                      <div className="absolute top-1/2 left-0 right-0 h-px bg-slate-300" style={{ transform: 'translateY(-50%)' }} />
                      {/* Min whisker */}
                      <div className="absolute top-1/2 w-px h-3 bg-slate-400" style={{ left: '0%', transform: 'translate(-50%, -50%)' }} />
                      {/* Max whisker */}
                      <div className="absolute top-1/2 w-px h-3 bg-slate-400" style={{ left: '100%', transform: 'translate(-50%, -50%)' }} />
                      {/* IQR Box (Q1 to Q3) */}
                      <div 
                        className="absolute top-1/2 h-4 bg-indigo-200 border border-indigo-400 rounded-sm"
                        style={{ left: `${q1Pos}%`, width: `${Math.max(boxWidth, 1)}%`, transform: 'translateY(-50%)' }}
                      />
                      {/* Median line */}
                      <div 
                        className="absolute top-1/2 w-0.5 h-5 bg-indigo-600 rounded"
                        style={{ left: `${q2Pos}%`, transform: 'translate(-50%, -50%)' }}
                      />
                      {/* Min/Max labels */}
                      <div className="absolute -bottom-3 left-0 text-[9px] text-slate-400">{min.toFixed(1)}</div>
                      <div className="absolute -bottom-3 right-0 text-[9px] text-slate-400">{max.toFixed(1)}</div>
                    </div>
                    
                    {/* Stats row */}
                    <div className="flex justify-between text-[10px] text-slate-500 mb-2 mt-4 px-1">
                      <div className="text-center">
                        <div className="text-slate-400">Min</div>
                        <div className="font-medium text-slate-600">{min.toFixed(2)}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-slate-400">Q1</div>
                        <div className="font-medium text-slate-600">{q1.toFixed(2)}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-slate-400">Median</div>
                        <div className="font-medium text-indigo-600">{q2.toFixed(2)}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-slate-400">Q3</div>
                        <div className="font-medium text-slate-600">{q3.toFixed(2)}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-slate-400">Max</div>
                        <div className="font-medium text-slate-600">{max.toFixed(2)}</div>
                      </div>
                      <div className="text-center border-l border-slate-200 pl-3">
                        <div className="text-slate-400">IQR</div>
                        <div className="font-medium text-slate-600">{iqr.toFixed(2)}</div>
                      </div>
                    </div>
                    
                    {/* Histogram bars */}
                    <div className="flex items-end gap-px h-12 mt-3">
                      {dist.histogram_counts.map((count, i) => {
                        const height = (count / maxCount) * 100;
                        const pct = ((count / totalCount) * 100).toFixed(1);
                        return (
                          <div
                            key={i}
                            className="flex-1 bg-indigo-400 hover:bg-indigo-500 transition-colors rounded-t cursor-pointer"
                            style={{ height: `${height}%`, minHeight: count > 0 ? '2px' : '0' }}
                            title={`${dist.histogram_bins[i]?.toFixed(2) ?? ''} - ${dist.histogram_bins[i + 1]?.toFixed(2) ?? ''}\nCount: ${count} (${pct}%)`}
                          />
                        );
                      })}
                    </div>
                    
                    {/* X-axis labels */}
                    <div className="flex justify-between mt-1 text-[9px] text-slate-400">
                      <span>{dist.histogram_bins[0]?.toFixed(1) ?? ''}</span>
                      <span className="text-slate-300">|</span>
                      <span>{dist.histogram_bins[Math.floor(dist.histogram_bins.length / 2)]?.toFixed(1) ?? ''}</span>
                      <span className="text-slate-300">|</span>
                      <span>{dist.histogram_bins[dist.histogram_bins.length - 1]?.toFixed(1) ?? ''}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
        
        {activeStatsTab === 'tests' && (
          <div style={{ display: 'flex', gap: '1.5rem' }}>
            <div style={{ width: '14rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint, marginBottom: '0.25rem' }}>Test Type</div>
                <StatsSelect value={selectedTest} onChange={setSelectedTest}
                  options={TEST_OPTIONS.map(opt => ({ value: opt.value, label: opt.label }))} />
              </div>
              <div>
                <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint, marginBottom: '0.25rem' }}>Field A</div>
                <StatsSelect value={testFieldA} onChange={setTestFieldA} placeholder="Select field..."
                  options={fields.filter(f => f.can_aggregate).map(f => ({ value: f.name, label: f.name }))} />
              </div>
              {['ttest_two', 'ttest_paired', 'chi_square_independence'].includes(selectedTest) && (
                <div>
                  <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint, marginBottom: '0.25rem' }}>Field B</div>
                  <StatsSelect value={testFieldB} onChange={setTestFieldB} placeholder="Select field..."
                    options={fields.filter(f => f.can_aggregate && f.name !== testFieldA).map(f => ({ value: f.name, label: f.name }))} />
                </div>
              )}
              {selectedTest === 'anova_one' && (
                <div>
                  <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint, marginBottom: '0.25rem' }}>Group By</div>
                  <StatsSelect value={testGroupBy} onChange={setTestGroupBy} placeholder="Select field..."
                    options={fields.filter(f => f.can_group).map(f => ({ value: f.name, label: f.name }))} />
                </div>
              )}
              {selectedTest === 'ttest_one' && (
                <div>
                  <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint, marginBottom: '0.25rem' }}>Population Mean</div>
                  <input type="number" value={testPopulationMean} onChange={e => setTestPopulationMean(e.target.value)}
                    style={{ ...selectStyle }} />
                </div>
              )}
              <button onClick={runTest} disabled={!testFieldA || testLoading}
                style={{ ...btnStyle, opacity: (!testFieldA || testLoading) ? 0.4 : 1, cursor: (!testFieldA || testLoading) ? 'not-allowed' : 'pointer' }}>
                {testLoading ? 'Running...' : 'Run Test'}
              </button>
            </div>
            <div style={{ flex: 1 }}>
              {testResult ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.813rem', fontWeight: 600, color: S.text }}>{testResult.test_name}</span>
                    <span style={{ fontSize: '0.625rem', fontWeight: 600, padding: '0.125rem 0.5rem', borderRadius: '0.375rem',
                      backgroundColor: testResult.significant_at_01 ? 'hsl(0 60% 93%)' : testResult.significant_at_05 ? 'hsl(40 80% 92%)' : 'hsl(150 40% 92%)',
                      color: testResult.significant_at_01 ? 'hsl(0 60% 40%)' : testResult.significant_at_05 ? 'hsl(40 80% 35%)' : 'hsl(150 40% 35%)',
                    }}>
                      {testResult.significant_at_01 ? 'Highly Significant (p < 0.01)' :
                       testResult.significant_at_05 ? 'Significant (p < 0.05)' :
                       'Not Significant'}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    <div style={{ padding: '0.75rem', borderRadius: '0.5rem', border: S.border }}>
                      <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint }}>Test Statistic</div>
                      <div style={{ fontSize: '1rem', fontWeight: 600, fontFamily: "'SF Mono', monospace", color: S.text, marginTop: '0.125rem' }}>{testResult.statistic != null ? testResult.statistic.toFixed(4) : '-'}</div>
                    </div>
                    <div style={{ padding: '0.75rem', borderRadius: '0.5rem', border: S.border }}>
                      <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint }}>P-Value</div>
                      <div style={{ fontSize: '1rem', fontWeight: 600, fontFamily: "'SF Mono', monospace", color: S.text, marginTop: '0.125rem' }}>{testResult.p_value != null ? testResult.p_value.toFixed(6) : '-'}</div>
                    </div>
                    {testResult.degrees_of_freedom != null && (
                      <div style={{ padding: '0.75rem', borderRadius: '0.5rem', border: S.border }}>
                        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: S.textFaint }}>Degrees of Freedom</div>
                        <div style={{ fontSize: '1rem', fontWeight: 600, fontFamily: "'SF Mono', monospace", color: S.text, marginTop: '0.125rem' }}>{testResult.degrees_of_freedom.toFixed(1)}</div>
                      </div>
                    )}
                  </div>
                  <div style={{ fontSize: '0.688rem', color: S.textMuted, borderTop: S.border, paddingTop: '0.75rem' }}>
                    {testResult.interpretation}
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: '0.688rem', color: S.textGhost }}>
                  Configure and run a test to see results
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
