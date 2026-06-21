import { useState } from 'react';
import { Play, RotateCcw, Clock } from 'lucide-react';
import { useAnalysisStore } from '../stores/analysisStore';
import { useSubmitAnalysis, useAnalysisStream, useCancelAnalysis } from '../hooks/useAnalysis';
import TickerInput from '../components/analysis/TickerInput';
import DatePicker from '../components/analysis/DatePicker';
import LanguageSelector from '../components/analysis/LanguageSelector';
import AnalystSelector from '../components/analysis/AnalystSelector';
import ResearchDepthSelector from '../components/analysis/ResearchDepthSelector';
import LLMProviderSelector from '../components/analysis/LLMProviderSelector';
import ModelSelector from '../components/analysis/ModelSelector';
import ProviderConfigSection from '../components/analysis/ProviderConfigSection';
import ProgressPanel from '../components/progress/ProgressPanel';
import ResultsDashboard from '../components/results/ResultsDashboard';
import MarkdownRenderer from '../components/shared/MarkdownRenderer';

export default function Dashboard() {
  const { form, taskId, taskStatus, result, isRunning, error, reset } = useAnalysisStore();
  const submit = useSubmitAnalysis();
  const cancel = useCancelAnalysis();
  const { messages, toolCalls, reports, agentTimes } = useAnalysisStream(taskId);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await submit();
    } catch {}
    setSubmitting(false);
  };

  // Show results if completed
  if (result) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold text-trading-text">Analysis Results</h1>
          <button
            onClick={() => reset()}
            className="flex items-center gap-2 px-4 py-2 bg-trading-surface border border-trading-border rounded-lg text-sm text-trading-textdim hover:text-trading-text hover:border-trading-textdim transition-all cursor-pointer"
          >
            <RotateCcw className="w-4 h-4" />
            New Analysis
          </button>
        </div>
        <ResultsDashboard result={result} />
      </div>
    );
  }

  // Show progress if running
  if (isRunning && taskStatus) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <ProgressPanel
          status={taskStatus}
          messages={messages}
          toolCalls={toolCalls}
          agentTimes={agentTimes}
          onCancel={cancel}
        />

        {/* Streamed report sections as they complete */}
        {reports.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide flex items-center gap-2">
              <Clock className="w-3.5 h-3.5" />
              Completed Reports
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {reports.map((r) => (
                <div key={r.section} className="bg-trading-surface border border-trading-border rounded-xl overflow-hidden animate-slide-up">
                  <div className="px-3 py-2 border-b border-trading-border flex items-center justify-between bg-trading-emerald/5">
                    <span className="text-xs font-semibold text-trading-emerald">{r.title}</span>
                    <span className="text-xs text-trading-textdim">{r.wall_time}s</span>
                  </div>
                  <div className="p-3 max-h-64 overflow-y-auto">
                    <MarkdownRenderer content={r.content.slice(0, 1500)} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="bg-trading-red/10 border border-trading-red/30 rounded-lg p-4 text-sm text-trading-red">
            {error}
          </div>
        )}
      </div>
    );
  }

  // Show error
  if (error && !isRunning) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="bg-trading-red/10 border border-trading-red/30 rounded-lg p-4 text-sm text-trading-red">
          {error}
          <button onClick={() => reset()} className="ml-4 underline cursor-pointer">Dismiss</button>
        </div>
      </div>
    );
  }

  // Show form
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-lg font-bold text-trading-text">New Analysis</h1>
        <p className="text-sm text-trading-textdim mt-1">
          Configure and run an AI-powered multi-agent trading analysis
        </p>
      </div>

      <div className="bg-trading-surface border border-trading-border rounded-xl p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <TickerInput />
          <DatePicker />
        </div>
        <LanguageSelector />
        <AnalystSelector />
        <ResearchDepthSelector />
        <div className="border-t border-trading-border pt-5">
          <LLMProviderSelector />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <ModelSelector mode="quick" />
          <ModelSelector mode="deep" />
        </div>
        <ProviderConfigSection />
      </div>

      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full py-3 bg-trading-emerald text-trading-bg font-semibold rounded-xl hover:bg-trading-emerald/90 transition-all flex items-center justify-center gap-2 text-sm cursor-pointer disabled:opacity-50"
      >
        {submitting ? 'Starting analysis...' : (
          <>
            <Play className="w-4 h-4" />
            Run Analysis
          </>
        )}
      </button>
    </div>
  );
}
