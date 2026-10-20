import { useState, useCallback, useEffect } from 'react';
import api from '@/services/api';
import type { ObjectTypeResult } from '@/features/canvas/types';
import { searchTickerList } from '@/hooks/useTickerSearch';
import { useTickerUniverseStore } from '@/stores/tickerUniverseStore';

// Helper function - copied from index.tsx
const detectObjectType = (symbol: string, exchange?: string): string => {
  const sym = symbol.toUpperCase();
  if (sym === '_MARKET_' || sym === 'MARKET' || sym === '') return 'market';
  if (sym.includes('-USD') || sym.includes('USDT') || sym.endsWith('BTC') || sym.endsWith('ETH')) return 'crypto';
  if (sym.match(/^[A-Z]{3}\/[A-Z]{3}$/) || (sym.match(/^[A-Z]{6}$/) && !exchange)) return 'forex';
  if (exchange && ['ARCA', 'BATS'].includes(exchange.toUpperCase())) return 'etf';
  return 'equity';  // Return 'equity' to match OBJECT_TYPES.id
};

// Static lists for commodity and macro types
export const COMMODITY_SYMBOLS = [
  { symbol: 'GCUSD', name: 'Gold' },
  { symbol: 'SIUSD', name: 'Silver' },
  { symbol: 'CLUSD', name: 'Crude Oil WTI' },
  { symbol: 'BZUSD', name: 'Brent Crude Oil' },
  { symbol: 'NGUSD', name: 'Natural Gas' },
  { symbol: 'HGUSD', name: 'Copper' },
  { symbol: 'PLUSD', name: 'Platinum' },
  { symbol: 'PAUSD', name: 'Palladium' },
  { symbol: 'ZSUSD', name: 'Soybeans' },
  { symbol: 'ZCUSD', name: 'Corn' },
  { symbol: 'ZWUSD', name: 'Wheat' },
  { symbol: 'CTUSD', name: 'Cotton' },
  { symbol: 'KCUSD', name: 'Coffee' },
  { symbol: 'SBUSD', name: 'Sugar' },
  { symbol: 'CCUSD', name: 'Cocoa' },
];

export const MACRO_SERIES = [
  { symbol: 'GDP', name: 'Gross Domestic Product' },
  { symbol: 'RGDP', name: 'Real GDP' },
  { symbol: 'CPI', name: 'Consumer Price Index' },
  { symbol: 'INFLATION', name: 'Inflation Rate' },
  { symbol: 'UNEMPLOYMENT', name: 'Unemployment Rate' },
  { symbol: 'FEDFUNDS', name: 'Federal Funds Rate' },
  { symbol: 'TB3MS', name: '3-Month Treasury Bill' },
  { symbol: 'GS10', name: '10-Year Treasury Rate' },
  { symbol: 'M2', name: 'M2 Money Stock' },
  { symbol: 'INDPRO', name: 'Industrial Production Index' },
  { symbol: 'PAYEMS', name: 'Nonfarm Payrolls' },
  { symbol: 'HOUST', name: 'Housing Starts' },
  { symbol: 'RETAIL', name: 'Retail Sales' },
  { symbol: 'PCE', name: 'Personal Consumption Expenditures' },
  { symbol: 'PPI', name: 'Producer Price Index' },
];

interface UseBrowserProps {
  forexPairs: string[];
  setForexPairs: (pairs: string[]) => void;
  cryptoPairs: string[];
  setCryptoPairs: (pairs: string[]) => void;
}

