import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usePortfolioStore } from '@stores/portfolioStore';
import { ArrowLeft, Edit2, HelpCircle, Save, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { TickerSearch } from '@/components/MarketLists/TickerSearch';
import { portfolioApiService, type Holding, type PurchaseLot } from '@/services/portfolioApi';
import type { MosaicNode } from 'react-mosaic-component';
import { PortfolioGuidePanel } from './PortfolioGuidePanel';
import { PortfolioDetailContext, type PortfolioDetailContextValue } from './mosaic/PortfolioDetailContext';
import PortfolioMosaic from './mosaic/PortfolioMosaic';
import MosaicLayoutToolbar from './mosaic/MosaicLayoutToolbar';
import type { TileId, PresetId } from './mosaic/types';
import { LAYOUT_PRESETS, DEFAULT_PRESET_ID } from './mosaic/presets';

import 'react-mosaic-component/react-mosaic-component.css';
import './mosaic/mosaic-overrides.css';

const HOLDINGS_PAGE_SIZE = 10;
const LAYOUT_STORAGE_KEY = 'portfolio-mosaic-layout-v2';
const PRESET_STORAGE_KEY = 'portfolio-mosaic-preset-v2';

interface TickerDetails {
  name: string;
  sector: string | null;
  industry: string | null;
  description: string | null;
  exchange: string | null;
}

const sectorColors: Record<string, string> = {
  'Technology': '#3b82f6',
  'Healthcare': '#10b981',
  'Financial Services': '#8b5cf6',
  'Consumer Cyclical': '#f59e0b',
  'Communication Services': '#06b6d4',
  'Industrials': '#6366f1',
  'Consumer Defensive': '#84cc16',
  'Energy': '#ef4444',
  'Basic Materials': '#f97316',
  'Real Estate': '#ec4899',
  'Utilities': '#14b8a6',
  'Unknown': '#9ca3af',
};

const LOGO_DEV_PUBLIC_KEY = 'pk_EnmLRp9RQ2-m1TKvOh6nEg';

const PortfolioDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { savedPortfolios, updatePortfolio, deletePortfolio, loadPortfolios, buyShares, sellShares, updateCashBalance } = usePortfolioStore();

  const portfolio = savedPortfolios.find(p => p.id === id);

  // --- Mosaic Layout State ---
  const [activePreset, setActivePreset] = useState<PresetId>(() => {
    try {
      const saved = localStorage.getItem(PRESET_STORAGE_KEY);
      if (saved && saved in LAYOUT_PRESETS) return saved as PresetId;
    } catch { /* ignore */ }
    return DEFAULT_PRESET_ID;
  });

  const [mosaicNode, setMosaicNode] = useState<MosaicNode<TileId> | null>(() => {
    try {
      const saved = localStorage.getItem(LAYOUT_STORAGE_KEY);
      if (saved) return JSON.parse(saved);
    } catch { /* ignore */ }
    return LAYOUT_PRESETS[DEFAULT_PRESET_ID].node;
  });

  const handleMosaicChange = useCallback((node: MosaicNode<TileId> | null) => {
    setMosaicNode(node);
    try {
      localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(node));
    } catch { /* ignore */ }
  }, []);

  const handlePresetChange = useCallback((presetId: PresetId) => {
    setActivePreset(presetId);
    try {
      localStorage.setItem(PRESET_STORAGE_KEY, presetId);
    } catch { /* ignore */ }
  }, []);

  // --- Existing State (preserved from original) ---
  const [isEditing, setIsEditing] = useState(false);
  const [editedName, setEditedName] = useState(portfolio?.name || '');
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [tickerDetails, setTickerDetails] = useState<Record<string, TickerDetails>>({});
  const [showGuide, setShowGuide] = useState(false);
  const [hoveredSector, setHoveredSector] = useState<{ sector: string; percentage: number } | null>(null);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [pricesLastUpdated, setPricesLastUpdated] = useState<Date | null>(null);
  const [loadingPrices, setLoadingPrices] = useState(false);
  const [isSyncingIBKR, setIsSyncingIBKR] = useState(false);
  const [showAddHoldingModal, setShowAddHoldingModal] = useState(false);
  const [newHolding, setNewHolding] = useState({ ticker: '', quantity: 1, purchasePrice: 0, purchaseDate: '' });
  const [editingCell, setEditingCell] = useState<{ ticker: string; field: 'quantity' | 'avgCost' | 'purchaseDate' } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [holdingsPage, setHoldingsPage] = useState(1);
  type SortColumn = 'ticker' | 'position' | 'change' | 'costBasis' | 'marketValue' | 'avgPrice' | 'weight' | 'unrealizedPL';
  const [sortColumn, setSortColumn] = useState<SortColumn>('weight');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [showBuyModal, setShowBuyModal] = useState(false);
  const [showSellModal, setShowSellModal] = useState(false);
  const [showCashModal, setShowCashModal] = useState(false);
  const [buyForms, setBuyForms] = useState([{ ticker: '', quantity: 0, price: 0 }]);
  const [sellForms, setSellForms] = useState([{ ticker: '', quantity: 0, price: 0 }]);
  const [cashForm, setCashForm] = useState({ amount: 0, operation: 'add' as 'add' | 'set' });
  const [isBuying, setIsBuying] = useState(false);
  const [isSelling, setIsSelling] = useState(false);
  const [expandedHoldings, setExpandedHoldings] = useState<Set<string>>(new Set());
  const [expandedMetadata, setExpandedMetadata] = useState<Set<string>>(new Set());
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [windowWidth, setWindowWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1024);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const isMobile = windowWidth < 640;
  const isTablet = windowWidth >= 640 && windowWidth < 1024;
  const isDesktop = windowWidth >= 1024;

  useEffect(() => {
    if (portfolio) setEditedName(portfolio.name);
  }, [portfolio]);

  // --- Helpers ---
  const calculateAvgCost = (lots: PurchaseLot[] | undefined): number => {
    if (!lots || lots.length === 0) return 0;
    const totalCost = lots.reduce((sum, lot) => sum + (lot.quantity * lot.purchasePrice), 0);
    const totalQuantity = lots.reduce((sum, lot) => sum + lot.quantity, 0);
    return totalQuantity > 0 ? totalCost / totalQuantity : 0;
  };

  const getTotalQuantity = (lots: PurchaseLot[] | undefined): number => {
    if (!lots || lots.length === 0) return 0;
    return lots.reduce((sum, lot) => sum + lot.quantity, 0);
  };

  const formatTickerDisplay = (holding: Holding): string => {
    const { ticker, metadata } = holding;
    if (metadata?.assetCategory === 'OPT' && metadata?.strike && metadata?.expiry) {
      return `${ticker} ${Number(metadata.strike)}${metadata.putCall || 'C'} ${metadata.expiry}`;
    }
    if (metadata?.assetCategory === 'FUT' && metadata?.expiry) return `${ticker} ${metadata.expiry}`;
    return ticker;
  };

  const getCompanyLogoUrl = (symbol: string) =>
    `https://img.logo.dev/ticker/${symbol.toUpperCase()}?token=${LOGO_DEV_PUBLIC_KEY}`;

  const toggleLotExpansion = (ticker: string) => {
    setExpandedHoldings(prev => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  };

  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      next.has(sectionId) ? next.delete(sectionId) : next.add(sectionId);
      return next;
    });
  };

  const toggleMetadataExpansion = (ticker: string) => {
    setExpandedMetadata(prev => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  };

  // --- Effects ---
  useEffect(() => {
    if (portfolio) {
      if (portfolio.holdings && portfolio.holdings.length > 0) {
        const hasLotsStructure = portfolio.holdings.every(h => h.lots && Array.isArray(h.lots));
        if (hasLotsStructure) {
          setHoldings(portfolio.holdings);
        } else {
          const convertedHoldings: Holding[] = portfolio.holdings.map(h => {
            const lot: PurchaseLot = {
              quantity: (h as any).quantity || 100,
              purchasePrice: (h as any).purchasePrice || 0,
              purchaseDate: (h as any).purchaseDate || new Date().toISOString().split('T')[0],
              lotId: `lot_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            };
            return { ticker: h.ticker, lots: [lot], currentPrice: h.currentPrice, priceUpdatedAt: h.priceUpdatedAt };
          });
          setHoldings(convertedHoldings);
        }

        const savedPrices: Record<string, number> = {};
        let latestPriceUpdate: Date | null = null;
        portfolio.holdings.forEach(h => {
          if (h.currentPrice !== undefined && h.currentPrice !== null) {
            savedPrices[h.ticker] = h.currentPrice;
            if (h.priceUpdatedAt) {
              const updateTime = new Date(h.priceUpdatedAt);
              if (!latestPriceUpdate || updateTime > latestPriceUpdate) latestPriceUpdate = updateTime;
            }
          }
        });
        if (Object.keys(savedPrices).length > 0) {
          setPrices(savedPrices);
          if (latestPriceUpdate) setPricesLastUpdated(latestPriceUpdate);
        }
      } else {
        const holdingsData: Holding[] = portfolio.tickers.map((ticker) => ({
          ticker,
          lots: [{ quantity: 100, purchasePrice: 0, purchaseDate: new Date().toISOString().split('T')[0], lotId: `lot_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` }],
          currentPrice: undefined,
          priceUpdatedAt: undefined,
        }));
        setHoldings(holdingsData);
      }
    }
  }, [portfolio]);

  useEffect(() => {
    if (holdings.length === 0) return;
    const timer = setTimeout(async () => {
      const missingTickers = holdings.map(h => h.ticker).filter(ticker => !tickerDetails[ticker]);
      if (missingTickers.length === 0) return;
      try {
        const response = await (await import('axios')).default.get(`${(await import('@/services/api')).API_BASE}/api/ticker-search/details?symbols=${missingTickers.join(',')}`);
        setTickerDetails(prev => ({ ...prev, ...response.data }));
      } catch (error) {
        console.error('Failed to fetch ticker details:', error);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [holdings]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(holdings.length / HOLDINGS_PAGE_SIZE));
    if (holdingsPage > maxPage) setHoldingsPage(maxPage);
  }, [holdings.length, holdingsPage]);

  // --- Computed values ---
  const holdingsValue = useMemo(() => {
    return holdings.reduce((sum, h) => {
      const storedValue = Number(h.totalValue);
      if (storedValue && storedValue > 0 && !isNaN(storedValue)) return sum + storedValue;
      return sum + (getTotalQuantity(h.lots) * (prices[h.ticker] || h.currentPrice || 0));
    }, 0);
  }, [holdings, prices]);

  const totalValue = useMemo(() => {
    return holdingsValue + Number(portfolio?.cash_balance || 0);
  }, [holdingsValue, portfolio?.cash_balance]);

  const sortedHoldings = useMemo(() => {
    return [...holdings].sort((a, b) => {
      const aQ = getTotalQuantity(a.lots), bQ = getTotalQuantity(b.lots);
      const aAC = calculateAvgCost(a.lots), bAC = calculateAvgCost(b.lots);
      const aP = prices[a.ticker] || a.currentPrice || 0, bP = prices[b.ticker] || b.currentPrice || 0;
      const aCB = aQ * aAC, bCB = bQ * bAC;
      const aSV = Number(a.totalValue), bSV = Number(b.totalValue);
      const aV = (aSV > 0 && !isNaN(aSV)) ? aSV : aQ * aP;
      const bV = (bSV > 0 && !isNaN(bSV)) ? bSV : bQ * bP;
      const aGL = aV - aCB, bGL = bV - bCB;
      const aR = aCB > 0 ? ((aV - aCB) / aCB) * 100 : 0, bR = bCB > 0 ? ((bV - bCB) / bCB) * 100 : 0;
      const aW = totalValue > 0 ? (aV / totalValue) * 100 : 0, bW = totalValue > 0 ? (bV / totalValue) * 100 : 0;

      let comp = 0;
      switch (sortColumn) {
        case 'ticker': comp = a.ticker.localeCompare(b.ticker); break;
        case 'position': comp = aQ - bQ; break;
        case 'change': comp = aR - bR; break;
        case 'costBasis': comp = aCB - bCB; break;
        case 'marketValue': comp = aV - bV; break;
        case 'avgPrice': comp = aAC - bAC; break;
        case 'weight': comp = aW - bW; break;
        case 'unrealizedPL': comp = aGL - bGL; break;
      }
      return sortDirection === 'asc' ? comp : -comp;
    });
  }, [holdings, sortColumn, sortDirection, prices, totalValue]);

  const totalHoldingsPages = Math.max(1, Math.ceil(sortedHoldings.length / HOLDINGS_PAGE_SIZE));
  const holdingsPageStartIndex = (holdingsPage - 1) * HOLDINGS_PAGE_SIZE;
  const paginatedHoldings = sortedHoldings.slice(holdingsPageStartIndex, holdingsPageStartIndex + HOLDINGS_PAGE_SIZE);

  const sectorAllocations = useMemo(() => {
    return holdings.reduce((acc, holding) => {
      const details = tickerDetails[holding.ticker];
      const sector = details?.sector || 'Unknown';
      const storedValue = Number(holding.totalValue);
      const value = (storedValue && storedValue > 0 && !isNaN(storedValue))
        ? storedValue
        : getTotalQuantity(holding.lots) * (prices[holding.ticker] || holding.currentPrice || 0);
      const weight = totalValue > 0 ? (value / totalValue) * 100 : 0;
      if (!acc[sector]) acc[sector] = 0;
      acc[sector] += weight;
      return acc;
    }, {} as Record<string, number>);
  }, [holdings, prices, tickerDetails, totalValue]);

  const totalWeight = useMemo(() => {
    return holdings.reduce((sum, h) => {
      const storedValue = Number(h.totalValue);
      const value = (storedValue && storedValue > 0 && !isNaN(storedValue))
        ? storedValue
        : getTotalQuantity(h.lots) * (prices[h.ticker] || h.currentPrice || 0);
      return sum + (totalValue > 0 ? value / totalValue : 0);
    }, 0);
  }, [holdings, prices, totalValue]);

  const sectorData = Object.entries(sectorAllocations)
    .map(([sector, percentage]) => ({ sector, percentage }))
    .sort((a, b) => b.percentage - a.percentage);

  // --- Handlers ---
  const handleSort = (column: string) => {
    const col = column as SortColumn;
    if (sortColumn === col) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(col);
      setSortDirection('desc');
    }
  };

  const handleRefreshPrices = async () => {
    if (holdings.length === 0) { toast.error('No holdings to fetch prices for'); return; }
    setLoadingPrices(true);
    try {
      const tickers = holdings.map(h => h.ticker);
      const priceData = await portfolioApiService.fetchPrices(tickers);
      setPrices(priceData.prices);
      setPricesLastUpdated(new Date(priceData.timestamp));
      const updatedHoldings = holdings.map(h => ({ ...h, currentPrice: priceData.prices[h.ticker] || h.currentPrice, priceUpdatedAt: priceData.timestamp }));
      setHoldings(updatedHoldings);
      const newTotalValue = updatedHoldings.reduce((sum, h) => sum + (getTotalQuantity(h.lots) * (priceData.prices[h.ticker] || h.currentPrice || 0)), 0);
      const weights = updatedHoldings.map(h => { const v = getTotalQuantity(h.lots) * (priceData.prices[h.ticker] || h.currentPrice || 0); return newTotalValue > 0 ? v / newTotalValue : 0; });
      await updatePortfolio(id!, { holdings: updatedHoldings, value: newTotalValue, weights, tickers: updatedHoldings.map(h => h.ticker) });
      await loadPortfolios();
      toast.success('Prices refreshed');
    } catch (error) {
      toast.error('Failed to fetch prices');
    } finally {
      setLoadingPrices(false);
    }
  };

  const handleSave = async () => {
    if (holdingsValue === 0) { toast.error('Portfolio must have at least one position with value'); return; }
    const weights = holdings.map(h => {
      const storedValue = Number(h.totalValue);
      const value = (storedValue && storedValue > 0 && !isNaN(storedValue)) ? storedValue : getTotalQuantity(h.lots) * (prices[h.ticker] || h.currentPrice || 0);
      return holdingsValue > 0 ? value / holdingsValue : 0;
    });
    try {
      await updatePortfolio(id!, { name: editedName, tickers: holdings.map(h => h.ticker), weights, value: totalValue, holdings });
      toast.success('Portfolio updated');
      setIsEditing(false);
    } catch { toast.error('Failed to update portfolio'); }
  };

  const handleBuy = async () => {
    for (let i = 0; i < buyForms.length; i++) {
      const form = buyForms[i];
      if (!form.ticker?.trim()) { toast.error(`Row ${i + 1}: Select a ticker`); return; }
      if (Number(form.quantity) <= 0) { toast.error(`Row ${i + 1}: Enter a valid quantity`); return; }
      if (Number(form.price) <= 0) { toast.error(`Row ${i + 1}: Enter a valid price`); return; }
    }
    setIsBuying(true);
    let successCount = 0;
    try {
      for (const form of buyForms) {
        await buyShares(id!, { ticker: form.ticker.toUpperCase(), quantity: Number(form.quantity), price: Number(form.price) });
        successCount++;
      }
      toast.success(`Bought ${successCount} position(s)`);
      setShowBuyModal(false);
      setBuyForms([{ ticker: '', quantity: 0, price: 0 }]);
      await loadPortfolios();
      const up = usePortfolioStore.getState().savedPortfolios.find(p => p.id === id);
      if (up?.holdings) setHoldings(up.holdings);
    } catch (error) {
      const msg = (error as Error).message || 'Failed to buy';
      if (msg.includes('Insufficient cash')) {
        toast.error(`Insufficient funds! ${msg}`, { duration: 5000 });
      } else {
        toast.error(`${successCount > 0 ? `${successCount} done. ` : ''}${msg}`);
      }
    } finally { setIsBuying(false); }
  };

  const handleSell = async () => {
    for (let i = 0; i < sellForms.length; i++) {
      const form = sellForms[i];
      if (!form.ticker?.trim()) { toast.error(`Row ${i + 1}: Select a holding`); return; }
      if (Number(form.quantity) <= 0) { toast.error(`Row ${i + 1}: Enter a valid quantity`); return; }
      if (Number(form.price) <= 0) { toast.error(`Row ${i + 1}: Enter a valid price`); return; }
    }
    setIsSelling(true);
    let successCount = 0;
    try {
      for (const form of sellForms) {
        await sellShares(id!, { ticker: form.ticker.toUpperCase(), quantity: Number(form.quantity), price: Number(form.price) });
        successCount++;
      }
      toast.success(`Sold ${successCount} position(s)`);
      setShowSellModal(false);
      setSellForms([{ ticker: '', quantity: 0, price: 0 }]);
      await loadPortfolios();
      const up = usePortfolioStore.getState().savedPortfolios.find(p => p.id === id);
      if (up?.holdings) setHoldings(up.holdings);
    } catch (error) {
      const msg = (error as Error).message || 'Failed to sell';
      toast.error(`${successCount > 0 ? `${successCount} done. ` : ''}${msg}`);
    } finally { setIsSelling(false); }
  };

  const handleUpdateCash = async () => {
    if (cashForm.amount < 0) { toast.error('Amount must be non-negative'); return; }
    try {
      await updateCashBalance(id!, { amount: cashForm.amount, operation: cashForm.operation });
      toast.success(`${cashForm.operation === 'add' ? 'Added' : 'Set'} cash: $${cashForm.amount.toLocaleString()}`);
      setShowCashModal(false);
      setCashForm({ amount: 0, operation: 'add' });
      await loadPortfolios();
    } catch (error) { toast.error((error as Error).message || 'Failed to update cash'); }
  };

  const handleSyncIBKR = async () => {
    if (!portfolio?.broker_connection_id) { toast.error('Not linked to IBKR'); return; }
    setIsSyncingIBKR(true);
    try {
      const result = await portfolioApiService.syncIBKRPortfolio(id!);
      toast.success(result.message);
      await loadPortfolios();
      const up = usePortfolioStore.getState().savedPortfolios.find(p => p.id === id);
      if (up?.holdings) setHoldings(up.holdings);
    } catch (error) {
      toast.error((error as Error).message || 'Failed to sync');
    } finally { setIsSyncingIBKR(false); }
  };

  const handleAddHoldingFromModal = () => {
    if (!newHolding.ticker.trim()) { toast.error('Enter a ticker'); return; }
    if (newHolding.quantity <= 0) { toast.error('Quantity must be > 0'); return; }
    if (newHolding.purchasePrice <= 0) { toast.error('Price must be > 0'); return; }
    if (!newHolding.purchaseDate) { toast.error('Enter a purchase date'); return; }
    const ticker = newHolding.ticker.toUpperCase();
    const newLot: PurchaseLot = { quantity: newHolding.quantity, purchasePrice: newHolding.purchasePrice, purchaseDate: newHolding.purchaseDate, lotId: `lot_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` };
    const existingIdx = holdings.findIndex(h => h.ticker === ticker);
    if (existingIdx >= 0) {
      const updated = [...holdings];
      updated[existingIdx] = { ...updated[existingIdx], lots: [...(updated[existingIdx].lots || []), newLot] };
      setHoldings(updated);
      toast.success(`Added to ${ticker}`);
    } else {
      setHoldings([...holdings, { ticker, lots: [newLot], currentPrice: undefined, priceUpdatedAt: undefined }]);
      toast.success(`Created ${ticker}`);
    }
    setNewHolding({ ticker: '', quantity: 1, purchasePrice: 0, purchaseDate: '' });
    setShowAddHoldingModal(false);
    setIsEditing(true);
  };

  const handleRemoveTicker = (ticker: string) => { setHoldings(holdings.filter(h => h.ticker !== ticker)); setIsEditing(true); };

  const handleCellEdit = (ticker: string, field: 'quantity' | 'avgCost' | 'purchaseDate', currentValue: string) => {
    setEditingCell({ ticker, field });
    setEditValue(currentValue);
  };

  const handleCellSave = async () => {
    if (!editingCell) return;
    const { ticker, field } = editingCell;
    const updatedHoldings = [...holdings];
    const hi = updatedHoldings.findIndex(h => h.ticker === ticker);
    if (hi === -1) { setEditingCell(null); setEditValue(''); return; }
    const h = updatedHoldings[hi];
    if (field === 'quantity') {
      const nq = parseFloat(editValue);
      if (!isNaN(nq) && nq > 0 && h.lots?.length) {
        const ratio = nq / getTotalQuantity(h.lots);
        h.lots = h.lots.map(lot => ({ ...lot, quantity: lot.quantity * ratio }));
      }
    } else if (field === 'avgCost') {
      const nc = parseFloat(editValue);
      if (!isNaN(nc) && nc >= 0 && h.lots?.length) h.lots = h.lots.map(lot => ({ ...lot, purchasePrice: nc }));
    } else if (field === 'purchaseDate' && h.lots?.length) {
      h.lots[0].purchaseDate = editValue;
    }
    setHoldings(updatedHoldings);
    setEditingCell(null);
    setEditValue('');
    setIsEditing(true);
    const ntv = updatedHoldings.reduce((s, x) => s + (getTotalQuantity(x.lots) * (prices[x.ticker] || x.currentPrice || 0)), 0);
    const ws = updatedHoldings.map(x => { const v = getTotalQuantity(x.lots) * (prices[x.ticker] || x.currentPrice || 0); return ntv > 0 ? v / ntv : 0; });
    try {
      await updatePortfolio(id!, { holdings: updatedHoldings, value: ntv, weights: ws, tickers: updatedHoldings.map(x => x.ticker) });
      toast.success('Updated');
    } catch { toast.error('Failed to save'); }
  };

  const handleCellCancel = () => { setEditingCell(null); setEditValue(''); };

  const equalizeQuantities = () => {
    if (holdings.length === 0) return;
    const equalValue = totalValue / holdings.length;
    const updatedHoldings = holdings.map(h => {
      const cp = prices[h.ticker] || h.currentPrice || 1;
      const nq = equalValue / cp;
      const ac = calculateAvgCost(h.lots);
      return { ...h, lots: [{ quantity: nq, purchasePrice: ac > 0 ? ac : cp, purchaseDate: new Date().toISOString().split('T')[0], lotId: `lot_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` }] };
    });
    setHoldings(updatedHoldings);
    setIsEditing(true);
  };

  // --- Context value ---
  const contextValue: PortfolioDetailContextValue = {
    portfolio: portfolio!,
    portfolioId: id!,
    holdings, setHoldings,
    sortedHoldings, paginatedHoldings,
    holdingsPage, setHoldingsPage,
    totalHoldingsPages,
    sortColumn, sortDirection, handleSort,
    prices, pricesLastUpdated, loadingPrices, handleRefreshPrices,
    holdingsValue, totalValue, totalWeight,
    sectorData, sectorColors,
    tickerDetails,
    expandedHoldings, toggleLotExpansion,
    expandedMetadata, toggleMetadataExpansion,
    expandedSections, toggleSection,
    isEditing, setIsEditing,
    editingCell, editValue,
    handleCellEdit, handleCellSave, handleCellCancel,
    isSyncingIBKR, handleSyncIBKR,
    setShowBuyModal, setShowSellModal, setShowCashModal, setShowAddHoldingModal,
    handleRemoveTicker, equalizeQuantities, handleSave,
    calculateAvgCost, getTotalQuantity, formatTickerDisplay, getCompanyLogoUrl,
    isMobile, isTablet, isDesktop,
    hoveredSector, setHoveredSector,
  };

  // --- Not found state ---
  if (!portfolio) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Portfolio not found</h2>
          <button onClick={() => navigate('/portfolio')} style={{ color: '#2563eb', background: 'transparent', border: 'none', fontSize: '14px', fontWeight: '500', cursor: 'pointer' }}>
            Return to Portfolios
          </button>
        </div>
      </div>
    );
  }

  return (
    <PortfolioDetailContext.Provider value={contextValue}>
      <div style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#f9fafb',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      }}>
        {/* Command Bar */}
        <div style={{ background: '#FFFFFF', borderBottom: '1px solid #E1DFDD', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', flexShrink: 0 }}>
          <div className="flex items-center justify-between flex-wrap gap-2" style={{ padding: isMobile ? '8px 12px' : '11px 16px' }}>
            <div className="flex items-center gap-2 sm:gap-4 flex-wrap">
              <button
                onClick={() => navigate('/portfolio')}
                style={{ padding: '6px', background: 'transparent', border: '1px solid #E1DFDD', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              >
                <ArrowLeft size={16} style={{ color: '#605E5C' }} />
              </button>

              {isEditing ? (
                <input
                  type="text"
                  value={editedName}
                  onChange={(e) => setEditedName(e.target.value)}
                  style={{ fontSize: '14px', fontWeight: '600', color: '#323130', border: '1px solid #E1DFDD', borderRadius: '4px', padding: '4px 8px', outline: 'none', fontFamily: 'inherit', background: '#FFFFFF' }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = '#0078D4')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = '#E1DFDD')}
                />
              ) : (
                <span style={{ color: '#323130', fontSize: '14px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {portfolio.name}
                  <button onClick={() => setIsEditing(true)} style={{ padding: '4px', background: 'transparent', border: 'none', cursor: 'pointer', borderRadius: '4px', display: 'flex', alignItems: 'center' }}>
                    <Edit2 size={12} style={{ color: '#605E5C' }} />
                  </button>
                </span>
              )}

              {!isMobile && <div style={{ width: '1px', height: '16px', background: '#E1DFDD' }} />}
              <span style={{ color: '#605E5C', fontSize: '14px' }}>{holdings.length} {holdings.length === 1 ? 'holding' : 'holdings'}</span>

              {portfolio.is_default && (
                <>
                  {!isMobile && <div style={{ width: '1px', height: '16px', background: '#E1DFDD' }} />}
                  <span style={{ fontSize: '11px', padding: '2px 8px', background: '#E7F5EC', color: '#0F6D31', borderRadius: '12px', fontWeight: '600' }}>Default</span>
                </>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button onClick={() => setShowGuide(true)} style={{ padding: '6px 12px', fontSize: '14px', background: '#FFFFFF', color: '#605E5C', border: '1px solid #E1DFDD', borderRadius: '4px', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <HelpCircle size={14} /> Help
              </button>

              {isEditing && (
                <>
                  <button onClick={handleSave} style={{ padding: '6px 12px', fontSize: '14px', background: '#0078D4', color: '#FFFFFF', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: '500', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Save size={14} /> Save
                  </button>
                  <button onClick={() => { setIsEditing(false); setEditedName(portfolio.name); }} style={{ padding: '6px 12px', fontSize: '14px', background: '#FFFFFF', color: '#605E5C', border: '1px solid #E1DFDD', borderRadius: '4px', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <X size={14} /> Cancel
                  </button>
                </>
              )}

              <button
                onClick={async () => { if (window.confirm('Delete this portfolio?')) { await deletePortfolio(id!); navigate('/portfolio'); } }}
                style={{ padding: '6px 12px', fontSize: '14px', background: '#FFFFFF', color: '#D13438', border: '1px solid #E1DFDD', borderRadius: '4px', cursor: 'pointer', fontFamily: 'inherit', fontWeight: '500' }}
              >
                Delete Portfolio
              </button>
            </div>
          </div>
        </div>

        {/* Layout Toolbar */}
        <MosaicLayoutToolbar
          currentNode={mosaicNode}
          onNodeChange={handleMosaicChange}
          activePreset={activePreset}
          onPresetChange={handlePresetChange}
        />

        {/* Mosaic Workspace */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <PortfolioMosaic value={mosaicNode} onChange={handleMosaicChange} />
        </div>

        {/* ========== MODALS ========== */}

        {/* Add Holding Modal */}
        {showAddHoldingModal && (
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000 }}>
            <div style={{ background: '#FFFFFF', borderRadius: '8px', padding: '24px', width: '90%', maxWidth: '500px', boxShadow: '0 10px 25px rgba(0,0,0,0.2)' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#111827', marginBottom: '20px' }}>Add New Holding</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ fontSize: '13px', fontWeight: '500', color: '#374151', marginBottom: '6px', display: 'block' }}>Ticker Symbol *</label>
                  <TickerSearch onSelect={(ticker) => setNewHolding({ ...newHolding, ticker: ticker.symbol })} placeholder="Search..." />
                  {newHolding.ticker && (
                    <div style={{ marginTop: '8px', padding: '8px', background: '#f3f4f6', borderRadius: '4px', fontSize: '13px', fontWeight: '600', color: '#111827' }}>Selected: {newHolding.ticker}</div>
                  )}
                </div>
                <div>
                  <label style={{ fontSize: '13px', fontWeight: '500', color: '#374151', marginBottom: '6px', display: 'block' }}>Quantity *</label>
                  <input type="number" value={newHolding.quantity} onChange={(e) => setNewHolding({ ...newHolding, quantity: parseFloat(e.target.value) || 0 })} style={{ width: '100%', padding: '8px 12px', fontSize: '14px', border: '1px solid #d1d5db', borderRadius: '4px', fontFamily: 'inherit' }} min="0" step="1" />
                </div>
                <div>
                  <label style={{ fontSize: '13px', fontWeight: '500', color: '#374151', marginBottom: '6px', display: 'block' }}>Purchase Price</label>
                  <input type="number" value={newHolding.purchasePrice} onChange={(e) => setNewHolding({ ...newHolding, purchasePrice: parseFloat(e.target.value) || 0 })} style={{ width: '100%', padding: '8px 12px', fontSize: '14px', border: '1px solid #d1d5db', borderRadius: '4px', fontFamily: 'inherit' }} min="0" step="0.01" />
                </div>
                <div>
                  <label style={{ fontSize: '13px', fontWeight: '500', color: '#374151', marginBottom: '6px', display: 'block' }}>Purchase Date</label>
                  <input type="date" value={newHolding.purchaseDate} onChange={(e) => setNewHolding({ ...newHolding, purchaseDate: e.target.value })} style={{ width: '100%', padding: '8px 12px', fontSize: '14px', border: '1px solid #d1d5db', borderRadius: '4px', fontFamily: 'inherit' }} />
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                  <button onClick={() => { setShowAddHoldingModal(false); setNewHolding({ ticker: '', quantity: 1, purchasePrice: 0, purchaseDate: '' }); }} style={{ flex: 1, padding: '10px 16px', fontSize: '14px', fontWeight: '500', background: '#FFFFFF', color: '#374151', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', fontFamily: 'inherit' }}>Cancel</button>
                  <button onClick={handleAddHoldingFromModal} style={{ flex: 1, padding: '10px 16px', fontSize: '14px', fontWeight: '500', background: '#10b981', color: '#FFFFFF', border: 'none', borderRadius: '6px', cursor: 'pointer', fontFamily: 'inherit' }}>Add Holding</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Buy Shares Modal */}
        {showBuyModal && (
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
            <div style={{ background: '#FFFFFF', borderRadius: '8px', padding: '24px', width: '90%', maxWidth: '600px', maxHeight: '85vh', overflow: 'auto', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
              <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600', color: '#111827' }}>Buy Shares</h3>
              {buyForms.map((form, index) => (
                <div key={index} style={{ marginBottom: '16px', padding: '16px', border: '1px solid #e5e7eb', borderRadius: '6px', position: 'relative' }}>
                  {buyForms.length > 1 && (
                    <button type="button" onClick={() => setBuyForms(buyForms.filter((_, i) => i !== index))} style={{ position: 'absolute', top: '8px', right: '8px', background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: '20px', padding: '0 6px', lineHeight: '1', fontWeight: '600' }}>×</button>
                  )}
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', marginBottom: '6px', color: '#374151' }}>Ticker *</label>
                    <TickerSearch onSelect={(t) => { const nf = [...buyForms]; nf[index].ticker = t.symbol; setBuyForms(nf); }} placeholder="Search..." />
                    {form.ticker && <div style={{ marginTop: '8px', padding: '8px', background: '#f3f4f6', borderRadius: '4px', fontSize: '13px', fontWeight: '600', color: '#111827', display: 'flex', justifyContent: 'space-between' }}><span>Selected: {form.ticker}</span><button type="button" onClick={() => { const nf = [...buyForms]; nf[index].ticker = ''; setBuyForms(nf); }} style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', fontSize: '18px' }}>×</button></div>}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', marginBottom: '4px', color: '#374151' }}>Quantity</label>
                      <input type="number" value={form.quantity || ''} onChange={(e) => { const nf = [...buyForms]; nf[index].quantity = parseFloat(e.target.value) || 0; setBuyForms(nf); }} placeholder="100" style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', fontFamily: 'inherit' }} />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', marginBottom: '4px', color: '#374151' }}>Price per Share</label>
                      <input type="number" value={form.price || ''} onChange={(e) => { const nf = [...buyForms]; nf[index].price = parseFloat(e.target.value) || 0; setBuyForms(nf); }} placeholder="150.00" step="0.01" style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', fontFamily: 'inherit' }} />
                    </div>
                  </div>
                  {form.quantity > 0 && form.price > 0 && <div style={{ marginTop: '8px', fontSize: '12px', color: '#6b7280' }}>Subtotal: ${(form.quantity * form.price).toFixed(2)}</div>}
                </div>
              ))}
              <button type="button" onClick={() => setBuyForms([...buyForms, { ticker: '', quantity: 0, price: 0 }])} style={{ width: '100%', padding: '8px', marginBottom: '16px', fontSize: '13px', fontWeight: '500', color: '#059669', background: 'white', border: '1px dashed #059669', borderRadius: '4px', cursor: 'pointer' }}>+ Add Another</button>
              <div style={{ fontSize: '13px', marginBottom: '16px', padding: '12px', background: '#ecfdf5', border: '1px solid #6ee7b7', borderRadius: '4px' }}>
                <strong>Total Cost:</strong> ${buyForms.reduce((s, f) => s + (f.quantity * f.price), 0).toFixed(2)}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => { setShowBuyModal(false); setBuyForms([{ ticker: '', quantity: 0, price: 0 }]); }} style={{ flex: 1, padding: '8px 16px', fontSize: '14px', background: '#FFFFFF', color: '#374151', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer', fontWeight: '500', fontFamily: 'inherit' }}>Cancel</button>
                <button onClick={handleBuy} disabled={isBuying} style={{ flex: 1, padding: '8px 16px', fontSize: '14px', background: isBuying ? '#9ca3af' : '#059669', color: '#FFFFFF', border: 'none', borderRadius: '4px', cursor: isBuying ? 'not-allowed' : 'pointer', fontWeight: '500', fontFamily: 'inherit', opacity: isBuying ? 0.7 : 1 }}>{isBuying ? 'Buying...' : 'Buy'}</button>
              </div>
            </div>
          </div>
        )}

        {/* Sell Shares Modal */}
        {showSellModal && (
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
            <div style={{ background: '#FFFFFF', borderRadius: '8px', padding: '24px', width: '90%', maxWidth: '600px', maxHeight: '85vh', overflow: 'auto', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
              <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600', color: '#111827' }}>Sell Shares</h3>
              {sellForms.map((form, index) => (
                <div key={index} style={{ marginBottom: '16px', padding: '16px', border: '1px solid #e5e7eb', borderRadius: '6px', position: 'relative' }}>
                  {sellForms.length > 1 && (
                    <button type="button" onClick={() => setSellForms(sellForms.filter((_, i) => i !== index))} style={{ position: 'absolute', top: '8px', right: '8px', background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: '20px', padding: '0 6px', lineHeight: '1', fontWeight: '600' }}>×</button>
                  )}
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', marginBottom: '4px', color: '#374151' }}>Select Holding</label>
                    <select value={form.ticker} onChange={(e) => { const nf = [...sellForms]; nf[index].ticker = e.target.value; setSellForms(nf); }} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', fontFamily: 'inherit', background: '#FFFFFF' }}>
                      <option value="">Choose a holding...</option>
                      {holdings.map(h => <option key={h.ticker} value={h.ticker}>{h.ticker} ({getTotalQuantity(h.lots).toFixed(2)} shares)</option>)}
                    </select>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', marginBottom: '4px', color: '#374151' }}>Quantity</label>
                      <input type="number" value={form.quantity || ''} onChange={(e) => { const nf = [...sellForms]; nf[index].quantity = parseFloat(e.target.value) || 0; setSellForms(nf); }} placeholder="100" style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', fontFamily: 'inherit' }} />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', marginBottom: '4px', color: '#374151' }}>Price per Share</label>
                      <input type="number" value={form.price || ''} onChange={(e) => { const nf = [...sellForms]; nf[index].price = parseFloat(e.target.value) || 0; setSellForms(nf); }} placeholder="150.00" step="0.01" style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', fontFamily: 'inherit' }} />
                    </div>
                  </div>
                  {form.ticker && (
                    <div style={{ marginTop: '8px', fontSize: '12px', color: '#6b7280' }}>
                      Available: {(() => { const h = holdings.find(x => x.ticker === form.ticker); return h ? getTotalQuantity(h.lots).toFixed(2) : '0'; })()} shares
                      {form.quantity > 0 && form.price > 0 && <span style={{ marginLeft: '16px' }}>Subtotal: ${(form.quantity * form.price).toFixed(2)}</span>}
                    </div>
                  )}
                </div>
              ))}
              <button type="button" onClick={() => setSellForms([...sellForms, { ticker: '', quantity: 0, price: 0 }])} style={{ width: '100%', padding: '8px', marginBottom: '16px', fontSize: '13px', fontWeight: '500', color: '#dc2626', background: 'white', border: '1px dashed #dc2626', borderRadius: '4px', cursor: 'pointer' }}>+ Add Another</button>
              <div style={{ fontSize: '13px', marginBottom: '16px', padding: '12px', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '4px' }}>
                <strong>Total Proceeds:</strong> ${sellForms.reduce((s, f) => s + (f.quantity * f.price), 0).toFixed(2)}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => { setShowSellModal(false); setSellForms([{ ticker: '', quantity: 0, price: 0 }]); }} style={{ flex: 1, padding: '8px 16px', fontSize: '14px', background: '#FFFFFF', color: '#374151', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer', fontWeight: '500', fontFamily: 'inherit' }}>Cancel</button>
                <button onClick={handleSell} disabled={isSelling} style={{ flex: 1, padding: '8px 16px', fontSize: '14px', background: isSelling ? '#9ca3af' : '#dc2626', color: '#FFFFFF', border: 'none', borderRadius: '4px', cursor: isSelling ? 'not-allowed' : 'pointer', fontWeight: '500', fontFamily: 'inherit', opacity: isSelling ? 0.7 : 1 }}>{isSelling ? 'Selling...' : 'Sell'}</button>
              </div>
            </div>
          </div>
        )}

        {/* Cash Modal */}
        {showCashModal && (
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
            <div style={{ background: '#FFFFFF', borderRadius: '8px', padding: '24px', width: '90%', maxWidth: '400px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
              <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600', color: '#111827' }}>Manage Cash Balance</h3>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', marginBottom: '4px', color: '#374151' }}>Operation</label>
                <select value={cashForm.operation} onChange={(e) => setCashForm({ ...cashForm, operation: e.target.value as 'add' | 'set' })} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', fontFamily: 'inherit', background: '#FFFFFF' }}>
                  <option value="add">Add to Balance</option>
                  <option value="set">Set Balance</option>
                </select>
              </div>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', marginBottom: '4px', color: '#374151' }}>Amount ($)</label>
                <input type="number" value={cashForm.amount || ''} onChange={(e) => setCashForm({ ...cashForm, amount: parseFloat(e.target.value) || 0 })} placeholder="10000" step="0.01" style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', fontFamily: 'inherit' }} />
              </div>
              <div style={{ fontSize: '13px', marginBottom: '16px', padding: '8px', background: '#f3f4f6', borderRadius: '4px' }}>
                <div><strong>Current:</strong> ${Number(portfolio?.cash_balance || 0).toLocaleString()}</div>
                <div style={{ marginTop: '4px' }}><strong>New:</strong> ${cashForm.operation === 'add' ? (Number(portfolio?.cash_balance || 0) + cashForm.amount).toLocaleString() : cashForm.amount.toLocaleString()}</div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => setShowCashModal(false)} style={{ flex: 1, padding: '8px 16px', fontSize: '14px', background: '#FFFFFF', color: '#374151', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer', fontWeight: '500', fontFamily: 'inherit' }}>Cancel</button>
                <button onClick={handleUpdateCash} style={{ flex: 1, padding: '8px 16px', fontSize: '14px', background: '#2563eb', color: '#FFFFFF', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: '500', fontFamily: 'inherit' }}>Update</button>
              </div>
            </div>
          </div>
        )}

        {/* Guide Panel */}
        <PortfolioGuidePanel isOpen={showGuide} onClose={() => setShowGuide(false)} context="detail" />
      </div>
    </PortfolioDetailContext.Provider>
  );
};

export default PortfolioDetailPage;
