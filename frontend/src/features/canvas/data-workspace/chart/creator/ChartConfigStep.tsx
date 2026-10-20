import { useState, useRef, useCallback, useEffect } from 'react';
import { C, sectionHeader, mono } from './tokens';
import { ChartField, ChartConfigState, OHLCConfig, MatrixConfig } from './types';

interface Props {
  fields: ChartField[];
  config: ChartConfigState;
  setConfig: React.Dispatch<React.SetStateAction<ChartConfigState>>;
  loadingFields: boolean;
  xAxisLabel?: string;
  yAxisLabel?: string;
  onXAxisLabelChange?: (v: string) => void;
  onYAxisLabelChange?: (v: string) => void;
  chartTitle?: string;
  onChartTitleChange?: (v: string) => void;
  filterFields?: string[];
  onAddFilter?: (field: string) => void;
  onRemoveFilter?: (field: string) => void;
  filters?: { id: string; field: string; filterType: string; minValue?: string | number; maxValue?: string | number }[];
  onUpdateFilter?: (field: string, patch: { minValue?: string | number; maxValue?: string | number }) => void;
  xAxisRange?: [number | string | null, number | string | null];
  yAxisRange?: [number | string | null, number | string | null];
  onXAxisRangeChange?: (range: [number | string | null, number | string | null] | undefined) => void;
  onYAxisRangeChange?: (range: [number | string | null, number | string | null] | undefined) => void;
}

type ChartType = 'line' | 'area' | 'bar' | 'pie' | 'scatter' | 'bubble' | 'box' | 'violin' | 'radar' | 'histogram' | 'scatter3d' | 'surface3d' | 'candlestick' | 'heatmap' | 'scatterMatrix' | 'dotPlot';

function detectOHLCFields(fields: ChartField[]): OHLCConfig | null {
  const findField = (variants: string[]) => {
    for (const variant of variants) {
      const found = fields.find(f => f.name.toLowerCase() === variant);
      if (found) return found.name;
    }
    return '';
  };
  const dateField = findField(['date', 'timestamp', 'time', 'datetime']);
  const openField = findField(['open', 'o', 'openprice', 'open_price']);
  const highField = findField(['high', 'h', 'highprice', 'high_price']);
  const lowField = findField(['low', 'l', 'lowprice', 'low_price']);
  const closeField = findField(['close', 'c', 'closeprice', 'close_price', 'adjclose', 'adj_close']);
  const volumeField = findField(['volume', 'vol', 'v']);
  if (dateField && openField && highField && lowField && closeField) {
    return { dateField, openField, highField, lowField, closeField, volumeField: volumeField || undefined };
  }
  return null;
}

