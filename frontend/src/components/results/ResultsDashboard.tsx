import SignalBadge from '../shared/SignalBadge';
import AnalystReportsGrid from './AnalystReportsGrid';
import ResearchDebatePanel from './ResearchDebatePanel';
import ReportCard from './ReportCard';
import PMDecisionCard from './PMDecisionCard';
import type { AnalysisResultResponse } from '../../types/api';

interface Props {
  result: AnalysisResultResponse;
}

export default function ResultsDashboard({ result }: Props) {
  const { final_state, signal, ticker, analysis_date, asset_type, stats } = result;

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Hero section */}
      <div className="bg-trading-surface border border-trading-border rounded-xl p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h2 className="text-xl font-bold text-trading-text">{ticker}</h2>
              {asset_type === 'crypto' && (
                <span className="px-2 py-0.5 rounded bg-trading-amber/10 text-trading-amber text-xs">Crypto</span>
              )}
            </div>
            <p className="text-sm text-trading-textdim">Analysis for {analysis_date}</p>
          </div>
          <SignalBadge signal={signal} size="lg" pulsing />
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-trading-border">
          <div>
            <p className="text-xs text-trading-textdim">LLM Calls</p>
            <p className="text-sm font-semibold text-trading-text">{stats.llm_calls}</p>
          </div>
          <div>
            <p className="text-xs text-trading-textdim">Tool Calls</p>
            <p className="text-sm font-semibold text-trading-text">{stats.tool_calls}</p>
          </div>
          <div>
            <p className="text-xs text-trading-textdim">Tokens</p>
            <p className="text-sm font-semibold text-trading-text">{(stats.tokens_in + stats.tokens_out).toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-trading-textdim">Duration</p>
            <p className="text-sm font-semibold text-trading-text">{stats.elapsed_seconds.toFixed(0)}s</p>
          </div>
        </div>
      </div>

      {/* Analyst reports grid */}
      <section>
        <h3 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide mb-3">
          Analyst Reports
        </h3>
        <AnalystReportsGrid state={final_state} />
      </section>

      {/* Research debate */}
      <section>
        <h3 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide mb-3">
          Research Debate
        </h3>
        <ResearchDebatePanel state={final_state.investment_debate_state} />
      </section>

      {/* Trader plan */}
      <section>
        <h3 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide mb-3">
          Trader Decision
        </h3>
        <ReportCard
          title="Trader Investment Plan"
          content={final_state.trader_investment_plan}
          icon="💼"
        />
      </section>

      {/* Risk debate */}
      {final_state.risk_debate_state && (
        <section>
          <h3 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide mb-3">
            Risk Debate
          </h3>
          <div className="space-y-3">
            {final_state.risk_debate_state.aggressive_history && (
              <ReportCard title="Aggressive Risk View" content={final_state.risk_debate_state.aggressive_history} icon="🔴" />
            )}
            {final_state.risk_debate_state.conservative_history && (
              <ReportCard title="Conservative Risk View" content={final_state.risk_debate_state.conservative_history} icon="🟢" />
            )}
            {final_state.risk_debate_state.neutral_history && (
              <ReportCard title="Neutral Risk View" content={final_state.risk_debate_state.neutral_history} icon="🟡" />
            )}
          </div>
        </section>
      )}

      {/* PM Final Decision */}
      <section>
        <h3 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide mb-3">
          Portfolio Manager Decision
        </h3>
        <PMDecisionCard content={final_state.final_trade_decision} signal={signal} />
      </section>

      {/* Investment Plan */}
      {final_state.investment_plan && (
        <section>
          <h3 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide mb-3">
            Investment Plan
          </h3>
          <ReportCard title="Research Manager Plan" content={final_state.investment_plan} icon="📐" />
        </section>
      )}
    </div>
  );
}
