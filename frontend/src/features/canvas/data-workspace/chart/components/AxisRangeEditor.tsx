/**
 * AxisRangeEditor - Controls for axis min/max range
 * 
 * Features:
 * - Auto mode (let Plotly determine range)
 * - Manual min/max inputs
 * - Date picker for date axes
 * - Number input for numeric axes
 */

import { useState, useMemo, useEffect } from 'react';

type AxisType = 'numeric' | 'date' | 'auto';

interface Props {
  label: string;
  range: [number | string | null, number | string | null] | undefined;
  onChange: (range: [number | string | null, number | string | null] | undefined) => void;
  axisType?: AxisType;
  dataMin?: number | string;
  dataMax?: number | string;
}

export function AxisRangeEditor({ 
  label, 
  range, 
  onChange, 
  axisType = 'auto',
  dataMin,
  dataMax,
}: Props) {
  const isAuto = !range || (range[0] === null && range[1] === null);
  const [localMin, setLocalMin] = useState<string>(
    range?.[0] != null ? String(range[0]) : ''
  );
  const [localMax, setLocalMax] = useState<string>(
    range?.[1] != null ? String(range[1]) : ''
  );

  // Sync local state when range prop changes externally
  useEffect(() => {
    setLocalMin(range?.[0] != null ? String(range[0]) : '');
    setLocalMax(range?.[1] != null ? String(range[1]) : '');
  }, [range]);

  // Determine if this is a date axis
  const isDateAxis = useMemo(() => {
    if (axisType === 'date') return true;
    if (axisType === 'numeric') return false;
    // Auto-detect from dataMin/dataMax
    if (typeof dataMin === 'string' && dataMin.match(/^\d{4}-\d{2}/)) return true;
    return false;
  }, [axisType, dataMin]);

  const handleToggleAuto = (checked: boolean) => {
    if (checked) {
      onChange(undefined);
    } else {
      // Initialize with data range if available
      onChange([dataMin ?? null, dataMax ?? null]);
      setLocalMin(dataMin != null ? String(dataMin) : '');
      setLocalMax(dataMax != null ? String(dataMax) : '');
    }
  };

  const handleMinChange = (value: string) => {
    setLocalMin(value);
    if (isDateAxis) {
      onChange([value || null, range?.[1] ?? null]);
    } else {
      const parsed = parseFloat(value);
      const num = value && !Number.isNaN(parsed) ? parsed : null;
      onChange([num, range?.[1] as number | null ?? null]);
    }
  };

  const handleMaxChange = (value: string) => {
    setLocalMax(value);
    if (isDateAxis) {
      onChange([range?.[0] ?? null, value || null]);
    } else {
      const parsed = parseFloat(value);
      const num = value && !Number.isNaN(parsed) ? parsed : null;
      onChange([range?.[0] as number | null ?? null, num]);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
          {label}
        </span>
        <label className="flex items-center gap-1.5 text-[10px] text-slate-500 cursor-pointer">
          <input
            type="checkbox"
            checked={isAuto}
            onChange={(e) => handleToggleAuto(e.target.checked)}
            className="w-3 h-3 rounded border-slate-300"
          />
          Auto
        </label>
      </div>

      {!isAuto && (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-slate-400">Min</label>
            {isDateAxis ? (
              <input
                type="date"
                value={localMin}
                onChange={(e) => handleMinChange(e.target.value)}
                className="w-full mt-0.5 text-xs px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            ) : (
              <input
                type="number"
                value={localMin}
                onChange={(e) => handleMinChange(e.target.value)}
                placeholder={dataMin != null ? String(dataMin) : 'Auto'}
                className="w-full mt-0.5 text-xs px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            )}
          </div>
          <div>
            <label className="text-[10px] text-slate-400">Max</label>
            {isDateAxis ? (
              <input
                type="date"
                value={localMax}
                onChange={(e) => handleMaxChange(e.target.value)}
                className="w-full mt-0.5 text-xs px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            ) : (
              <input
                type="number"
                value={localMax}
                onChange={(e) => handleMaxChange(e.target.value)}
                placeholder={dataMax != null ? String(dataMax) : 'Auto'}
                className="w-full mt-0.5 text-xs px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            )}
          </div>
        </div>
      )}

      {isAuto && dataMin != null && dataMax != null && (
        <div className="text-[10px] text-slate-400">
          Range: {String(dataMin).slice(0, 10)} — {String(dataMax).slice(0, 10)}
        </div>
      )}
    </div>
  );
}

