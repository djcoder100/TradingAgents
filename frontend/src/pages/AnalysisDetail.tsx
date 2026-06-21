import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useAnalysisStore } from '../stores/analysisStore';
import { useAnalysisStream } from '../hooks/useAnalysis';
import { fetchRunDetail } from '../api/client';
import ProgressPanel from '../components/progress/ProgressPanel';
import ResultsDashboard from '../components/results/ResultsDashboard';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import type { AnalysisResultResponse } from '../types/api';

export default function AnalysisDetail() {
  const { taskId, runId } = useParams();
  const navigate = useNavigate();
  const { result, taskStatus, isRunning, error } = useAnalysisStore();
  const [histResult, setHistResult] = useState<AnalysisResultResponse | null>(null);
  const [histLoading, setHistLoading] = useState(false);
  const [histError, setHistError] = useState<string | null>(null);

  // Live analysis mode: connect SSE
  useAnalysisStream(taskId || null);

  // Historical run mode: load from history API
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    (async () => {
      setHistLoading(true);
      try {
        const data = await fetchRunDetail(runId);

        if (!cancelled) {
          // Transform the raw JSON log into the AnalysisResultResponse shape
          const signal = extractSignal(data);
          const histResult: AnalysisResultResponse = {
            task_id: runId,
            ticker: data.company_of_interest || '',
            analysis_date: data.trade_date || '',
            signal,
            final_state: {
              market_report: data.market_report || null,
              sentiment_report: data.sentiment_report || null,
              news_report: data.news_report || null,
              fundamentals_report: data.fundamentals_report || null,
              investment_plan: data.investment_plan || null,
              trader_investment_plan: data.trader_investment_decision || null,
              final_trade_decision: data.final_trade_decision || null,
              investment_debate_state: data.investment_debate_state
                ? {
                    bull_history: data.investment_debate_state.bull_history || null,
                    bear_history: data.investment_debate_state.bear_history || null,
                    judge_decision: data.investment_debate_state.judge_decision || null,
                  }
                : null,
              risk_debate_state: data.risk_debate_state
                ? {
                    aggressive_history: data.risk_debate_state.aggressive_history || null,
                    conservative_history: data.risk_debate_state.conservative_history || null,
                    neutral_history: data.risk_debate_state.neutral_history || null,
                    judge_decision: data.risk_debate_state.judge_decision || null,
                  }
                : null,
            },
            stats: {
              llm_calls: 0,
              tool_calls: 0,
              tokens_in: 0,
              tokens_out: 0,
              elapsed_seconds: 0,
              analyst_wall_times: {},
            },
            asset_type: data.asset_type || 'stock',
            instrument_context: data.instrument_context || null,
          };
          setHistResult(histResult);
        }
      } catch (err: any) {
        if (!cancelled) setHistError(err.message);
      } finally {
        if (!cancelled) setHistLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [runId]);

  // Determine which result to show
  const displayResult = result || histResult;
  const displayError = error || histError;
  const displayLoading = (isRunning && !result) || histLoading;
  const displayProgress = isRunning && taskStatus && !result;

  if (displayResult) {
    return (
      <div className="max-w-5xl mx-auto">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-sm text-trading-textdim hover:text-trading-text mb-6 transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <ResultsDashboard result={displayResult} />
      </div>
    );
  }

  if (displayProgress) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-lg font-bold text-trading-text">Analysis in Progress</h1>
        <ProgressPanel status={taskStatus} />
      </div>
    );
  }

  if (displayError) {
    return (
      <div className="max-w-5xl mx-auto">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-sm text-trading-textdim hover:text-trading-text mb-6 transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <div className="bg-trading-red/10 border border-trading-red/30 rounded-lg p-4 text-sm text-trading-red">
          {displayError}
        </div>
      </div>
    );
  }

  if (displayLoading) {
    return (
      <div className="max-w-5xl mx-auto">
        <LoadingSpinner label="Loading analysis..." />
      </div>
    );
  }

  return null;
}

/** Extract signal from a raw JSON log's final_trade_decision. */
function extractSignal(data: any): string {
  const decision = data.final_trade_decision || '';
  // Match "Rating: X" or "Rating - X"
  const match = decision.match(/(?:Rating|Signal)[:\s-]+(\w+)/i);
  if (match) return match[1];
  // Fallback: search for first rating word
  const ratings = ['Buy', 'Overweight', 'Hold', 'Underweight', 'Sell'];
  for (const r of ratings) {
    if (decision.includes(r)) return r;
  }
  return 'Hold';
}
