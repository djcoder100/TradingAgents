import { Loader2 } from 'lucide-react';
import { useAnalysisStore } from '../../stores/analysisStore';

export default function TopBar() {
  const { isRunning, taskStatus } = useAnalysisStore();

  return (
    <header className="h-14 border-b border-trading-border bg-trading-bg/80 backdrop-blur-sm flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        <span className="text-sm text-trading-textdim">
          BRV Trading — Multi-Agent Analysis
        </span>
      </div>

      <div className="flex items-center gap-4">
        {isRunning && taskStatus && (
          <div className="flex items-center gap-2 bg-trading-emerald/10 text-trading-emerald px-3 py-1 rounded-full text-xs">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>
              {taskStatus.progress.reports_completed}/{taskStatus.progress.reports_total} reports
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
