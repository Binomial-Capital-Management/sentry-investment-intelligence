import { useState, useEffect } from 'react';
import { portfolioApi } from '../../services/portfolioApi';
import { toast } from 'react-hot-toast';
import { Transaction, TransactionHistoryResponse, TransactionFilters } from '../../types/transaction';
import { Search, Calendar, Filter, Trash2, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';

interface TransactionHistoryTabProps {
  portfolioId: string;
}

export default function TransactionHistoryTab({ portfolioId }: TransactionHistoryTabProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [perPage] = useState(20);
  const [filters, setFilters] = useState<TransactionFilters>({
    ticker: null,
    type: null,
    dateFrom: null,
    dateTo: null,
  });
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [availableTickers, setAvailableTickers] = useState<string[]>([]);

  // Fetch transactions
  const fetchTransactions = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        per_page: perPage.toString(),
      });

      if (filters.ticker) params.append('ticker', filters.ticker);
      if (filters.type) params.append('transaction_type', filters.type);
      if (filters.dateFrom) params.append('date_from', filters.dateFrom);
      if (filters.dateTo) params.append('date_to', filters.dateTo);

      const response = await portfolioApi.get<TransactionHistoryResponse>(
        `/${portfolioId}/transactions?${params}`,
      );

      setTransactions(response.data.transactions);
      setTotalPages(response.data.total_pages);
      setTotal(response.data.total);

      // Extract unique tickers for filter dropdown
      const tickers = Array.from(new Set(response.data.transactions.map(t => t.ticker)));
      setAvailableTickers(tickers);
    } catch (error) {
      console.error('Failed to fetch transactions:', error);
      toast.error('Failed to load transaction history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [currentPage, filters]);

  // Handle select all (current page)
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const newSelected = new Set(selectedIds);
      transactions.forEach(t => newSelected.add(t.id));
      setSelectedIds(newSelected);
    } else {
      setSelectedIds(new Set());
    }
  };

  // Handle individual selection
  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedIds(newSelected);
  };

  // Handle delete
  const handleDelete = async () => {
    if (selectedIds.size === 0) return;

    try {
      await portfolioApi.delete(`/${portfolioId}/transactions`, {
        data: { transaction_ids: Array.from(selectedIds) },
      });

      toast.success(`Deleted ${selectedIds.size} transaction(s)`);
      setSelectedIds(new Set());
      setShowDeleteModal(false);

      // If we deleted all items on current page and not on page 1, go to previous page
      if (transactions.length === selectedIds.size && currentPage > 1) {
        setCurrentPage(currentPage - 1);
      } else {
        fetchTransactions();
      }
    } catch (error) {
      console.error('Failed to delete transactions:', error);
      toast.error('Failed to delete transactions');
    }
  };

  // Clear filters
  const clearFilters = () => {
    setFilters({ ticker: null, type: null, dateFrom: null, dateTo: null });
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

  return (
    <div className="space-y-4">
      {/* Minimalist Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-gray-100">
        <div className="flex items-center gap-4">
          {/* Ticker Filter - Text Only */}
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

          {/* Type Filter - Text Only */}
          <div className="relative">
            <select
              value={filters.type || ''}
              onChange={(e) => setFilters({ ...filters, type: e.target.value as 'BUY' | 'SELL' | null })}
              className="appearance-none bg-transparent text-sm font-medium text-gray-900 pr-6 py-1 focus:outline-none cursor-pointer hover:text-gray-600"
            >
              <option value="">All Types</option>
              <option value="BUY">Buys</option>
              <option value="SELL">Sells</option>
            </select>
            <ChevronDown className="absolute right-0 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400 pointer-events-none" />
          </div>

          <div className="h-4 w-px bg-gray-200"></div>

          {/* Date Filter - Compact */}
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

          {(filters.ticker || filters.type || filters.dateFrom || filters.dateTo) && (
            <button
              onClick={clearFilters}
              className="text-xs text-red-500 hover:text-red-700 ml-2 font-medium"
            >
              Clear
            </button>
          )}
        </div>

        {/* Actions */}
        {selectedIds.size > 0 && (
          <button
            onClick={() => setShowDeleteModal(true)}
            className="flex items-center gap-1.5 text-xs font-medium text-red-600 hover:text-red-700 bg-red-50 px-2 py-1 rounded transition-colors"
          >
            <Trash2 className="h-3 w-3" />
            Delete ({selectedIds.size})
          </button>
        )}
      </div>

      {/* Transactions Table - Professional/Dense */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-5 w-5 border-2 border-gray-300 border-t-gray-900"></div>
          </div>
        ) : transactions.length === 0 ? (
          <div className="text-center py-12 text-sm text-gray-500">
            No transactions found
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/30">
                    <th className="px-4 py-3 w-8 text-center">
                      <input
                        type="checkbox"
                        checked={allPageSelected}
                        onChange={(e) => handleSelectAll(e.target.checked)}
                        className="w-3.5 h-3.5 text-gray-900 rounded border-gray-300 focus:ring-gray-900 focus:ring-offset-0"
                      />
                    </th>
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
                  {transactions.map((transaction) => {
                    const isBuy = transaction.transaction_type === 'BUY';
                    return (
                      <tr
                        key={transaction.id}
                        className="hover:bg-gray-50/50 transition-colors"
                      >
                        <td className="px-4 py-2.5 text-center">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(transaction.id)}
                            onChange={(e) => handleSelectOne(transaction.id, e.target.checked)}
                            className="w-3.5 h-3.5 text-gray-900 rounded border-gray-300 focus:ring-gray-900 focus:ring-offset-0"
                          />
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap text-xs text-gray-500 font-medium tabular-nums">
                          {formatDate(transaction.transaction_date)}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap text-xs font-bold text-gray-900">
                          {transaction.ticker}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          <span
                            className={`text-xs font-semibold ${isBuy ? 'text-blue-600' : 'text-emerald-600'}`}
                          >
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
                            <span className={transaction.realized_gain_loss >= 0 ? 'text-emerald-600 font-medium' : 'text-red-600 font-medium'}>
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
            </div>

            {/* Compact Footer */}
            <div className="px-4 py-2 border-t border-gray-100 flex items-center justify-between bg-white">
              <span className="text-[10px] text-gray-400">
                {total} items
              </span>
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
            </div>
          </>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-sm transition-opacity">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full shadow-2xl border border-gray-100 transform transition-all scale-100">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Confirm Deletion</h3>
            <p className="text-sm text-gray-500 mb-6 leading-relaxed">
              Are you sure you want to delete <span className="font-bold text-gray-900">{selectedIds.size}</span> transaction(s)? This action cannot be undone and will affect your portfolio history.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors focus:ring-2 focus:ring-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-lg hover:bg-red-700 transition-colors shadow-sm focus:ring-2 focus:ring-red-500 focus:ring-offset-1"
              >
                Delete Transactions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