export function useBrowser({
  forexPairs,
  setForexPairs,
  cryptoPairs,
  setCryptoPairs,
}: UseBrowserProps) {
  const [browsingType, setBrowsingType] = useState<string | null>(null);
  const [browserSearchQuery, setBrowserSearchQuery] = useState('');
  const [browserResults, setBrowserResults] = useState<ObjectTypeResult[]>([]);
  const [browserLoading, setBrowserLoading] = useState(false);

  const searchBrowserSymbols = useCallback(async (query: string, objectType: string) => {
    if (!query || query.length < 1) {
      setBrowserResults([]);
      return;
    }
    
    const searchLower = query.toLowerCase();
    
    try {
      // Handle different object types with appropriate data sources
      if (objectType === 'equity' || objectType === 'etf') {
        // Use pre-fetched ticker universe for equities/ETFs
        const store = useTickerUniverseStore.getState();
        if (!store.isLoaded && !store.isLoading) await store.fetchTickers();
        const matches = searchTickerList(store.tickers, query, { limit: 50 });
        const filtered = matches
          .map(r => ({
            symbol: r.symbol,
            name: r.name,
            exchange: r.exchange,
            object_type: detectObjectType(r.symbol, r.exchange),
          }))
          .filter(r => r.object_type === objectType);
        setBrowserResults(filtered);
        
      } else if (objectType === 'forex') {
        // Filter from forex pairs (fetch if needed)
        let pairs = forexPairs;
        if (pairs.length === 0) {
          try {
            const response = await api.get<{ pairs: string[]; count: number }>('/api/canvas/data/forex/pairs');
            pairs = response.data.pairs || [];
            setForexPairs(pairs);
          } catch {
            pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD'];
          }
        }
        const filtered = pairs
          .filter(p => p.toLowerCase().includes(searchLower))
          .slice(0, 50)
          .map(p => ({ symbol: p, name: p, exchange: 'FOREX', object_type: 'forex' }));
        setBrowserResults(filtered);
        
      } else if (objectType === 'crypto') {
        // Filter from crypto pairs (fetch if needed)
        let pairs = cryptoPairs;
        if (pairs.length === 0) {
          try {
            const response = await api.get<{ pairs: string[]; count: number }>('/api/canvas/data/crypto/pairs');
            pairs = response.data.pairs || [];
            setCryptoPairs(pairs);
          } catch {
            pairs = ['BTCUSD', 'ETHUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'DOGEUSD'];
          }
        }
        const filtered = pairs
          .filter(p => p.toLowerCase().includes(searchLower))
          .slice(0, 50)
          .map(p => ({ symbol: p, name: p.replace('USD', ''), exchange: 'CRYPTO', object_type: 'crypto' }));
        setBrowserResults(filtered);
        
      } else if (objectType === 'commodity') {
        // Filter from static commodity list
        const filtered = COMMODITY_SYMBOLS
          .filter(c => c.symbol.toLowerCase().includes(searchLower) || c.name.toLowerCase().includes(searchLower))
          .slice(0, 50)
          .map(c => ({ symbol: c.symbol, name: c.name, exchange: 'COMMODITY', object_type: 'commodity' }));
        setBrowserResults(filtered);
        
      } else if (objectType === 'macro_series') {
        // Filter from static macro series list
        const filtered = MACRO_SERIES
          .filter(m => m.symbol.toLowerCase().includes(searchLower) || m.name.toLowerCase().includes(searchLower))
          .slice(0, 50)
          .map(m => ({ symbol: m.symbol, name: m.name, exchange: 'FRED', object_type: 'macro_series' }));
        setBrowserResults(filtered);
        
      } else {
        // Fallback to ticker universe search
        const store = useTickerUniverseStore.getState();
        if (!store.isLoaded && !store.isLoading) await store.fetchTickers();
        const matches = searchTickerList(store.tickers, query, { limit: 50 });
        const filtered = matches.map(r => ({
          symbol: r.symbol,
          name: r.name,
          exchange: r.exchange,
          object_type: detectObjectType(r.symbol, r.exchange),
        }));
        setBrowserResults(filtered);
      }
    } catch (error) {
      console.error('Error searching browser symbols:', error);
      setBrowserResults([]);
    }
  }, [forexPairs, cryptoPairs, setForexPairs, setCryptoPairs]);

  // Load initial browse results when browsing type changes
  useEffect(() => {
    if (!browsingType) return;
    
    const loadInitialBrowseResults = async () => {
      if (browsingType === 'forex') {
        // Load and show all forex pairs
        let pairs = forexPairs;
        if (pairs.length === 0) {
          try {
            const response = await api.get<{ pairs: string[]; count: number }>('/api/canvas/data/forex/pairs');
            pairs = response.data.pairs || [];
            setForexPairs(pairs);
          } catch {
            pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD'];
          }
        }
        setBrowserResults(pairs.slice(0, 50).map(p => ({ symbol: p, name: p, exchange: 'FOREX', object_type: 'forex' })));
      } else if (browsingType === 'crypto') {
        // Load and show all crypto pairs
        let pairs = cryptoPairs;
        if (pairs.length === 0) {
          try {
            const response = await api.get<{ pairs: string[]; count: number }>('/api/canvas/data/crypto/pairs');
            pairs = response.data.pairs || [];
            setCryptoPairs(pairs);
          } catch {
            pairs = ['BTCUSD', 'ETHUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'DOGEUSD'];
          }
        }
        setBrowserResults(pairs.slice(0, 50).map(p => ({ symbol: p, name: p.replace('USD', ''), exchange: 'CRYPTO', object_type: 'crypto' })));
      } else if (browsingType === 'commodity') {
        // Show all commodities
        setBrowserResults(COMMODITY_SYMBOLS.map(c => ({ symbol: c.symbol, name: c.name, exchange: 'COMMODITY', object_type: 'commodity' })));
      } else if (browsingType === 'macro_series') {
        // Show all macro series
        setBrowserResults(MACRO_SERIES.map(m => ({ symbol: m.symbol, name: m.name, exchange: 'FRED', object_type: 'macro_series' })));
      }
      // For equity/etf, user must search - too many to show all
    };
    
    loadInitialBrowseResults();
  }, [browsingType, forexPairs, cryptoPairs, setForexPairs, setCryptoPairs]);

  return {
    // State
    browsingType,
    setBrowsingType,
    browserSearchQuery,
    setBrowserSearchQuery,
    browserResults,
    setBrowserResults,
    browserLoading,
    setBrowserLoading,
    
    // Handlers
    searchBrowserSymbols,
  };
}
