import { createContext, useContext } from 'react';
import type { Holding, PurchaseLot, PortfolioData } from '@/services/portfolioApi';

export interface PortfolioDetailContextValue {
  portfolio: PortfolioData;
  portfolioId: string;

  // Holdings
  holdings: Holding[];
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  sortedHoldings: Holding[];
  paginatedHoldings: Holding[];
  holdingsPage: number;
  setHoldingsPage: React.Dispatch<React.SetStateAction<number>>;
  totalHoldingsPages: number;

  // Sorting
  sortColumn: string;
  sortDirection: 'asc' | 'desc';
  handleSort: (column: string) => void;

  // Prices
  prices: Record<string, number>;
  pricesLastUpdated: Date | null;
  loadingPrices: boolean;
  handleRefreshPrices: () => Promise<void>;

  // Values
  holdingsValue: number;
  totalValue: number;
  totalWeight: number;
  sectorData: { sector: string; percentage: number }[];
  sectorColors: Record<string, string>;

  // Ticker details
  tickerDetails: Record<string, { name: string; sector: string | null; industry: string | null; description: string | null; exchange: string | null }>;

  // Expansion state
  expandedHoldings: Set<string>;
  toggleLotExpansion: (ticker: string) => void;
  expandedMetadata: Set<string>;
  toggleMetadataExpansion: (ticker: string) => void;
  expandedSections: Set<string>;
  toggleSection: (sectionId: string) => void;

  // Editing
  isEditing: boolean;
  setIsEditing: React.Dispatch<React.SetStateAction<boolean>>;
  editingCell: { ticker: string; field: 'quantity' | 'avgCost' | 'purchaseDate' } | null;
  editValue: string;
  handleCellEdit: (ticker: string, field: 'quantity' | 'avgCost' | 'purchaseDate', currentValue: string) => void;
  handleCellSave: () => Promise<void>;
  handleCellCancel: () => void;

  // IBKR
  isSyncingIBKR: boolean;
  handleSyncIBKR: () => Promise<void>;

  // Modal triggers
  setShowBuyModal: React.Dispatch<React.SetStateAction<boolean>>;
  setShowSellModal: React.Dispatch<React.SetStateAction<boolean>>;
  setShowCashModal: React.Dispatch<React.SetStateAction<boolean>>;
  setShowAddHoldingModal: React.Dispatch<React.SetStateAction<boolean>>;

  // Actions
  handleRemoveTicker: (ticker: string) => void;
  equalizeQuantities: () => void;
  handleSave: () => Promise<void>;

  // Helpers
  calculateAvgCost: (lots: PurchaseLot[] | undefined) => number;
  getTotalQuantity: (lots: PurchaseLot[] | undefined) => number;
  formatTickerDisplay: (holding: Holding) => string;
  getCompanyLogoUrl: (symbol: string) => string;

  // Responsive
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;

  // Guide
  hoveredSector: { sector: string; percentage: number } | null;
  setHoveredSector: React.Dispatch<React.SetStateAction<{ sector: string; percentage: number } | null>>;
}

export const PortfolioDetailContext = createContext<PortfolioDetailContextValue | null>(null);

export function usePortfolioDetail(): PortfolioDetailContextValue {
  const ctx = useContext(PortfolioDetailContext);
  if (!ctx) {
    throw new Error('usePortfolioDetail must be used within a PortfolioDetailContext.Provider');
  }
  return ctx;
}
