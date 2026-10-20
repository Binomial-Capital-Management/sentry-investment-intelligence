import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { Search, X } from 'lucide-react';
import type { FormMode } from '@/features/canvas/types';
import { OptionsContractBuilder } from '@/features/canvas/data-workspace/query-builder';
import { useForexCryptoOptions } from '@/features/canvas/data-workspace/query-builder/hooks/useForexCryptoOptions';
import { detectObjectType } from '@/features/canvas/data-workspace/query-builder/utils/queryUtils';
import { useTickerSearch } from '@/hooks/useTickerSearch';
import { useTickerUniverseStore } from '@/stores/tickerUniverseStore';
import { TickerPicker, TickerVirtualList } from '@/features/canvas/shared/symbol-search';
import { useDataWorkspaceStore } from '../../stores/dataWorkspaceStore';
import {
  selectAddDataPanelFormMode,
  selectAddDataPanelCustomIdentifier,
  selectSymbols,
} from '../../stores/selectors';

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: '$', EUR: '€', GBP: '£', JPY: '¥', CHF: 'Fr', AUD: 'A$', CAD: 'C$',
  NZD: 'NZ$', SEK: 'kr', NOK: 'kr', DKK: 'kr', SGD: 'S$', HKD: 'HK$',
  KRW: '₩', CNY: '¥', INR: '₹', TRY: '₺', ZAR: 'R', BRL: 'R$', MXN: 'Mex$',
  PLN: 'zł', THB: '฿', RUB: '₽', ILS: '₪', CZK: 'Kč', HUF: 'Ft',
  BTC: '₿', ETH: 'Ξ', SOL: 'SOL', XRP: 'XRP', ADA: 'ADA', DOGE: 'DOGE',
  DOT: 'DOT', LINK: 'LINK', MATIC: 'MATIC', UNI: 'UNI', AVAX: 'AVAX', ATOM: 'ATOM',
};

const getCurrencySymbol = (code: string) => CURRENCY_SYMBOLS[code] || code;

const getCryptoIconUrl = (symbol: string) =>
  `/crypto-icons/${symbol.toLowerCase()}.svg`;

const getCryptoFallbackUrl = (symbol: string) =>
  `https://assets.coincap.io/assets/icons/${symbol.toLowerCase()}@2x.png`;

const handleCryptoImgError = (e: React.SyntheticEvent<HTMLImageElement>) => {
  const img = e.target as HTMLImageElement;
  const fallback = img.dataset.fallback;
  if (fallback && img.src !== fallback) {
    img.src = fallback;
    img.classList.add('grayscale');
  } else {
    img.style.display = 'none';
  }
};

const SIDEBAR_MODES: { mode: FormMode; label: string }[] = [
  { mode: 'symbol', label: 'Stock/ETF' },
  { mode: 'market', label: 'Market' },
  { mode: 'options', label: 'Options' },
  { mode: 'forex', label: 'Forex' },
  { mode: 'crypto', label: 'Crypto' },
];

