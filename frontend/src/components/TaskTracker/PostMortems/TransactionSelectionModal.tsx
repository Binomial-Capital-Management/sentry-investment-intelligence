import { useState, useEffect } from 'react';
import { X, ChevronDown, ChevronLeft, ChevronRight, Save } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { getAuthToken } from '../../../services/authService';
import { API_BASE } from '../../../services/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  transactions?: Transaction[];
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  onSuccess?: () => void;
  isSaving?: boolean;
}

export default function TransactionSelectionModal({
  isOpen,
  onClose,
  transactions = [],
  selectedIds = new Set(),
  onSelectionChange,
  onSuccess,
  isSaving = false,
}: Props) {
  // Remove local state fetch logic if transactions are provided via props
  // But keep fetch logic if we are in "create mode" (no transactions prop)
  const isCreateMode = transactions.length === 0;

  const [localTransactions, setLocalTransactions] = useState<Transaction[]>([]);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(false);
  // Use either prop-controlled selectedIds or local state
  const [localSelectedIds, setLocalSelectedIds] = useState<Set<string>>(new Set());
  const [isLocalSaving, setIsLocalSaving] = useState(false);

  const effectiveTransactions = isCreateMode ? localTransactions : transactions;
  const effectiveSelectedIds = onSelectionChange ? selectedIds : localSelectedIds;

  const handleSelectionChange = (newSet: Set<string>) => {
    if (onSelectionChange) {
      onSelectionChange(newSet);
    } else {
      setLocalSelectedIds(newSet);
    }
  };

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [availableTickers, setAvailableTickers] = useState<string[]>([]);
  const perPage = 20;

  const [filters, setFilters] = useState<Filters>({
    portfolioId: null,
    ticker: null,
    dateFrom: null,
    dateTo: null,
  });

  // Fetch portfolios (only needed for filtering in create mode)
  useEffect(() => {
    if (!isCreateMode) return;

    const fetchPortfolios = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/portfolios`, {
          headers: {
            'Authorization': `Bearer ${await getAuthToken()}`,
          },
        });
        if (response.ok) {
          const data = await response.json();
          setPortfolios(data);
        }
      } catch (error) {
        console.error('Failed to fetch portfolios:', error);
      }
    };
    if (isOpen) {
      fetchPortfolios();
    }
  }, [isOpen, isCreateMode]);

  // Fetch transactions (only in create mode)
  const fetchTransactions = async () => {
    if (!isCreateMode) return;

    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        per_page: perPage.toString(),
      });

      if (filters.portfolioId) params.append('portfolio_id', filters.portfolioId);
      if (filters.ticker) params.append('ticker', filters.ticker);
      if (filters.dateFrom) params.append('date_from', filters.dateFrom);
      if (filters.dateTo) params.append('date_to', filters.dateTo);

      const response = await fetch(`${API_BASE}/api/postmortem/transactions?${params}`, {
        headers: {
          'Authorization': `Bearer ${await getAuthToken()}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch transactions');

      const data: TransactionsResponse = await response.json();
      setLocalTransactions(data.transactions);
      setTotalPages(data.total_pages);
      setTotal(data.total);

      // Extract unique tickers
      const tickers = Array.from(new Set(data.transactions.map(t => t.ticker)));
      setAvailableTickers(tickers);
    } catch (error) {
      console.error('Failed to fetch transactions:', error);
      toast.error('Failed to load transactions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && isCreateMode) {
      fetchTransactions();
    }
  }, [currentPage, filters, isOpen, isCreateMode]);

  // Handle select all
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const newSelected = new Set(effectiveSelectedIds);
      effectiveTransactions.forEach(t => newSelected.add(t.id));
      handleSelectionChange(newSelected);
    } else {
      handleSelectionChange(new Set());
    }
  };

  // Handle individual selection
  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(effectiveSelectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    handleSelectionChange(newSelected);
  };

  // Save as post-mortem (only in create mode)
  const handleSave = async () => {
    if (onSelectionChange) {
      // In "selection mode", call onSuccess to trigger parent's save logic
      if (onSuccess) {
        onSuccess();
      } else {
        onClose();
      }
      return;
    }

    if (localSelectedIds.size === 0) {
      toast.error('Please select at least one transaction');
      return;
    }

    setIsLocalSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/postmortem/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await getAuthToken()}`,
        },
        body: JSON.stringify({
          transaction_ids: Array.from(localSelectedIds),
        }),
      });

      if (!response.ok) throw new Error('Failed to save post-mortem');

      toast.success(`Saved ${localSelectedIds.size} transaction(s) to post-mortem`);
      if (onSuccess) onSuccess();
    } catch (error) {
      console.error('Failed to save post-mortem:', error);
      toast.error('Failed to save post-mortem');
    } finally {
      setIsLocalSaving(false);
    }
  };

  // Clear filters
  const clearFilters = () => {
    setFilters({ portfolioId: null, ticker: null, dateFrom: null, dateTo: null });
    setCurrentPage(1);
  };

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  // Check if all current page items are selected
  const allPageSelected = transactions.length > 0 && transactions.every(t => selectedIds.has(t.id));

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-gray-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Select Transactions</h2>
            <p className="text-xs text-gray-500 mt-1">Choose trades to analyze in your post-mortem</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Filters */}
        <div className="px-6 py-3 border-b border-gray-100 flex items-center gap-4">
          {/* Portfolio Filter */}
          <div className="relative">
            <select
              value={filters.portfolioId || ''}
              onChange={(e) => setFilters({ ...filters, portfolioId: e.target.value || null })}
              className="appearance-none bg-transparent text-sm font-medium text-gray-900 pr-6 py-1 focus:outline-none cursor-pointer hover:text-gray-600"
            >
              <option value="">All Portfolios</option>
              {portfolios.map(portfolio => (
                <option key={portfolio.id} value={portfolio.id}>{portfolio.name}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-0 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400 pointer-events-none" />
          </div>

          <div className="h-4 w-px bg-gray-200"></div>

          {/* Ticker Filter */}
          <div className="relative">
            <select
              value={filters.ticker || ''}
              onChange={(e) => setFilters({ ...filters, ticker: e.target.value || null })}
              className="appearance-none bg-transparent text-sm font-medium text-gray-900 pr-6 py-1 focus:outline-none cursor-pointer hover:text-gray-600"
            >
              <option value="">All Tickers</option>
              {availableTickers.map(ticker => (
                <option key={ticker} value={ticker}>{ticker}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-0 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400 pointer-events-none" />
          </div>

          <div className="h-4 w-px bg-gray-200"></div>

          {/* Date Filter */}
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={filters.dateFrom || ''}
              onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value || null })}
              className="text-xs text-gray-600 bg-transparent border-none focus:ring-0 p-0 cursor-pointer font-medium"
              placeholder="From"
            />
            <span className="text-gray-300 text-xs">—</span>
            <input
              type="date"
              value={filters.dateTo || ''}
              onChange={(e) => setFilters({ ...filters, dateTo: e.target.value || null })}
              className="text-xs text-gray-600 bg-transparent border-none focus:ring-0 p-0 cursor-pointer font-medium"
              placeholder="To"
            />
          </div>

          {(filters.portfolioId || filters.ticker || filters.dateFrom || filters.dateTo) && (
            <button
              onClick={clearFilters}
              className="text-xs text-red-500 hover:text-red-700 ml-2 font-medium"
            >
              Clear
            </button>
          )}

          <div className="ml-auto text-xs text-gray-500">
            {selectedIds.size > 0 && `${selectedIds.size} selected`}
          </div>
        </div>

        {/* Transactions Table */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-5 w-5 border-2 border-gray-300 border-t-gray-900"></div>
            </div>
          ) : effectiveTransactions.length === 0 ? (
            <div className="text-center py-12 text-sm text-gray-500">
              No transactions found
            </div>
          ) : (
            <table className="min-w-full">
              <thead className="sticky top-0 bg-gray-50/30 border-b border-gray-100">
                <tr>
                  <th className="px-4 py-3 w-8 text-center">
                    <input
                      type="checkbox"
                      checked={effectiveTransactions.length > 0 && effectiveTransactions.every(t => effectiveSelectedIds.has(t.id))}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                      className="w-3.5 h-3.5 text-gray-900 rounded border-gray-300 focus:ring-gray-900 focus:ring-offset-0"
                    />
                  </th>
                  <th className="px-4 py-2 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider">Portfolio</th>
                  <th className="px-4 py-2 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider">Date</th>
                  <th className="px-4 py-2 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider">Ticker</th>
                  <th className="px-4 py-2 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider">Type</th>
                  <th className="px-4 py-2 text-right text-[10px] font-bold text-gray-400 uppercase tracking-wider">Qty</th>
                  <th className="px-4 py-2 text-right text-[10px] font-bold text-gray-400 uppercase tracking-wider">Price</th>
                  <th className="px-4 py-2 text-right text-[10px] font-bold text-gray-400 uppercase tracking-wider">Value</th>
                  <th className="px-4 py-2 text-right text-[10px] font-bold text-gray-400 uppercase tracking-wider">Realized</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {effectiveTransactions.map((transaction) => {
                  const isBuy = transaction.transaction_type === 'BUY';
                  return (
                    <tr key={transaction.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-4 py-2.5 text-center">
                        <input
                          type="checkbox"
                          checked={effectiveSelectedIds.has(transaction.id)}
                          onChange={(e) => handleSelectOne(transaction.id, e.target.checked)}
                          className="w-3.5 h-3.5 text-gray-900 rounded border-gray-300 focus:ring-gray-900 focus:ring-offset-0"
                        />
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap text-xs text-gray-600 font-medium">
                        {transaction.portfolio_name}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap text-xs text-gray-500 font-medium tabular-nums">
                        {formatDate(transaction.transaction_date)}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap text-xs font-bold text-gray-900">
                        {transaction.ticker}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap">
                        <span className={`text-xs font-semibold ${isBuy ? 'text-gray-600' : 'text-gray-900'}`}>
                          {isBuy ? 'Buy' : 'Sell'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap text-xs text-gray-900 text-right tabular-nums">
                        {transaction.quantity.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap text-xs text-gray-900 text-right tabular-nums">
                        {formatCurrency(transaction.price)}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap text-xs font-medium text-gray-900 text-right tabular-nums">
                        {isBuy ? '-' : '+'}{formatCurrency(Math.abs(transaction.total_amount))}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap text-xs text-right tabular-nums">
                        {transaction.realized_gain_loss !== null && transaction.realized_gain_loss !== undefined ? (
                          <span className={transaction.realized_gain_loss >= 0 ? 'text-gray-900 font-medium' : 'text-red-600 font-medium'}>
                            {transaction.realized_gain_loss >= 0 ? '+' : ''}
                            {formatCurrency(transaction.realized_gain_loss)}
                          </span>
                        ) : (
                          <span className="text-gray-300 text-[10px]">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

          {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between bg-white">
          <div className="flex items-center gap-4">
            {isCreateMode && (
              <>
                <span className="text-[10px] text-gray-400">{total} items</span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    className="p-1 rounded hover:bg-gray-100 disabled:opacity-30 text-gray-600"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <span className="text-[10px] font-medium text-gray-600 min-w-[40px] text-center">
                    {currentPage} / {totalPages}
                  </span>
                  <button
                    onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                    disabled={currentPage === totalPages}
                    className="p-1 rounded hover:bg-gray-100 disabled:opacity-30 text-gray-600"
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="text-sm text-gray-600 hover:text-gray-900 font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={effectiveSelectedIds.size === 0 || isSaving || isLocalSaving}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#0051cc] text-white text-sm font-medium rounded hover:bg-[#003d99] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSaving || isLocalSaving ? (
                'Saving...'
              ) : onSelectionChange ? (
                'Done'
              ) : (
                <>
                  <Save className="h-3.5 w-3.5" />
                  Save Post Mortem ({effectiveSelectedIds.size})
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
