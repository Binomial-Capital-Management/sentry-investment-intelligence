import { useEffect, useMemo } from 'react';
import { useTickerUniverseStore, type TickerEntry } from '@/stores/tickerUniverseStore';

interface UseTickerSearchOptions {
  limit?: number;
  excludeSymbols?: string[];
}

interface UseTickerSearchResult {
  results: TickerEntry[];
  isLoading: boolean;
  error: string | null;
}

function bigrams(s: string): Set<string> {
  const set = new Set<string>();
  for (let i = 0; i < s.length - 1; i++) {
    set.add(s.substring(i, i + 2));
  }
  return set;
}

function bigramSimilarity(a: string, b: string): number {
  const setA = bigrams(a);
  const setB = bigrams(b);
  if (setA.size === 0 || setB.size === 0) return 0;
  let intersection = 0;
  for (const bg of setB) {
    if (setA.has(bg)) intersection++;
  }
  return intersection / Math.max(setA.size, setB.size);
}

function scoreTicker(ticker: TickerEntry, query: string): number {
  const q = query.toUpperCase();
  const sym = ticker.symbol.toUpperCase();
  const name = ticker.name.toUpperCase();

  if (sym === q) return 1000;
  if (sym.startsWith(q)) return 500 + (q.length / sym.length) * 100;

  let score = 0;
  if (sym.includes(q)) score += 200;
  if (name.includes(q)) score += 100;

  if (score === 0) {
    score = bigramSimilarity(sym, q) * 50 + bigramSimilarity(name, q) * 50;
    if (score < 5) return 0;
  }

  return score;
}

export function searchTickerList(
  tickers: TickerEntry[],
  query: string,
  options?: UseTickerSearchOptions,
): TickerEntry[] {
  const q = query.trim();
  if (!q) return [];

  const limit = options?.limit ?? 15;
  const excludeSet = options?.excludeSymbols
    ? new Set(options.excludeSymbols.map(s => s.toUpperCase()))
    : null;

  const scored: { ticker: TickerEntry; score: number }[] = [];

  for (const ticker of tickers) {
    if (excludeSet?.has(ticker.symbol.toUpperCase())) continue;
    const score = scoreTicker(ticker, q);
    if (score > 0) scored.push({ ticker, score });
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit).map(s => s.ticker);
}

export function useTickerSearch(
  query: string,
  options?: UseTickerSearchOptions,
): UseTickerSearchResult {
  const tickers = useTickerUniverseStore(s => s.tickers);
  const isLoading = useTickerUniverseStore(s => s.isLoading);
  const error = useTickerUniverseStore(s => s.error);
  const fetchTickers = useTickerUniverseStore(s => s.fetchTickers);

  useEffect(() => {
    fetchTickers();
  }, [fetchTickers]);

  const results = useMemo(
    () => searchTickerList(tickers, query, options),
    [tickers, query, options?.limit, options?.excludeSymbols],
  );

  return { results, isLoading, error };
}
