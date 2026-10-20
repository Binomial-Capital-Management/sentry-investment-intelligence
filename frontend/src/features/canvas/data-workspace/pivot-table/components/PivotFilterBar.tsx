import { PivotResult } from '../types';

interface PivotFilterBarProps {
  filterOptions: Record<string, string[]>;
  activeFilters: Record<string, Set<string>>;
  filteredRowCount: number;
  totalRowCount: number;
  onClearAllFilters: () => void;
  sortColumn: string | null;
  sortDirection: 'asc' | 'desc';
  clearSort: () => void;
  pivotResult: PivotResult | null;
}

export function PivotFilterBar({
  filterOptions,
  activeFilters,
  filteredRowCount,
  totalRowCount,
  onClearAllFilters,
  sortColumn,
  sortDirection,
  clearSort,
}: PivotFilterBarProps) {
  const hasActiveFilters = Object.values(activeFilters).some(s => s.size > 0);
  const isFiltered = hasActiveFilters && filteredRowCount < totalRowCount;

  if (!isFiltered && !sortColumn) {
    return null;
  }

  return (
    <div className="bg-white border-b border-slate-200 px-4 py-1.5 flex flex-wrap gap-2 items-center">
      {isFiltered && (
        <>
          {Object.entries(filterOptions).map(([field, values]) => {
            const selected = activeFilters[field];
            if (!selected || selected.size === 0 || selected.size >= values.length) return null;
            return (
              <span key={field} className="px-1.5 py-0.5 text-[10px] bg-slate-50 border border-slate-200 rounded text-slate-600">
                {field} <span className="text-slate-400">({selected.size}/{values.length})</span>
              </span>
            );
          })}
          <button
            onClick={onClearAllFilters}
            className="text-[10px] text-slate-400 hover:text-red-500 underline"
          >
            Clear All
          </button>
        </>
      )}
      <span className="text-[10px] text-slate-400 ml-auto">
        {isFiltered ? `${filteredRowCount} of ${totalRowCount} rows` : ''}
      </span>
      {sortColumn && (
        <button
          onClick={clearSort}
          className="px-2 py-0.5 text-[10px] bg-amber-50 text-amber-700 rounded hover:bg-amber-100 transition-colors flex items-center gap-1"
          title="Clear sort"
        >
          {sortColumn === '_row' ? 'Row' : sortColumn === '_grand_total' ? 'Total' : sortColumn}
          {sortDirection === 'asc' ? '↑' : '↓'}
          <span className="text-amber-400 ml-0.5">×</span>
        </button>
      )}
    </div>
  );
}
