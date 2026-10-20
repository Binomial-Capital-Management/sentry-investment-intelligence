import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Portfolio } from '@/types';
import portfolioApiService, { PortfolioData, PortfolioCreate, BuySharesRequest, SellSharesRequest, UpdateCashRequest } from '@/services/portfolioApi';

interface PortfolioStore {
  // Current active portfolio
  portfolio: Portfolio | null;

  // ID of the currently selected portfolio
  selectedPortfolioId: string | null;

  // All saved portfolios from backend
  savedPortfolios: PortfolioData[];

  // UI state
  isLoading: boolean;
  error: string | null;

  // API-connected methods
  loadPortfolios: () => Promise<void>;
  createPortfolio: (portfolio: PortfolioCreate) => Promise<PortfolioData>;
  updatePortfolio: (portfolioId: string, updates: Partial<PortfolioCreate>) => Promise<void>;
  deletePortfolio: (portfolioId: string) => Promise<void>;
  setDefaultPortfolio: (portfolioId: string) => Promise<void>;
  selectPortfolio: (portfolioId: string) => void;

  // Trading operations
  buyShares: (portfolioId: string, request: BuySharesRequest) => Promise<void>;
  sellShares: (portfolioId: string, request: SellSharesRequest) => Promise<void>;
  updateCashBalance: (portfolioId: string, request: UpdateCashRequest) => Promise<void>;

  // Broker integration methods
  getBrokerPortfolios: () => PortfolioData[];
  getManualPortfolios: () => PortfolioData[];

  // Analytics methods
  getTopHoldings: (limit?: number) => Array<{ ticker: string; totalValue: number; totalQuantity: number }>;

  // Local state methods
  setPortfolio: (portfolio: Portfolio) => void;
  updateTickers: (tickers: string[]) => void;
  updateWeights: (weights: number[]) => void;
  updateValue: (value: number) => void;
  clearPortfolio: () => void;
  clearError: () => void;
}

