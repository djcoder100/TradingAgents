import { useAnalysisStore } from '../../stores/analysisStore';
import { useConfigStore } from '../../stores/configStore';

export default function LanguageSelector() {
  const { form, setForm } = useAnalysisStore();
  const config = useConfigStore((s) => s.config);

  const languages = config?.output_languages || [];

  return (
    <div>
      <label className="block text-xs font-medium text-trading-textdim mb-1.5">
        Output Language
      </label>
      <select
        value={form.output_language}
        onChange={(e) => setForm({ output_language: e.target.value })}
        className="w-full bg-trading-surface border border-trading-border rounded-lg px-3 py-2 text-sm text-trading-text focus:outline-none focus:border-trading-emerald transition-colors"
      >
        {languages.map((l) => (
          <option key={l.value} value={l.value}>
            {l.label}
          </option>
        ))}
      </select>
    </div>
  );
}
