import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2, TrendingUp, TrendingDown, RefreshCw, Plus, ArrowUp, ArrowDown } from 'lucide-react';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';

const HOLDINGS_PAGE_SIZE = 10;

const responsive = {
  fonts: {
    tableHeader: 'clamp(0.6875rem, 0.65rem + 0.2vw, 0.75rem)',
    tableData: 'clamp(0.75rem, 0.7rem + 0.2vw, 0.875rem)',
    lotExpander: 'clamp(0.625rem, 0.6rem + 0.15vw, 0.6875rem)',
  },
  padding: {
    tight: 'clamp(0.25rem, 0.2rem + 0.22vw, 0.375rem)',
  },
};

export default function HoldingsTile() {
  const navigate = useNavigate();
  const ctx = usePortfolioDetail();
  const {
    portfolio,
    holdings,
    paginatedHoldings,
    holdingsPage,
    setHoldingsPage,
    totalHoldingsPages,
    sortColumn,
    sortDirection,
    handleSort,
    prices,
    pricesLastUpdated,
    loadingPrices,
    handleRefreshPrices,
    totalValue,
    tickerDetails,
    expandedHoldings,
    toggleLotExpansion,
    expandedMetadata,
    toggleMetadataExpansion,
    editingCell,
    editValue,
    handleCellEdit,
    handleCellSave,
    handleCellCancel,
    isSyncingIBKR,
    handleSyncIBKR,
    setShowAddHoldingModal,
    setShowBuyModal,
    setShowSellModal,
    handleRemoveTicker,
    equalizeQuantities,
    calculateAvgCost,
    getTotalQuantity,
    getCompanyLogoUrl,
  } = ctx;

  const holdingsPageStartIndex = (holdingsPage - 1) * HOLDINGS_PAGE_SIZE;

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#fff' }}>
      <div className="bg-white overflow-hidden h-full flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200 flex justify-between items-center flex-wrap gap-2 bg-gray-50/50 shrink-0">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Holdings</h2>
          <div className="flex items-center gap-2">
            {pricesLastUpdated && (
              <span className="text-xs text-gray-400 mr-2 hidden sm:inline-block">
                Updated {pricesLastUpdated.toLocaleTimeString()}
              </span>
            )}
            <div className="flex items-center bg-white rounded-lg border border-gray-200 p-1">
              {!portfolio.broker_connection_id && (
                <button
                  onClick={handleRefreshPrices}
                  disabled={loadingPrices || holdings.length === 0}
                  className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors disabled:opacity-50"
                  title="Refresh Prices"
                >
                  <RefreshCw size={14} className={loadingPrices ? 'animate-spin' : ''} />
                </button>
              )}
              {portfolio.broker_connection_id && (
                <button
                  onClick={handleSyncIBKR}
                  disabled={isSyncingIBKR}
                  className="p-1.5 text-gray-500 hover:text-emerald-600 hover:bg-emerald-50 rounded-md transition-colors disabled:opacity-50"
                  title="Sync with IBKR"
                >
                  <RefreshCw size={14} className={isSyncingIBKR ? 'animate-spin' : ''} />
                </button>
              )}
              <div className="w-px h-4 bg-gray-200 mx-1" />
              <button
                onClick={equalizeQuantities}
                className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                title="Equalize Positions"
              >
                <span className="font-mono text-xs font-bold">=</span>
              </button>
            </div>
            <div className="flex items-center gap-1.5 ml-1">
              <button
                onClick={() => setShowAddHoldingModal(true)}
                className="inline-flex items-center px-2.5 py-1 text-xs font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors shadow-sm"
              >
                <Plus size={12} className="mr-1" />
                Add
              </button>
              <button
                onClick={() => setShowBuyModal(true)}
                className="inline-flex items-center px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg hover:bg-emerald-100 transition-colors shadow-sm"
              >
                <TrendingUp size={12} className="mr-1" />
                Buy
              </button>
              <button
                onClick={() => setShowSellModal(true)}
                className="inline-flex items-center px-2.5 py-1 text-xs font-medium text-red-700 bg-red-50 border border-red-100 rounded-lg hover:bg-red-100 transition-colors shadow-sm"
              >
                <TrendingDown size={12} className="mr-1" />
                Sell
              </button>
            </div>
          </div>
        </div>

        <div className="overflow-auto flex-1">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="bg-gray-50/90 border-b border-gray-100 backdrop-blur">
                <th onClick={() => handleSort('ticker')} className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700">
                  <div className="flex items-center gap-1">
                    Company
                    {sortColumn === 'ticker' && (sortDirection === 'asc' ? <ArrowUp size={12} className="text-blue-500" /> : <ArrowDown size={12} className="text-blue-500" />)}
                  </div>
                </th>
                <th onClick={() => handleSort('position')} className="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700">
                  <div className="flex items-center justify-end gap-1">
                    Position
                    {sortColumn === 'position' && (sortDirection === 'asc' ? <ArrowUp size={12} className="text-blue-500" /> : <ArrowDown size={12} className="text-blue-500" />)}
                  </div>
                </th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                <th onClick={() => handleSort('costBasis')} className="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700">
                  <div className="flex items-center justify-end gap-1">
                    Cost Basis
                    {sortColumn === 'costBasis' && (sortDirection === 'asc' ? <ArrowUp size={12} className="text-blue-500" /> : <ArrowDown size={12} className="text-blue-500" />)}
                  </div>
                </th>
                <th onClick={() => handleSort('marketValue')} className="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700">
                  <div className="flex items-center justify-end gap-1">
                    Value
                    {sortColumn === 'marketValue' && (sortDirection === 'asc' ? <ArrowUp size={12} className="text-blue-500" /> : <ArrowDown size={12} className="text-blue-500" />)}
                  </div>
                </th>
                <th onClick={() => handleSort('avgPrice')} className="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700">
                  <div className="flex items-center justify-end gap-1">
                    Avg Price
                    {sortColumn === 'avgPrice' && (sortDirection === 'asc' ? <ArrowUp size={12} className="text-blue-500" /> : <ArrowDown size={12} className="text-blue-500" />)}
                  </div>
                </th>
                <th onClick={() => handleSort('weight')} className="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700">
                  <div className="flex items-center justify-end gap-1">
                    Weight
                    {sortColumn === 'weight' && (sortDirection === 'asc' ? <ArrowUp size={12} className="text-blue-500" /> : <ArrowDown size={12} className="text-blue-500" />)}
                  </div>
                </th>
                <th onClick={() => handleSort('unrealizedPL')} className="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700">
                  <div className="flex items-center justify-end gap-1">
                    P/L
                    {sortColumn === 'unrealizedPL' && (sortDirection === 'asc' ? <ArrowUp size={12} className="text-blue-500" /> : <ArrowDown size={12} className="text-blue-500" />)}
                  </div>
                </th>
                <th className="px-4 py-2.5 w-8" />
              </tr>
            </thead>
            <tbody>
              {paginatedHoldings.map((holding) => {
                const details = tickerDetails[holding.ticker];
                const totalQuantity = getTotalQuantity(holding.lots);
                const avgCost = calculateAvgCost(holding.lots);
                const currentPrice = prices[holding.ticker] || holding.currentPrice || 0;
                const costBasis = totalQuantity * avgCost;
                const storedTotalValue = Number(holding.totalValue);
                const currentValue = (storedTotalValue && storedTotalValue > 0 && !isNaN(storedTotalValue))
                  ? storedTotalValue
                  : totalQuantity * currentPrice;
                const gainLoss = avgCost > 0 ? currentValue - costBasis : null;
                const returnPct = costBasis > 0 ? ((currentValue - costBasis) / costBasis) * 100 : null;

                const tickerIndex = portfolio?.tickers?.indexOf(holding.ticker) ?? -1;
                const rawWeight = holding.metadata?.percentOfNAV
                  ?? (totalValue > 0 && currentValue > 0
                    ? (currentValue / totalValue) * 100
                    : (tickerIndex >= 0 && portfolio?.weights?.[tickerIndex] !== undefined
                      ? portfolio.weights[tickerIndex] * 100
                      : 0));
                const weight = isFinite(rawWeight) && !isNaN(rawWeight) ? rawWeight : 0;

                return (
                  <React.Fragment key={holding.ticker}>
                    <tr className="group border-b border-gray-50 hover:bg-gray-50/80 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <img
                            src={getCompanyLogoUrl(holding.ticker)}
                            alt={holding.ticker}
                            className="w-7 h-7 rounded-full bg-gray-50 object-contain p-0.5 border border-gray-100"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                          />
                          <div className="flex flex-col">
                            <div className="flex items-center gap-1.5">
                              <button
                                onClick={() => navigate(`/company/${holding.ticker}`)}
                                className="text-sm font-bold text-gray-900 hover:text-blue-600 transition-colors"
                              >
                                {holding.ticker}
                              </button>
                              {holding.metadata?.source === 'ibkr' && (
                                <span className="px-1 py-0.5 text-[9px] font-bold text-emerald-700 bg-emerald-50 rounded border border-emerald-100">IBKR</span>
                              )}
                            </div>
                            {details && (
                              <span className="text-xs text-gray-500 font-medium truncate max-w-[160px]">{details.name}</span>
                            )}
                            {holding.metadata && Object.keys(holding.metadata).length > 0 && (
                              <button
                                onClick={() => toggleMetadataExpansion(holding.ticker)}
                                className="text-[10px] text-blue-600 hover:text-blue-700 font-medium mt-0.5 flex items-center gap-0.5"
                              >
                                {expandedMetadata.has(holding.ticker) ? 'Hide' : 'View'} Details
                              </button>
                            )}
                          </div>
                        </div>
                        {expandedMetadata.has(holding.ticker) && (
                          <div className="mt-2 p-2.5 bg-gray-50 rounded-lg border border-gray-100 text-xs text-gray-600">
                            <div className="grid grid-cols-2 gap-1.5">
                              {holding.metadata?.source && <div><span className="font-medium">Source:</span> {holding.metadata.source.toUpperCase()}</div>}
                              {holding.metadata?.assetCategory && <div><span className="font-medium">Type:</span> {holding.metadata.assetCategory}</div>}
                              {holding.metadata?.currency && <div><span className="font-medium">Currency:</span> {holding.metadata.currency}</div>}
                              {holding.metadata?.description && (
                                <div className="col-span-2"><span className="font-medium">Description:</span> {holding.metadata.description}</div>
                              )}
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex flex-col items-end">
                          {editingCell?.ticker === holding.ticker && editingCell?.field === 'quantity' ? (
                            <input
                              type="number"
                              value={editValue}
                              onChange={() => {}}
                              onBlur={handleCellSave}
                              onKeyDown={(e) => { if (e.key === 'Enter') handleCellSave(); if (e.key === 'Escape') handleCellCancel(); }}
                              autoFocus
                              className="w-20 px-2 py-1 text-sm text-right border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                          ) : (
                            <span
                              onClick={() => handleCellEdit(holding.ticker, 'quantity', totalQuantity.toString())}
                              className="text-sm font-medium text-gray-900 cursor-pointer hover:text-blue-600 transition-colors tabular-nums"
                              title="Click to edit"
                            >
                              {totalQuantity.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                            </span>
                          )}
                          {holding.lots && holding.lots.length > 1 && (
                            <button
                              onClick={() => toggleLotExpansion(holding.ticker)}
                              className="text-[10px] font-medium text-gray-400 hover:text-gray-600 mt-0.5"
                            >
                              {expandedHoldings.has(holding.ticker) ? 'Collapse' : 'Expand'} {holding.lots.length} lots
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="text-sm font-medium text-gray-900 tabular-nums">
                          {currentPrice > 0 ? `$${currentPrice.toFixed(2)}` : '-'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="text-sm text-gray-600 tabular-nums">
                          {costBasis > 0 ? costBasis.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="text-sm font-semibold text-gray-900 tabular-nums">
                          {currentValue > 0 ? currentValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {editingCell?.ticker === holding.ticker && editingCell?.field === 'avgCost' ? (
                          <input
                            type="number"
                            value={editValue}
                            onChange={() => {}}
                            onBlur={handleCellSave}
                            onKeyDown={(e) => { if (e.key === 'Enter') handleCellSave(); if (e.key === 'Escape') handleCellCancel(); }}
                            autoFocus
                            className="w-20 px-2 py-1 text-sm text-right border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                          />
                        ) : (
                          <span
                            onClick={() => handleCellEdit(holding.ticker, 'avgCost', avgCost.toFixed(2))}
                            className="text-sm text-gray-600 cursor-pointer hover:text-blue-600 transition-colors tabular-nums border-b border-dotted border-gray-300 hover:border-blue-500"
                            title="Click to edit"
                          >
                            {avgCost > 0 ? avgCost.toFixed(2) : '-'}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 tabular-nums">
                          {weight > 0 ? `${weight.toFixed(2)}%` : '-'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {gainLoss !== null ? (
                          <div className="flex flex-col items-end">
                            <span className={`text-sm font-semibold tabular-nums ${gainLoss >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                              {gainLoss >= 0 ? '+' : ''}{gainLoss.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                            {returnPct !== null && (
                              <span className={`text-xs font-medium tabular-nums ${returnPct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                ({returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%)
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-sm text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => handleRemoveTicker(holding.ticker)}
                          className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-all"
                          title="Remove position"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>

                    {expandedHoldings.has(holding.ticker) && holding.lots && holding.lots.length > 1 && (
                      <tr key={`${holding.ticker}-lots`}>
                        <td colSpan={12} style={{ padding: 0, background: '#f9fafb', borderTop: '1px solid #e5e7eb' }}>
                          <div style={{ padding: '12px 16px' }}>
                            <h4 style={{ fontSize: responsive.fonts.tableData, fontWeight: '600', marginBottom: '8px', color: '#111827' }}>
                              Lots for {holding.ticker}
                            </h4>
                            <table style={{ width: '100%', fontSize: responsive.fonts.tableData, borderCollapse: 'collapse' }}>
                              <thead>
                                <tr style={{ borderBottom: '1px solid #e5e7eb', background: '#fff' }}>
                                  <th style={{ textAlign: 'left', padding: responsive.padding.tight, fontSize: responsive.fonts.lotExpander, fontWeight: '600', color: '#6b7280' }}>Lot ID</th>
                                  <th style={{ textAlign: 'right', padding: responsive.padding.tight, fontSize: responsive.fonts.lotExpander, fontWeight: '600', color: '#6b7280' }}>Qty</th>
                                  <th style={{ textAlign: 'right', padding: responsive.padding.tight, fontSize: responsive.fonts.lotExpander, fontWeight: '600', color: '#6b7280' }}>Purchase Price</th>
                                  <th style={{ textAlign: 'right', padding: responsive.padding.tight, fontSize: responsive.fonts.lotExpander, fontWeight: '600', color: '#6b7280' }}>Date</th>
                                  <th style={{ textAlign: 'right', padding: responsive.padding.tight, fontSize: responsive.fonts.lotExpander, fontWeight: '600', color: '#6b7280' }}>Cost Basis</th>
                                  <th style={{ textAlign: 'right', padding: responsive.padding.tight, fontSize: responsive.fonts.lotExpander, fontWeight: '600', color: '#6b7280' }}>Value</th>
                                  <th style={{ textAlign: 'right', padding: responsive.padding.tight, fontSize: responsive.fonts.lotExpander, fontWeight: '600', color: '#6b7280' }}>P/L</th>
                                </tr>
                              </thead>
                              <tbody>
                                {holding.lots.map((lot, lotIndex) => {
                                  const cp = prices[holding.ticker] || holding.currentPrice || 0;
                                  const cv = lot.currentValue || (lot.quantity * cp);
                                  const cb = lot.costBasis || (lot.quantity * lot.purchasePrice);
                                  const upl = lot.unrealizedPnL || (cv - cb);
                                  return (
                                    <tr key={lot.lotId || lotIndex} style={{ borderBottom: '1px solid #f3f4f6', background: '#fff' }}>
                                      <td style={{ padding: responsive.padding.tight, color: '#9ca3af', fontSize: responsive.fonts.lotExpander }}>
                                        {lot.lotId ? lot.lotId.slice(0, 8) + '...' : `Lot ${lotIndex + 1}`}
                                      </td>
                                      <td style={{ textAlign: 'right', padding: responsive.padding.tight, color: '#111827' }}>{lot.quantity.toFixed(2)}</td>
                                      <td style={{ textAlign: 'right', padding: responsive.padding.tight, color: '#111827' }}>${lot.purchasePrice.toFixed(2)}</td>
                                      <td style={{ textAlign: 'right', padding: responsive.padding.tight, color: '#6b7280' }}>
                                        {(() => { const d = String(lot.purchaseDate); return new Date(d.length === 8 ? `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}` : d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); })()}
                                      </td>
                                      <td style={{ textAlign: 'right', padding: responsive.padding.tight, color: '#111827' }}>${cb.toFixed(2)}</td>
                                      <td style={{ textAlign: 'right', padding: responsive.padding.tight, color: '#111827' }}>${cv.toFixed(2)}</td>
                                      <td style={{ textAlign: 'right', padding: responsive.padding.tight, color: upl >= 0 ? '#059669' : '#dc2626', fontWeight: '500' }}>
                                        {upl >= 0 ? '+' : ''}${upl.toFixed(2)}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        {totalHoldingsPages > 1 && (
          <div className="shrink-0 flex justify-between items-center px-4 py-2.5 border-t border-gray-200 bg-gray-50/50">
            <span style={{ fontSize: responsive.fonts.tableData }} className="text-gray-500">
              {holdings.length === 0 ? 0 : holdingsPageStartIndex + 1}-{Math.min(holdingsPageStartIndex + HOLDINGS_PAGE_SIZE, holdings.length)} of {holdings.length}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setHoldingsPage(p => Math.max(1, p - 1))}
                disabled={holdingsPage === 1}
                className="px-2.5 py-1 text-xs rounded border border-gray-200 bg-white text-gray-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Prev
              </button>
              <span className="text-xs text-gray-500">{holdingsPage}/{totalHoldingsPages}</span>
              <button
                onClick={() => setHoldingsPage(p => Math.min(totalHoldingsPages, p + 1))}
                disabled={holdingsPage === totalHoldingsPages}
                className="px-2.5 py-1 text-xs rounded border border-gray-200 bg-white text-gray-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
