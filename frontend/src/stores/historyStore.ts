import { create } from 'zustand';
import type { HistoryRun, MemoryEntry } from '../types/api';
import { fetchHistory, fetchTickers, fetchMemoryLog } from '../api/client';

interface HistoryStore {
  runs: HistoryRun[];
  tickers: string[];
  memoryEntries: MemoryEntry[];
  total: number;
  isLoading: boolean;
  error: string | null;

  // Filters
  filterTicker: string | null;
  filterSignal: string | null;

  loadHistory: (params?: { ticker?: string; offset?: number; limit?: number }) => Promise<void>;
  loadTickers: () => Promise<void>;
  loadMemoryLog: () => Promise<void>;
  setFilterTicker: (ticker: string | null) => void;
  setFilterSignal: (signal: string | null) => void;
}

export const useHistoryStore = create<HistoryStore>((set, get) => ({
  runs: [],
  tickers: [],
  memoryEntries: [],
  total: 0,
  isLoading: false,
  error: null,
  filterTicker: null,
  filterSignal: null,

  loadHistory: async (params) => {
    set({ isLoading: true, error: null });
    try {
      const result = await fetchHistory({
        ticker: params?.ticker || get().filterTicker || undefined,
        offset: params?.offset || 0,
        limit: params?.limit || 50,
      });
      set({ runs: result.items, total: result.total, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  loadTickers: async () => {
    try {
      const result = await fetchTickers();
      set({ tickers: result.tickers });
    } catch {}
  },

  loadMemoryLog: async () => {
    try {
      const result = await fetchMemoryLog();
      set({ memoryEntries: result.entries });
    } catch {}
  },

  setFilterTicker: (ticker) => set({ filterTicker: ticker }),
  setFilterSignal: (signal) => set({ filterSignal: signal }),
}));
