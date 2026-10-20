import { useState, useEffect } from 'react';
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

export default function FilterByPortfolioTab({ filters, onFiltersChange, onPreviewChange }: Props) {
  const [loading, setLoading] = useState(false);
  const debouncedFilters = useDebounce(filters, 500);

  // Fetch preview on filter changes
  useEffect(() => {
    if (debouncedFilters.portfolioIds.length === 0) {
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
      {/* Portfolio Selection */}
      <section>
        <label className="text-sm font-medium text-gray-900 block mb-3">
          Select Portfolios
        </label>
        <PortfolioCheckboxList
          selectedIds={filters.portfolioIds}
          onChange={(ids) => onFiltersChange({ ...filters, portfolioIds: ids })}
        />
      </section>

      {/* Date Range */}
      <section>
        <label className="text-sm font-medium text-gray-900 block mb-3">
          Date Range (Optional)
        </label>
        <p className="text-xs text-gray-500 mb-3">
          Leave blank to include all transactions
        </p>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={filters.dateFrom || ''}
            onChange={(e) => onFiltersChange({ ...filters, dateFrom: e.target.value || null })}
            className="flex-1 text-xs text-gray-600 border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
            placeholder="From"
          />
          <span className="text-gray-400 text-xs">—</span>
          <input
            type="date"
            value={filters.dateTo || ''}
            onChange={(e) => onFiltersChange({ ...filters, dateTo: e.target.value || null })}
            className="flex-1 text-xs text-gray-600 border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
            placeholder="To"
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
