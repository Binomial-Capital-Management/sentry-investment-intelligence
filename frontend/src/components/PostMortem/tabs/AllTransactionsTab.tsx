import { useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import PortfolioCheckboxList from '../shared/PortfolioCheckboxList';
import { fetchTransactionPreview } from '../../../services/postmortemApi';
import type { ImportFilters, TransactionImportPreview } from '../types';

interface Props {
  filters: ImportFilters;
  onFiltersChange: (filters: ImportFilters) => void;
  onPreviewChange: (preview: TransactionImportPreview | null) => void;
}

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

export default function AllTransactionsTab({ filters, onFiltersChange, onPreviewChange }: Props) {
  const [loading, setLoading] = useState(false);
  const debouncedFilters = useDebounce(filters, 500);

  // Fetch preview on filter changes
  useEffect(() => {
    if (
      debouncedFilters.portfolioIds.length === 0 ||
      !debouncedFilters.dateFrom ||
      !debouncedFilters.dateTo
    ) {
      onPreviewChange(null);
      return;
    }

    const loadPreview = async () => {
      setLoading(true);
      try {
        const preview = await fetchTransactionPreview(debouncedFilters);
        onPreviewChange(preview);
      } catch (error) {
        console.error('Preview failed:', error);
        onPreviewChange(null);
      } finally {
        setLoading(false);
      }
    };

    loadPreview();
  }, [debouncedFilters, onPreviewChange]);

  return (
    <div className="space-y-6">
      {/* Portfolio Multi-Select */}
      <section>
        <label className="text-sm font-medium text-gray-900 block mb-3">
          Portfolios
        </label>
        <PortfolioCheckboxList
          selectedIds={filters.portfolioIds}
          onChange={(ids) => onFiltersChange({ ...filters, portfolioIds: ids })}
        />
      </section>

      {/* Date Range */}
      <section>
        <label className="text-sm font-medium text-gray-900 block mb-3">
          Date Range
        </label>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={filters.dateFrom || ''}
            onChange={(e) => onFiltersChange({ ...filters, dateFrom: e.target.value || null })}
            className="flex-1 text-xs text-gray-600 border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
          />
          <span className="text-gray-400 text-xs">—</span>
          <input
            type="date"
            value={filters.dateTo || ''}
            onChange={(e) => onFiltersChange({ ...filters, dateTo: e.target.value || null })}
            className="flex-1 text-xs text-gray-600 border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
          />
        </div>
      </section>

      {/* Optional Filters */}
      <section>
        <label className="text-sm font-medium text-gray-900 block mb-3">
          Additional Filters (Optional)
        </label>
        <div className="flex items-center gap-3">
          {/* Source Filter */}
          <div className="relative flex-1">
            <select
              value={filters.source || 'all'}
              onChange={(e) => onFiltersChange({ ...filters, source: e.target.value as any })}
              className="w-full appearance-none text-xs text-gray-700 border border-gray-200 rounded px-3 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
            >
              <option value="all">All Sources</option>
              <option value="manual">Manual Only</option>
              <option value="ibkr">IBKR Only</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400 pointer-events-none" />
          </div>

          {/* Min Value Filter */}
          <input
            type="number"
            placeholder="Min value ($)"
            value={filters.minValue || ''}
            onChange={(e) => onFiltersChange({ ...filters, minValue: e.target.value ? parseFloat(e.target.value) : undefined })}
            className="flex-1 text-xs text-gray-700 border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
          />
        </div>
      </section>

      {loading && (
        <div className="text-center py-4">
          <div className="inline-block animate-spin rounded-full h-5 w-5 border-2 border-gray-300 border-t-gray-900" />
          <p className="mt-2 text-xs text-gray-500">Loading preview...</p>
        </div>
      )}
    </div>
  );
}
