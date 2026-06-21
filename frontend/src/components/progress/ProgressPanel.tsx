import { useState } from 'react';
import { Clock, MessageSquare, Wrench, Zap, Square } from 'lucide-react';
import type { TaskStatusResponse } from '../../types/api';
import MessageFeed, { type FeedMessage, type ToolCall } from './MessageFeed';

interface Props {
  status: TaskStatusResponse | null;
  messages?: FeedMessage[];
  toolCalls?: ToolCall[];
  agentTimes?: Record<string, number>;
  minimized?: boolean;
  onCancel?: () => void;
}

const AGENT_ORDER = [
  'Market Analyst',
  'Sentiment Analyst',
  'News Analyst',
  'Fundamentals Analyst',
  'Bull Researcher',
  'Bear Researcher',
  'Research Manager',
  'Trader',
  'Aggressive Analyst',
  'Conservative Analyst',
  'Neutral Analyst',
  'Portfolio Manager',
];

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: 'bg-trading-green',
    running: 'bg-trading-accent animate-pulse',
    error: 'bg-trading-red',
    pending: 'bg-trading-border',
  };
  return <span className={`w-2 h-2 rounded-full shrink-0 ${colors[status] || colors.pending}`} />;
}

function formatSeconds(s: number): string {
  if (s < 1) return '<1s';
  if (s < 60) return `${s.toFixed(0)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}m ${sec}s`;
}

export default function ProgressPanel({
  status,
  messages = [],
  toolCalls = [],
  agentTimes = {},
  minimized = false,
  onCancel,
}: Props) {
  const [showCancel, setShowCancel] = useState(false);

  if (!status) return null;

  const { agent_status, reports_completed, reports_total, llm_calls, tool_calls, tokens_in, tokens_out, elapsed_seconds } = status.progress;

  if (minimized) {
    return (
      <div className="bg-trading-surface border border-trading-border rounded-lg p-3 mb-4 flex items-center gap-4 text-xs">
        <span className="text-trading-emerald font-mono">{reports_completed}/{reports_total}</span>
        <div className="flex-1 h-1.5 bg-trading-border rounded-full overflow-hidden">
          <div
            className="h-full bg-trading-emerald rounded-full transition-all duration-500"
            style={{ width: `${reports_total > 0 ? (reports_completed / reports_total) * 100 : 0}%` }}
          />
        </div>
        <span className="text-trading-textdim">{elapsed_seconds.toFixed(0)}s</span>
      </div>
    );
  }

  return (
    <div className="bg-trading-surface border border-trading-border rounded-xl overflow-hidden space-y-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-trading-border flex items-center justify-between">
        <h3 className="text-sm font-semibold text-trading-text">Analysis in Progress</h3>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-3 text-xs text-trading-textdim">
            <span className="flex items-center gap-1"><Zap className="w-3 h-3" /> {(tokens_in + tokens_out).toLocaleString()}</span>
            <span className="flex items-center gap-1"><Wrench className="w-3 h-3" /> {tool_calls}</span>
            <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" /> {llm_calls}</span>
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {formatSeconds(elapsed_seconds)}</span>
          </div>
          {onCancel && (
            <button
              onClick={() => setShowCancel(true)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-trading-red/10 text-trading-red text-xs hover:bg-trading-red/20 transition-colors cursor-pointer"
            >
              <Square className="w-3 h-3" />
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Cancel confirmation */}
      {showCancel && (
        <div className="mx-4 p-3 bg-trading-red/5 border border-trading-red/20 rounded-lg">
          <p className="text-xs text-trading-red font-medium mb-2">Stop this analysis?</p>
          <p className="text-xs text-trading-textdim mb-2">
            The current run will be cancelled and partial results will be lost.
            LLM API calls already made will still be billed.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => { onCancel?.(); setShowCancel(false); }}
              className="px-3 py-1 rounded text-xs font-medium bg-trading-red text-white hover:bg-trading-red/80 cursor-pointer"
            >
              Yes, stop
            </button>
            <button
              onClick={() => setShowCancel(false)}
              className="px-3 py-1 rounded text-xs border border-trading-border text-trading-textdim hover:text-trading-text cursor-pointer"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Progress bar */}
      <div className="h-1 bg-trading-border">
        <div
          className="h-full bg-trading-emerald transition-all duration-500 ease-out"
          style={{ width: `${reports_total > 0 ? (reports_completed / reports_total) * 100 : 0}%` }}
        />
      </div>

      {/* Agent pipeline with timing */}
      <div className="px-4 py-3 border-b border-trading-border">
        <p className="text-xs font-medium text-trading-textdim mb-2 uppercase tracking-wide">Agent Pipeline</p>
        <div className="flex flex-wrap gap-1.5">
          {AGENT_ORDER.map((name) => {
            const s = agent_status[name] || 'pending';
            const wall = agentTimes[name];
            return (
              <div
                key={name}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                  s === 'running'
                    ? 'bg-trading-accent/10 text-trading-accent ring-1 ring-trading-accent/30'
                    : s === 'completed'
                    ? 'bg-trading-emerald/10 text-trading-emerald'
                    : s === 'error'
                    ? 'bg-trading-red/10 text-trading-red'
                    : 'bg-trading-bg text-trading-textdim'
                }`}
              >
                <StatusDot status={s} />
                <span className="whitespace-nowrap">{name}</span>
                {wall !== undefined && wall > 0 && (
                  <span className="text-trading-textdim ml-0.5 tabular-nums">
                    {formatSeconds(wall)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Message feed */}
      <div>
        <p className="px-4 pt-3 text-xs font-medium text-trading-textdim uppercase tracking-wide">
          Live Messages
        </p>
        <MessageFeed messages={messages} toolCalls={toolCalls} />
      </div>
    </div>
  );
}
