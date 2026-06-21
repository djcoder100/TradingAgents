import { useEffect } from 'react';
import { useAnalysisStore } from '../../stores/analysisStore';
import { useConfigStore } from '../../stores/configStore';

interface Props {
  mode: 'quick' | 'deep';
}

export default function ModelSelector({ mode }: Props) {
  const { form, setForm } = useAnalysisStore();
  const getModels = useConfigStore((s) => s.getModels);
  const loadModels = useConfigStore((s) => s.loadModels);

  const models = getModels(form.llm_provider, mode);
  const currentValue = mode === 'quick' ? form.quick_think_llm : form.deep_think_llm;

  useEffect(() => {
    // Ensure models are loaded for the current provider
    if (form.llm_provider) {
      loadModels(form.llm_provider);
    }
  }, [form.llm_provider, loadModels]);

  const handleChange = (value: string) => {
    if (value === 'custom') {
      // Switch to custom — keep current value so user can type in the input
    }
    if (mode === 'quick') {
      setForm({ quick_think_llm: value });
    } else {
      setForm({ deep_think_llm: value });
    }
  };

  // Check if current value is actually in the loaded models list
  const currentValueValid = models.length === 0 || models.some(m => m.value === currentValue) || currentValue === '';

  if (models.length === 0) {
    return (
      <div>
        <label className="block text-xs font-medium text-trading-textdim mb-1.5">
          {mode === 'quick' ? 'Quick-Thinking Model' : 'Deep-Thinking Model'}
        </label>
        <div className="w-full bg-trading-surface border border-trading-border rounded-lg px-3 py-2 text-sm text-trading-textdim">
          Loading...
        </div>
      </div>
    );
  }

  return (
    <div>
      <label className="block text-xs font-medium text-trading-textdim mb-1.5">
        {mode === 'quick' ? 'Quick-Thinking Model' : 'Deep-Thinking Model'}
      </label>
      <select
        value={currentValueValid ? currentValue : models[0]?.value || ''}
        onChange={(e) => handleChange(e.target.value)}
        className="w-full bg-trading-surface border border-trading-border rounded-lg px-3 py-2 text-sm text-trading-text focus:outline-none focus:border-trading-emerald transition-colors"
      >
        {!currentValueValid && (
          <option value="" disabled>Select a model...</option>
        )}
        {models.map((m) => (
          <option key={m.value} value={m.value}>
            {m.display}
          </option>
        ))}
      </select>

      {/* Show warning if current value isn't valid (e.g., after provider switch) */}
      {!currentValueValid && currentValue !== '' && (
        <p className="text-xs text-trading-amber mt-1">
          Model "{currentValue}" is not available for {form.llm_provider}. Please select one above.
        </p>
      )}

      {/* Custom model ID input */}
      {currentValue === 'custom' && (
        <input
          type="text"
          placeholder="Enter custom model ID..."
          className="w-full mt-2 bg-trading-surface border border-trading-border rounded-lg px-3 py-2 text-sm text-trading-text focus:outline-none focus:border-trading-emerald transition-colors"
          onChange={(e) => {
            const val = e.target.value;
            if (mode === 'quick') setForm({ quick_think_llm: val });
            else setForm({ deep_think_llm: val });
          }}
        />
      )}
    </div>
  );
}
