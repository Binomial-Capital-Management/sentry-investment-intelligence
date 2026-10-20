import { useState, useEffect } from 'react';
import { usePortfolioStore } from '@stores/portfolioStore';
import clsx from 'clsx';

const PortfolioSelector = () => {
  const {
    portfolio,
    savedPortfolios,
    selectPortfolio,
    setDefaultPortfolio,
    deletePortfolio,
    loadPortfolios,
    isLoading,
  } = usePortfolioStore();

  // Load portfolios on mount
  useEffect(() => {
    loadPortfolios();
  }, [loadPortfolios]);

  const [isOpen, setIsOpen] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const currentPortfolioName = savedPortfolios.find(p =>
    p.tickers.join(',') === portfolio?.tickers.join(','),
  )?.name || 'Custom Portfolio';

  return (
    <>
      {/* Dropdown Trigger */}
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            background: '#FFFFFF',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            fontSize: '14px',
            cursor: isLoading ? 'wait' : 'pointer',
            opacity: isLoading ? 0.5 : 1,
            width: '240px',
            transition: 'all 0.2s',
            boxShadow: isOpen ? '0 0 0 2px rgba(37, 99, 235, 0.1)' : 'none',
          }}
          onMouseEnter={(e) => {
            if (!isOpen) e.currentTarget.style.borderColor = '#2563eb';
          }}
          onMouseLeave={(e) => {
            if (!isOpen) e.currentTarget.style.borderColor = '#d1d5db';
          }}
          disabled={isLoading}
        >
          <span style={{ fontWeight: '500', flex: 1, textAlign: 'left', color: '#111827' }}>{currentPortfolioName}</span>
          <svg className={clsx('w-4 h-4 transition-transform', isOpen && 'rotate-180')}
               fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Dropdown Menu */}
        {isOpen && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '4px',
            width: '240px',
            background: '#FFFFFF',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
            zIndex: 50,
            overflow: 'hidden',
          }}>
            <div>
              <div style={{
                fontSize: '11px',
                fontWeight: '600',
                color: '#6b7280',
                padding: '10px 14px',
                background: '#f9fafb',
                borderBottom: '1px solid #e5e7eb',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}>
                Saved Portfolios
              </div>

              {savedPortfolios.length === 0 ? (
                <div style={{
                  padding: '20px',
                  textAlign: 'center',
                  fontSize: '13px',
                  color: '#9ca3af',
                }}>
                  No saved portfolios yet
                </div>
              ) : (
                <div className="max-h-64 overflow-y-auto">
                  {savedPortfolios.map((p) => (
                    <div
                      key={p.id}
                      className={clsx(
                        'group flex items-center justify-between px-3 py-2 rounded cursor-pointer',
                        'hover:bg-gray-100 dark:hover:bg-gray-700',
                        p.tickers.join(',') === portfolio?.tickers.join(',') && 'bg-blue-50 dark:bg-blue-900/20',
                      )}
                      onClick={() => {
                        selectPortfolio(p.id);
                        setIsOpen(false);
                      }}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{p.name}</span>
                          {p.is_default && (
                            <span className="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400 rounded">
                              Default
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {!p.is_default && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDefaultPortfolio(p.id);
                            }}
                            className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                            title="Set as default"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                    d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                            </svg>
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm(`Delete portfolio "${p.name}"?`)) {
                              deletePortfolio(p.id);
                            }
                          }}
                          className="p-1 hover:bg-red-100 dark:hover:bg-red-900/20 rounded text-red-600 dark:text-red-400"
                          title="Delete"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ borderTop: '1px solid #e5e7eb', padding: '4px' }}>
                <button
                  onClick={() => {
                    setShowCreateModal(true);
                    setIsOpen(false);
                  }}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 14px',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '13px',
                    textAlign: 'left',
                    borderRadius: '4px',
                    transition: 'background 0.2s',
                    color: '#2563eb',
                    fontWeight: '500',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#f3f4f6'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M12 4v16m8-8H4" />
                  </svg>
                  <span>Create New Portfolio</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Create Portfolio Modal */}
      {showCreateModal && (
        <CreatePortfolioModal onClose={() => setShowCreateModal(false)} />
      )}
    </>
  );
};

