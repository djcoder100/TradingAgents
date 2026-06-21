import { useEffect, useState, useCallback } from 'react';
import { useAnalysisStore } from '../../stores/analysisStore';
import { useConfigStore } from '../../stores/configStore';

export default function LLMProviderSelector() {
  const { form, setForm } = useAnalysisStore();
  const config = useConfigStore((s) => s.config);
  const loadModels = useConfigStore((s) => s.loadModels);
  const getModels = useConfigStore((s) => s.getModels);
  const [selectedRegion, setSelectedRegion] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);

  const providers = config?.available_providers || [];
  const currentProvider = providers.find((p) => p.key === form.llm_provider);

  const handleProviderChange = useCallback(async (key: string) => {
    const provider = providers.find((p) => p.key === key);
    const newBackendUrl = provider?.default_url || null;

    // Set provider first
    setForm({
      llm_provider: key,
      backend_url: newBackendUrl,
      google_thinking_level: null,
      openai_reasoning_effort: null,
      anthropic_effort: null,
    });

    // Load models, then set defaults for this provider
    setLoadingModels(true);
    try {
      await useConfigStore.getState().loadModels(key);
      // Small delay to ensure store is updated
      await new Promise(r => setTimeout(r, 50));
      const quickModels = useConfigStore.getState().getModels(key, 'quick');
      const deepModels = useConfigStore.getState().getModels(key, 'deep');

      if (quickModels.length > 0) {
        // Pick the first non-custom entry as default
        const defaultQuick = quickModels.find(m => m.value !== 'custom')?.value || quickModels[0].value;
        const defaultDeep = deepModels.find(m => m.value !== 'custom')?.value || deepModels[0].value;
        setForm({ quick_think_llm: defaultQuick, deep_think_llm: defaultDeep });
      }
    } catch {
      // Keep current models if loading fails
    } finally {
      setLoadingModels(false);
    }

    setSelectedRegion(false);
  }, [providers, setForm]);

  const handleRegionChange = useCallback(async (regionKey: string, url: string) => {
    setForm({ llm_provider: regionKey, backend_url: url });

    setLoadingModels(true);
    try {
      await useConfigStore.getState().loadModels(regionKey);
      await new Promise(r => setTimeout(r, 50));
      const quickModels = useConfigStore.getState().getModels(regionKey, 'quick');
      const deepModels = useConfigStore.getState().getModels(regionKey, 'deep');
      if (quickModels.length > 0) {
        const defaultQuick = quickModels.find(m => m.value !== 'custom')?.value || quickModels[0].value;
        const defaultDeep = deepModels.find(m => m.value !== 'custom')?.value || deepModels[0].value;
        setForm({ quick_think_llm: defaultQuick, deep_think_llm: defaultDeep });
      }
    } catch {
      // Keep current models
    } finally {
      setLoadingModels(false);
    }

    setSelectedRegion(true);
  }, [setForm]);

  // Load models for initial provider
  useEffect(() => {
    if (form.llm_provider) {
      loadModels(form.llm_provider);
    }
  }, []);

  // Auto-fix models when provider changes externally (e.g., page load)
  useEffect(() => {
    if (!loadingModels && form.llm_provider) {
      const quickModels = getModels(form.llm_provider, 'quick');
      const deepModels = getModels(form.llm_provider, 'deep');
      if (quickModels.length > 0 && deepModels.length > 0) {
        const quickValid = quickModels.some(m => m.value === form.quick_think_llm);
        const deepValid = deepModels.some(m => m.value === form.deep_think_llm);
        if (!quickValid || !deepValid) {
          const defaultQuick = quickModels.find(m => m.value !== 'custom')?.value || quickModels[0].value;
          const defaultDeep = deepModels.find(m => m.value !== 'custom')?.value || deepModels[0].value;
          setForm({ quick_think_llm: defaultQuick, deep_think_llm: defaultDeep });
        }
      }
    }
  }, [form.llm_provider, loadingModels]);

  return (
    <div className="space-y-3">
      <label className="block text-xs font-medium text-trading-textdim">
        LLM Provider
      </label>

      {/* Provider grid */}
      <div className="grid grid-cols-3 gap-2">
        {providers
          .filter((p) => !p.has_regions || !selectedRegion)
          .map((p) => (
            <button
              key={p.key}
              onClick={() => handleProviderChange(p.key)}
              disabled={loadingModels}
              className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all cursor-pointer disabled:opacity-50 ${
                form.llm_provider === p.key
                  ? 'bg-trading-emerald/10 border-trading-emerald text-trading-emerald'
                  : 'bg-trading-surface border-trading-border text-trading-textdim hover:border-trading-textdim'
              }`}
            >
              {p.display_name}
            </button>
          ))}
      </div>

      {/* Region picker for multi-region providers */}
      {currentProvider?.has_regions && currentProvider.regions.length > 0 && (
        <div className="space-y-2 pl-1 border-l-2 border-trading-border">
          <p className="text-xs text-trading-textdim">Select region:</p>
          {currentProvider.regions.map((r) => (
            <button
              key={r.key}
              onClick={() => handleRegionChange(r.key, r.url)}
              disabled={loadingModels}
              className={`block w-full text-left px-3 py-1.5 rounded text-xs transition-colors cursor-pointer disabled:opacity-50 ${
                form.llm_provider === r.key
                  ? 'bg-trading-emerald/10 text-trading-emerald'
                  : 'text-trading-textdim hover:text-trading-text'
              }`}
            >
              {r.display_name.split('(')[0].trim()}
            </button>
          ))}
        </div>
      )}

      {loadingModels && (
        <p className="text-xs text-trading-textdim">Loading models...</p>
      )}
    </div>
  );
}
