import { useState } from 'react';
import { X } from 'lucide-react';
import AllTransactionsTab from './tabs/AllTransactionsTab';
import FilterByDateTab from './tabs/FilterByDateTab';
import FilterByPortfolioTab from './tabs/FilterByPortfolioTab';
import TransactionPreview from './shared/TransactionPreview';
import type { ViewMode, ImportFilters, TransactionImportPreview } from './types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onImport: (filters: ImportFilters, preview: TransactionImportPreview) => void;
}

export default function TransactionImportModal({ isOpen, onClose, onImport }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('all');
  const [filters, setFilters] = useState<ImportFilters>({
    portfolioIds: [],
    dateFrom: null,
    dateTo: null,
    source: 'all',
  });
  const [preview, setPreview] = useState<TransactionImportPreview | null>(null);

  if (!isOpen) return null;

  const canImport = preview !== null && preview.count > 0;

  const handleImport = () => {
    if (canImport && preview) {
      onImport(filters, preview);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Import Trades</h2>
            <p className="text-xs text-gray-500 mt-1">Select transactions for post-mortem analysis</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="px-6 pt-4 border-b border-gray-100">
          <div className="flex gap-1">
            <TabButton
              active={viewMode === 'all'}
              onClick={() => setViewMode('all')}
              label="All"
            />
            <TabButton
              active={viewMode === 'date'}
              onClick={() => setViewMode('date')}
              label="By Date"
            />
            <TabButton
              active={viewMode === 'portfolio'}
              onClick={() => setViewMode('portfolio')}
              label="By Portfolio"
            />
          </div>
        </div>

        {/* Tab Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[50vh]">
          {viewMode === 'all' && (
            <AllTransactionsTab
              filters={filters}
              onFiltersChange={setFilters}
              onPreviewChange={setPreview}
            />
          )}
          {viewMode === 'date' && (
            <FilterByDateTab
              filters={filters}
              onFiltersChange={setFilters}
              onPreviewChange={setPreview}
            />
          )}
          {viewMode === 'portfolio' && (
            <FilterByPortfolioTab
              filters={filters}
              onFiltersChange={setFilters}
              onPreviewChange={setPreview}
            />
          )}

          {/* Preview Stats */}
          {preview && (
            <div className="mt-6">
              <TransactionPreview preview={preview} />
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="text-sm text-gray-600 hover:text-gray-900 font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleImport}
            disabled={!canImport}
            className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Import {preview?.count || 0} Trades →
          </button>
        </div>
      </div>
    </div>
  );
}

// Tab Button Component
function TabButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`
        px-4 py-2 text-sm font-medium transition-colors relative
        ${active
          ? 'text-gray-900'
          : 'text-gray-500 hover:text-gray-700'
        }
      `}
    >
      {label}
      {active && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gray-900" />
      )}
    </button>
  );
}