export function SymbolSelector() {
  const sidebarFormMode = useDataWorkspaceStore(selectAddDataPanelFormMode) as FormMode;
  const setSidebarFormMode = useDataWorkspaceStore(s => s.setAddDataPanelFormMode);
  const sidebarCustomIdentifier = useDataWorkspaceStore(selectAddDataPanelCustomIdentifier);
  const setSidebarCustomIdentifier = useDataWorkspaceStore(s => s.setAddDataPanelCustomIdentifier);
  const setObjects = useDataWorkspaceStore(s => s.setObjects);
  const addTab = useDataWorkspaceStore(s => s.addTab);
  const currentSymbols = useDataWorkspaceStore(selectSymbols);

  // Transient search state
  const [sidebarSymbolSearch, setSidebarSymbolSearch] = useState('');
  const [tickerListShowTopFade, setTickerListShowTopFade] = useState(false);
  const [tickerListShowBottomFade, setTickerListShowBottomFade] = useState(false);
  const tickerListRef = useRef<HTMLDivElement>(null);

  // Ticker dropdown state
  const [tickerDropdownOpen, setTickerDropdownOpen] = useState(false);
  const tickerDropdownRef = useRef<HTMLDivElement>(null);
  const tickerSearchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!tickerDropdownOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (tickerDropdownRef.current && !tickerDropdownRef.current.contains(e.target as Node)) {
        setTickerDropdownOpen(false);
        setSidebarSymbolSearch('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [tickerDropdownOpen]);

  const updateTickerListFades = useCallback(() => {
    const el = tickerListRef.current;
    if (!el) return;
    setTickerListShowTopFade(el.scrollTop > 2);
    setTickerListShowBottomFade(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
  }, []);
  const allTickers = useTickerUniverseStore(s => s.tickers);
  const fetchTickers = useTickerUniverseStore(s => s.fetchTickers);
  const tickersLoading = useTickerUniverseStore(s => s.isLoading);
  const { results: filteredTickers } = useTickerSearch(sidebarSymbolSearch, { limit: Infinity });

  // Fetch ticker universe on mount
  useEffect(() => { fetchTickers(); }, [fetchTickers]);

  // Recheck fades when any list content changes (stocks, forex, crypto)
  useEffect(() => {
    requestAnimationFrame(updateTickerListFades);
  }, [allTickers, sidebarSymbolSearch, filteredTickers, sidebarFormMode, updateTickerListFades]);

  // Options: same data as Stock/ETF, filtered to plain equity symbols
  const equityOnly = useMemo(
    () => allTickers.filter(r => !r.symbol.includes(':') && !r.symbol.includes('/')),
    [allTickers],
  );
  const optionsFilteredTickers = useMemo(
    () => sidebarSymbolSearch.trim()
      ? filteredTickers.filter(r => !r.symbol.includes(':') && !r.symbol.includes('/'))
      : equityOnly,
    [sidebarSymbolSearch, filteredTickers, equityOnly],
  );

  // For options mode, absorb hook's continuous rebuilds into local state
  const [optionsBuiltTicker, setOptionsBuiltTicker] = useState('');
  const handleHookIdentifier = useCallback((id: string) => {
    if (sidebarFormMode === 'options') {
      setOptionsBuiltTicker(id);
    } else {
      setSidebarCustomIdentifier(id);
    }
  }, [sidebarFormMode, setSidebarCustomIdentifier]);

  const forexCryptoOptions = useForexCryptoOptions({
    formMode: sidebarFormMode,
    setFormCustomIdentifier: handleHookIdentifier,
    setFormParams: () => {},
  });

  const effectiveIdentifier = sidebarFormMode === 'options' ? optionsBuiltTicker : sidebarCustomIdentifier;

  // Options mode: select underlying ticker and close dropdown
  const handleOptionsUnderlyingSelect = useCallback((result: { symbol: string; name: string; exchange?: string }) => {
    forexCryptoOptions.setOptionsUnderlying(result.symbol);
    forexCryptoOptions.setOptionsUnderlyingSearch(result.symbol);
    setSidebarSymbolSearch('');
    setTickerDropdownOpen(false);
  }, [forexCryptoOptions]);

  const handleSidebarModeChange = useCallback((mode: FormMode) => {
    setSidebarFormMode(mode);
    setTickerDropdownOpen(false);
  }, [setSidebarFormMode]);

  // Options/forex/crypto confirm — append to chips
  const handleSidebarIdentifierConfirm = useCallback(() => {
    if (!effectiveIdentifier) return;
    const objectType = sidebarFormMode === 'options' ? 'options' : sidebarFormMode === 'forex' ? 'forex' : 'crypto';
    if (!currentSymbols.some(s => s.symbol === effectiveIdentifier)) {
      setObjects([...currentSymbols, { symbol: effectiveIdentifier, name: effectiveIdentifier, objectType }]);
    }
  }, [effectiveIdentifier, sidebarFormMode, setObjects, currentSymbols]);

  // Save/restore endpoint selection per object type so mode switches preserve state
  const savedEndpointStateRef = useRef<Record<string, {
    endpoint: any;
    fields: string[];
    params: Record<string, string>;
  }>>({});
  const prevObjectTypeRef = useRef<string | null>(null);

  // Reset refs when tab changes so state doesn't leak across tabs
  const activeTabId = useDataWorkspaceStore(s => s.activeTabId);
  const prevTabIdRef = useRef(activeTabId);
  useEffect(() => {
    if (activeTabId !== prevTabIdRef.current) {
      savedEndpointStateRef.current = {};
      prevObjectTypeRef.current = null;
      prevTabIdRef.current = activeTabId;
    }
  }, [activeTabId]);

  // Keep a ref to currentSymbols so the market auto-add effect can read them without re-triggering.
  const symbolsRef = useRef(currentSymbols);
  symbolsRef.current = currentSymbols;

  // Market mode auto-add: when switching to market mode, add _MARKET_ symbol.
  // Only runs when sidebarFormMode changes — not when symbols change — so users can remove the card.
  // Skipped when no tab exists to avoid auto-creating tabs from side effects.
  useEffect(() => {
    if (sidebarFormMode === 'market' && useDataWorkspaceStore.getState().activeTabId) {
      const syms = symbolsRef.current;
      const hasMarket = syms.some(s => s.symbol === '_MARKET_');
      if (!hasMarket) {
        setObjects([...syms, { symbol: '_MARKET_', name: 'Market Data', objectType: 'market' }]);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sidebarFormMode]);

  return (
    <>
      <div className="px-4 py-2" style={{ fontFamily: "var(--ss-font, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif)" }}>
        <div className="flex items-center gap-1">
          {SIDEBAR_MODES.map(({ mode, label }) => {
            const isActive = sidebarFormMode === mode;
            return (
              <button
                key={mode}
                onClick={() => handleSidebarModeChange(mode)}
                style={{
                  padding: '0.2rem 0.5rem',
                  fontSize: '0.563rem',
                  fontWeight: 500,
                  borderRadius: '0.375rem',
                  transition: 'all 0.1s ease',
                  border: isActive ? '0.5px solid hsl(30 3.3% 11.8% / 20%)' : '0.5px solid transparent',
                  backgroundColor: isActive ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                  color: isActive ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 40%)',
                  cursor: 'pointer',
                }}
                onMouseEnter={e => { if (!isActive) { e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 5%)'; e.currentTarget.style.color = 'hsl(60 2.5% 23.3% / 60%)'; } }}
                onMouseLeave={e => { if (!isActive) { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'hsl(60 2.5% 23.3% / 40%)'; } }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="px-4 pb-2 pt-1" style={{ fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif" }}>
        {sidebarFormMode === 'symbol' && (
          <TickerPicker
            mode="multi"
            selectedSymbols={currentSymbols
              .filter(s => s.objectType !== 'forex' && s.objectType !== 'crypto' && s.objectType !== 'market')
              .map(s => s.symbol)}
            onSelect={(t) => {
              if (!useDataWorkspaceStore.getState().activeTabId) {
                addTab('single', `${t.symbol} Data`);
              }
              const objectType = detectObjectType(t.symbol, t.exchange);
              if (!currentSymbols.some(s => s.symbol === t.symbol)) {
                setObjects([...currentSymbols, { symbol: t.symbol, name: t.name, objectType }]);
              }
            }}
            onRemove={(sym) => setObjects(currentSymbols.filter(cs => cs.symbol !== sym))}
            placeholder="Select tickers..."
            showChips={false}
          />
        )}

        {sidebarFormMode === 'options' && (
          <div ref={tickerDropdownRef} className="relative">
            {/* Dropdown trigger */}
            <button
              type="button"
              onClick={() => {
                const opening = !tickerDropdownOpen;
                setTickerDropdownOpen(opening);
                setSidebarSymbolSearch('');
                if (opening) {
                  forexCryptoOptions.setOptionsExpiryDropdownOpen(false);
                  setTimeout(() => tickerSearchInputRef.current?.focus(), 0);
                }
              }}
              style={{
                width: '100%',
                height: 30,
                padding: '0.3rem 0.625rem',
                fontSize: '0.688rem',
                fontWeight: 500,
                textAlign: 'left' as const,
                border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                borderRadius: '0.5rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                color: forexCryptoOptions.optionsUnderlying ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 35%)',
                backgroundColor: 'hsl(30 3.3% 11.8% / 3%)',
                cursor: 'pointer',
              }}
            >
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                {forexCryptoOptions.optionsUnderlying || 'Select ticker...'}
              </span>
              <svg
                style={{ width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', flexShrink: 0, transition: 'transform 0.15s ease', transform: tickerDropdownOpen ? 'rotate(180deg)' : 'none' }}
                fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Dropdown panel */}
            {tickerDropdownOpen && (
              <div
                className="absolute left-0 right-0 z-20 mt-1 flex flex-col"
                style={{
                  backgroundColor: 'white',
                  borderRadius: '0.75rem',
                  border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
                  height: 260,
                }}
              >
                {/* Search input */}
                <div className="px-3 pt-2 pb-1.5 flex-shrink-0">
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2" style={{ width: 12, height: 12, color: 'hsl(60 2.5% 23.3% / 35%)' }} />
                    <input
                      ref={tickerSearchInputRef}
                      type="text"
                      value={sidebarSymbolSearch}
                      onChange={e => setSidebarSymbolSearch(e.target.value)}
                      placeholder="Search..."
                      className="focus:outline-none"
                      style={{
                        width: '100%',
                        padding: '0.25rem 0.25rem 0.25rem 1.5rem',
                        fontSize: '0.625rem',
                        border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                        borderRadius: '0.375rem',
                        color: 'hsl(60 2.5% 23.3%)',
                      }}
                    />
                  </div>
                </div>

                {/* Ticker list */}
                <div className="relative flex-1 min-h-0" style={{ borderRadius: '0 0 0.75rem 0.75rem', overflow: 'hidden' }}>
                  {tickerListShowTopFade && (
                    <div className="pointer-events-none absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white to-transparent z-10" />
                  )}
                  {tickerListShowBottomFade && (
                    <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 z-10" style={{ borderRadius: '0 0 0.75rem 0.75rem', background: 'linear-gradient(to top, white, transparent)' }} />
                  )}
                  <TickerVirtualList
                    parentRef={tickerListRef}
                    onScroll={updateTickerListFades}
                    tickers={optionsFilteredTickers}
                    loading={tickersLoading}
                    selectedSymbols={forexCryptoOptions.optionsUnderlying ? [forexCryptoOptions.optionsUnderlying] : []}
                    onSelect={handleOptionsUnderlyingSelect}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {sidebarFormMode === 'market' && (
          <div className="text-[10px] text-slate-400 py-1">Market-wide data — no symbol needed</div>
        )}

        {sidebarFormMode === 'options' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem', marginTop: '0.125rem' }}>
            <OptionsContractBuilder
              optionsUnderlying={forexCryptoOptions.optionsUnderlying}
              optionsType={forexCryptoOptions.optionsType}
              onCloseOtherDropdowns={() => setTickerDropdownOpen(false)}
              onSetOptionsType={forexCryptoOptions.setOptionsType}
              optionsExpiry={forexCryptoOptions.optionsExpiry}
              onSetOptionsExpiry={forexCryptoOptions.setOptionsExpiry}
              optionsExpirations={forexCryptoOptions.optionsExpirations}
              loadingExpirations={forexCryptoOptions.loadingExpirations}
              optionsStrike={forexCryptoOptions.optionsStrike}
              onSetOptionsStrike={forexCryptoOptions.setOptionsStrike}
              optionsExpiryDropdownOpen={forexCryptoOptions.optionsExpiryDropdownOpen}
              onSetOptionsExpiryDropdownOpen={forexCryptoOptions.setOptionsExpiryDropdownOpen}
            />
            {effectiveIdentifier && forexCryptoOptions.isValidOptionsTicker(effectiveIdentifier) && (
              <button
                onClick={handleSidebarIdentifierConfirm}
                style={{
                  width: '100%',
                  marginTop: '0.375rem',
                  padding: '0.375rem 0.625rem',
                  fontSize: '0.688rem',
                  fontWeight: 500,
                  fontFamily: "system-ui, -apple-system, sans-serif",
                  borderRadius: '0.5rem',
                  border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
                  backgroundColor: 'hsl(30 3.3% 11.8% / 8%)',
                  color: 'hsl(60 2.5% 23.3%)',
                  cursor: 'pointer',
                }}
              >
                Add {effectiveIdentifier}
              </button>
            )}
          </div>
        )}

        {sidebarFormMode === 'forex' && (
          <div ref={tickerDropdownRef} className="relative">
            {/* Dropdown trigger */}
            <button
              type="button"
              onClick={() => {
                setTickerDropdownOpen(!tickerDropdownOpen);
                forexCryptoOptions.setForexSearch('');
                if (!tickerDropdownOpen) {
                  setTimeout(() => tickerSearchInputRef.current?.focus(), 0);
                }
              }}
              style={{
                width: '100%',
                padding: '0.325rem 0.5rem',
                fontSize: '0.688rem',
                fontWeight: 500,
                textAlign: 'left' as const,
                border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
                borderRadius: '0.5rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                color: currentSymbols.some(s => s.objectType === 'forex') ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 35%)',
                backgroundColor: 'white',
                cursor: 'pointer',
              }}
            >
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                {currentSymbols.filter(s => s.objectType === 'forex').length > 0
                  ? currentSymbols.filter(s => s.objectType === 'forex').map(s => s.symbol).join(', ')
                  : 'Select pairs...'}
              </span>
              <svg
                style={{ width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', flexShrink: 0, transition: 'transform 0.15s ease', transform: tickerDropdownOpen ? 'rotate(180deg)' : 'none' }}
                fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Chips moved to shared section below */}

            {/* Dropdown panel */}
            {tickerDropdownOpen && (
              <div
                className="absolute left-0 right-0 z-20 mt-1 flex flex-col"
                style={{
                  backgroundColor: 'white',
                  borderRadius: '0.75rem',
                  border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
                  height: 260,
                }}
              >
                <div className="px-3 pt-2 pb-1.5 flex-shrink-0">
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2" style={{ width: 12, height: 12, color: 'hsl(60 2.5% 23.3% / 35%)' }} />
                    <input
                      ref={tickerSearchInputRef}
                      type="text"
                      value={forexCryptoOptions.forexSearch}
                      onChange={e => forexCryptoOptions.setForexSearch(e.target.value.toUpperCase())}
                      placeholder="Search..."
                      className="focus:outline-none"
                      style={{
                        width: '100%',
                        padding: '0.25rem 0.25rem 0.25rem 1.5rem',
                        fontSize: '0.625rem',
                        border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                        borderRadius: '0.375rem',
                        color: 'hsl(60 2.5% 23.3%)',
                      }}
                    />
                  </div>
                </div>

                <div className="relative flex-1 min-h-0" style={{ borderRadius: '0 0 0.75rem 0.75rem', overflow: 'hidden' }}>
                  {tickerListShowTopFade && (
                    <div className="pointer-events-none absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white to-transparent z-10" />
                  )}
                  {tickerListShowBottomFade && (
                    <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 z-10" style={{ borderRadius: '0 0 0.75rem 0.75rem', background: 'linear-gradient(to top, white, transparent)' }} />
                  )}
                  <div
                    ref={tickerListRef}
                    onScroll={updateTickerListFades}
                    className="overflow-y-auto px-3 py-1.5 flex flex-col gap-0.5 h-full"
                  >
                    {forexCryptoOptions.loadingForexPairs ? (
                      <div className="flex items-center justify-center py-6">
                        <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-500 rounded-full animate-spin" />
                      </div>
                    ) : forexCryptoOptions.filteredForexPairs.length === 0 ? (
                      <p style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 30%)', textAlign: 'center', padding: '1rem 0' }}>
                        No pairs found
                      </p>
                    ) : (
                      forexCryptoOptions.filteredForexPairs.map((pair) => {
                        const alreadySelected = currentSymbols.some(s => s.symbol === pair);
                        return (
                          <button
                            key={pair}
                            onClick={() => {
                              if (!alreadySelected) {
                                setObjects([...currentSymbols, { symbol: pair, name: pair, objectType: 'forex' }]);
                              }
                            }}
                            style={{
                              width: '100%',
                              textAlign: 'left' as const,
                              padding: '0.3rem 0.5rem',
                              fontSize: '0.688rem',
                              borderRadius: '0.5rem',
                              border: 'none',
                              backgroundColor: alreadySelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                              opacity: alreadySelected ? 0.4 : 1,
                              color: 'hsl(60 2.5% 23.3% / 60%)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.375rem',
                              transition: 'background-color 0.1s ease',
                            }}
                            onMouseEnter={e => { if (!alreadySelected) e.currentTarget.style.backgroundColor = 'hsl(210 10% 87% / 50%)'; }}
                            onMouseLeave={e => { e.currentTarget.style.backgroundColor = alreadySelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent'; }}
                          >
                            <span style={{ fontWeight: 500, fontFamily: 'monospace', color: 'hsl(60 2.5% 23.3%)' }}>
                              <span style={{ color: 'hsl(60 2.5% 23.3% / 35%)' }}>{getCurrencySymbol(pair.slice(0, 3))}</span> {pair.slice(0, 3)}/{pair.slice(3)} <span style={{ color: 'hsl(60 2.5% 23.3% / 35%)' }}>{getCurrencySymbol(pair.slice(3))}</span>
                            </span>
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {sidebarFormMode === 'crypto' && (
          <div ref={tickerDropdownRef} className="relative">
            {/* Dropdown trigger */}
            <button
              type="button"
              onClick={() => {
                setTickerDropdownOpen(!tickerDropdownOpen);
                forexCryptoOptions.setCryptoSearch('');
                if (!tickerDropdownOpen) {
                  setTimeout(() => tickerSearchInputRef.current?.focus(), 0);
                }
              }}
              style={{
                width: '100%',
                padding: '0.325rem 0.5rem',
                fontSize: '0.688rem',
                fontWeight: 500,
                textAlign: 'left' as const,
                border: '0.5px solid hsl(30 3.3% 11.8% / 20%)',
                borderRadius: '0.5rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                color: currentSymbols.some(s => s.objectType === 'crypto') ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 35%)',
                backgroundColor: 'white',
                cursor: 'pointer',
              }}
            >
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                {currentSymbols.filter(s => s.objectType === 'crypto').length > 0
                  ? currentSymbols.filter(s => s.objectType === 'crypto').map(s => s.symbol.replace('USD', '/USD')).join(', ')
                  : 'Select pairs...'}
              </span>
              <svg
                style={{ width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', flexShrink: 0, transition: 'transform 0.15s ease', transform: tickerDropdownOpen ? 'rotate(180deg)' : 'none' }}
                fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Chips moved to shared section below */}

            {/* Dropdown panel */}
            {tickerDropdownOpen && (
              <div
                className="absolute left-0 right-0 z-20 mt-1 flex flex-col"
                style={{
                  backgroundColor: 'white',
                  borderRadius: '0.75rem',
                  border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
                  height: 260,
                }}
              >
                <div className="px-3 pt-2 pb-1.5 flex-shrink-0">
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2" style={{ width: 12, height: 12, color: 'hsl(60 2.5% 23.3% / 35%)' }} />
                    <input
                      ref={tickerSearchInputRef}
                      type="text"
                      value={forexCryptoOptions.cryptoSearch}
                      onChange={e => forexCryptoOptions.setCryptoSearch(e.target.value.toUpperCase())}
                      placeholder="Search..."
                      className="focus:outline-none"
                      style={{
                        width: '100%',
                        padding: '0.25rem 0.25rem 0.25rem 1.5rem',
                        fontSize: '0.625rem',
                        border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                        borderRadius: '0.375rem',
                        color: 'hsl(60 2.5% 23.3%)',
                      }}
                    />
                  </div>
                </div>

                <div className="relative flex-1 min-h-0" style={{ borderRadius: '0 0 0.75rem 0.75rem', overflow: 'hidden' }}>
                  {tickerListShowTopFade && (
                    <div className="pointer-events-none absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white to-transparent z-10" />
                  )}
                  {tickerListShowBottomFade && (
                    <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 z-10" style={{ borderRadius: '0 0 0.75rem 0.75rem', background: 'linear-gradient(to top, white, transparent)' }} />
                  )}
                  <div
                    ref={tickerListRef}
                    onScroll={updateTickerListFades}
                    className="overflow-y-auto px-3 py-1.5 flex flex-col gap-0.5 h-full"
                  >
                    {forexCryptoOptions.loadingCryptoPairs ? (
                      <div className="flex items-center justify-center py-6">
                        <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-500 rounded-full animate-spin" />
                      </div>
                    ) : forexCryptoOptions.filteredCryptoPairs.length === 0 ? (
                      <p style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 30%)', textAlign: 'center', padding: '1rem 0' }}>
                        No pairs found
                      </p>
                    ) : (
                      forexCryptoOptions.filteredCryptoPairs.map((pair) => {
                        const alreadySelected = currentSymbols.some(s => s.symbol === pair);
                        return (
                          <button
                            key={pair}
                            onClick={() => {
                              if (!alreadySelected) {
                                setObjects([...currentSymbols, { symbol: pair, name: pair.replace('USD', ''), objectType: 'crypto' }]);
                              }
                            }}
                            style={{
                              width: '100%',
                              textAlign: 'left' as const,
                              padding: '0.3rem 0.5rem',
                              fontSize: '0.688rem',
                              borderRadius: '0.5rem',
                              border: 'none',
                              backgroundColor: alreadySelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                              opacity: alreadySelected ? 0.4 : 1,
                              color: 'hsl(60 2.5% 23.3% / 60%)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.375rem',
                              transition: 'background-color 0.1s ease',
                            }}
                            onMouseEnter={e => { if (!alreadySelected) e.currentTarget.style.backgroundColor = 'hsl(210 10% 87% / 50%)'; }}
                            onMouseLeave={e => { e.currentTarget.style.backgroundColor = alreadySelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent'; }}
                          >
                            <img
                              src={getCryptoIconUrl(pair.replace('USD', ''))}
                              data-fallback={getCryptoFallbackUrl(pair.replace('USD', ''))}
                              alt=""
                              className="opacity-30"
                              style={{ width: 14, height: 14, objectFit: 'contain', flexShrink: 0 }}
                              onError={handleCryptoImgError}
                            />
                            <span style={{ fontWeight: 500, fontFamily: 'monospace', color: 'hsl(60 2.5% 23.3%)' }}>
                              {pair.replace('USD', '')}/USD
                            </span>
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        {/* Shared selected ticker chips — always visible regardless of mode */}
        {currentSymbols.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {currentSymbols.map(s => {
              let displayLabel = s.symbol;
              if (s.objectType === 'forex') {
                displayLabel = `${s.symbol.slice(0, 3)}/${s.symbol.slice(3)}`;
              } else if (s.objectType === 'crypto') {
                displayLabel = s.symbol.replace('USD', '/USD');
              }
              return (
                <span
                  key={s.symbol}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                    padding: '0.2rem 0.5rem',
                    backgroundColor: 'hsl(30 3.3% 11.8% / 6%)',
                    border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
                    borderRadius: '0.375rem',
                    fontSize: '0.625rem',
                    fontFamily: "'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace",
                    fontWeight: 600,
                    color: 'hsl(60 2.5% 23.3%)',
                  }}
                >
                  {displayLabel}
                  <button
                    onClick={() => setObjects(currentSymbols.filter(cs => cs.symbol !== s.symbol))}
                    style={{ color: 'hsl(60 2.5% 23.3% / 30%)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', padding: 0 }}
                  >
                    <X className="w-2.5 h-2.5" />
                  </button>
                </span>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
