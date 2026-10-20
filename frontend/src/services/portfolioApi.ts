import axios from 'axios';
import { getAuthToken } from './authService';
import { API_BASE } from './api';

// Create axios instance for portfolio API
const portfolioApi = axios.create({
  baseURL: `${API_BASE}/api/portfolios`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth header and organization context to all requests
portfolioApi.interceptors.request.use(
  async (config) => {
    try {
      // Get token from auth service (updated by AuthProvider)
      const token = await getAuthToken();

      if (token) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any).Authorization = `Bearer ${token}`;
      } else {
        // DEVELOPMENT ONLY: Auto-auth when Clerk is not available
        const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (isDevelopment) {
          const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
          const devUserId = 'dev-local-user';

          if (!config.headers) config.headers = {} as any;
          (config.headers as any)['X-Dev-Secret'] = devSecret;
          (config.headers as any)['X-Dev-User-Id'] = devUserId;
        }
      }
    } catch (error) {
      console.error('[Portfolio API] Error getting token:', error);
    }

    // Attach organization context for workspace switching
    try {
      const activeOrgId = localStorage.getItem('activeOrganization');
      if (activeOrgId) {
        if (!config.headers) config.headers = {} as any;
        (config.headers as any)['X-Organization-ID'] = activeOrgId;
      }
    } catch (error) {
      console.error('[Portfolio API] Error attaching organization ID:', error);
    }

    return config;
  },
  (error) => Promise.reject(error),
);

// Response error handling
portfolioApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'Unknown error';
    console.error('Portfolio API error:', message);
    return Promise.reject(new Error(message));
  },
);

// Purchase lot types
export interface PurchaseLot {
  lotId?: string;
  quantity: number;  // Can be negative for short positions
  purchasePrice: number;
  purchaseDate: string | Date;
  costBasis?: number;        // Total cost basis for this lot (quantity * purchasePrice)
  currentValue?: number;     // Current market value of this lot
  unrealizedPnL?: number;    // Unrealized profit/loss for this lot
}

export interface Holding {
  ticker: string;
  lots?: PurchaseLot[];
  currentPrice?: number;
  priceUpdatedAt?: string;

  // Aggregated metrics (calculated from all lots)
  totalQuantity?: number;         // Sum of all lot quantities
  totalCostBasis?: number;        // Sum of all lot cost bases
  totalValue?: number;            // Sum of all lot current values
  totalUnrealizedPnL?: number;    // Sum of all lot unrealized P/L
  averageCostBasis?: number;      // Weighted average cost basis

  // Optional metadata for IBKR-specific fields or user notes
  metadata?: {
    // Core fields
    source?: 'ibkr' | 'manual';
    accountId?: string;           // IBKR account ID
    currency?: string;            // Trading currency (USD, CAD, EUR, etc.)
    assetCategory?: string;       // Asset type (STK, OPT, FUT, etc.)
    subCategory?: string;         // Asset sub-type (COMMON, ETF, ADR, REIT)
    description?: string;         // Full asset description
    conid?: string;               // IBKR contract ID (unique identifier)
    side?: string;                // Position side (LONG/SHORT)

    // Financial details
    fxRateToBase?: number;        // Foreign exchange rate to base currency
    multiplier?: number;          // Contract multiplier (options/futures)
    openPrice?: number;           // Opening price
    percentOfNAV?: number;        // Position as % of portfolio NAV

    // Security identifiers
    isin?: string;                // International Securities ID
    cusip?: string;               // US identifier
    figi?: string;                // Bloomberg Global ID
    securityID?: string;          // Primary security ID
    securityIDType?: string;      // Type of security ID (ISIN, CUSIP, etc.)

    // Exchange and issuer
    listingExchange?: string;     // Exchange where security is listed (NYSE, NASDAQ, etc.)
    issuer?: string;              // Issuing company or entity
    issuerCountryCode?: string;   // Country code of issuer (US, CA, CH, etc.)
    reportDate?: string;          // Report date (YYYYMMDD format)

    // Options/derivatives
    strike?: string | number;     // Strike price for options
    expiry?: string;              // Expiry date for options/futures
    putCall?: 'CALL' | 'PUT';     // Option type
    underlyingSymbol?: string;    // Underlying security symbol
    underlyingConid?: string;     // Underlying contract ID

    // Trade tracking
    levelOfDetail?: string;       // LOT for lot-level detail
    code?: string;                // Trade type code (ST = stock trade)

    [key: string]: any;           // Allow any additional IBKR fields
  };

