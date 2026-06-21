import { useAnalysisStore } from '../../stores/analysisStore';

export default function ProviderConfigSection() {
  const { form, setForm } = useAnalysisStore();
  const provider = form.llm_provider;

  if (provider === 'openai') {
    return (
      <div>
        <label className="block text-xs font-medium text-trading-textdim mb-1.5">
          OpenAI Reasoning Effort
        </label>
        <div className="grid grid-cols-3 gap-2">
          {[
            { key: 'low', label: 'Low' },
            { key: 'medium', label: 'Medium' },
            { key: 'high', label: 'High' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setForm({ openai_reasoning_effort: key })}
              className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all cursor-pointer ${
                form.openai_reasoning_effort === key
                  ? 'bg-trading-emerald/10 border-trading-emerald text-trading-emerald'
                  : 'bg-trading-surface border-trading-border text-trading-textdim hover:border-trading-textdim'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (provider === 'google') {
    return (
      <div>
        <label className="block text-xs font-medium text-trading-textdim mb-1.5">
          Gemini Thinking Level
        </label>
        <div className="grid grid-cols-2 gap-2">
          {[
            { key: 'high', label: 'Enable Thinking' },
            { key: 'minimal', label: 'Minimal' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setForm({ google_thinking_level: key })}
              className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all cursor-pointer ${
                form.google_thinking_level === key
                  ? 'bg-trading-emerald/10 border-trading-emerald text-trading-emerald'
                  : 'bg-trading-surface border-trading-border text-trading-textdim hover:border-trading-textdim'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (provider === 'anthropic' || provider === 'anthropic-cn') {
    return (
      <div>
        <label className="block text-xs font-medium text-trading-textdim mb-1.5">
          Anthropic Effort Level
        </label>
        <div className="grid grid-cols-3 gap-2">
          {[
            { key: 'low', label: 'Low' },
            { key: 'medium', label: 'Medium' },
            { key: 'high', label: 'High' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setForm({ anthropic_effort: key })}
              className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all cursor-pointer ${
                form.anthropic_effort === key
                  ? 'bg-trading-emerald/10 border-trading-emerald text-trading-emerald'
                  : 'bg-trading-surface border-trading-border text-trading-textdim hover:border-trading-textdim'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return null;
}
