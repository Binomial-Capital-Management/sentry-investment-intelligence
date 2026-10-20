import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePortfolioStore } from '@stores/portfolioStore';
import { Trash2, Star, Link, ChevronDown, FileSpreadsheet, Plus, Search, LayoutGrid, List as ListIcon, MoreHorizontal, HelpCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import WorkspaceIndicator from '@/components/Common/WorkspaceIndicator';
import { IBKRConnectionModal } from './IBKRConnectionModal';
import { PortfolioImportModal } from './PortfolioImportModal';
import { PortfolioGuidePanel } from './PortfolioGuidePanel';

const PortfolioPage = () => {
  const navigate = useNavigate();
  const {
    savedPortfolios = [],
    createPortfolio,
    deletePortfolio,
    setDefaultPortfolio,
    loadPortfolios,
    isLoading,
  } = usePortfolioStore();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showBrokerModal, setShowBrokerModal] = useState(false);
  const [showBrokerDropdown, setShowBrokerDropdown] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [searchQuery, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list'); // Defaulting to list as per preference

  // Enhanced portfolio state with holdings
  interface Lot {
    quantity: number;
    purchasePrice: number;
    purchaseDate: string;
  }

  interface Holding {
    ticker: string;
    lots: Lot[];
    showLots?: boolean;
  }

  const [newPortfolio, setNewPortfolio] = useState({
    name: '',
    holdings: [] as Holding[],
    cashBalance: 0,
  });

  const [currentHolding, setCurrentHolding] = useState({
    ticker: '',
    quantity: '',
    purchasePrice: '',
    purchaseDate: new Date().toISOString().split('T')[0],
  });

  useEffect(() => {
    loadPortfolios();
  }, [loadPortfolios]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (showBrokerDropdown && !target.closest('[data-broker-dropdown]')) {
        setShowBrokerDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showBrokerDropdown]);

  const handleCreate = async () => {
    try {
      if (newPortfolio.holdings.length === 0) {
        toast.error('Please add at least one holding');
        return;
      }

      const holdingsPayload = newPortfolio.holdings.map(holding => ({
        ticker: holding.ticker,
        lots: holding.lots,
      }));

      const tickers = newPortfolio.holdings.map(h => h.ticker);

      const calculateHoldingValue = (holding: Holding) => {
        return holding.lots.reduce((sum, lot) => sum + (lot.quantity * lot.purchasePrice), 0);
      };

      const totalHoldingsValue = newPortfolio.holdings.reduce((sum, h) =>
        sum + calculateHoldingValue(h), 0,
      );
      const totalPortfolioValue = totalHoldingsValue + newPortfolio.cashBalance;

      const weights = totalPortfolioValue > 0
        ? newPortfolio.holdings.map(h => calculateHoldingValue(h) / totalPortfolioValue)
        : tickers.map(() => 1 / tickers.length);

      const createdPortfolio = await createPortfolio({
        name: newPortfolio.name || 'Untitled Portfolio',
        tickers,
        weights,
        holdings: holdingsPayload,
        value: totalPortfolioValue,
        cash_balance: newPortfolio.cashBalance,
      });

      await loadPortfolios();
      toast.success('Portfolio created successfully');
      setShowCreateModal(false);
      resetForm();

      if (createdPortfolio?.id) {
        navigate(`/portfolio/${createdPortfolio.id}`);
      }
    } catch (error) {
      console.error('Portfolio creation error:', error);
      toast.error('Failed to create portfolio');
    }
  };

  const resetForm = () => {
    setNewPortfolio({ name: '', holdings: [], cashBalance: 0 });
    setCurrentHolding({
      ticker: '',
      quantity: '',
      purchasePrice: '',
      purchaseDate: new Date().toISOString().split('T')[0],
    });
  };

  const handleAddHolding = () => {
    const { ticker, quantity, purchasePrice, purchaseDate } = currentHolding;
    if (!ticker || !quantity || !purchasePrice) {
      toast.error('Please fill in all holding fields');
      return;
    }
    const qty = parseFloat(quantity);
    const price = parseFloat(purchasePrice);
    if (qty <= 0 || price <= 0) {
      toast.error('Quantity and price must be positive');
      return;
    }

    const existingIndex = newPortfolio.holdings.findIndex(h => h.ticker === ticker.toUpperCase());

    if (existingIndex >= 0) {
      const updatedHoldings = [...newPortfolio.holdings];
      updatedHoldings[existingIndex].lots.push({
        quantity: qty,
        purchasePrice: price,
        purchaseDate: purchaseDate,
      });
      setNewPortfolio({ ...newPortfolio, holdings: updatedHoldings });
    } else {
      const newHolding: Holding = {
        ticker: ticker.toUpperCase(),
        lots: [{ quantity: qty, purchasePrice: price, purchaseDate: purchaseDate }],
        showLots: false,
      };
      setNewPortfolio({ ...newPortfolio, holdings: [...newPortfolio.holdings, newHolding] });
    }
    setCurrentHolding({
      ticker: '',
      quantity: '',
      purchasePrice: '',
      purchaseDate: new Date().toISOString().split('T')[0],
    });
    toast.success('Holding added');
  };

  const handleRemoveHolding = (ticker: string) => {
    setNewPortfolio({
      ...newPortfolio,
      holdings: newPortfolio.holdings.filter(h => h.ticker !== ticker),
    });
  };

  const handleBrokerConnectionSuccess = async (portfolioId: string, portfolioName: string) => {
    toast.success(`IBKR account connected! Portfolio "${portfolioName}" created.`);
    await loadPortfolios();
  };

  const handleImportFile = () => {
    setShowBrokerDropdown(false);
    setShowImportModal(true);
  };

  const handleImportSuccess = async () => {
    toast.success('Portfolio imported successfully!');
    await loadPortfolios();
  };

  const filteredPortfolios = savedPortfolios.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="flex flex-col h-full bg-[#fafafa] transition-all duration-300" style={{ marginRight: showGuide ? '576px' : '0' }}>
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
             <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Portfolios</h1>
             <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
                <span>Manage your investment collections</span>
                <span className="text-gray-300">•</span>
                <WorkspaceIndicator size="sm" />
             </div>
          </div>
          <div className="flex items-center gap-3">
             <button
               onClick={() => setShowGuide(true)}
               className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
               title="Portfolio Guide"
             >
               <HelpCircle size={20} />
             </button>
             <div data-broker-dropdown className="relative">
                <button
                  onClick={() => setShowBrokerDropdown(!showBrokerDropdown)}
                  className="px-4 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-lg shadow-sm transition-all flex items-center gap-2"
                >
                  <Link className="w-4 h-4 text-blue-600" />
                  Connect Broker
                  <ChevronDown className="w-3 h-3 text-gray-400" />
                </button>

                {showBrokerDropdown && (
                  <div className="absolute top-full right-0 mt-2 w-64 bg-white border border-gray-100 rounded-xl shadow-xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100">
                    <div className="p-1">
                        <button
                          onClick={() => { setShowBrokerDropdown(false); setShowBrokerModal(true); }}
                          className="w-full px-3 py-2.5 flex items-center gap-3 hover:bg-gray-50 rounded-lg transition-colors text-left group"
                        >
                          <div className="w-8 h-8 bg-white border border-gray-100 rounded-lg flex items-center justify-center shadow-sm group-hover:border-blue-200 transition-colors">
                             <img src="/connector-logos/ibkr-logo.png" alt="IBKR" className="w-5 h-5 object-contain" />
                          </div>
                          <div>
                             <div className="text-sm font-semibold text-gray-900">Interactive Brokers</div>
                             <div className="text-xs text-gray-500">Direct API sync</div>
                          </div>
                        </button>

                        <div className="h-px bg-gray-100 my-1" />

                        <button onClick={handleImportFile} className="w-full px-3 py-2.5 flex items-center gap-3 hover:bg-gray-50 rounded-lg transition-colors text-left">
                           <FileSpreadsheet className="w-4 h-4 text-emerald-600 ml-2" />
                           <span className="text-sm text-gray-700 font-medium ml-1">Import CSV / Excel</span>
                        </button>
                    </div>
                  </div>
                )}
             </div>

             <button
                onClick={() => setShowCreateModal(true)}
                style={{ backgroundColor: '#0051cc' }}
                className="px-4 py-2 text-white text-sm font-medium rounded-lg shadow-sm hover:shadow-md flex items-center gap-2 transition-all hover:opacity-90"
              >
                <Plus className="w-4 h-4" />
                New Portfolio
              </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
            {/* Search */}
            <div className="relative max-w-md w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                    type="text"
                    placeholder="Search portfolios..."
                    value={searchQuery}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 bg-gray-50 border-0 rounded-lg text-sm focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
            </div>

            {/* View Toggle */}
            <div className="flex items-center bg-gray-100 p-1 rounded-lg border border-gray-200/50">
                <button
                    onClick={() => setViewMode('list')}
                    className={`p-1.5 rounded-md transition-all ${viewMode === 'list' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
                    title="List View"
                >
                    <ListIcon className="w-4 h-4" />
                </button>
                <button
                    onClick={() => setViewMode('grid')}
                    className={`p-1.5 rounded-md transition-all ${viewMode === 'grid' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
                    title="Grid View"
                >
                    <LayoutGrid className="w-4 h-4" />
                </button>
            </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-8">
        {filteredPortfolios.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-96 bg-white rounded-2xl border border-gray-100 border-dashed">
             <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mb-4">
                <Search className="w-5 h-5 text-gray-400" />
             </div>
             <h3 className="text-sm font-semibold text-gray-900">No portfolios found</h3>
             <p className="text-gray-500 text-sm mt-1">
                {savedPortfolios.length === 0 ? 'Create your first portfolio to get started.' : 'Try adjusting your search terms.'}
             </p>
          </div>
        ) : (
          <>
            {viewMode === 'grid' ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                    {filteredPortfolios.map((p) => (
                    <div
                        key={p.id}
                        onClick={() => navigate(`/portfolio/${p.id}`)}
                        className="group bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md hover:border-gray-300 transition-all duration-200 cursor-pointer relative overflow-hidden flex flex-col"
                    >
                        <div className="p-5 flex-1">
                            <div className="flex justify-between items-start mb-3">
                                <div>
                                    <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors truncate pr-2">
                                        {p.name}
                                    </h3>
                                    <p className="text-xs text-gray-500 mt-0.5">
                                        {new Date(p.created_at || Date.now()).toLocaleDateString()}
                                    </p>
                                </div>
                                {p.is_default && (
                                    <span className="bg-amber-50 text-amber-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border border-amber-100">
                                        Default
                                    </span>
                                )}
                            </div>

                            <div className="mt-4">
                                <div className="text-2xl font-bold text-gray-900 tracking-tight">
                                    ${((p.value || 0) / 1000000).toFixed(2)}M
                                </div>
                                <div className="text-xs text-gray-500 mt-1 font-medium">
                                    Total Value
                                </div>
                            </div>
                        </div>

                        <div className="px-5 py-3 bg-gray-50/50 border-t border-gray-100 flex items-center justify-between text-xs">
                            <span className="font-medium text-gray-600">{p.tickers.length} positions</span>

                            <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                {!p.is_default && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setDefaultPortfolio(p.id); }}
                                        className="text-gray-400 hover:text-amber-500 transition-colors"
                                        title="Set default"
                                    >
                                        <Star className="w-3.5 h-3.5" />
                                    </button>
                                )}
                                <button
                                    onClick={(e) => { e.stopPropagation(); if(confirm('Delete?')) deletePortfolio(p.id); }}
                                    className="text-gray-400 hover:text-red-500 transition-colors"
                                    title="Delete"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>
                    </div>
                    ))}
                </div>
            ) : (
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-gray-50/80 text-gray-500 font-medium border-b border-gray-200">
                            <tr>
                                <th className="px-6 py-3 w-1/3">Name</th>
                                <th className="px-6 py-3 text-right">Value</th>
                                <th className="px-6 py-3 text-center">Positions</th>
                                <th className="px-6 py-3 text-right">Last Updated</th>
                                <th className="px-6 py-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {filteredPortfolios.map((p) => (
                                <tr
                                    key={p.id}
                                    onClick={() => navigate(`/portfolio/${p.id}`)}
                                    className="hover:bg-gray-50 transition-colors cursor-pointer group"
                                >
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-gray-900">{p.name}</span>
                                            {p.is_default && (
                                                <span className="bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border border-amber-100">
                                                    Default
                                                </span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-right font-sans font-medium text-gray-900">
                                        ${((p.value || 0) / 1000000).toFixed(2)}M
                                    </td>
                                    <td className="px-6 py-4 text-center text-gray-600">
                                        {p.tickers.length}
                                    </td>
                                    <td className="px-6 py-4 text-right text-gray-500">
                                        {new Date(p.created_at || Date.now()).toLocaleDateString()}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                            {!p.is_default && (
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); setDefaultPortfolio(p.id); }}
                                                    className="p-1.5 hover:bg-amber-50 text-gray-400 hover:text-amber-600 rounded transition-colors"
                                                    title="Set Default"
                                                >
                                                    <Star className="w-4 h-4" />
                                                </button>
                                            )}
                                            <button
                                                onClick={(e) => { e.stopPropagation(); if(confirm('Delete?')) deletePortfolio(p.id); }}
                                                className="p-1.5 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded transition-colors"
                                                title="Delete"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
          </>
        )}
      </div>

      <IBKRConnectionModal isOpen={showBrokerModal} onClose={() => setShowBrokerModal(false)} onSuccess={handleBrokerConnectionSuccess} />
      <PortfolioImportModal isOpen={showImportModal} onClose={() => setShowImportModal(false)} onSuccess={handleImportSuccess} />

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
           <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
                 <h2 className="text-lg font-bold text-gray-900">Create Portfolio</h2>
                 <button onClick={() => setShowCreateModal(false)} className="p-2 hover:bg-gray-200 rounded-full text-gray-500">
                    <ChevronDown className="w-5 h-5 rotate-180" />
                 </button>
              </div>

              <div className="p-6 overflow-y-auto flex-1">
                 <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-700 mb-2">Portfolio Name</label>
                    <input
                       type="text"
                       value={newPortfolio.name}
                       onChange={(e) => setNewPortfolio({...newPortfolio, name: e.target.value})}
                       placeholder="e.g. Tech Growth Fund"
                       className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                    />
                 </div>

                 {/* Add Holding Section */}
                 <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 mb-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-3">Add Position</h3>
                    <div className="grid grid-cols-4 gap-3 mb-3">
                       <input
                          placeholder="Ticker (e.g. AAPL)"
                          value={currentHolding.ticker}
                          onChange={e => setCurrentHolding({...currentHolding, ticker: e.target.value.toUpperCase()})}
                          className="px-3 py-2 border border-gray-200 rounded-lg text-sm uppercase"
                       />
                       <input
                          type="number"
                          placeholder="Quantity"
                          value={currentHolding.quantity}
                          onChange={e => setCurrentHolding({...currentHolding, quantity: e.target.value})}
                          className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
                       />
                       <input
                          type="number"
                          placeholder="Price"
                          value={currentHolding.purchasePrice}
                          onChange={e => setCurrentHolding({...currentHolding, purchasePrice: e.target.value})}
                          className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
                       />
                       <button
                          onClick={handleAddHolding}
                          className="bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                       >
                          Add Position
                       </button>
                    </div>
                 </div>

                 {/* Holdings List */}
                 {newPortfolio.holdings.length > 0 && (
                    <div className="border border-gray-200 rounded-xl overflow-hidden mb-6">
                       <table className="w-full text-sm text-left">
                          <thead className="bg-gray-50 text-gray-500 font-medium">
                             <tr>
                                <th className="px-4 py-3">Ticker</th>
                                <th className="px-4 py-3 text-right">Qty</th>
                                <th className="px-4 py-3 text-right">Avg Price</th>
                                <th className="px-4 py-3 text-right">Total</th>
                                <th className="px-4 py-3"></th>
                             </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                             {newPortfolio.holdings.map(h => (
                                <tr key={h.ticker} className="hover:bg-gray-50">
                                   <td className="px-4 py-3 font-semibold">{h.ticker}</td>
                                   <td className="px-4 py-3 text-right">{h.lots.reduce((s, l) => s + l.quantity, 0)}</td>
                                   <td className="px-4 py-3 text-right">${(h.lots.reduce((s, l) => s + (l.quantity * l.purchasePrice), 0) / h.lots.reduce((s, l) => s + l.quantity, 0)).toFixed(2)}</td>
                                   <td className="px-4 py-3 text-right font-medium">${h.lots.reduce((s, l) => s + (l.quantity * l.purchasePrice), 0).toLocaleString()}</td>
                                   <td className="px-4 py-3 text-right">
                                      <button onClick={() => handleRemoveHolding(h.ticker)} className="text-red-500 hover:bg-red-50 p-1.5 rounded-md">
                                         <Trash2 className="w-4 h-4" />
                                      </button>
                                   </td>
                                </tr>
                             ))}
                          </tbody>
                       </table>
                    </div>
                 )}
              </div>

              <div className="p-6 border-t border-gray-100 bg-gray-50/50 flex justify-end gap-3">
                 <button onClick={() => setShowCreateModal(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors">Cancel</button>
                 <button
                    onClick={handleCreate}
                    disabled={newPortfolio.holdings.length === 0}
                    className="px-6 py-2 bg-gray-900 text-white rounded-lg font-medium hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-gray-900/10 transition-all"
                 >
                    Create Portfolio
                 </button>
              </div>
           </div>
        </div>
      )}

      {/* Portfolio Guide Panel (slides in from right) */}
      <PortfolioGuidePanel
        isOpen={showGuide}
        onClose={() => setShowGuide(false)}
        context="list"
        onOpenIBKRModal={() => setShowBrokerModal(true)}
      />
    </div>
  );
};

export default PortfolioPage;