export const usePortfolioStore = create<PortfolioStore>()(
  persist(
    (set, get) => ({
      portfolio: {
        tickers: ['AAPL', 'MSFT', 'GOOGL'],
        weights: [0.33, 0.33, 0.34],
        value: 4000000,
        lastUpdated: new Date(),
      },
      selectedPortfolioId: null,
      savedPortfolios: [],
      isLoading: false,
      error: null,

      // Load all portfolios from backend
      loadPortfolios: async () => {
        set({ isLoading: true, error: null });
        try {
          const portfolios = await portfolioApiService.listPortfolios();
          set({ savedPortfolios: portfolios, isLoading: false });

          // Auto-select default portfolio if current is null
          const defaultPortfolio = portfolios.find(p => p.is_default);
          if (defaultPortfolio && !get().portfolio) {
            get().selectPortfolio(defaultPortfolio.id);
          }
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
        }
      },

      // Create new portfolio via API
      createPortfolio: async (portfolio: PortfolioCreate) => {
        set({ isLoading: true, error: null });
        try {
          const newPortfolio = await portfolioApiService.createPortfolio(portfolio);

          // Optimistically add to local state
          set((state) => ({
            savedPortfolios: [...state.savedPortfolios, newPortfolio],
            isLoading: false,
          }));

          // Auto-select if it's the first or default
          if (portfolio.is_default || get().savedPortfolios.length === 1) {
            get().selectPortfolio(newPortfolio.id);
          }

          return newPortfolio;
        } catch (error) {
          console.error('Failed to create portfolio:', error);
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      // Update portfolio via API
      updatePortfolio: async (portfolioId: string, updates: Partial<PortfolioCreate>) => {
        set({ isLoading: true, error: null });
        try {
          const updatedPortfolio = await portfolioApiService.updatePortfolio(portfolioId, updates);
          set((state) => ({
            savedPortfolios: state.savedPortfolios.map(p =>
              p.id === portfolioId ? updatedPortfolio : p,
            ),
            isLoading: false,
          }));

          // Update current portfolio if it's the one being edited
          if (get().portfolio && portfolioId === get().savedPortfolios.find(p =>
            p.tickers.join(',') === get().portfolio?.tickers.join(','))?.id) {
            set({
              portfolio: {
                tickers: updatedPortfolio.tickers,
                weights: updatedPortfolio.weights,
                value: updatedPortfolio.value || 1000000,
                lastUpdated: new Date(updatedPortfolio.created_at),
              },
            });
          }
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
        }
      },

      // Delete portfolio via API
      deletePortfolio: async (portfolioId: string) => {
        set({ isLoading: true, error: null });
        try {
          await portfolioApiService.deletePortfolio(portfolioId);

          // Optimistically remove from local state
          set((state) => ({
            savedPortfolios: state.savedPortfolios.filter(p => p.id !== portfolioId),
            isLoading: false,
          }));

          // Clear current if it was deleted
          const deleted = get().savedPortfolios.find(p => p.id === portfolioId);
          if (deleted && get().portfolio?.tickers.join(',') === deleted.tickers.join(',')) {
            set({ portfolio: null });
          }
        } catch (error) {
          console.error('Failed to delete portfolio:', error);
          set({ error: (error as Error).message, isLoading: false });
          // Reload portfolios to sync with backend after error
          get().loadPortfolios();
          throw error;
        }
      },

      // Set portfolio as default
      setDefaultPortfolio: async (portfolioId: string) => {
        set({ isLoading: true, error: null });
        try {
          await portfolioApiService.setDefault(portfolioId);

          // Optimistically update local state
          set((state) => ({
            savedPortfolios: state.savedPortfolios.map(p => ({
              ...p,
              is_default: p.id === portfolioId,
            })),
            isLoading: false,
          }));

          // Auto-select the new default
          get().selectPortfolio(portfolioId);
        } catch (error) {
          console.error('Failed to set default portfolio:', error);
          set({ error: (error as Error).message, isLoading: false });
          // Reload portfolios to sync with backend after error
          get().loadPortfolios();
          throw error;
        }
      },

      // Select a saved portfolio as current
      selectPortfolio: (portfolioId: string) => {
        const portfolio = get().savedPortfolios.find(p => p.id === portfolioId);
        if (portfolio) {
          set({
            selectedPortfolioId: portfolioId,
            portfolio: {
              tickers: portfolio.tickers,
              weights: portfolio.weights,
              value: portfolio.value || 1000000,
              lastUpdated: new Date(portfolio.created_at),
            },
          });
        }
      },

      // Buy shares: deduct from cash, add lot to holdings
      buyShares: async (portfolioId: string, request: BuySharesRequest) => {
        set({ isLoading: true, error: null });
        try {
          const updatedPortfolio = await portfolioApiService.buyShares(portfolioId, request);

          // Update savedPortfolios with new data
          set((state) => ({
            savedPortfolios: state.savedPortfolios.map(p =>
              p.id === portfolioId ? updatedPortfolio : p,
            ),
            isLoading: false,
          }));

          // Update current portfolio if it's the one being traded
          if (get().selectedPortfolioId === portfolioId) {
            set({
              portfolio: {
                tickers: updatedPortfolio.tickers,
                weights: updatedPortfolio.weights,
                value: updatedPortfolio.value || 1000000,
                lastUpdated: new Date(),
              },
            });
          }
        } catch (error) {
          console.error('Failed to buy shares:', error);
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      // Sell shares: remove lots (FIFO), add to cash
      sellShares: async (portfolioId: string, request: SellSharesRequest) => {
        set({ isLoading: true, error: null });
        try {
          const updatedPortfolio = await portfolioApiService.sellShares(portfolioId, request);

          // Update savedPortfolios with new data
          set((state) => ({
            savedPortfolios: state.savedPortfolios.map(p =>
              p.id === portfolioId ? updatedPortfolio : p,
            ),
            isLoading: false,
          }));

          // Update current portfolio if it's the one being traded
          if (get().selectedPortfolioId === portfolioId) {
            set({
              portfolio: {
                tickers: updatedPortfolio.tickers,
                weights: updatedPortfolio.weights,
                value: updatedPortfolio.value || 1000000,
                lastUpdated: new Date(),
              },
            });
          }
        } catch (error) {
          console.error('Failed to sell shares:', error);
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      // Update cash balance directly
      updateCashBalance: async (portfolioId: string, request: UpdateCashRequest) => {
        set({ isLoading: true, error: null });
        try {
          const updatedPortfolio = await portfolioApiService.updateCash(portfolioId, request);

          // Update savedPortfolios with new data
          set((state) => ({
            savedPortfolios: state.savedPortfolios.map(p =>
              p.id === portfolioId ? updatedPortfolio : p,
            ),
            isLoading: false,
          }));

          // Update current portfolio if it's the one being modified
          if (get().selectedPortfolioId === portfolioId) {
            set({
              portfolio: {
                tickers: updatedPortfolio.tickers,
                weights: updatedPortfolio.weights,
                value: updatedPortfolio.value || 1000000,
                lastUpdated: new Date(),
              },
            });
          }
        } catch (error) {
          console.error('Failed to update cash:', error);
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      // Broker integration helpers
      getBrokerPortfolios: () => {
        return get().savedPortfolios.filter(p => p.source_type === 'broker');
      },

      getManualPortfolios: () => {
        return get().savedPortfolios.filter(p => p.source_type !== 'broker');
      },

      // Get top holdings across all portfolios by market value
      getTopHoldings: (limit = 5) => {
        const holdingsMap = new Map<string, { totalValue: number; totalQuantity: number }>();

        // Aggregate holdings across all portfolios
        get().savedPortfolios.forEach(portfolio => {
          const portfolioValue = portfolio.value || 0;

          // Calculate market value from tickers and weights
          portfolio.tickers.forEach((ticker, index) => {
            const weight = portfolio.weights[index] || 0;
            const marketValue = portfolioValue * weight;  // Value of this position in this portfolio

            const existing = holdingsMap.get(ticker) || { totalValue: 0, totalQuantity: 0 };

            holdingsMap.set(ticker, {
              totalValue: existing.totalValue + marketValue,  // Sum market values across portfolios
              totalQuantity: existing.totalQuantity,
            });
          });
        });

        // Convert to array, filter, and sort by total market value
        return Array.from(holdingsMap.entries())
          .map(([ticker, data]) => ({ ticker, ...data }))
          .filter(item => item.totalValue > 0)
          .sort((a, b) => b.totalValue - a.totalValue)
          .slice(0, limit);
      },

      // Local state management (for temporary edits before saving)
      setPortfolio: (portfolio) =>
        set({ portfolio: { ...portfolio, lastUpdated: new Date() } }),

      updateTickers: (tickers) =>
        set((state) => ({
          portfolio: state.portfolio
            ? { ...state.portfolio, tickers, lastUpdated: new Date() }
            : null,
        })),

      updateWeights: (weights) =>
        set((state) => ({
          portfolio: state.portfolio
            ? { ...state.portfolio, weights, lastUpdated: new Date() }
            : null,
        })),

      updateValue: (value) =>
        set((state) => ({
          portfolio: state.portfolio
            ? { ...state.portfolio, value, lastUpdated: new Date() }
            : null,
        })),

      clearPortfolio: () => set({ portfolio: null, selectedPortfolioId: null }),

      clearError: () => set({ error: null }),
    }),
    {
      name: 'binomial-portfolio',
      partialize: (state) => ({
        portfolio: state.portfolio,
        selectedPortfolioId: state.selectedPortfolioId,
        // Don't persist savedPortfolios as they come from backend
      }),
    },
  ),
);
