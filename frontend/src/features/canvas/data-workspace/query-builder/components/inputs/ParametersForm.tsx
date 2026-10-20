/**
 * ParametersForm - Form inputs for endpoint required parameters
 * Extracted from SingleObjectForm lines 744-803
 *
 * Enhanced to support UW expiry dropdowns that fetch real expiration dates.
 */

import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Calendar, Check } from 'lucide-react';

interface ParametersFormProps {
  params: string[];
  formParams: Record<string, string>;
  onSetFormParams: (params: Record<string, string>) => void;
  uwEnums?: Record<string, string[]>;
  onFetchUwEnum?: (enumName: string) => void;
  // New props for UW expiry dropdown
  ticker?: string;
  isUwSource?: boolean;
  uwExpirations?: Record<string, string[]>;
  uwExpirationsLoading?: Set<string>;
  onFetchUwExpirations?: (ticker: string) => void;
}

/* ── Custom Select ────────────────────────────────────────────────── */

function CustomSelect({ value, onChange, options, placeholder = 'Select...' }: {
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
    const dropdownHeight = Math.min(options.length * 28 + 8, 200);
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
        className="w-full px-2.5 py-1.5 text-xs text-left bg-white border border-slate-200 rounded-lg hover:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors flex items-center justify-between gap-1"
      >
        <span className={value ? 'text-slate-700' : 'text-slate-400'}>{selectedLabel}</span>
        <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && createPortal(
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
          <div
            className="fixed z-[9999] bg-white rounded-lg shadow-lg border border-slate-200 py-1 overflow-auto"
            style={{ top: pos.top, left: pos.left, width: pos.width, maxHeight: 200 }}
          >
            {options.map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => { onChange(opt.value); setOpen(false); }}
                className={`w-full px-2.5 py-1.5 text-xs text-left flex items-center gap-2 hover:bg-slate-50 transition-colors ${
                  value === opt.value ? 'text-blue-600 bg-blue-50/50' : 'text-slate-600'
                }`}
              >
                <span className={`w-3 h-3 flex items-center justify-center ${value === opt.value ? 'text-blue-600' : 'text-transparent'}`}>
                  <Check className="w-3 h-3" />
                </span>
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

/* ── Custom Date Picker ────────────────────────────────────────────── */

function CustomDateInput({ value, onChange }: {
  value: string;
  onChange: (val: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  // Parse value or default to today
  const parsed = value ? new Date(value + 'T00:00:00') : new Date();
  const [viewYear, setViewYear] = useState(parsed.getFullYear());
  const [viewMonth, setViewMonth] = useState(parsed.getMonth());

  // Sync view when value changes externally
  useEffect(() => {
    if (value) {
      const d = new Date(value + 'T00:00:00');
      setViewYear(d.getFullYear());
      setViewMonth(d.getMonth());
    }
  }, [value]);

  const updatePos = useCallback(() => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const calendarHeight = 280;
    const spaceBelow = window.innerHeight - rect.bottom - 8;
    const flipUp = spaceBelow < calendarHeight;
    setPos({
      top: flipUp ? rect.top - calendarHeight - 4 : rect.bottom + 4,
      left: rect.left,
    });
  }, []);

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstDayOfWeek = new Date(viewYear, viewMonth, 1).getDay();
  const monthName = new Date(viewYear, viewMonth).toLocaleString('default', { month: 'long' });

  const prevMonth = () => {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(y => y - 1); }
    else setViewMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 11) { setViewMonth(0); setViewYear(y => y + 1); }
    else setViewMonth(m => m + 1);
  };

  const selectDay = (day: number) => {
    const m = String(viewMonth + 1).padStart(2, '0');
    const d = String(day).padStart(2, '0');
    onChange(`${viewYear}-${m}-${d}`);
    setOpen(false);
  };

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  const displayValue = value
    ? new Date(value + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : '';

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={() => { updatePos(); setOpen(!open); }}
        className="w-full px-2.5 py-1.5 text-xs text-left bg-white border border-slate-200 rounded-lg hover:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors flex items-center justify-between gap-1"
      >
        <span className={value ? 'text-slate-700' : 'text-slate-400'}>
          {displayValue || 'Select date...'}
        </span>
        <Calendar className="w-3 h-3 text-slate-400" />
      </button>
      {open && createPortal(
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
          <div
            className="fixed z-[9999] bg-white rounded-xl shadow-lg border border-slate-200 p-3 w-[220px]"
            style={{ top: pos.top, left: pos.left }}
          >
            {/* Month/Year header */}
            <div className="flex items-center justify-between mb-2">
              <button type="button" onClick={prevMonth} className="p-1 rounded hover:bg-slate-100 text-slate-500">
                <ChevronDown className="w-3.5 h-3.5 rotate-90" />
              </button>
              <span className="text-xs font-medium text-slate-700">{monthName} {viewYear}</span>
              <button type="button" onClick={nextMonth} className="p-1 rounded hover:bg-slate-100 text-slate-500">
                <ChevronDown className="w-3.5 h-3.5 -rotate-90" />
              </button>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 mb-1">
              {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
                <div key={i} className="text-center text-[10px] text-slate-400 font-medium py-0.5">{d}</div>
              ))}
            </div>

            {/* Day grid */}
            <div className="grid grid-cols-7">
              {Array.from({ length: firstDayOfWeek }).map((_, i) => (
                <div key={`empty-${i}`} />
              ))}
              {Array.from({ length: daysInMonth }).map((_, i) => {
                const day = i + 1;
                const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                const isSelected = dateStr === value;
                const isToday = dateStr === todayStr;
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => selectDay(day)}
                    className={`w-7 h-7 text-[11px] rounded-lg flex items-center justify-center transition-colors ${
                      isSelected
                        ? 'bg-blue-600 text-white font-medium'
                        : isToday
                        ? 'bg-blue-50 text-blue-600 font-medium'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {day}
                  </button>
                );
              })}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => { onChange(''); setOpen(false); }}
                className="text-[10px] text-slate-400 hover:text-slate-600"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => { onChange(todayStr); setOpen(false); }}
                className="text-[10px] text-blue-600 hover:text-blue-700 font-medium"
              >
                Today
              </button>
            </div>
          </div>
        </>,
        document.body
      )}
    </>
  );
}

/* ── Main Component ───────────────────────────────────────────────── */

export default function ParametersForm({
  params,
  formParams,
  onSetFormParams,
  uwEnums = {},
  onFetchUwEnum,
  ticker,
  isUwSource = false,
  uwExpirations = {},
  uwExpirationsLoading = new Set(),
  onFetchUwExpirations,
}: ParametersFormProps) {
  // Check if we have an expiry param that needs UW data
  const hasExpiryParam = useMemo(() => {
    return params.some(p => {
      const lp = p.toLowerCase();
      return lp === 'expiry' || lp === 'expirations' || lp === 'expiration';
    });
  }, [params]);

  // Compute which UW enums need to be fetched
  const uwEnumsToFetch = useMemo(() => {
    return params
      .map(p => p.toLowerCase())
      .filter(lowerParam =>
        ['sector', 'flow_group', 'month', 'week'].includes(lowerParam) &&
        !uwEnums[lowerParam]
      );
  }, [params, uwEnums]);

  // Fetch UW enums in an effect (not during render)
  useEffect(() => {
    if (onFetchUwEnum && uwEnumsToFetch.length > 0) {
      uwEnumsToFetch.forEach(enumName => {
        onFetchUwEnum(enumName);
      });
    }
  }, [onFetchUwEnum, uwEnumsToFetch]);

  // Fetch UW expirations when we have a ticker and UW source with expiry param
  useEffect(() => {
    if (
      isUwSource &&
      ticker &&
      hasExpiryParam &&
      onFetchUwExpirations &&
      !uwExpirations[ticker] &&
      !uwExpirationsLoading.has(ticker)
    ) {
      onFetchUwExpirations(ticker);
    }
  }, [isUwSource, ticker, hasExpiryParam, onFetchUwExpirations, uwExpirations, uwExpirationsLoading]);

  // Auto-select first expiry when expirations load
  useEffect(() => {
    if (
      isUwSource &&
      ticker &&
      uwExpirations[ticker]?.length > 0 &&
      hasExpiryParam
    ) {
      const expiryParams = params.filter(p => {
        const lp = p.toLowerCase();
        return lp === 'expiry' || lp === 'expirations' || lp === 'expiration';
      });

      for (const param of expiryParams) {
        const lowerParam = param.toLowerCase();
        if (!formParams[lowerParam]) {
          onSetFormParams({ ...formParams, [lowerParam]: uwExpirations[ticker][0] });
          break;
        }
      }
    }
  }, [isUwSource, ticker, uwExpirations, hasExpiryParam, params, formParams, onSetFormParams]);

  if (params.length === 0) return null;

  // Get available expirations for the current ticker
  const availableExpirations = ticker && isUwSource ? uwExpirations[ticker] || [] : [];
  const isLoadingExpirations = ticker ? uwExpirationsLoading.has(ticker) : false;

  return (
    <div>
      <h3 className="text-xs font-medium text-slate-600 mb-3">Parameters</h3>
      <div className="space-y-3">
        {params.map((param) => {
          const lowerParam = param.toLowerCase();
          const isExpiryParam = lowerParam === 'expiry' || lowerParam === 'expirations' || lowerParam === 'expiration';
          const isDateParam = ['from', 'to', 'date', 'start', 'end'].some(d => lowerParam.includes(d));
          const isSelectParam = ['period', 'timeframe', 'interval', 'type', 'exchange'].includes(lowerParam);
          const isUwEnum = ['sector', 'flow_group', 'month', 'week'].includes(lowerParam);

          // Special handling for expiry param when UW source
          if (isExpiryParam && isUwSource) {
            return (
              <div key={param} className="flex flex-col gap-1">
                <label className="text-[10px] text-slate-500">{param}</label>
                {isLoadingExpirations ? (
                  <div className="w-full px-2.5 py-1.5 text-xs text-slate-400 border border-slate-200 rounded-lg bg-slate-50">
                    Loading...
                  </div>
                ) : availableExpirations.length > 0 ? (
                  <CustomSelect
                    value={formParams[lowerParam] || ''}
                    onChange={val => onSetFormParams({ ...formParams, [lowerParam]: val })}
                    options={[
                      { value: '', label: 'Select expiry...' },
                      ...availableExpirations.map(exp => ({ value: exp, label: exp })),
                    ]}
                    placeholder="Select expiry..."
                  />
                ) : (
                  <CustomDateInput
                    value={formParams[lowerParam] || ''}
                    onChange={val => onSetFormParams({ ...formParams, [lowerParam]: val })}
                  />
                )}
              </div>
            );
          }

          return (
            <div key={param} className="flex flex-col gap-1">
              <label className="text-[10px] text-slate-500">{param}</label>
              {isExpiryParam || isDateParam ? (
                <CustomDateInput
                  value={formParams[lowerParam] || ''}
                  onChange={val => onSetFormParams({ ...formParams, [lowerParam]: val })}
                />
              ) : isSelectParam ? (
                <CustomSelect
                  value={formParams[lowerParam] || ''}
                  onChange={val => onSetFormParams({ ...formParams, [lowerParam]: val })}
                  options={[
                    { value: '', label: 'Select...' },
                    ...(lowerParam === 'period'
                      ? ['annual', 'quarter', 'ttm'].map(v => ({ value: v, label: v }))
                      : lowerParam === 'timeframe'
                      ? ['1min', '5min', '15min', '30min', '1hour', '4hour', '1day'].map(v => ({ value: v, label: v }))
                      : []),
                  ]}
                />
              ) : isUwEnum && uwEnums[lowerParam] ? (
                <CustomSelect
                  value={formParams[lowerParam] || ''}
                  onChange={val => onSetFormParams({ ...formParams, [lowerParam]: val })}
                  options={[
                    { value: '', label: 'Select...' },
                    ...uwEnums[lowerParam].map(v => ({ value: v, label: v })),
                  ]}
                />
              ) : (
                <input
                  type="text"
                  value={formParams[lowerParam] || ''}
                  onChange={e => onSetFormParams({ ...formParams, [lowerParam]: e.target.value })}
                  placeholder={lowerParam === 'limit' ? '20' : lowerParam === 'page' ? '0' : ''}
                  className="w-full px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg hover:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors text-slate-700"
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
