import { useAnalysisStore } from '../../stores/analysisStore';
import { useConfigStore } from '../../stores/configStore';

export default function AnalystSelector() {
  const { form, setForm } = useAnalysisStore();
  const config = useConfigStore((s) => s.config);

  const isCrypto = form.ticker.toUpperCase().endsWith('-USD') ||
    form.ticker.toUpperCase().endsWith('-USDT') ||
    form.ticker.toUpperCase().endsWith('-USDC') ||
    form.ticker.toUpperCase().endsWith('-BTC') ||
    form.ticker.toUpperCase().endsWith('-ETH');

  const analysts = config?.analysts || [];

  const toggle = (key: string) => {
    const current = form.analysts;
    if (current.includes(key)) {
      if (current.length <= 1) return; // minimum 1
      setForm({ analysts: current.filter((a) => a !== key) });
    } else {
      setForm({ analysts: [...current, key] });
    }
  };

  return (
    <div>
      <label className="block text-xs font-medium text-trading-textdim mb-1.5">
        Analyst Team
      </label>
      <div className="grid grid-cols-2 gap-2">
        {analysts
          .filter((a) => !isCrypto || a.available_for_crypto)
          .map((a) => {
            const selected = form.analysts.includes(a.key);
            const disabled = !a.available_for_crypto && isCrypto;
            return (
              <button
                key={a.key}
                onClick={() => toggle(a.key)}
                disabled={disabled}
                className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
                  selected
                    ? 'bg-trading-emerald/10 border-trading-emerald text-trading-emerald'
                    : 'bg-trading-surface border-trading-border text-trading-textdim hover:border-trading-textdim'
                } ${disabled ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                {a.label}
              </button>
            );
          })}
      </div>
    </div>
  );
}
