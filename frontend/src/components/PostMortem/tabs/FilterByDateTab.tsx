import { useState, useEffect } from 'react';
import PortfolioCheckboxList from '../shared/PortfolioCheckboxList';
import { fetchTransactionPreview } from '../../../services/postmortemApi';
import type { ImportFilters, TransactionImportPreview } from '../types';

const QUICK_DATE_OPTIONS = [
  { label: 'Last 7 Days', days: 7 },
  { label: 'Last 30 Days', days: 30 },
  { label: 'Last 90 Days', days: 90 },
  { label: 'This Year', days: 365 },
];

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

export default function FilterByDateTab({ filters, onFiltersChange, onPreviewChange }: Props) {
  const [loading, setLoading] = useState(false);
  const debouncedFilters = useDebounce(filters, 500);

  const handleQuickDate = (days: number) => {
    const dateTo = new Date().toISOString().split('T')[0];
    const dateFrom = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    onFiltersChange({ ...filters, dateFrom, dateTo });
  };

  // Fetch preview on filter changes
  useEffect(() => {
    if (!debouncedFilters.dateFrom || !debouncedFilters.dateTo) {
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
      {/* Date Range */}
      <section>
        <label className="text-sm font-medium text-gray-900 block mb-3">
          Select Date Range
        </label>
        <div className="flex items-center gap-2 mb-3">
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

        {/* Quick Date Buttons */}
        <div className="flex flex-wrap gap-2">
          {QUICK_DATE_OPTIONS.map((option) => (
            <button
              key={option.days}
              onClick={() => handleQuickDate(option.days)}
              className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded hover:bg-gray-100 transition-colors"
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      {/* Portfolio Filter (Optional) */}
      <section>
        <label className="text-sm font-medium text-gray-900 block mb-3">
          Filter by Portfolios (Optional)
        </label>
        <p className="text-xs text-gray-500 mb-3">
          Leave unselected to include all portfolios
        </p>
        <PortfolioCheckboxList
          selectedIds={filters.portfolioIds}
          onChange={(ids) => onFiltersChange({ ...filters, portfolioIds: ids })}
        />
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
