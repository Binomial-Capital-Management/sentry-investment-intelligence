import type { TransactionImportPreview } from '../types';

interface Props {
  preview: TransactionImportPreview;
}

export default function TransactionPreview({ preview }: Props) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  return (
    <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
      <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-3">Preview</h3>
      <div className="grid grid-cols-3 gap-4">
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-1">Trades</div>
          <div className="text-lg font-bold text-gray-900">{preview.count}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-1">Win Rate</div>
          <div className="text-lg font-bold text-emerald-600">{preview.metrics.winRate.toFixed(1)}%</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-1">Total P&L</div>
          <div className={`text-lg font-bold ${preview.metrics.totalPnL >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {preview.metrics.totalPnL >= 0 ? '+' : ''}{formatCurrency(preview.metrics.totalPnL)}
          </div>
        </div>
      </div>

      {/* Additional metrics */}
      <div className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-gray-500">Avg Win:</span>
          <span className="ml-2 font-medium text-emerald-600">{formatCurrency(preview.metrics.avgWin)}</span>
        </div>
        <div>
          <span className="text-gray-500">Avg Loss:</span>
          <span className="ml-2 font-medium text-red-600">{formatCurrency(preview.metrics.avgLoss)}</span>
        </div>
        <div>
          <span className="text-gray-500">Payoff Ratio:</span>
          <span className="ml-2 font-medium text-gray-900">{preview.metrics.payoffRatio.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-gray-500">Best Trade:</span>
          <span className="ml-2 font-medium text-emerald-600">{formatCurrency(preview.metrics.biggestWin)}</span>
        </div>
      </div>
    </div>
  );
}