const CHART_TYPES: { id: ChartType; name: string; icon: React.ReactNode }[] = [
  { id: 'line', name: 'Line', icon: <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M7 12l3-3 3 3 4-4" /></svg> },
  { id: 'area', name: 'Area', icon: <svg style={{ width: 14, height: 14 }} fill="currentColor" viewBox="0 0 24 24"><path d="M3 19V5l4 8 5-6 5 4 4-6v14H3z" opacity="0.3" /><path d="M3 19V5l4 8 5-6 5 4 4-6" fill="none" stroke="currentColor" strokeWidth="2" /></svg> },
  { id: 'bar', name: 'Bar', icon: <svg style={{ width: 14, height: 14 }} fill="currentColor" viewBox="0 0 24 24"><rect x="4" y="14" width="3" height="6" /><rect x="9" y="10" width="3" height="10" /><rect x="14" y="6" width="3" height="14" /><rect x="19" y="8" width="3" height="12" /></svg> },
  { id: 'pie', name: 'Pie', icon: <svg style={{ width: 14, height: 14 }} fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8v8l5.66 5.66C14.54 19.08 13.32 20 12 20z" /></svg> },
  { id: 'scatter', name: 'Scatter', icon: <svg style={{ width: 14, height: 14 }} fill="currentColor" viewBox="0 0 24 24"><circle cx="6" cy="18" r="1.5" /><circle cx="10" cy="10" r="1.5" /><circle cx="14" cy="14" r="1.5" /><circle cx="18" cy="6" r="1.5" /></svg> },
  { id: 'bubble', name: 'Bubble', icon: <svg style={{ width: 14, height: 14 }} fill="currentColor" viewBox="0 0 24 24"><circle cx="7" cy="17" r="3" opacity="0.7" /><circle cx="12" cy="9" r="5" opacity="0.7" /><circle cx="18" cy="15" r="2" opacity="0.7" /></svg> },
  { id: 'box', name: 'Box', icon: <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><rect x="6" y="8" width="4" height="8" fill="currentColor" opacity="0.3" /><rect x="6" y="8" width="4" height="8" /><line x1="8" y1="4" x2="8" y2="8" /><line x1="8" y1="16" x2="8" y2="20" /></svg> },
  { id: 'violin', name: 'Violin', icon: <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path d="M8 4 Q4 8 4 12 Q4 16 8 20 Q12 16 12 12 Q12 8 8 4" fill="currentColor" opacity="0.3" /><path d="M8 4 Q4 8 4 12 Q4 16 8 20 Q12 16 12 12 Q12 8 8 4" /></svg> },
  { id: 'radar', name: 'Radar', icon: <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" fill="currentColor" opacity="0.2" /><polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" /></svg> },
  { id: 'histogram', name: 'Histogram', icon: <svg style={{ width: 14, height: 14 }} fill="currentColor" viewBox="0 0 24 24"><rect x="2" y="14" width="4" height="6" /><rect x="7" y="8" width="4" height="12" /><rect x="12" y="4" width="4" height="16" /><rect x="17" y="10" width="4" height="10" /></svg> },
  { id: 'scatter3d', name: '3D Scatter', icon: <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" /><circle cx="12" cy="8" r="1.5" fill="currentColor" /></svg> },
  { id: 'candlestick', name: 'OHLC', icon: <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path d="M4 8h2v8H4zM9 6h2v12H9zM14 4h2v16h-2zM19 7h2v10h-2z" /></svg> },
  { id: 'heatmap', name: 'Heatmap', icon: <svg style={{ width: 14, height: 14 }} fill="currentColor" viewBox="0 0 24 24"><rect x="2" y="2" width="6" height="6" opacity="0.3" /><rect x="9" y="2" width="6" height="6" opacity="0.6" /><rect x="16" y="2" width="6" height="6" opacity="0.9" /><rect x="2" y="9" width="6" height="6" opacity="0.5" /><rect x="9" y="9" width="6" height="6" opacity="0.8" /><rect x="16" y="9" width="6" height="6" opacity="0.4" /></svg> },
  { id: 'surface3d', name: 'Surface', icon: <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M2 20L12 4l10 16" /><path strokeLinecap="round" strokeLinejoin="round" d="M4 16l8-8 8 8" opacity="0.5" /></svg> },
  { id: 'scatterMatrix', name: 'Matrix', icon: <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><rect x="2" y="2" width="6" height="6" rx="0.5" opacity="0.3" fill="currentColor" /><rect x="9" y="2" width="6" height="6" rx="0.5" /><rect x="2" y="9" width="6" height="6" rx="0.5" /><rect x="9" y="9" width="6" height="6" rx="0.5" opacity="0.3" fill="currentColor" /></svg> },
  { id: 'dotPlot', name: 'Dot Plot', icon: <svg style={{ width: 14, height: 14 }} fill="currentColor" viewBox="0 0 24 24"><circle cx="10" cy="8" r="1.5" /><circle cx="9" cy="12" r="1.5" /><circle cx="11" cy="10" r="1.5" /><circle cx="17" cy="6" r="1.5" /></svg> },
];

const HINTS: Record<string, string> = {
  histogram: 'Add numeric fields to Y-Series for distribution analysis.',
  scatter3d: '3D scatter requires X, Y, and Z axes.',
  candlestick: 'Requires Date, Open, High, Low, Close. Volume optional.',
  heatmap: 'Needs categorical X/Y and numeric Z. Best for correlation matrices.',
  surface3d: 'Needs X, Y, Z numeric fields. Ideal for volatility surfaces.',
  scatterMatrix: 'Requires 2+ numeric Y-series for pairwise relationships.',
  dotPlot: 'Shows individual data points per category.',
};

function ChartTypeDropdown({ value, onChange, hint, chartTitle, onChartTitleChange }: {
  value: ChartType;
  onChange: (type: ChartType) => void;
  hint?: string;
  chartTitle?: string;
  onChartTitleChange?: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = CHART_TYPES.find(t => t.id === value) || CHART_TYPES[0];
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showTopFade, setShowTopFade] = useState(false);
  const [showBottomFade, setShowBottomFade] = useState(false);

  const updateFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setShowTopFade(el.scrollTop > 2);
    setShowBottomFade(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
  }, []);

  useEffect(() => {
    if (open) requestAnimationFrame(updateFades);
  }, [open, updateFades]);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.375rem', marginBottom: '0.375rem' }}>
        <div style={sectionHeader}>Chart Type</div>
        {onChartTitleChange && (
          <input
            type="text"
            value={chartTitle || ''}
            onChange={e => onChartTitleChange(e.target.value)}
            placeholder="title"
            style={{
              flex: 1, minWidth: 0, padding: 0, fontSize: '0.5rem',
              border: 'none', outline: 'none',
              color: C.textFaint, backgroundColor: 'transparent',
              fontStyle: chartTitle ? 'normal' : 'italic',
              letterSpacing: '0.02em',
            }}
          />
        )}
      </div>
      <div>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          style={{
            width: '100%',
            height: 30,
            padding: '0.3rem 0.625rem',
            fontSize: '0.688rem',
            fontWeight: 500,
            textAlign: 'left' as const,
            border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
            borderRadius: '0.5rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            color: C.text,
            backgroundColor: 'white',
            cursor: 'pointer',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', color: C.textMuted }}>{selected.icon}</span>
          <span style={{ flex: 1 }}>{selected.name}</span>
          <svg
            style={{ width: 10, height: 10, color: C.textFaint, flexShrink: 0, transition: 'transform 0.15s ease', transform: open ? 'rotate(180deg)' : 'none' }}
            fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {open && (
          <div style={{
            marginTop: 4,
            backgroundColor: 'white',
            borderRadius: '0.75rem',
            border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
            position: 'relative',
            overflow: 'hidden',
          }}>
            {showTopFade && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 24, background: 'linear-gradient(to bottom, white, transparent)', zIndex: 1, pointerEvents: 'none', borderRadius: '0.75rem 0.75rem 0 0' }} />}
            <div
              ref={scrollRef}
              onScroll={updateFades}
              style={{
                maxHeight: 180,
                overflowY: 'auto',
                padding: '0.25rem',
              }}
            >
              {CHART_TYPES.map((type) => {
                const isSelected = value === type.id;
                return (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() => { onChange(type.id); setOpen(false); }}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.375rem 0.5rem',
                      fontSize: '0.688rem',
                      border: 'none',
                      borderRadius: '0.375rem',
                      backgroundColor: isSelected ? C.bgActive : 'transparent',
                      color: isSelected ? C.text : C.textMuted,
                      cursor: 'pointer',
                      textAlign: 'left' as const,
                    }}
                    onMouseEnter={e => { if (!isSelected) e.currentTarget.style.backgroundColor = C.bgHover; }}
                    onMouseLeave={e => { e.currentTarget.style.backgroundColor = isSelected ? C.bgActive : 'transparent'; }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>{type.icon}</span>
                    <span style={{ fontWeight: isSelected ? 600 : 400 }}>{type.name}</span>
                  </button>
                );
              })}
            </div>
            {showBottomFade && <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 24, background: 'linear-gradient(to top, white, transparent)', zIndex: 1, pointerEvents: 'none', borderRadius: '0 0 0.75rem 0.75rem' }} />}
          </div>
        )}
      </div>
      {hint && (
        <div style={{ fontSize: '0.563rem', color: C.textFaint, padding: '0.25rem 0', marginTop: '0.25rem' }}>{hint}</div>
      )}
    </div>
  );
}

