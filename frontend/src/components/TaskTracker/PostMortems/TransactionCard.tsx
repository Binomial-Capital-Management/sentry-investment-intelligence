import { TrendingUp, TrendingDown } from 'lucide-react';

interface Transaction {
  date: string;
  ticker: string;
  type: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  realized_pnl?: number | null;
}

interface TransactionCardProps {
  transactions: Transaction[];
}

export default function TransactionCard({ transactions }: TransactionCardProps) {
  const totalPnL = transactions.reduce((sum, tx) => sum + (tx.realized_pnl || 0), 0);
  const winners = transactions.filter(tx => (tx.realized_pnl || 0) > 0).length;
  const losers = transactions.filter(tx => (tx.realized_pnl || 0) < 0).length;

  return (
    <div className="mb-3 bg-gray-50 border border-gray-200 rounded-lg p-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium text-gray-700">
          {transactions.length} Trade{transactions.length !== 1 ? 's' : ''} Analyzed
        </div>
        <div className={`text-xs font-bold ${totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {totalPnL >= 0 ? '+' : ''}{totalPnL.toFixed(2)} P&L
        </div>
      </div>

      {/* Summary Stats */}
      <div className="flex items-center gap-3 mt-2 text-[10px] text-gray-600">
        <span className="flex items-center gap-1">
          <TrendingUp size={12} className="text-green-600" />
          {winners} Win{winners !== 1 ? 's' : ''}
        </span>
        <span className="flex items-center gap-1">
          <TrendingDown size={12} className="text-red-600" />
          {losers} Loss{losers !== 1 ? 'es' : ''}
        </span>
        {winners + losers > 0 && (
          <span>
            {((winners / (winners + losers)) * 100).toFixed(0)}% Win Rate
          </span>
        )}
      </div>
    </div>
  );
}
