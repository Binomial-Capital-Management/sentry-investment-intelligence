import { create } from 'zustand';
import api from '@/services/api';

export interface TickerEntry {
  symbol: string;
  name: string;
  exchange: string;
}

interface TickerUniverseStore {
  tickers: TickerEntry[];
  isLoading: boolean;
  isLoaded: boolean;
  error: string | null;
  fetchTickers: () => Promise<void>;
}

export const useTickerUniverseStore = create<TickerUniverseStore>((set, get) => ({
  tickers: [],
  isLoading: false,
  isLoaded: false,
  error: null,

  fetchTickers: async () => {
    const { isLoaded, isLoading } = get();
    if (isLoaded || isLoading) return;

    set({ isLoading: true, error: null });
    try {
      const res = await api.get('/api/ticker-search/universe');
      set({ tickers: res.data.tickers, isLoaded: true, isLoading: false });
    } catch (e: any) {
      set({ error: e.message || 'Failed to fetch tickers', isLoading: false });
    }
  },
}));