  // Legacy fields for backward compatibility
  quantity?: number;
  purchasePrice?: number;
  purchaseDate?: string;
}

// Portfolio types
export interface PortfolioData {
  id: string;
  name: string;
  tickers: string[];
  weights: number[];
  is_default: boolean;
  value?: number;
  cash_balance?: number;
  created_at: string;
  updated_at?: string;
  holdings?: Holding[];
  metadata?: Record<string, any>;
  // Broker integration fields
  broker_connection_id?: string | null;
  source_type?: 'manual' | 'broker';
  synced_at?: string | null;
}

export interface PortfolioCreate {
  name: string;
  tickers: string[];
  weights: number[];
  value?: number;
  is_default?: boolean;
  holdings?: Holding[];
  cash_balance?: number;
}

export interface PortfolioUpdate {
  name?: string;
  tickers?: string[];
  weights?: number[];
  value?: number;
  cash_balance?: number;
  is_default?: boolean;
  holdings?: Holding[];
}

export interface PriceData {
  prices: Record<string, number>;
  timestamp: string;
}

export interface PortfolioValueHistory {
  id: string;
  portfolio_id: string;
  snapshot_date: string;
  total_value: number;
  created_at: string;
  holdings_snapshot?: Holding[];
  prices_snapshot?: Record<string, number>;
}

// Trading operation types
export interface BuySharesRequest {
  ticker: string;
  quantity: number;
  price: number;
  purchase_date?: string;
}

export interface SellSharesRequest {
  ticker: string;
  quantity: number;
  price: number;
  lot_ids?: string[];
}

export interface UpdateCashRequest {
  amount: number;
  operation: 'add' | 'set';
}

const buildAuthHeaders = async (): Promise<Record<string, string>> => {
  const headers: Record<string, string> = {};
  const token = await getAuthToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  } else {
    const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (isDevelopment) {
      const devSecret = (import.meta as any).env?.VITE_DEV_SECRET;
      const devUserId = 'dev-local-user';
      if (devSecret) {
        headers['X-Dev-Secret'] = devSecret;
      }
      headers['X-Dev-User-Id'] = devUserId;
    }
  }
  return headers;
};

// Export the axios instance for direct use
export { portfolioApi };

