import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Search, X } from 'lucide-react';
import { useTickerSearch } from '@/hooks/useTickerSearch';
import { useTickerUniverseStore, type TickerEntry } from '@/stores/tickerUniverseStore';

const ROW_HEIGHT = 32;
const ROW_INSET = 2;

interface TickerVirtualListProps {
  parentRef: React.RefObject<HTMLDivElement>;
  onScroll: () => void;
  tickers: TickerEntry[];
  loading: boolean;
  selectedSymbols: string[];
  onSelect: (ticker: TickerEntry) => void;
}

export function TickerVirtualList({
  parentRef,
  onScroll,
  tickers,
  loading,
  selectedSymbols,
  onSelect,
}: TickerVirtualListProps) {
  const virtualizer = useVirtualizer({
    count: tickers.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 15,
  });

  if (loading) {
    return (
      <div ref={parentRef} className="overflow-y-auto h-full">
        <div className="flex items-center justify-center py-6">
          <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-500 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (tickers.length === 0) {
    return (
      <div ref={parentRef} className="overflow-y-auto h-full">
        <p style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 30%)', textAlign: 'center', padding: '1rem 0' }}>
          No tickers found
        </p>
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      onScroll={onScroll}
      className="overflow-y-auto px-3 py-1.5 h-full"
    >
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const r = tickers[virtualRow.index];
          const alreadySelected = selectedSymbols.includes(r.symbol);
          return (
            <button
              key={r.symbol}
              onClick={() => onSelect(r)}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: virtualRow.size - ROW_INSET * 2,
                transform: `translateY(${virtualRow.start + ROW_INSET}px)`,
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
                justifyContent: 'space-between',
                gap: '0.5rem',
              }}
              onMouseEnter={e => { if (!alreadySelected) e.currentTarget.style.backgroundColor = 'hsl(210 10% 87% / 50%)'; }}
              onMouseLeave={e => { e.currentTarget.style.backgroundColor = alreadySelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent'; }}
            >
              <span style={{ fontWeight: 500, fontFamily: 'monospace', color: 'hsl(60 2.5% 23.3%)' }}>{r.symbol}</span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, fontSize: '0.563rem', color: 'hsl(60 2.5% 23.3% / 35%)' }}>
                {r.name}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export interface TickerPickerProps {
  mode: 'single' | 'multi';
  selectedSymbols: string[];
  onSelect: (ticker: TickerEntry) => void;
  onRemove?: (symbol: string) => void;
  placeholder?: string;
  maxTickers?: number;
  disabled?: boolean;
  showChips?: boolean;
}

export function TickerPicker({
  mode,
  selectedSymbols,
  onSelect,
  onRemove,
  placeholder,
  maxTickers,
  disabled,
  showChips,
}: TickerPickerProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [showTopFade, setShowTopFade] = useState(false);
  const [showBottomFade, setShowBottomFade] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const allTickers = useTickerUniverseStore(s => s.tickers);
  const fetchTickers = useTickerUniverseStore(s => s.fetchTickers);
  const isLoading = useTickerUniverseStore(s => s.isLoading);
  const { results: filteredTickers } = useTickerSearch(search, { limit: Infinity });

  useEffect(() => { fetchTickers(); }, [fetchTickers]);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const updateFades = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    setShowTopFade(el.scrollTop > 2);
    setShowBottomFade(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
  }, []);

  const displayedTickers = useMemo(
    () => (search.trim() ? filteredTickers : allTickers),
    [search, filteredTickers, allTickers],
  );

  useEffect(() => {
    requestAnimationFrame(updateFades);
  }, [displayedTickers, open, updateFades]);

  const handleTriggerClick = useCallback(() => {
    if (disabled) return;
    const opening = !open;
    setOpen(opening);
    setSearch('');
    if (opening) {
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open, disabled]);

  const atCap = mode === 'multi' && maxTickers != null && selectedSymbols.length >= maxTickers;

  const handleSelect = useCallback((ticker: TickerEntry) => {
    if (mode === 'single') {
      onSelect(ticker);
      setOpen(false);
      setSearch('');
      return;
    }
    if (selectedSymbols.includes(ticker.symbol)) return;
    if (atCap) return;
    onSelect(ticker);
    setSearch('');
  }, [mode, onSelect, selectedSymbols, atCap]);

  const triggerPlaceholder = placeholder ?? (mode === 'single' ? 'Select ticker...' : 'Select tickers...');
  const triggerLabel = selectedSymbols.length > 0 ? selectedSymbols.join(', ') : triggerPlaceholder;
  const triggerHasValue = selectedSymbols.length > 0;

  const shouldShowChips = (showChips ?? mode === 'multi') && mode === 'multi' && selectedSymbols.length > 0;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={handleTriggerClick}
        disabled={disabled}
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
          color: triggerHasValue ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 35%)',
          backgroundColor: 'white',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
          {triggerLabel}
        </span>
        <svg
          style={{ width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', flexShrink: 0, transition: 'transform 0.15s ease', transform: open ? 'rotate(180deg)' : 'none' }}
          fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
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
                ref={inputRef}
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
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
            {showTopFade && (
              <div className="pointer-events-none absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white to-transparent z-10" />
            )}
            {showBottomFade && (
              <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 z-10" style={{ borderRadius: '0 0 0.75rem 0.75rem', background: 'linear-gradient(to top, white, transparent)' }} />
            )}
            <TickerVirtualList
              parentRef={listRef}
              onScroll={updateFades}
              tickers={displayedTickers}
              loading={isLoading}
              selectedSymbols={selectedSymbols}
              onSelect={handleSelect}
            />
          </div>
        </div>
      )}

      {shouldShowChips && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {selectedSymbols.map(sym => (
            <span
              key={sym}
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
              {sym}
              {onRemove && (
                <button
                  onClick={() => onRemove(sym)}
                  style={{ color: 'hsl(60 2.5% 23.3% / 30%)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', padding: 0 }}
                >
                  <X className="w-2.5 h-2.5" />
                </button>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
