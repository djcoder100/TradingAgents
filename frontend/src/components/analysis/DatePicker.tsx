import { useAnalysisStore } from '../../stores/analysisStore';

export default function DatePicker() {
  const { form, setForm } = useAnalysisStore();

  return (
    <div>
      <label className="block text-xs font-medium text-trading-textdim mb-1.5">
        Analysis Date
      </label>
      <input
        type="date"
        value={form.analysis_date}
        onChange={(e) => setForm({ analysis_date: e.target.value })}
        max={new Date().toISOString().slice(0, 10)}
        className="w-full bg-trading-surface border border-trading-border rounded-lg px-3 py-2 text-sm text-trading-text focus:outline-none focus:border-trading-emerald transition-colors [color-scheme:dark]"
      />
    </div>
  );
}