export default function ChartConfigStep({ fields, config, setConfig, loadingFields, xAxisLabel, yAxisLabel, onXAxisLabelChange, onYAxisLabelChange, chartTitle, onChartTitleChange, filterFields, onAddFilter, onRemoveFilter, filters, onUpdateFilter, xAxisRange, yAxisRange, onXAxisRangeChange, onYAxisRangeChange }: Props) {
  if (loadingFields) {
    return (
      <div style={{ textAlign: 'center', padding: '1rem 0' }}>
        <svg className="w-4 h-4 animate-spin mx-auto" style={{ color: C.textMuted }} fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <div style={{ fontSize: '0.563rem', color: C.textFaint, marginTop: '0.375rem' }}>Analyzing fields...</div>
      </div>
    );
  }

  const showXAxis = config.chartType !== 'histogram' && config.chartType !== 'candlestick' && config.chartType !== 'heatmap' && config.chartType !== 'surface3d';
  const showZAxis = config.chartType === 'scatter3d';
  const isCandlestick = config.chartType === 'candlestick';
  const isMatrixChart = config.chartType === 'heatmap' || config.chartType === 'surface3d';

  const handleChartTypeChange = (type: ChartType) => {
    if (type === 'candlestick') {
      const detected = detectOHLCFields(fields);
      setConfig((prev) => ({
        ...prev, chartType: type, zAxis: undefined, matrix: undefined,
        ohlc: detected || prev.ohlc || { dateField: '', openField: '', highField: '', lowField: '', closeField: '' },
        xAxis: detected?.dateField || 'date',
        ySeries: [{ field: detected?.closeField || 'close' }],
      }));
    } else if (type === 'heatmap' || type === 'surface3d') {
      const numericFields = fields.filter(f => f.type === 'numeric');
      const categoricalFields = fields.filter(f => f.type === 'categorical' || f.type === 'datetime');
      let xField = '', yField = '', zField = '';
      if (categoricalFields.length === 2 && numericFields.length === 1) {
        xField = categoricalFields[0].name; yField = categoricalFields[1].name; zField = numericFields[0].name;
      } else if (categoricalFields.length === 1 && numericFields.length === 1) {
        xField = categoricalFields[0].name; yField = categoricalFields[0].name; zField = numericFields[0].name;
      } else {
        xField = categoricalFields[0]?.name || numericFields[0]?.name || '';
        yField = categoricalFields[1]?.name || categoricalFields[0]?.name || numericFields[1]?.name || '';
        zField = numericFields[0]?.name || '';
      }
      setConfig((prev) => ({
        ...prev, chartType: type, zAxis: undefined, ohlc: undefined,
        matrix: prev.matrix || { xField, yField, zField },
        xAxis: xField, ySeries: [{ field: zField }],
      }));
    } else {
      setConfig((prev) => ({
        ...prev, chartType: type,
        zAxis: type === 'scatter3d' ? prev.zAxis : undefined,
        ohlc: undefined, matrix: undefined,
      }));
    }
  };

  const hint = HINTS[config.chartType];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Chart type dropdown */}
      <ChartTypeDropdown
        value={config.chartType}
        onChange={handleChartTypeChange}
        hint={hint}
        chartTitle={chartTitle}
        onChartTitleChange={onChartTitleChange}
      />

      {/* Type-specific config */}
      {isCandlestick ? (
        <OHLCFieldMapping
          fields={fields}
          ohlc={config.ohlc || { dateField: '', openField: '', highField: '', lowField: '', closeField: '' }}
          onChange={(ohlc) => setConfig((prev) => ({ ...prev, ohlc, xAxis: ohlc.dateField, ySeries: [{ field: ohlc.closeField }] }))}
        />
      ) : isMatrixChart ? (
        <MatrixFieldMapping
          fields={fields}
          matrix={config.matrix || { xField: '', yField: '', zField: '' }}
          chartType={config.chartType}
          onChange={(matrix) => setConfig((prev) => ({ ...prev, matrix, xAxis: matrix.xField, ySeries: [{ field: matrix.zField }] }))}
        />
      ) : (
        <>
          <FieldsList fields={fields} config={config} setConfig={setConfig} showZAxis={showZAxis} />
          <div style={{ fontSize: '0.5rem', color: C.textFaint, display: 'flex', gap: '0.5rem' }}>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Numeric</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-blue-500" /> Date</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Text</span>
          </div>
          <AxisDropZones
            config={config} setConfig={setConfig} showXAxis={showXAxis} showZAxis={showZAxis}
            xAxisLabel={xAxisLabel} yAxisLabel={yAxisLabel}
            onXAxisLabelChange={onXAxisLabelChange} onYAxisLabelChange={onYAxisLabelChange}
            filters={filters} onUpdateFilter={onUpdateFilter}
            xAxisRange={xAxisRange} yAxisRange={yAxisRange}
            onXAxisRangeChange={onXAxisRangeChange} onYAxisRangeChange={onYAxisRangeChange}
            xIsDate={fields.some(f => f.name === config.xAxis && f.type === 'datetime')}
          />
          {onAddFilter && onRemoveFilter && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <DropZone
                label="Filters"
                items={filterFields || []}
                onDrop={f => { if (!(filterFields || []).includes(f)) onAddFilter(f); }}
                onRemove={onRemoveFilter}
              />
              {filters && filters.length > 0 && onUpdateFilter && filters.map(f => (
                <div key={f.field} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', paddingLeft: '0.25rem' }}>
                  <span style={{ fontSize: '0.5rem', color: C.textGhost, flexShrink: 0, fontFamily: mono, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '4rem' }}>{f.field}</span>
                  <RangeRow value={f.minValue} onChange={v => onUpdateFilter(f.field, { minValue: v ?? undefined })} isDate={f.filterType === 'date_range'} placeholder="min" />
                  <span style={{ fontSize: '0.5rem', color: C.textGhost }}>–</span>
                  <RangeRow value={f.maxValue} onChange={v => onUpdateFilter(f.field, { maxValue: v ?? undefined })} isDate={f.filterType === 'date_range'} placeholder="max" />
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ============================================================================
// Field Scroll List with edge fades
// ============================================================================

function FieldScrollList({ children }: { children: React.ReactNode }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showTopFade, setShowTopFade] = useState(false);
  const [showBottomFade, setShowBottomFade] = useState(false);

  const updateFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setShowTopFade(el.scrollTop > 2);
    setShowBottomFade(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
  }, []);

  useEffect(() => { requestAnimationFrame(updateFades); }, [children, updateFades]);

  return (
    <div style={{ position: 'relative', overflow: 'hidden', maxHeight: '8rem' }}>
      {showTopFade && <div className="absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white to-transparent z-10 pointer-events-none" />}
      <div ref={scrollRef} onScroll={updateFades} style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem', padding: '0.25rem 0.375rem', maxHeight: '8rem', overflowY: 'auto' }}>
        {children}
      </div>
      {showBottomFade && <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-white to-transparent z-10 pointer-events-none" />}
    </div>
  );
}

// ============================================================================
// Fields List (per-source collapsible sections)
// ============================================================================

function FieldsList({ fields, config, setConfig, showZAxis }: {
  fields: ChartField[];
  config: ChartConfigState;
  setConfig: React.Dispatch<React.SetStateAction<ChartConfigState>>;
  showZAxis: boolean;
}) {
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set(['_all']));

  const fieldsBySource = fields.reduce<Record<string, ChartField[]>>((acc, f) => {
    const key = f.source || '_all';
    if (!acc[key]) acc[key] = [];
    acc[key].push(f);
    return acc;
  }, {});

  const sources = Object.keys(fieldsBySource);

  const getFieldZone = (name: string): string | null => {
    if (config.xAxis === name) return 'X';
    if (config.ySeries.some(s => s.field === name)) return 'Y';
    if (config.zAxis === name) return 'Z';
    return null;
  };

  const toggleField = (field: ChartField) => {
    const zone = getFieldZone(field.name);
    if (zone === 'X') { setConfig(p => ({ ...p, xAxis: '' })); return; }
    if (zone === 'Y') { setConfig(p => ({ ...p, ySeries: p.ySeries.filter(s => s.field !== field.name) })); return; }
    if (zone === 'Z') { setConfig(p => ({ ...p, zAxis: undefined })); return; }

    const needsXAxis = config.chartType !== 'histogram' && !config.xAxis;
    const needsZAxis = showZAxis && !config.zAxis && config.ySeries.length >= 1;

    if (needsXAxis && field.type !== 'numeric') { setConfig(p => ({ ...p, xAxis: field.name })); }
    else if (needsXAxis && config.ySeries.length === 0) { setConfig(p => ({ ...p, xAxis: field.name })); }
    else if (needsZAxis && field.type === 'numeric') { setConfig(p => ({ ...p, zAxis: field.name })); }
    else if (field.type === 'numeric') { setConfig(p => ({ ...p, ySeries: [...p.ySeries, { field: field.name }] })); }
    else if (!config.xAxis && config.chartType !== 'histogram') { setConfig(p => ({ ...p, xAxis: field.name })); }
  };

  const toggleSource = (key: string) => {
    setExpandedSources(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  if (sources.length === 1 && sources[0] === '_all') {
    return (
      <div>
        <div style={{ ...sectionHeader, marginBottom: '0.25rem' }}>Fields</div>
        <div style={{ border: C.border, borderRadius: '0.5rem', overflow: 'hidden' }}>
          <FieldScrollList>
            {fields.map(field => {
              const zone = getFieldZone(field.name);
              return (
                <FieldRow key={field.name} field={field} zone={zone} onToggle={() => toggleField(field)}
                  onDragStart={e => e.dataTransfer.setData('field', JSON.stringify({ name: field.name, type: field.type }))} />
              );
            })}
          </FieldScrollList>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ ...sectionHeader, marginBottom: '0.25rem' }}>Fields</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {sources.map(source => {
          const isExpanded = expandedSources.has(source);
          const sourceFields = fieldsBySource[source];
          return (
            <div key={source} style={{ border: C.border, borderRadius: '0.5rem', overflow: 'hidden' }}>
              <div
                onClick={() => toggleSource(source)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.375rem',
                  padding: '0.375rem 0.5rem', backgroundColor: C.bgSubtle,
                  cursor: 'pointer', fontSize: '0.625rem', fontWeight: 600, color: C.text,
                }}
              >
                <svg
                  style={{ width: 8, height: 8, flexShrink: 0, transition: 'transform 0.15s ease', transform: isExpanded ? 'rotate(90deg)' : 'none' }}
                  fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: mono }}>{source}</span>
                <span style={{ fontSize: '0.5rem', fontWeight: 400, color: C.textFaint }}>({sourceFields.length})</span>
              </div>
              {isExpanded && (
                <FieldScrollList>
                  {sourceFields.map(field => {
                    const zone = getFieldZone(field.name);
                    return (
                      <FieldRow key={field.name} field={field} zone={zone} onToggle={() => toggleField(field)}
                        onDragStart={e => e.dataTransfer.setData('field', JSON.stringify({ name: field.name, type: field.type }))} />
                    );
                  })}
                </FieldScrollList>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FieldRow({ field, zone, onToggle, onDragStart }: {
  field: ChartField; zone: string | null;
  onToggle: () => void; onDragStart: (e: React.DragEvent) => void;
}) {
  const dotColor = field.type === 'numeric' ? 'bg-emerald-500' : field.type === 'datetime' ? 'bg-blue-500' : 'bg-amber-500';
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onToggle}
      style={{
        padding: '0.375rem 0.5rem', fontSize: '0.688rem',
        display: 'flex', alignItems: 'center', gap: '0.375rem',
        borderRadius: '0.5rem',
        border: zone ? C.borderSel : '0.5px solid transparent',
        backgroundColor: zone ? C.bgActive : 'transparent',
        color: zone ? C.text : C.textMuted,
        cursor: 'pointer', transition: 'all 0.1s ease',
      }}
      onMouseEnter={e => { if (!zone) e.currentTarget.style.backgroundColor = C.bgHover; }}
      onMouseLeave={e => { e.currentTarget.style.backgroundColor = zone ? C.bgActive : 'transparent'; }}
    >
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: mono }}>{field.name}</span>
      {zone ? (
        <span style={{ fontSize: '0.5rem', fontWeight: 600, padding: '0.0625rem 0.25rem', borderRadius: '0.25rem', backgroundColor: C.bgActive, border: C.borderSel, color: C.textMuted, flexShrink: 0 }}>{zone}</span>
      ) : (
        <span style={{ fontSize: '0.563rem', color: C.textGhost, flexShrink: 0 }}>{field.type === 'numeric' ? '#' : field.type === 'datetime' ? '@' : 'Abc'}</span>
      )}
    </div>
  );
}

// ============================================================================
// Drop Zone (matches PivotTableCreator DropZone)
// ============================================================================

function DropZone({ label, items, onDrop, onRemove, axisLabel, onAxisLabelChange }: {
  label: string; items: string[];
  onDrop: (fieldName: string) => void; onRemove: (fieldName: string) => void;
  axisLabel?: string; onAxisLabelChange?: (v: string) => void;
}) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.375rem', marginBottom: '0.25rem' }}>
        <div style={sectionHeader}>{label}</div>
        {onAxisLabelChange && (
          <input
            type="text"
            value={axisLabel || ''}
            onChange={e => onAxisLabelChange(e.target.value)}
            placeholder="label"
            style={{
              flex: 1, minWidth: 0, padding: 0, fontSize: '0.5rem',
              border: 'none', outline: 'none',
              color: C.textFaint, backgroundColor: 'transparent',
              fontStyle: axisLabel ? 'normal' : 'italic',
              letterSpacing: '0.02em',
            }}
          />
        )}
      </div>
      <div
        style={{ border: '0.5px dashed hsl(30 3.3% 11.8% / 15%)', borderRadius: '0.5rem', backgroundColor: C.bgSubtle, minHeight: '1.75rem', padding: '0.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.25rem', transition: 'all 0.1s ease' }}
        onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 30%)'; e.currentTarget.style.backgroundColor = C.bgActive; }}
        onDragLeave={e => { e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 15%)'; e.currentTarget.style.backgroundColor = C.bgSubtle; }}
        onDrop={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'hsl(30 3.3% 11.8% / 15%)'; e.currentTarget.style.backgroundColor = C.bgSubtle; try { onDrop(JSON.parse(e.dataTransfer.getData('field')).name); } catch {} }}
      >
        {items.map(item => (
          <span key={item} style={{ padding: '0.125rem 0.375rem', backgroundColor: 'white', border: '0.5px solid hsl(30 3.3% 11.8% / 12%)', borderRadius: '0.25rem', fontSize: '0.563rem', color: C.text, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            {item}
            <button onClick={() => onRemove(item)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textGhost, fontSize: '0.625rem', padding: 0, lineHeight: 1 }}
              onMouseEnter={e => { e.currentTarget.style.color = 'hsl(0 70% 50%)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = C.textGhost; }}>×</button>
          </span>
        ))}
        {items.length === 0 && <span style={{ fontSize: '0.563rem', color: C.textGhost, padding: '0.125rem 0.25rem' }}>Drag fields here</span>}
      </div>
    </div>
  );
}

// ============================================================================
// Axis Drop Zones
// ============================================================================

function RangeRow({ value, onChange, isDate, placeholder }: {
  value?: number | string | null;
  onChange: (v: number | string | null) => void;
  isDate?: boolean;
  placeholder: string;
}) {
  return (
    <input
      type={isDate ? 'date' : 'number'}
      value={value ?? ''}
      onChange={e => {
        const v = e.target.value;
        if (!v) { onChange(null); return; }
        if (isDate) { onChange(v); return; }
        const n = parseFloat(v);
        onChange(Number.isNaN(n) ? null : n);
      }}
      placeholder={placeholder}
      className="[&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none [appearance:textfield]"
      style={{
        flex: 1, minWidth: 0, padding: '0.125rem 0.25rem', fontSize: '0.5rem',
        border: C.border, borderRadius: '0.25rem', outline: 'none',
        color: C.text, backgroundColor: 'white', fontFamily: mono,
      }}
    />
  );
}

function InlineRange({ label, range, onChange, isDate }: {
  label: string;
  range?: [number | string | null, number | string | null];
  onChange: (range: [number | string | null, number | string | null] | undefined) => void;
  isDate?: boolean;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', paddingLeft: '0.25rem' }}>
      <span style={{ fontSize: '0.5rem', color: C.textGhost, flexShrink: 0 }}>{label}</span>
      <RangeRow value={range?.[0]} onChange={v => onChange([v, range?.[1] ?? null])} isDate={isDate} placeholder="min" />
      <span style={{ fontSize: '0.5rem', color: C.textGhost }}>–</span>
      <RangeRow value={range?.[1]} onChange={v => onChange([range?.[0] ?? null, v])} isDate={isDate} placeholder="max" />
    </div>
  );
}

function AxisDropZones({ config, setConfig, showXAxis, showZAxis, xAxisLabel, yAxisLabel, onXAxisLabelChange, onYAxisLabelChange, filters, onUpdateFilter, xAxisRange, yAxisRange, onXAxisRangeChange, onYAxisRangeChange, xIsDate }: {
  config: ChartConfigState;
  setConfig: React.Dispatch<React.SetStateAction<ChartConfigState>>;
  showXAxis: boolean; showZAxis: boolean;
  xAxisLabel?: string; yAxisLabel?: string;
  onXAxisLabelChange?: (v: string) => void; onYAxisLabelChange?: (v: string) => void;
  filters?: { id: string; field: string; filterType: string; minValue?: string | number; maxValue?: string | number }[];
  onUpdateFilter?: (field: string, patch: { minValue?: string | number; maxValue?: string | number }) => void;
  xAxisRange?: [number | string | null, number | string | null];
  yAxisRange?: [number | string | null, number | string | null];
  onXAxisRangeChange?: (range: [number | string | null, number | string | null] | undefined) => void;
  onYAxisRangeChange?: (range: [number | string | null, number | string | null] | undefined) => void;
  xIsDate?: boolean;
}) {
  const xFields = config.xAxis ? [config.xAxis] : [];
  const yFields = config.ySeries.map(s => s.field);
  const xFilters = (filters || []).filter(f => xFields.includes(f.field));
  const yFilters = (filters || []).filter(f => yFields.includes(f.field));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {showXAxis && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <DropZone
            label={showZAxis ? 'X-Axis (width)' : 'X-Axis'}
            items={xFields}
            onDrop={f => setConfig(p => ({ ...p, xAxis: f }))}
            onRemove={() => setConfig(p => ({ ...p, xAxis: '' }))}
            axisLabel={xAxisLabel}
            onAxisLabelChange={onXAxisLabelChange}
          />
          {xFilters.length > 0 && onUpdateFilter && xFilters.map(f => (
            <div key={f.field} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', paddingLeft: '0.25rem' }}>
              <span style={{ fontSize: '0.5rem', color: C.textGhost, flexShrink: 0 }}>filter</span>
              <RangeRow value={f.minValue} onChange={v => onUpdateFilter(f.field, { minValue: v ?? undefined })} isDate={f.filterType === 'date_range'} placeholder="min" />
              <span style={{ fontSize: '0.5rem', color: C.textGhost }}>–</span>
              <RangeRow value={f.maxValue} onChange={v => onUpdateFilter(f.field, { maxValue: v ?? undefined })} isDate={f.filterType === 'date_range'} placeholder="max" />
            </div>
          ))}
          {onXAxisRangeChange && (
            <InlineRange label="range" range={xAxisRange} onChange={onXAxisRangeChange} isDate={xIsDate} />
          )}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <DropZone
          label={config.chartType === 'histogram' ? 'Values' : showZAxis ? 'Y-Axis (height)' : 'Y-Series'}
          items={yFields}
          onDrop={f => { if (!config.ySeries.some(s => s.field === f)) setConfig(p => ({ ...p, ySeries: [...p.ySeries, { field: f }] })); }}
          onRemove={f => setConfig(p => ({ ...p, ySeries: p.ySeries.filter(s => s.field !== f) }))}
          axisLabel={yAxisLabel}
          onAxisLabelChange={onYAxisLabelChange}
        />
        {yFilters.length > 0 && onUpdateFilter && yFilters.map(f => (
          <div key={f.field} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', paddingLeft: '0.25rem' }}>
            <span style={{ fontSize: '0.5rem', color: C.textGhost, flexShrink: 0 }}>{f.field}</span>
            <RangeRow value={f.minValue} onChange={v => onUpdateFilter(f.field, { minValue: v ?? undefined })} isDate={f.filterType === 'date_range'} placeholder="min" />
            <span style={{ fontSize: '0.5rem', color: C.textGhost }}>–</span>
            <RangeRow value={f.maxValue} onChange={v => onUpdateFilter(f.field, { maxValue: v ?? undefined })} isDate={f.filterType === 'date_range'} placeholder="max" />
          </div>
        ))}
        {onYAxisRangeChange && (
          <InlineRange label="range" range={yAxisRange} onChange={onYAxisRangeChange} />
        )}
      </div>
      {showZAxis && (
        <DropZone
          label="Z-Axis (depth)"
          items={config.zAxis ? [config.zAxis] : []}
          onDrop={f => setConfig(p => ({ ...p, zAxis: f }))}
          onRemove={() => setConfig(p => ({ ...p, zAxis: undefined }))}
        />
      )}
    </div>
  );
}

// ============================================================================
// OHLC Field Mapping
// ============================================================================

const selectStyle: React.CSSProperties = {
  width: '100%', padding: '0.25rem 0.375rem', fontSize: '0.563rem',
  border: C.border, borderRadius: '0.375rem', outline: 'none',
  color: C.text, backgroundColor: 'white', marginTop: '0.25rem',
};

function OHLCFieldMapping({ fields, ohlc, onChange }: {
  fields: ChartField[]; ohlc: OHLCConfig; onChange: (ohlc: OHLCConfig) => void;
}) {
  const dateFields = fields.filter(f => f.type === 'datetime' || f.name.toLowerCase().includes('date'));
  const numericFields = fields.filter(f => f.type === 'numeric');
  const isComplete = ohlc.dateField && ohlc.openField && ohlc.highField && ohlc.lowField && ohlc.closeField;

  const renderSelect = (label: string, value: string, options: ChartField[], onVal: (v: string) => void, dotColor: string, required = true) => (
    <div>
      <div style={{ fontSize: '0.5rem', color: C.textFaint, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        {label}{required ? ' *' : ''}
      </div>
      <select value={value} onChange={e => onVal(e.target.value)} style={selectStyle}>
        <option value="">{required ? 'Select...' : 'None'}</option>
        {options.map(f => <option key={f.name} value={f.name}>{f.name}</option>)}
      </select>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={sectionHeader}>OHLC Fields</div>
      {isComplete && (
        <div style={{ fontSize: '0.5rem', color: 'hsl(150 50% 40%)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <svg style={{ width: 10, height: 10 }} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
          All fields mapped
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
        {renderSelect('Date', ohlc.dateField, dateFields.length > 0 ? dateFields : fields, v => onChange({ ...ohlc, dateField: v }), 'bg-blue-500')}
        {renderSelect('Volume', ohlc.volumeField || '', numericFields, v => onChange({ ...ohlc, volumeField: v || undefined }), 'bg-slate-300', false)}
        {renderSelect('Open', ohlc.openField, numericFields, v => onChange({ ...ohlc, openField: v }), 'bg-emerald-500')}
        {renderSelect('High', ohlc.highField, numericFields, v => onChange({ ...ohlc, highField: v }), 'bg-emerald-500')}
        {renderSelect('Low', ohlc.lowField, numericFields, v => onChange({ ...ohlc, lowField: v }), 'bg-red-500')}
        {renderSelect('Close', ohlc.closeField, numericFields, v => onChange({ ...ohlc, closeField: v }), 'bg-red-500')}
      </div>
    </div>
  );
}

// ============================================================================
// Matrix Field Mapping (heatmap / surface3d)
// ============================================================================

function MatrixFieldMapping({ fields, matrix, chartType, onChange }: {
  fields: ChartField[]; matrix: MatrixConfig; chartType: string; onChange: (m: MatrixConfig) => void;
}) {
  const numericFields = fields.filter(f => f.type === 'numeric');
  const isComplete = matrix.xField && matrix.yField && matrix.zField;
  const isHeatmap = chartType === 'heatmap';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={sectionHeader}>{isHeatmap ? 'Matrix Fields' : 'Surface Fields'}</div>
      {isComplete && (
        <div style={{ fontSize: '0.5rem', color: 'hsl(150 50% 40%)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <svg style={{ width: 10, height: 10 }} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
          All fields mapped
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
        <div>
          <div style={{ fontSize: '0.5rem', color: C.textFaint, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" /> X{isHeatmap ? ' (cols)' : ''} *
          </div>
          <select value={matrix.xField} onChange={e => onChange({ ...matrix, xField: e.target.value })} style={selectStyle}>
            <option value="">Select...</option>
            {fields.map(f => <option key={f.name} value={f.name}>{f.name}</option>)}
          </select>
        </div>
        <div>
          <div style={{ fontSize: '0.5rem', color: C.textFaint, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Y{isHeatmap ? ' (rows)' : ''} *
          </div>
          <select value={matrix.yField} onChange={e => onChange({ ...matrix, yField: e.target.value })} style={selectStyle}>
            <option value="">Select...</option>
            {fields.map(f => <option key={f.name} value={f.name}>{f.name}</option>)}
          </select>
        </div>
        <div>
          <div style={{ fontSize: '0.5rem', color: C.textFaint, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500" /> Z (val) *
          </div>
          <select value={matrix.zField} onChange={e => onChange({ ...matrix, zField: e.target.value })} style={selectStyle}>
            <option value="">Select...</option>
            {numericFields.map(f => <option key={f.name} value={f.name}>{f.name}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
}
