import { useState } from 'react';
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown, Gavel } from 'lucide-react';
import MarkdownRenderer from '../shared/MarkdownRenderer';
import type { DebateState } from '../../types/api';

interface Props {
  state: DebateState | null;
}

export default function ResearchDebatePanel({ state }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!state) return null;
  const { bull_history, bear_history, judge_decision } = state;

  return (
    <div className="bg-trading-surface border border-trading-border rounded-xl overflow-hidden animate-slide-up">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-trading-surface2/50 transition-colors cursor-pointer"
      >
        <h4 className="text-sm font-semibold text-trading-text flex items-center gap-2">
          <Gavel className="w-4 h-4 text-trading-amber" />
          Research Debate — Bull vs Bear
        </h4>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-trading-textdim" />
        ) : (
          <ChevronDown className="w-4 h-4 text-trading-textdim" />
        )}
      </button>

      {expanded && (
        <div className="p-4 space-y-4">
          {/* Bull argument */}
          {bull_history && (
            <div className="bg-trading-bg rounded-lg p-3 border-l-2 border-trading-green">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-trading-green" />
                <span className="text-xs font-semibold text-trading-green">Bull Case</span>
              </div>
              <MarkdownRenderer content={bull_history} />
            </div>
          )}

          {/* Bear argument */}
          {bear_history && (
            <div className="bg-trading-bg rounded-lg p-3 border-l-2 border-trading-red">
              <div className="flex items-center gap-2 mb-2">
                <TrendingDown className="w-4 h-4 text-trading-red" />
                <span className="text-xs font-semibold text-trading-red">Bear Case</span>
              </div>
              <MarkdownRenderer content={bear_history} />
            </div>
          )}

          {/* Judge verdict */}
          {judge_decision && (
            <div className="bg-trading-amber/5 border border-trading-amber/20 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Gavel className="w-4 h-4 text-trading-amber" />
                <span className="text-xs font-semibold text-trading-amber">Research Manager Verdict</span>
              </div>
              <MarkdownRenderer content={judge_decision} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
