import { useState, useMemo, useEffect, useRef } from 'react';
import { Search, Check, X } from 'lucide-react';

interface Transaction {
  id: string;
  portfolio_name: string;
  ticker: string;
  transaction_type: string;
  quantity: number;
  price: number;
  transaction_date: string;
  realized_gain_loss: number | null;
  total_amount: number;
}

interface TransactionSelectorMenuProps {
  isOpen: boolean;
  onClose: () => void;
  transactions: Transaction[];
  selectedIds: Set<string>;
  onSelectionChange: (ids: Set<string>) => void;
}

export default function TransactionSelectorMenu({
  isOpen,
  onClose,
  transactions,
  selectedIds,
  onSelectionChange,
}: TransactionSelectorMenuProps) {
  const [search, setSearch] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  const filteredTransactions = useMemo(() => {
    if (!search.trim()) return transactions;
    const lowerSearch = search.toLowerCase();
    return transactions.filter(t =>
      t.ticker.toLowerCase().includes(lowerSearch) ||
      t.portfolio_name.toLowerCase().includes(lowerSearch),
    );
  }, [transactions, search]);

  const toggleTransaction = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    onSelectionChange(newSelected);
  };

  const handleSelectAll = () => {
    const newSelected = new Set(selectedIds);
    filteredTransactions.forEach(t => newSelected.add(t.id));
    onSelectionChange(newSelected);
  };

  const handleDeselectAll = () => {
    const newSelected = new Set(selectedIds);
    filteredTransactions.forEach(t => newSelected.delete(t.id));
    onSelectionChange(newSelected);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  if (!isOpen) return null;

  return (
    <div
      ref={menuRef}
      className="absolute bottom-full right-0 mb-2 w-[320px] bg-white border border-gray-200 rounded-lg shadow-xl z-50 flex flex-col animate-in slide-in-from-bottom-2 duration-200"
      style={{ maxHeight: '360px' }}
    >
      {/* Header / Search */}
      <div className="p-2 border-b border-gray-100 bg-white rounded-t-lg space-y-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-[11px] font-semibold text-gray-800">Select Transactions</span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSelectAll}
              className="text-[10px] text-blue-600 hover:text-blue-800 font-medium"
            >
              All
            </button>
            <span className="text-gray-200 text-[10px]">|</span>
            <button
              onClick={handleDeselectAll}
              className="text-[10px] text-gray-400 hover:text-gray-600"
            >
              None
            </button>
          </div>
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-1.5 h-3 w-3 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter..."
            className="w-full pl-6 pr-2 py-1 text-[11px] border border-gray-200 rounded bg-gray-50 focus:outline-none focus:border-blue-400 focus:bg-white transition-colors placeholder:text-gray-400"
            autoFocus
          />
        </div>
      </div>

      {/* List */}
      <div className="overflow-y-auto flex-1 py-1">
        {filteredTransactions.length === 0 ? (
          <div className="py-4 text-center text-xs text-gray-400">
            No transactions found
          </div>
        ) : (
          filteredTransactions.map(t => {
            const isSelected = selectedIds.has(t.id);
            const isBuy = t.transaction_type === 'BUY';
            return (
              <div
                key={t.id}
                onClick={() => toggleTransaction(t.id)}
                className={`px-2 py-1.5 flex items-center gap-2 cursor-pointer hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0 ${
                  isSelected ? 'bg-blue-50/40 hover:bg-blue-50/60' : ''
                }`}
              >
                <div className={`flex-shrink-0 w-3 h-3 border rounded flex items-center justify-center transition-colors ${
                  isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-300'
                }`}>
                  {isSelected && <Check className="h-2 w-2 text-white" />}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-[11px] text-gray-900">{t.ticker}</span>
                      <span className={`text-[9px] px-1 rounded-sm ${
                        isBuy ? 'bg-gray-100 text-gray-600' : 'bg-gray-100 text-gray-900'
                      }`}>
                        {t.transaction_type}
                      </span>
                    </div>
                    <span className={`text-[10px] font-medium tabular-nums ${
                      (t.realized_gain_loss || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {t.realized_gain_loss ? (t.realized_gain_loss >= 0 ? '+' : '') + formatCurrency(t.realized_gain_loss) : '-'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[9px] text-gray-400">
                    <div className="flex items-center gap-1">
                      <span>{formatDate(t.transaction_date)}</span>
                      <span className="text-gray-200">•</span>
                      <span className="truncate max-w-[80px]">{t.portfolio_name}</span>
                    </div>
                    <span className="tabular-nums text-gray-500">{formatCurrency(Math.abs(t.total_amount))}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="px-2 py-1.5 border-t border-gray-100 bg-white rounded-b-lg flex items-center justify-between">
        <span className="text-[10px] text-gray-400">
          {selectedIds.size} selected
        </span>
        <button
          onClick={onClose}
          className="px-2 py-0.5 text-[10px] bg-gray-900 text-white rounded shadow-sm hover:bg-gray-800 font-medium transition-colors"
        >
          Done
        </button>
      </div>
    </div>
  );
}
