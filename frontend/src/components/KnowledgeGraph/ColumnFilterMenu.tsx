/**
 * ColumnFilterMenu - Excel AutoFilter-style column filtering and sorting
 */

import { useState, useEffect, useRef, useMemo } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown, Search, X } from 'lucide-react';

interface ColumnFilterMenuProps {
  columnIndex: number;
  columnData: any[];
  onClose: () => void;
  onSort: (direction: 'asc' | 'desc') => void;
  onFilter: (values: Set<string>) => void;
  position: { x: number; y: number };
}

export default function ColumnFilterMenu({
  columnIndex,
  columnData,
  onClose,
  onSort,
  onFilter,
  position,
}: ColumnFilterMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedValues, setSelectedValues] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(true);

  // Get unique values from column
  const uniqueValues = useMemo(() => {
    const values = new Map<string, number>(); // value -> count
    columnData.forEach(cell => {
      const val = cell?.value == null ? '(Blank)' : String(cell.value);
      values.set(val, (values.get(val) || 0) + 1);
    });
    return Array.from(values.entries())
      .sort((a, b) => {
        // Sort blanks to bottom, then alphabetically
        if (a[0] === '(Blank)') return 1;
        if (b[0] === '(Blank)') return -1;
        return a[0].localeCompare(b[0]);
      });
  }, [columnData]);

  // Initialize with all values selected
  useEffect(() => {
    setSelectedValues(new Set(uniqueValues.map(([val]) => val)));
  }, [uniqueValues]);

  // Filtered values based on search
  const filteredValues = useMemo(() => {
    if (!searchTerm) return uniqueValues;
    const term = searchTerm.toLowerCase();
    return uniqueValues.filter(([val]) =>
      val.toLowerCase().includes(term),
    );
  }, [uniqueValues, searchTerm]);

  // Close on click outside or Escape
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  const handleToggleValue = (value: string) => {
    const newSelected = new Set(selectedValues);
    if (newSelected.has(value)) {
      newSelected.delete(value);
    } else {
      newSelected.add(value);
    }
    setSelectedValues(newSelected);
    setSelectAll(newSelected.size === uniqueValues.length);
  };

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedValues(new Set());
      setSelectAll(false);
    } else {
      setSelectedValues(new Set(uniqueValues.map(([val]) => val)));
      setSelectAll(true);
    }
  };

  const handleApplyFilter = () => {
    onFilter(selectedValues);
    onClose();
  };

  return (
    <div
      ref={menuRef}
      className="fixed bg-white border border-slate-300 rounded-lg shadow-2xl z-[200] w-72 animate-in fade-in slide-in-from-top-2 duration-150"
      style={{ left: position.x, top: position.y }}
    >
      {/* Sort Options */}
      <div className="p-2 border-b border-slate-200">
        <button
          onClick={() => {
            onSort('asc');
            onClose();
          }}
          className="w-full px-3 py-2 text-left text-sm hover:bg-slate-100 rounded flex items-center gap-2"
        >
          <ArrowUp size={14} className="text-slate-600" />
          <span>Sort A → Z</span>
        </button>
        <button
          onClick={() => {
            onSort('desc');
            onClose();
          }}
          className="w-full px-3 py-2 text-left text-sm hover:bg-slate-100 rounded flex items-center gap-2"
        >
          <ArrowDown size={14} className="text-slate-600" />
          <span>Sort Z → A</span>
        </button>
      </div>

      {/* Search */}
      <div className="p-2 border-b border-slate-200">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search..."
            className="w-full pl-8 pr-8 py-1.5 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 hover:bg-slate-200 rounded"
            >
              <X size={12} className="text-slate-500" />
            </button>
          )}
        </div>
      </div>

      {/* Select All */}
      <div className="p-2 border-b border-slate-200">
        <label className="flex items-center gap-2 px-3 py-1.5 hover:bg-slate-100 rounded cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={selectAll}
            onChange={handleSelectAll}
            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="font-medium">(Select All)</span>
        </label>
      </div>

      {/* Value List */}
      <div className="max-h-64 overflow-y-auto p-2">
        {filteredValues.length === 0 ? (
          <div className="text-sm text-slate-500 text-center py-4">No matches found</div>
        ) : (
          filteredValues.map(([value, count]) => (
            <label
              key={value}
              className="flex items-center justify-between gap-2 px-3 py-1.5 hover:bg-slate-100 rounded cursor-pointer text-sm"
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <input
                  type="checkbox"
                  checked={selectedValues.has(value)}
                  onChange={() => handleToggleValue(value)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 shrink-0"
                />
                <span className="truncate" title={value}>
                  {value}
                </span>
              </div>
              <span className="text-xs text-slate-400 shrink-0">({count})</span>
            </label>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-2 border-t border-slate-200 flex items-center justify-between gap-2">
        <span className="text-xs text-slate-600">
          {selectedValues.size} of {uniqueValues.length} selected
        </span>
        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded"
          >
            Cancel
          </button>
          <button
            onClick={handleApplyFilter}
            className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
