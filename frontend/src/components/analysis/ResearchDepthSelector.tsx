import { useAnalysisStore } from '../../stores/analysisStore';
import { useConfigStore } from '../../stores/configStore';

export default function ResearchDepthSelector() {
  const { form, setForm } = useAnalysisStore();
  const config = useConfigStore((s) => s.config);

  const depths = config?.research_depths || [];

  return (
    <div>
      <label className="block text-xs font-medium text-trading-textdim mb-1.5">
        Research Depth
      </label>
      <div className="grid grid-cols-3 gap-2">
        {depths.map((d) => (
          <button
            key={d.value}
            onClick={() => setForm({ research_depth: d.value })}
            className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all cursor-pointer ${
              form.research_depth === d.value
                ? 'bg-trading-emerald/10 border-trading-emerald text-trading-emerald'
                : 'bg-trading-surface border-trading-border text-trading-textdim hover:border-trading-textdim'
            }`}
          >
            {d.label.split(' - ')[0]}
          </button>
        ))}
      </div>
    </div>
  );
}
