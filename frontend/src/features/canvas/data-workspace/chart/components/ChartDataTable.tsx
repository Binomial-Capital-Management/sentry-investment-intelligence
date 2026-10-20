/**
 * ChartDataTable - Shows raw data used by the chart in a scrollable table
 */

import { useMemo } from 'react';

// Convert internal field names to user-friendly display names
const FIELD_DISPLAY_NAMES: Record<string, string> = {
  '_source_symbol': 'Symbol',
  '_row': 'Row',
  'fiscalYear': 'Fiscal Year',
  'calendarYear': 'Calendar Year',
};

function getFieldDisplayName(field: string): string {
  return FIELD_DISPLAY_NAMES[field] || field;
}

interface ChartDataTableProps {
  data: any[];
  xAxis: string;
  ySeries: { field: string; label?: string }[];
  maxRows?: number;
}

export function ChartDataTable({ data, xAxis, ySeries, maxRows = 100 }: ChartDataTableProps) {
  // Columns to display: x-axis + all y-series
  const columns = useMemo(() => {
    const cols = [xAxis];
    ySeries.forEach((s) => {
      if (!cols.includes(s.field)) {
        cols.push(s.field);
      }
    });
    return cols;
  }, [xAxis, ySeries]);

  // Limit data for performance
  const displayData = useMemo(() => {
    return data.slice(0, maxRows);
  }, [data, maxRows]);

  const formatValue = (val: any): string => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'number') {
      // Format numbers nicely
      if (Number.isInteger(val)) return val.toLocaleString();
      return val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    }
    return String(val);
  };

  if (data.length === 0) {
    return (
      <div className="p-4 text-sm text-slate-400 text-center">
        No data to display
      </div>
    );
  }

  return (
    <div className="bg-white">
      <table className="w-full text-xs">
        <thead className="sticky top-0 z-10" style={{ backgroundColor: '#f8f8f7' }}>
            <tr>
              <th className="text-left px-2 py-1.5 text-slate-500 font-medium border-b border-slate-200 w-8">
                #
              </th>
              {columns.map((col) => (
                <th
                  key={col}
                  className="text-left px-2 py-1.5 text-slate-500 font-medium border-b border-slate-200 whitespace-nowrap"
                >
                  {getFieldDisplayName(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {displayData.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50">
                <td className="px-2 py-1 text-slate-400 tabular-nums">
                  {idx + 1}
                </td>
                {columns.map((col) => (
                  <td
                    key={col}
                    className="px-2 py-1 text-slate-700 whitespace-nowrap tabular-nums"
                  >
                    {formatValue(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
      </table>
      {data.length > maxRows && (
        <div className="px-3 py-1.5 text-[10px] text-slate-400 border-t border-slate-100">
          ... and {data.length - maxRows} more rows
        </div>
      )}
    </div>
  );
}

