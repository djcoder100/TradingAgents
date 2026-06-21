import { create } from 'zustand';
import type { AppConfig, ProviderInfo, ModelOption } from '../types/api';
import { fetchConfig, fetchProviderModels } from '../api/client';

interface ConfigStore {
  config: AppConfig | null;
  isLoading: boolean;
  error: string | null;

  // Cached models per provider
  modelCache: Record<string, { quick: ModelOption[]; deep: ModelOption[] }>;

  loadConfig: () => Promise<void>;
  loadModels: (providerKey: string) => Promise<void>;
  getModels: (providerKey: string, mode: 'quick' | 'deep') => ModelOption[];
  getProvider: (key: string) => ProviderInfo | undefined;
}

export const useConfigStore = create<ConfigStore>((set, get) => ({
  config: null,
  isLoading: false,
  error: null,
  modelCache: {},

  loadConfig: async () => {
    set({ isLoading: true, error: null });
    try {
      const config = await fetchConfig();
      set({ config, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  loadModels: async (providerKey: string) => {
    const cache = get().modelCache;
    if (cache[providerKey]) return;

    try {
      const [quick, deep] = await Promise.all([
        fetchProviderModels(providerKey, 'quick'),
        fetchProviderModels(providerKey, 'deep'),
      ]);
      set({
        modelCache: {
          ...cache,
          [providerKey]: {
            quick: quick.models,
            deep: deep.models,
          },
        },
      });
    } catch {
      // Silently fail — models will be empty
    }
  },

  getModels: (providerKey: string, mode: 'quick' | 'deep') => {
    const cache = get().modelCache[providerKey];
    if (!cache) return [];
    return mode === 'quick' ? cache.quick : cache.deep;
  },

  getProvider: (key: string) => {
    const config = get().config;
    if (!config) return undefined;
    return config.available_providers.find(
      (p) => p.key === key || p.regions.some((r) => r.key === key)
    );
  },
}));
