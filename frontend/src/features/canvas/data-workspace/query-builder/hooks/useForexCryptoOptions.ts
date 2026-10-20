import { useState, useCallback, useMemo, useEffect } from 'react';
import api from '@/services/api';
import type { FormMode, ObjectTypeResult } from '@/features/canvas/types';
import { searchTickerList } from '@/hooks/useTickerSearch';
import { useTickerUniverseStore } from '@/stores/tickerUniverseStore';

interface UseForexCryptoOptionsProps {
  formMode: FormMode;
  setFormCustomIdentifier: (value: string) => void;
  setFormParams: (params: Record<string, string>) => void;
  currentFormParams?: Record<string, string>;
}

export function useForexCryptoOptions({
  formMode,
  setFormCustomIdentifier,
  setFormParams,
  currentFormParams = {},
}: UseForexCryptoOptionsProps) {
  // Forex/Crypto state
  const [forexPairs, setForexPairs] = useState<string[]>([]);
  const [cryptoPairs, setCryptoPairs] = useState<string[]>([]);
  const [loadingForexPairs, setLoadingForexPairs] = useState(false);
  const [loadingCryptoPairs, setLoadingCryptoPairs] = useState(false);
  const [forexDropdownOpen, setForexDropdownOpen] = useState(false);
  const [forexSearch, setForexSearch] = useState('');
  const [cryptoDropdownOpen, setCryptoDropdownOpen] = useState(false);
  const [cryptoSearch, setCryptoSearch] = useState('');
  
  // Options builder state
  const [optionsUnderlying, setOptionsUnderlying] = useState('');
  const [optionsUnderlyingSearch, setOptionsUnderlyingSearch] = useState('');
  const [optionsUnderlyingResults, setOptionsUnderlyingResults] = useState<Array<{ symbol: string; name: string }>>([]);
  const [optionsUnderlyingDropdownOpen, setOptionsUnderlyingDropdownOpen] = useState(false);
  const [optionsType, setOptionsType] = useState<'C' | 'P'>('C');
  const [optionsExpiry, setOptionsExpiry] = useState('');
  const [optionsExpirations, setOptionsExpirations] = useState<string[]>([]);
  const [loadingExpirations, setLoadingExpirations] = useState(false);
  const [optionsStrike, setOptionsStrike] = useState('');
  const [optionsExpiryDropdownOpen, setOptionsExpiryDropdownOpen] = useState(false);
  
  // UW enum values for dropdowns (sector, flow_group, month, etc.)
  const [uwEnums, setUwEnums] = useState<Record<string, string[]>>({});
  const [uwEnumsLoading, setUwEnumsLoading] = useState<Set<string>>(new Set());
  
  // UW expiration dates per ticker (for options endpoints that need expiry param)
  const [uwExpirations, setUwExpirations] = useState<Record<string, string[]>>({});
  const [uwExpirationsLoading, setUwExpirationsLoading] = useState<Set<string>>(new Set());

  // Fetch forex pairs
  const fetchForexPairs = useCallback(async () => {
    if (forexPairs.length > 0) return;
    setLoadingForexPairs(true);
    try {
      const response = await api.get<{ pairs: string[]; count: number }>('/api/canvas/data/forex/pairs');
      setForexPairs(response.data.pairs || []);
    } catch (error) {
      console.error('Error fetching forex pairs:', error);
      setForexPairs([
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD',
        'EURGBP', 'EURJPY', 'GBPJPY', 'AUDJPY', 'EURAUD', 'EURCHF'
      ]);
    } finally {
      setLoadingForexPairs(false);
    }
  }, [forexPairs.length]);

  // Fetch crypto pairs
  const fetchCryptoPairs = useCallback(async () => {
    if (cryptoPairs.length > 0) return;
    setLoadingCryptoPairs(true);
    try {
      const response = await api.get<{ pairs: string[]; count: number }>('/api/canvas/data/crypto/pairs');
      setCryptoPairs(response.data.pairs || []);
    } catch (error) {
      console.error('Error fetching crypto pairs:', error);
      setCryptoPairs([
        'BTCUSD', 'ETHUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'DOGEUSD',
        'DOTUSD', 'LINKUSD', 'MATICUSD', 'UNIUSD', 'AVAXUSD', 'ATOMUSD'
      ]);
    } finally {
      setLoadingCryptoPairs(false);
    }
  }, [cryptoPairs.length]);

  // Fetch options expirations when underlying is selected
  const fetchOptionsExpirations = useCallback(async (ticker: string) => {
    if (!ticker) {
      setOptionsExpirations([]);
      return;
    }
    setLoadingExpirations(true);
    try {
      const response = await api.get<{ ticker: string; expirations: string[]; count: number }>(
        `/api/canvas/data/options/expirations/${encodeURIComponent(ticker)}`
      );
      setOptionsExpirations(response.data.expirations || []);
      if (response.data.expirations?.length > 0 && !optionsExpiry) {
        setOptionsExpiry(response.data.expirations[0]);
      }
    } catch (error) {
      console.error('Error fetching options expirations:', error);
      setOptionsExpirations([]);
    } finally {
      setLoadingExpirations(false);
    }
  }, [optionsExpiry]);

  // Fetch UW enum values (sector, flow_group, month, etc.)
  const fetchUwEnum = useCallback(async (enumName: string) => {
    if (uwEnums[enumName] || uwEnumsLoading.has(enumName)) return;
    
    setUwEnumsLoading(prev => new Set(prev).add(enumName));
    try {
      const response = await api.get<{ enum: string; values: string[]; count: number }>(
        `/api/canvas/data/uw/enums/${encodeURIComponent(enumName)}`
      );
      setUwEnums(prev => ({ ...prev, [enumName]: response.data.values || [] }));
    } catch (error) {
      console.error(`Error fetching UW enum ${enumName}:`, error);
      setUwEnums(prev => ({ ...prev, [enumName]: [] }));
    } finally {
      setUwEnumsLoading(prev => {
        const next = new Set(prev);
        next.delete(enumName);
        return next;
      });
    }
  }, [uwEnums, uwEnumsLoading]);

  // Fetch UW expiration dates for a ticker (for options endpoints needing expiry param)
  const fetchUwExpirations = useCallback(async (ticker: string) => {
    if (!ticker || uwExpirations[ticker] || uwExpirationsLoading.has(ticker)) return;
    
    setUwExpirationsLoading(prev => new Set(prev).add(ticker));
    try {
      const response = await api.get<{ ticker: string; expirations: string[]; count: number }>(
        `/api/canvas/data/uw/expirations/${encodeURIComponent(ticker)}`
      );
      setUwExpirations(prev => ({ ...prev, [ticker]: response.data.expirations || [] }));
    } catch (error) {
      console.error(`Error fetching UW expirations for ${ticker}:`, error);
      setUwExpirations(prev => ({ ...prev, [ticker]: [] }));
    } finally {
      setUwExpirationsLoading(prev => {
        const next = new Set(prev);
        next.delete(ticker);
        return next;
      });
    }
  }, [uwExpirations, uwExpirationsLoading]);

  // Build options ticker from components (Polygon format)
  const buildOptionsTicker = useCallback((underlying: string, expiry: string, type: 'C' | 'P', strike: string): string | null => {
    if (!underlying || !expiry || !strike) return null;
    const strikeNum = parseFloat(strike);
    if (isNaN(strikeNum) || strikeNum <= 0) return null;
    
    const date = expiry.replace(/-/g, '').slice(2);
    const strikeStr = Math.round(strikeNum * 1000).toString().padStart(8, '0');
    
    return `O:${underlying}${date}${type}${strikeStr}`;
  }, []);

  // Validate options ticker format
  const isValidOptionsTicker = useCallback((ticker: string): boolean => {
    const match = ticker.match(/^O:([A-Z]+)(\d{6})([CP])(\d{8})$/);
    return !!match;
  }, []);

  // Search for options underlying ticker — same approach as Stock/ETF:
  // show full universe when no query, useTickerSearch results when searching
  const searchOptionsUnderlying = useCallback(async (query: string) => {
    const store = useTickerUniverseStore.getState();
    if (!store.isLoaded && !store.isLoading) await store.fetchTickers();

    if (!query || query.length < 1) {
      const all = store.tickers
        .filter(r => !r.symbol.includes(':') && !r.symbol.includes('/'))
        .map(r => ({ symbol: r.symbol, name: r.name }));
      setOptionsUnderlyingResults(all);
      return;
    }
    const matches = searchTickerList(store.tickers, query, { limit: 50 });
    const results = matches
      .filter(r => !r.symbol.includes(':') && !r.symbol.includes('/'))
      .map(r => ({ symbol: r.symbol, name: r.name }));
    setOptionsUnderlyingResults(results);
  }, []);

  // Filter forex/crypto pairs by search
  const filteredForexPairs = useMemo(() => {
    if (!forexSearch) return forexPairs;
    const search = forexSearch.toUpperCase();
    return forexPairs.filter(pair => pair.includes(search));
  }, [forexPairs, forexSearch]);

  const filteredCryptoPairs = useMemo(() => {
    if (!cryptoSearch) return cryptoPairs;
    const search = cryptoSearch.toUpperCase();
    return cryptoPairs.filter(pair => pair.includes(search));
  }, [cryptoPairs, cryptoSearch]);

  // ===== Effects for forex/crypto/options =====
  
  // Load forex/crypto pairs when mode changes
  useEffect(() => {
    if (formMode === 'forex') {
      fetchForexPairs();
    } else if (formMode === 'crypto') {
      fetchCryptoPairs();
    }
  }, [formMode, fetchForexPairs, fetchCryptoPairs]);

  // Fetch expirations when underlying changes
  useEffect(() => {
    if (optionsUnderlying) {
      fetchOptionsExpirations(optionsUnderlying);
    }
  }, [optionsUnderlying, fetchOptionsExpirations]);

  // Update formCustomIdentifier when options components change
  useEffect(() => {
    if (formMode === 'options' && optionsUnderlying && optionsExpiry && optionsStrike) {
      const ticker = buildOptionsTicker(optionsUnderlying, optionsExpiry, optionsType, optionsStrike);
      if (ticker) {
        setFormCustomIdentifier(ticker);
        setFormParams({ ...currentFormParams, options_ticker: ticker });
      }
    }
  }, [formMode, optionsUnderlying, optionsExpiry, optionsType, optionsStrike, buildOptionsTicker, setFormCustomIdentifier, setFormParams]);

  // Debounced search for options underlying
  useEffect(() => {
    const timer = setTimeout(() => {
      if (optionsUnderlyingSearch && formMode === 'options') {
        searchOptionsUnderlying(optionsUnderlyingSearch);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [optionsUnderlyingSearch, formMode, searchOptionsUnderlying]);

  return {
    // Forex state
    forexPairs,
    setForexPairs,
    cryptoPairs,
    setCryptoPairs,
    loadingForexPairs,
    loadingCryptoPairs,
    forexDropdownOpen,
    setForexDropdownOpen,
    forexSearch,
    setForexSearch,
    cryptoDropdownOpen,
    setCryptoDropdownOpen,
    cryptoSearch,
    setCryptoSearch,
    
    // Options state
    optionsUnderlying,
    setOptionsUnderlying,
    optionsUnderlyingSearch,
    setOptionsUnderlyingSearch,
    optionsUnderlyingResults,
    setOptionsUnderlyingResults,
    optionsUnderlyingDropdownOpen,
    setOptionsUnderlyingDropdownOpen,
    optionsType,
    setOptionsType,
    optionsExpiry,
    setOptionsExpiry,
    optionsExpirations,
    loadingExpirations,
    optionsStrike,
    setOptionsStrike,
    optionsExpiryDropdownOpen,
    setOptionsExpiryDropdownOpen,
    
    // UW enums
    uwEnums,
    uwEnumsLoading,
    fetchUwEnum,
    
    // UW expirations (for options endpoints needing expiry param)
    uwExpirations,
    uwExpirationsLoading,
    fetchUwExpirations,
    
    // Handlers
    fetchForexPairs,
    fetchCryptoPairs,
    fetchOptionsExpirations,
    buildOptionsTicker,
    isValidOptionsTicker,
    searchOptionsUnderlying,
    
    // Computed
    filteredForexPairs,
    filteredCryptoPairs,
  };
}