// Create Portfolio Modal Component
const CreatePortfolioModal = ({ onClose }: { onClose: () => void }) => {
  const { createPortfolio, loadPortfolios, isLoading: storeLoading } = usePortfolioStore();
  const [name, setName] = useState('');
  const [tickerInput, setTickerInput] = useState('');
  const [holdings, setHoldings] = useState<{ticker: string, weight: string}[]>([]);
  const [value, setValue] = useState('1000000');
  const [isDefault, setIsDefault] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const addTicker = () => {
    const ticker = tickerInput.trim().toUpperCase();
    if (ticker && !holdings.find(h => h.ticker === ticker)) {
      // Add new ticker with empty weight (user will fill it)
      setHoldings([...holdings, { ticker, weight: '' }]);
      setTickerInput('');
    }
  };

  const removeTicker = (index: number) => {
    setHoldings(holdings.filter((_, i) => i !== index));
  };

  const updateWeight = (index: number, weight: string) => {
    const newHoldings = [...holdings];
    newHoldings[index].weight = weight;
    setHoldings(newHoldings);
  };

  const equalizeWeights = () => {
    if (holdings.length > 0) {
      const equalWeight = (100 / holdings.length).toFixed(1);
      setHoldings(holdings.map(h => ({...h, weight: equalWeight})));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    if (holdings.length === 0) {
      setError('Please add at least one ticker');
      setIsSubmitting(false);
      return;
    }

    // Parse weights and check validity
    const weights = holdings.map(h => parseFloat(h.weight) || 0);
    if (weights.some(w => w <= 0)) {
      setError('Please enter valid weights for all holdings');
      setIsSubmitting(false);
      return;
    }

    const decimalWeights = weights.map(w => w / 100); // Convert percentage to decimal (don't normalize - cash is implied)

    try {
      await createPortfolio({
        name: name || `Portfolio ${new Date().toLocaleDateString()}`,
        tickers: holdings.map(h => h.ticker),
        weights: decimalWeights,
        value: parseFloat(value) || 1000000,
        is_default: isDefault,
      });

      // Reload portfolios from backend to ensure consistency
      await loadPortfolios();

      setIsSubmitting(false);
      onClose();
    } catch (err) {
      console.error('Portfolio creation error:', err);
      setError((err as Error).message);
      setIsSubmitting(false);
    }
  };

  const totalWeight = holdings.reduce((sum, h) => (parseFloat(h.weight) || 0) + sum, 0);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold">Quick Portfolio Builder</h2>
        </div>

        <div className="p-6">
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 mb-1">Portfolio Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Portfolio"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
            />
          </div>

          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 mb-1">Add Holdings</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTicker())}
                placeholder="Enter ticker (e.g., AAPL)"
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm font-mono"
              />
              <button
                type="button"
                onClick={addTicker}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
              >
                Add
              </button>
            </div>
          </div>

          {holdings.length > 0 && (
            <div className="mb-4 max-h-64 overflow-y-auto">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-medium text-gray-500">HOLDINGS</span>
                <button
                  type="button"
                  onClick={equalizeWeights}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                >
                  Equalize All
                </button>
              </div>
              <div className="space-y-2">
                {holdings.map((holding, index) => {
                  const weight = parseFloat(holding.weight) || 0;
                  const percentage = totalWeight > 0 ? (weight / totalWeight * 100) : 0;

                  return (
                    <div key={index} className="flex items-center gap-2">
                      <span className="font-mono text-sm font-semibold w-16">{holding.ticker}</span>
                      <input
                        type="text"
                        value={holding.weight}
                        onChange={(e) => updateWeight(index, e.target.value)}
                        placeholder="Weight"
                        className="w-20 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm text-center"
                      />
                      <span className="text-sm text-gray-500 w-12 text-right">
                        {percentage > 0 ? `${percentage.toFixed(1)}%` : '-'}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeTicker(index)}
                        className="text-red-500 hover:text-red-700 text-lg px-1"
                      >
                        ?
                      </button>
                    </div>
                  );
                })}
              </div>
              {Math.abs(totalWeight - 100) > 0.1 && (
                <p className="text-xs text-amber-600 mt-2">
                  Weights will be normalized to 100%
                </p>
              )}
            </div>
          )}

          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 mb-1">Portfolio Value (USD)</label>
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value.replace(/[^0-9.]/g, ''))}
              placeholder="1000000"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">Total value of this portfolio in USD</p>
          </div>

          <div className="flex items-center gap-2 mb-4">
            <input
              type="checkbox"
              id="isDefault"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="isDefault" className="text-sm">Set as default portfolio</label>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 p-2 rounded mb-4">
              {error}
            </div>
          )}
        </div>

        <div className="px-6 py-3 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={holdings.length === 0 || isSubmitting}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            style={{
              cursor: isSubmitting ? 'wait' : 'pointer',
            }}
          >
            {isSubmitting ? 'Creating...' : 'Create Portfolio'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PortfolioSelector;