// API methods
export const portfolioApiService = {
  // List all portfolios for the user
  listPortfolios: async (): Promise<PortfolioData[]> => {
    const startTime = Date.now();
    try {
      const response = await portfolioApi.get('');
      const duration = Date.now() - startTime;
      console.log(`[Portfolio API] Loaded ${response.data.length} portfolios in ${duration}ms`);
      return response.data;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`[Portfolio API] Failed to load portfolios after ${duration}ms`, error);
      throw error;
    }
  },

  // Create a new portfolio
  createPortfolio: async (portfolio: PortfolioCreate): Promise<PortfolioData> => {
    console.log('[Portfolio API] Creating portfolio:', portfolio);
    const startTime = Date.now();
    try {
      const response = await portfolioApi.post('', portfolio);
      const duration = Date.now() - startTime;
      console.log(`[Portfolio API] Portfolio created successfully in ${duration}ms`, response.data);
      return response.data;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`[Portfolio API] Portfolio creation failed after ${duration}ms`, error);
      throw error;
    }
  },

  // Get a specific portfolio
  getPortfolio: async (portfolioId: string): Promise<PortfolioData> => {
    const response = await portfolioApi.get(`/${portfolioId}`);
    return response.data;
  },

  // Update a portfolio
  updatePortfolio: async (portfolioId: string, updates: PortfolioUpdate): Promise<PortfolioData> => {
    const response = await portfolioApi.put(`/${portfolioId}`, updates);
    return response.data;
  },

  // Delete a portfolio
  deletePortfolio: async (portfolioId: string): Promise<void> => {
    await portfolioApi.delete(`/${portfolioId}`);
  },

  // Set portfolio as default
  setDefault: async (portfolioId: string): Promise<PortfolioData> => {
    const response = await portfolioApi.post(`/${portfolioId}/set-default`);
    return response.data;
  },

  // Fetch current prices for tickers
  fetchPrices: async (tickers: string[]): Promise<PriceData> => {
    const response = await portfolioApi.post('/prices', { tickers });
    return response.data;
  },

  // Get portfolio value history for charting
  getValueHistory: async (portfolioId: string, days: number = 30): Promise<PortfolioValueHistory[]> => {
    const headers = await buildAuthHeaders();
    const response = await axios.get(`${API_BASE}/portfolio-history/${portfolioId}/history`, {
      params: { days },
      headers,
    });
    return response.data;
  },

  // Buy shares: deduct from cash, add lot to holdings
  buyShares: async (portfolioId: string, request: BuySharesRequest): Promise<PortfolioData> => {
    console.log('[Portfolio API] Buying shares:', { portfolioId, request });
    const startTime = Date.now();
    try {
      const response = await portfolioApi.post(`/${portfolioId}/buy`, request);
      const duration = Date.now() - startTime;
      console.log(`[Portfolio API] Shares purchased successfully in ${duration}ms`, response.data);
      return response.data;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`[Portfolio API] Share purchase failed after ${duration}ms`, error);
      throw error;
    }
  },

  // Sell shares: remove lots (FIFO), add to cash
  sellShares: async (portfolioId: string, request: SellSharesRequest): Promise<PortfolioData> => {
    console.log('[Portfolio API] Selling shares:', { portfolioId, request });
    const startTime = Date.now();
    try {
      const response = await portfolioApi.post(`/${portfolioId}/sell`, request);
      const duration = Date.now() - startTime;
      console.log(`[Portfolio API] Shares sold successfully in ${duration}ms`, response.data);
      return response.data;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`[Portfolio API] Share sale failed after ${duration}ms`, error);
      throw error;
    }
  },

  // Update cash balance directly
  updateCash: async (portfolioId: string, request: UpdateCashRequest): Promise<PortfolioData> => {
    console.log('[Portfolio API] Updating cash:', { portfolioId, request });
    const startTime = Date.now();
    try {
      const response = await portfolioApi.put(`/${portfolioId}/cash`, request);
      const duration = Date.now() - startTime;
      console.log(`[Portfolio API] Cash updated successfully in ${duration}ms`, response.data);
      return response.data;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`[Portfolio API] Cash update failed after ${duration}ms`, error);
      throw error;
    }
  },

  // Manually sync IBKR portfolio positions
  syncIBKRPortfolio: async (portfolioId: string): Promise<{
    status: string;
    message: string;
    synced_at: string;
    position_count: number;
  }> => {
    console.log(`[Portfolio API] Syncing IBKR portfolio ${portfolioId}...`);
    const startTime = Date.now();
    const headers = await buildAuthHeaders();
    try {
      const response = await axios.post(
        `${API_BASE}/api/brokers/ibkr/sync/${portfolioId}`,
        {},
        { headers },
      );
      const duration = Date.now() - startTime;
      console.log(`[Portfolio API] IBKR sync completed in ${duration}ms:`, response.data);
      return response.data;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`[Portfolio API] IBKR sync failed after ${duration}ms`, error);
      throw error;
    }
  },
};

export default portfolioApiService;
