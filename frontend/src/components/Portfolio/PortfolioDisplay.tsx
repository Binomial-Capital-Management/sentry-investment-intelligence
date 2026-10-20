import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePortfolioStore } from '@stores/portfolioStore';
import PortfolioSelector from './PortfolioSelector';
import { Settings, Edit2, Briefcase, TrendingUp, TrendingDown, Activity, DollarSign } from 'lucide-react';

const PortfolioDisplay = () => {
  const navigate = useNavigate();
  const { portfolio, savedPortfolios, updateValue } = usePortfolioStore();
  const [isEditingValue, setIsEditingValue] = useState(false);
  const [editValue, setEditValue] = useState('');
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  if (!portfolio) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-12 text-center">
        <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Briefcase className="w-8 h-8 text-gray-400" />
        </div>
        <p className="text-gray-500 text-sm mb-6">No portfolio currently selected.</p>
        <PortfolioSelector />
      </div>
    );
  }

  const totalWeight = portfolio.weights?.reduce((sum, w) => sum + w, 0) || 0;
  const isBalanced = Math.abs(totalWeight - 1.0) < 0.001;
  const savedPortfolio = savedPortfolios.find(p =>
    p.tickers.join(',') === portfolio.tickers.join(','),
  );

  return (
    <div className="font-sans">
      {/* Portfolio Header Card */}
      <div className="bg-gradient-to-br from-white to-blue-50/50 rounded-2xl border border-blue-100 mb-6 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-blue-100/50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded-lg border border-blue-100 shadow-sm">
                <Briefcase className="w-5 h-5 text-blue-600" />
            </div>
            <span className="text-lg font-bold text-gray-900 tracking-tight">
              Portfolio Overview
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Value Editor */}
            <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-gray-200 shadow-sm">
                {isEditingValue ? (
                <input
                    type="number"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onBlur={() => {
                    const newValue = parseFloat(editValue);
                    if (!isNaN(newValue) && newValue > 0) updateValue(newValue);
                    setIsEditingValue(false);
                    }}
                    onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                        const newValue = parseFloat(editValue);
                        if (!isNaN(newValue) && newValue > 0) updateValue(newValue);
                        setIsEditingValue(false);
                    } else if (e.key === 'Escape') setIsEditingValue(false);
                    }}
                    className="w-32 text-sm font-mono border-0 focus:ring-0 p-0"
                    autoFocus
                />
                ) : (
                <>
                    <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">Value</span>
                    <span className="text-sm font-bold text-gray-900 font-mono">
                    ${portfolio.value.toLocaleString()}
                    </span>
                    <button
                    onClick={() => { setEditValue(portfolio.value.toString()); setIsEditingValue(true); }}
                    className="p-1 hover:bg-gray-100 rounded-md text-gray-400 hover:text-gray-600 transition-colors"
                    >
                    <Edit2 className="w-3 h-3" />
                    </button>
                </>
                )}
            </div>

            <button
              onClick={() => setShowSettingsModal(true)}
              className="p-2 hover:bg-white hover:shadow-sm hover:border-gray-200 border border-transparent rounded-lg text-gray-400 hover:text-gray-700 transition-all"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="px-6 py-4 bg-white/50">
          <div className="flex items-center gap-4 flex-wrap">
            <PortfolioSelector />
            {savedPortfolio?.is_default && (
              <span className="px-2.5 py-1 bg-amber-50 text-amber-700 text-[10px] font-bold rounded-md uppercase tracking-wider border border-amber-100">
                Default
              </span>
            )}
            {!isBalanced && (
              <div className="flex items-center gap-2 px-3 py-1 bg-red-50 border border-red-100 rounded-md ml-auto">
                <Activity className="w-3 h-3 text-red-500" />
                <span className="text-xs font-bold text-red-600">
                  Weights: {(totalWeight * 100).toFixed(1)}% (Unbalanced)
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                <Briefcase className="w-3.5 h-3.5" /> Positions
            </div>
            <div className="text-2xl font-bold text-gray-900">
                {portfolio.tickers.length} <span className="text-sm font-medium text-gray-400">assets</span>
            </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                <DollarSign className="w-3.5 h-3.5" /> Total AUM
            </div>
            <div className="text-2xl font-bold text-gray-900">
                ${(portfolio.value / 1000000).toFixed(2)}M
            </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5" /> Status
            </div>
            <div className={`text-2xl font-bold ${isBalanced ? 'text-emerald-600' : 'text-red-600'}`}>
                {isBalanced ? 'Balanced' : 'Unbalanced'}
            </div>
        </div>
      </div>

      {/* Holdings Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="bg-gray-50/80 border-b border-gray-200">
              <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs">Ticker</th>
              <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs text-right">Weight</th>
              <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs text-center">Allocation</th>
              <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs text-right">Value</th>
              <th className="px-6 py-3 font-semibold text-gray-500 uppercase tracking-wider text-xs text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {portfolio.tickers.map((ticker, index) => {
              const weight = portfolio.weights?.[index] || 0;
              const value = portfolio.value * weight;
              const isOverweight = weight > 0.4;
              const isUnderweight = weight < 0.05;

              return (
                <tr
                  key={ticker}
                  className="hover:bg-gray-50/80 transition-colors group"
                >
                  <td className="px-6 py-4">
                    <button
                      onClick={() => navigate(`/company/${ticker}`)}
                      className="font-mono font-bold text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {ticker}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-right font-medium text-gray-700">
                    {(weight * 100).toFixed(2)}%
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-center gap-3">
                      <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                           className={`h-full rounded-full ${isOverweight ? 'bg-red-500' : isUnderweight ? 'bg-amber-400' : 'bg-blue-500'}`}
                           style={{ width: `${weight * 100}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right font-medium text-gray-900">
                    ${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </td>
                  <td className="px-6 py-4 text-center">
                    {isOverweight ? (
                      <span className="px-2 py-0.5 bg-red-50 text-red-600 rounded text-[10px] font-bold uppercase border border-red-100">Over</span>
                    ) : isUnderweight ? (
                      <span className="px-2 py-0.5 bg-amber-50 text-amber-600 rounded text-[10px] font-bold uppercase border border-amber-100">Low</span>
                    ) : (
                      <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded text-[10px] font-bold uppercase border border-emerald-100">OK</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot className="bg-gray-50 border-t border-gray-200">
            <tr>
              <td className="px-6 py-3 font-bold text-gray-900 text-xs uppercase">Total</td>
              <td className="px-6 py-3 text-right font-bold text-gray-900 text-xs uppercase">
                {(totalWeight * 100).toFixed(2)}%
              </td>
              <td className="px-6 py-3 text-center">
                {isBalanced ? (
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded text-[10px] font-bold uppercase">Valid</span>
                ) : (
                  <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-[10px] font-bold uppercase">Invalid</span>
                )}
              </td>
              <td className="px-6 py-3 text-right font-bold text-gray-900 text-xs uppercase">
                ${portfolio.value.toLocaleString()}
              </td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Action Buttons */}
      <div className="mt-6 flex gap-3">
        <button className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg shadow-sm transition-colors">
          Analyze Risk
        </button>
        <button className="px-5 py-2.5 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 font-medium rounded-lg transition-colors">
          Optimize Allocation
        </button>
        <button className="px-5 py-2.5 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 font-medium rounded-lg transition-colors">
          Rebalance
        </button>
      </div>

      {/* Settings Modal (Placeholder) */}
      {showSettingsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
           <div className="bg-white rounded-xl p-6 w-full max-w-md">
              <div className="flex justify-between items-center mb-4">
                 <h3 className="font-bold text-lg">Settings</h3>
                 <button onClick={() => setShowSettingsModal(false)}><Settings className="w-5 h-5 text-gray-400" /></button>
              </div>
              <p className="text-gray-500 text-sm">Settings configuration would go here...</p>
              <button onClick={() => setShowSettingsModal(false)} className="mt-6 w-full py-2 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium">Close</button>
           </div>
        </div>
      )}
    </div>
  );
};

export default PortfolioDisplay;
