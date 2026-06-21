import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  TrendingUp, TrendingDown, Activity,
  AlertTriangle, Clock, BarChart3, Target, Shield,
  ChevronRight, ExternalLink, Info, Repeat2,
} from 'lucide-react';
import SignalBadge from '../components/shared/SignalBadge';
import MarkdownRenderer from '../components/shared/MarkdownRenderer';
import Tooltip from '../components/shared/Tooltip';

// ---- Types (mirrors the API response) ----
interface Signal {
  ticker: string;
  action: string;
  confidence: number;
  order_size_notional: number;
  entry_price_target: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  created_at: number;
  expires_at: number;
  is_expired: boolean;
  analysis: string;
  analysis_id: string | null;
}

interface Position {
  ticker: string;
  direction: string;
  size_notional: number;
  avg_entry_price: number;
  current_px: number | null;
  unrealized_pnl: number | null;
  opened_at: number;
}

interface Trade {
  timestamp: number;
  ticker: string;
  action: string;
  size_notional: number;
  fill_price: number | null;
  status: string;
  reason: string;
  signal_confidence: number;
  analysis_excerpt: string;
  analysis_full: string;
  analysis_id: string | null;
  order_id: string;
}

interface Metrics {
  total_return_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number | null;
  intervals_recorded: number;
  intervals_needed: number;
  sharpe_capped: boolean;
}

interface Account {
  equity: number;
  used_margin: number;
  leverage: number;
  margin_usage_pct: number;
  open_positions_count: number;
}

interface AnalysisProgress {
  stage: string;
  step: number;
  total: number;
  started_at: number;
  elapsed_s: number;
}

interface CompetitionState {
  signals: Signal[];
  positions: Position[];
  trades: Trade[];
  account: Account | null;
  metrics: Metrics | null;
  analysis_progress: Record<string, AnalysisProgress>;
  last_updated: number;
  uptime: string;
  round_trip_count: number;
  violations: { severity: string; rule: string; detail: string }[];
}

const API_BASE = '/api';

function formatNotional(n: number): string {
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString();
}

function formatExpires(ts: number): string {
  const diff = ts - Date.now() / 1000;
  if (diff <= 0) return 'Expired';
  const m = Math.floor(diff / 60);
  const s = Math.floor(diff % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatPnl(pnl: number | null | undefined): string {
  if (pnl == null) return '—';
  const sign = pnl >= 0 ? '+' : '';
  return `${sign}$${pnl.toFixed(2)}`;
}

export default function Competition() {
  const navigate = useNavigate();
  const [state, setState] = useState<CompetitionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastError, setLastError] = useState<{ message: string; time: string } | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [expandedTrade, setExpandedTrade] = useState<string | null>(null);
  const [filterTicker, setFilterTicker] = useState<string>('');
  const [filterAction, setFilterAction] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  const fetchState = useCallback(async () => {
    try {
      const startTime = Date.now();
      const res = await fetch(`${API_BASE}/competition/state`, { signal: AbortSignal.timeout(10000) });
      const duration = Date.now() - startTime;

      if (res.status === 503) {
        const msg = 'Competition engine not running. Start with: ./scripts/competition-start-distributed.sh (or uv run competition --web-only)';
        setError(msg);
        setLastError({ message: msg, time: new Date().toLocaleTimeString() });
        setIsConnected(false);
        console.warn(`[Competition] Engine unavailable (503) — ${msg}`);
        return;
      }

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      setState(data);
      setError(null);
      setRetryCount(0);

      if (!isConnected) {
        console.info(`[Competition] ✓ Connected to API (${duration}ms)`);
        setIsConnected(true);
      }
    } catch (e: any) {
      const errMsg = e.message || 'Unknown error';
      const timestamp = new Date().toLocaleTimeString();

      if (errMsg.includes('ECONNREFUSED') || errMsg.includes('Failed to fetch')) {
        const newRetryCount = retryCount + 1;
        setRetryCount(newRetryCount);
        setIsConnected(false);
        console.warn(`[Competition] Connection refused (attempt ${newRetryCount}) — Is the API running?`);
        console.warn(`  Error: ${errMsg}`);
        console.warn(`  Expected endpoint: http://localhost:8000/api/competition/state`);
        setLastError({
          message: `Connection refused — API server may not be running (attempt ${newRetryCount})`,
          time: timestamp
        });
        setError('Waiting for API server… (Make sure the engine or web-only process is running)');
      } else if (errMsg.includes('AbortError')) {
        setIsConnected(false);
        console.warn(`[Competition] Request timeout (>10s) — API may be slow or unresponsive`);
        setLastError({ message: 'Request timeout (>10s)', time: timestamp });
        setError('API server timeout — it may be overloaded or unresponsive');
      } else if (!errMsg.includes('fetch')) {
        console.error(`[Competition] Fetch error: ${errMsg}`);
        setLastError({ message: errMsg, time: timestamp });
        setError(errMsg);
        setIsConnected(false);
      }
    }
  }, [isConnected, retryCount]);

  useEffect(() => {
    console.info('[Competition] Dashboard mounted, starting data poll');
    fetchState();
    const interval = setInterval(fetchState, 2000);
    return () => {
      clearInterval(interval);
      console.info('[Competition] Dashboard unmounted, stopped data poll');
    };
  }, [fetchState]);

  // ---- Error / waiting state ----
  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-trading-bg">
        <div className="text-center max-w-md">
          <div className="flex justify-center mb-4">
            <Activity className={`w-12 h-12 ${isConnected ? 'text-trading-emerald' : 'text-trading-amber'} ${!isConnected ? 'animate-pulse' : ''}`} />
          </div>
          <h2 className="text-lg font-semibold text-trading-text mb-2">
            {isConnected ? 'Connected' : 'Connecting…'}
          </h2>
          <p className="text-trading-textdim text-sm mb-4">{error}</p>

          {lastError && (
            <div className="bg-trading-surface/50 border border-trading-border rounded p-3 text-left mb-4">
              <p className="text-xs text-trading-textdim mb-1">Last error:</p>
              <p className="text-xs text-trading-text font-mono mb-1">{lastError.message}</p>
              <p className="text-xs text-trading-textdim">{lastError.time}</p>
            </div>
          )}

          {!isConnected && (
            <div className="bg-trading-surface/50 border border-trading-border rounded p-3 text-left text-xs text-trading-textdim space-y-1">
              <p><strong>Troubleshooting:</strong></p>
              <p>1. Start all services:</p>
              <p className="ml-2 font-mono text-trading-text">./scripts/competition-start-distributed.sh</p>
              <p>   Or manually:</p>
              <p className="ml-2 font-mono text-trading-text">Terminal 1: uv run competition --mock --dry-run</p>
              <p className="ml-2 font-mono text-trading-text">Terminal 2: uv run competition --web-only</p>
              <p>2. Check API: <strong>curl http://localhost:8000/api/competition/state</strong></p>
              <p>3. Browser console (F12 → Console) shows detailed errors</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (!state || !state.last_updated) {
    return (
      <div className="flex items-center justify-center h-screen bg-trading-bg">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-trading-emerald border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-trading-textdim text-sm">Waiting for engine data…</p>
          {lastError && (
            <p className="text-xs text-trading-amber mt-4">Last attempt: {lastError.time}</p>
          )}
        </div>
      </div>
    );
  }

  const { signals, positions, trades, account, metrics, violations, uptime, analysis_progress, round_trip_count } = state;
  const runningAnalyses = Object.entries(analysis_progress || {});

  // Filter trades based on selected filters
  const filteredTrades = trades.filter(t => {
    if (filterTicker && !t.ticker.toLowerCase().includes(filterTicker.toLowerCase())) return false;
    if (filterAction && t.action !== filterAction) return false;
    if (filterStatus && t.status !== filterStatus) return false;
    return true;
  });

  // Get unique values for filter dropdowns
  const uniqueTickers = [...new Set(trades.map(t => t.ticker))];
  const uniqueActions = [...new Set(trades.map(t => t.action))];
  const uniqueStatuses = [...new Set(trades.map(t => t.status))];

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-trading-text">Competition Dashboard</h1>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-trading-emerald animate-none' : 'bg-trading-amber animate-pulse'}`} />
          <span className={`text-xs font-mono ${isConnected ? 'text-trading-emerald' : 'text-trading-amber'}`}>
            {isConnected ? 'Connected' : `Reconnecting (${retryCount})`}
          </span>
        </div>
      </div>

      {/* ---- Scoreboard Bar ---- */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
        <ScoreCard icon={TrendingUp} label="Return" value={metrics ? `${metrics.total_return_pct >= 0 ? '+' : ''}${metrics.total_return_pct.toFixed(2)}%` : '—'} color={metrics && metrics.total_return_pct >= 0 ? 'text-trading-green' : 'text-trading-red'}
          tooltip="Total return vs opening equity. Worth 70% of the composite competition score. Calculated as (current equity − starting equity) / starting equity." />
        <ScoreCard icon={TrendingDown} label="Max DD" value={metrics ? `${metrics.max_drawdown_pct.toFixed(2)}%` : '—'} color="text-trading-red"
          tooltip="Maximum drawdown: largest peak-to-trough equity drop. Worth 15% of the composite score AND the secondary tie-breaker. Lower is better — it separates consistent strategies from lucky one-trade spikes that briefly sink the account." />
        <ScoreCard icon={BarChart3} label="Sharpe" value={metrics?.sharpe_ratio != null ? metrics.sharpe_ratio.toFixed(2) : '—'} color="text-trading-text" sub={metrics?.sharpe_capped ? 'capped' : undefined}
          tooltip="MoMQ raw Sharpe: Mean(r) / Std(r) of 15-min equity returns — NOT annualised. Worth 10% of composite score and is the tertiary tie-breaker. Requires ≥8 return observations; fewer caps your Sharpe rank at 50 pts max." />
        <ScoreCard icon={Activity} label="Equity" value={account ? formatNotional(account.equity) : '—'} color="text-trading-emerald"
          tooltip="Total account equity in USD: starting $1,000,000 plus all realised and unrealised P&L from open positions." />
        <ScoreCard icon={Shield} label="Leverage" value={account ? `${account.leverage.toFixed(1)}x` : '—'} color={account && account.leverage > 25 ? 'text-trading-red' : 'text-trading-text'}
          tooltip="Gross notional exposure ÷ equity. The firewall caps orders at 25x. A 20-point penalty is logged at 28x and disqualification triggers at 30x." />
        <ScoreCard icon={AlertTriangle} label="Margin" value={account ? `${(account.margin_usage_pct * 100).toFixed(1)}%` : '—'} color={account && account.margin_usage_pct > 0.8 ? 'text-trading-red' : 'text-trading-text'}
          tooltip="Used margin as a percentage of equity. New orders are blocked above 80%. Sustaining above 90% for 30+ minutes triggers a 20-point competition penalty." />
        <ScoreCard icon={Target} label="Obs" value={metrics ? `${metrics.intervals_recorded}/${metrics.intervals_needed}` : '—'} color={metrics && metrics.intervals_recorded < metrics.intervals_needed ? 'text-trading-amber' : 'text-trading-green'}
          tooltip="15-min return observations recorded vs the 8 required for a full Sharpe score. First snapshot is the baseline; returns start accumulating from the second snapshot. Engine records one per 15-min wall-clock boundary." />
        <ScoreCard icon={Repeat2} label="Round-trips" value={`${round_trip_count ?? 0}/30`} color={(round_trip_count ?? 0) >= 30 ? 'text-trading-green' : (round_trip_count ?? 0) >= 15 ? 'text-trading-amber' : 'text-trading-textdim'}
          tooltip="Completed round-trip trades (open + close = 1 round-trip). The Best Sharpe category requires ≥30 round-trips to be eligible. Each entry/exit pair counts as one. Currently at half-way when amber." />
      </div>

      {/* ---- Risk Metrics Breakdown ---- */}
      {account && (
        <div className="bg-trading-surface border border-trading-border rounded-xl p-4">
          <div className="flex items-center gap-1.5 mb-3">
            <h2 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide">Risk Profile</h2>
            <Tooltip content="Your current risk exposure: open positions, margin usage, leverage, and portfolio concentration. The firewall enforces hard limits: 25x max leverage, 80% max margin usage, 30x disqualification." position="bottom" maxWidth={260}>
              <Info className="w-3 h-3 text-trading-border hover:text-trading-textdim cursor-help transition-colors" />
            </Tooltip>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="bg-trading-surface2 rounded-lg p-3 border border-trading-border/50">
              <p className="text-trading-textdim mb-1">Open Positions</p>
              <p className="font-mono font-bold text-trading-text">{account.open_positions_count}</p>
            </div>
            <div className="bg-trading-surface2 rounded-lg p-3 border border-trading-border/50">
              <p className="text-trading-textdim mb-1">Used Margin</p>
              <p className="font-mono font-bold text-trading-text">${account.used_margin.toFixed(0)}</p>
              <p className="text-trading-textdim text-xs mt-1">{(account.margin_usage_pct * 100).toFixed(1)}% of equity</p>
            </div>
            <div className="bg-trading-surface2 rounded-lg p-3 border border-trading-border/50">
              <p className="text-trading-textdim mb-1">Current Leverage</p>
              <p className={`font-mono font-bold ${account.leverage > 25 ? 'text-trading-red' : account.leverage > 15 ? 'text-trading-amber' : 'text-trading-emerald'}`}>{account.leverage.toFixed(1)}x</p>
              <p className="text-trading-textdim text-xs mt-1">Max: 25x</p>
            </div>
            <div className="bg-trading-surface2 rounded-lg p-3 border border-trading-border/50">
              <p className="text-trading-textdim mb-1">Equity</p>
              <p className="font-mono font-bold text-trading-text">{formatNotional(account.equity)}</p>
            </div>
          </div>
        </div>
      )}

      {/* ---- Alerts ---- */}
      {violations.length > 0 && (
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-xs font-semibold text-trading-textdim uppercase tracking-wide">Risk Alerts</span>
            <Tooltip content="Rule violations detected by the competition firewall. PENALTY deducts points from your score. DISQUALIFICATION removes you from rankings for the session. Fix the underlying position to clear an alert." position="right" maxWidth={260}>
              <Info className="w-3 h-3 text-trading-border hover:text-trading-textdim cursor-help transition-colors" />
            </Tooltip>
          </div>
          {violations.map((v, i) => (
            <div key={i} className={`px-3 py-2 rounded-lg text-xs border ${
              v.severity === 'DISQUALIFICATION' ? 'bg-trading-red/10 border-trading-red text-trading-red' :
              v.severity === 'PENALTY' ? 'bg-trading-amber/10 border-trading-amber text-trading-amber' :
              'bg-trading-surface2 border-trading-border text-trading-textdim'
            }`}>
              <span className="font-semibold">[{v.severity}]</span> {v.rule}: {v.detail}
            </div>
          ))}
        </div>
      )}

      {/* ---- Analysis Progress ---- */}
      {runningAnalyses.length > 0 && (
        <div className="bg-trading-surface border border-trading-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-trading-emerald animate-pulse" />
            <h2 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide">
              LLM Analysis In Progress ({runningAnalyses.length})
            </h2>
            <Tooltip content="The TradingAgents multi-agent pipeline is running. Each instrument goes through 12 pipeline stages: 4 analysts (technical, sentiment, news, fundamentals) → bull/bear debate → research manager → trader → 3 risk analysts → portfolio manager. The final decision becomes an active signal." position="bottom" maxWidth={280}>
              <Info className="w-3 h-3 text-trading-border hover:text-trading-textdim cursor-help transition-colors" />
            </Tooltip>
          </div>
          <div className="space-y-3">
            {runningAnalyses.map(([ticker, prog]) => {
              const pct = prog.total > 0 ? Math.round((prog.step / prog.total) * 100) : 0;
              const mins = Math.floor(prog.elapsed_s / 60);
              const secs = Math.floor(prog.elapsed_s % 60);
              const elapsed = `${mins}:${secs.toString().padStart(2, '0')}`;
              return (
                <div key={ticker}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <a
                        href={`https://finviz.com/quote.ashx?t=${ticker.replace(/[=X]/g, '')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono font-bold text-sm text-trading-emerald hover:text-trading-emerald/80 transition-colors underline"
                      >
                        {ticker}
                      </a>
                      <span className="text-xs text-trading-textdim">{prog.stage}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-trading-textdim">
                      <span>{prog.step}/{prog.total} stages</span>
                      <span className="font-mono">{elapsed}</span>
                    </div>
                  </div>
                  <div className="w-full bg-trading-surface2 rounded-full h-1.5">
                    <div
                      className="bg-trading-emerald h-1.5 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ---- Signals & Positions Grid ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Signals */}
        <div className="bg-trading-surface border border-trading-border rounded-xl p-4">
          <div className="flex items-center gap-1.5 mb-3">
            <h2 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide">
              Active Signals ({signals.length})
            </h2>
            <Tooltip content="Buy/Sell recommendations from the TradingAgents LLM pipeline. Each signal has a confidence level (0–100%), a notional size in USD, and an expiry. Expired signals are stale and won't trigger new orders. Click a signal row to see the full analyst report." position="bottom" maxWidth={270}>
              <Info className="w-3 h-3 text-trading-border hover:text-trading-textdim cursor-help transition-colors" />
            </Tooltip>
          </div>
          {signals.length === 0 ? (
            <p className="text-xs text-trading-textdim">
              {runningAnalyses.length > 0
                ? `Analysis running for ${runningAnalyses.map(([t]) => t).join(', ')} — signals will appear when complete.`
                : 'No active signals — waiting for next refresh.'}
            </p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {signals.map((s) => (
                <button
                  key={s.ticker}
                  className="w-full flex items-center justify-between p-3 rounded-lg bg-trading-surface2 hover:bg-trading-border/50 transition-colors text-left group"
                  onClick={() => navigate(`/competition/analysis/${s.analysis_id || s.ticker}`)}
                >
                  <div className="flex items-center gap-3">
                    <a
                      href={`https://finviz.com/quote.ashx?t=${s.ticker.replace(/[=X]/g, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="font-mono font-bold text-sm text-trading-emerald hover:text-trading-text transition-colors underline"
                    >
                      {s.ticker}
                    </a>
                    <SignalBadge signal={s.action} size="sm" />
                    {s.analysis && (
                      <span className="text-xs text-trading-emerald opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                        <ExternalLink className="w-3 h-3" /> View analysis
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-trading-textdim">
                    <Tooltip content="Portfolio Manager confidence: how strongly the LLM pipeline rates this signal. 90%=Strong Buy/Sell, 70%=Overweight/Underweight, 50%=Hold." position="top">
                      <span className="cursor-help">{(s.confidence * 100).toFixed(0)}% conf</span>
                    </Tooltip>
                    <Tooltip content="USD notional order size calculated as a percentage of current equity. Sized by the Portfolio Manager's position recommendation, capped at the competition max position limit." position="top">
                      <span className="cursor-help">{formatNotional(s.order_size_notional)}</span>
                    </Tooltip>
                    <Tooltip content={s.is_expired ? 'Signal has expired — it will not trigger new orders and will be refreshed on the next engine cycle.' : 'Time until this signal expires. The engine will re-run analysis and may renew or change the signal before it lapses.'} position="top">
                      <span className={`cursor-help ${s.is_expired ? 'text-trading-red' : 'text-trading-textdim'}`}>
                        {formatExpires(s.expires_at)}
                      </span>
                    </Tooltip>
                    <ChevronRight className="w-4 h-4 opacity-40 group-hover:opacity-100 transition-opacity" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Open Positions */}
        <div className="bg-trading-surface border border-trading-border rounded-xl p-4">
          <div className="flex items-center gap-1.5 mb-3">
            <h2 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide">
              Positions ({positions.length})
            </h2>
            <Tooltip content="Open positions currently held by the competition account. Entry @ shows average fill price. Current shows the latest market price. Unrealised P&L counts toward your equity and Return score in real time." position="bottom" maxWidth={260}>
              <Info className="w-3 h-3 text-trading-border hover:text-trading-textdim cursor-help transition-colors" />
            </Tooltip>
          </div>
          {positions.length === 0 ? (
            <p className="text-xs text-trading-textdim">No open positions.</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {positions.map((p, i) => (
                <div key={`${p.ticker}-${i}`} className="flex items-center justify-between p-3 rounded-lg bg-trading-surface2">
                  <div className="flex items-center gap-3">
                    <a
                      href={`https://finviz.com/quote.ashx?t=${p.ticker.replace(/[=X]/g, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono font-bold text-sm text-trading-emerald hover:text-trading-text transition-colors underline"
                    >
                      {p.ticker}
                    </a>
                    <SignalBadge signal={p.direction} size="sm" />
                    <Tooltip content="Notional USD exposure for this position (shares × price). This counts toward your leverage and margin calculations." position="top">
                      <span className="text-xs text-trading-textdim cursor-help">{formatNotional(p.size_notional)}</span>
                    </Tooltip>
                  </div>
                  <div className="text-right">
                    <Tooltip content={`Entry @ ${p.avg_entry_price?.toFixed(4)} — average fill price when the order was executed. Current: ${p.current_px?.toFixed(4) || 'loading'} — latest market price from yfinance.`} position="top" maxWidth={240}>
                      <div className="text-xs text-trading-textdim cursor-help">
                        @ {p.avg_entry_price?.toFixed(4)} → {p.current_px?.toFixed(4) || '—'}
                      </div>
                    </Tooltip>
                    <Tooltip content="Unrealised P&L = (current price − entry price) × quantity. This is included in your equity and Return score. Positions are marked to market every 2 seconds." position="top" maxWidth={250}>
                      <div className={`text-xs font-mono font-semibold cursor-help ${
                        (p.unrealized_pnl ?? 0) >= 0 ? 'text-trading-green' : 'text-trading-red'
                      }`}>
                        {formatPnl(p.unrealized_pnl)}
                      </div>
                    </Tooltip>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ---- Trade History ---- */}
      <div className="bg-trading-surface border border-trading-border rounded-xl p-4">
        <div className="flex items-center gap-1.5 mb-3">
          <h2 className="text-sm font-semibold text-trading-textdim uppercase tracking-wide">
            Trade History ({filteredTrades.length}/{trades.length})
          </h2>
          <Tooltip content="All orders dispatched by the competition engine. In dry-run mode, orders are simulated at market price with no real execution. Click a row to expand details or 'View' to open the full LLM analysis." position="bottom" maxWidth={270}>
            <Info className="w-3 h-3 text-trading-border hover:text-trading-textdim cursor-help transition-colors" />
          </Tooltip>
        </div>

        {/* Filters */}
        {trades.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            <select
              value={filterTicker}
              onChange={(e) => setFilterTicker(e.target.value)}
              className="px-2 py-1 text-xs bg-trading-surface2 border border-trading-border rounded text-trading-text focus:outline-none"
            >
              <option value="">All Tickers</option>
              {uniqueTickers.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <select
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="px-2 py-1 text-xs bg-trading-surface2 border border-trading-border rounded text-trading-text focus:outline-none"
            >
              <option value="">All Actions</option>
              {uniqueActions.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-2 py-1 text-xs bg-trading-surface2 border border-trading-border rounded text-trading-text focus:outline-none"
            >
              <option value="">All Statuses</option>
              {uniqueStatuses.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            {(filterTicker || filterAction || filterStatus) && (
              <button
                onClick={() => { setFilterTicker(''); setFilterAction(''); setFilterStatus(''); }}
                className="px-2 py-1 text-xs bg-trading-amber/10 border border-trading-amber text-trading-amber rounded hover:bg-trading-amber/20 transition-colors"
              >
                Clear Filters
              </button>
            )}
          </div>
        )}

        {trades.length === 0 ? (
          <p className="text-xs text-trading-textdim">No trades yet.</p>
        ) : filteredTrades.length === 0 ? (
          <p className="text-xs text-trading-textdim">No trades match the selected filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-trading-textdim border-b border-trading-border">
                  <th className="text-left py-2 px-2">
                    <Tooltip content="UTC timestamp when the order was dispatched to the broker/simulator." position="bottom">
                      <span className="cursor-help border-b border-dotted border-trading-textdim/40">Time</span>
                    </Tooltip>
                  </th>
                  <th className="text-left py-2 px-2">Ticker</th>
                  <th className="text-left py-2 px-2">
                    <Tooltip content="BUY = long entry or adding to position. SELL = short entry or closing a long. The direction comes from the Portfolio Manager's final rating." position="bottom">
                      <span className="cursor-help border-b border-dotted border-trading-textdim/40">Action</span>
                    </Tooltip>
                  </th>
                  <th className="text-right py-2 px-2">
                    <Tooltip content="USD notional value of the order (not units). Sized as a percentage of equity at signal time, capped by the competition firewall." position="bottom">
                      <span className="cursor-help border-b border-dotted border-trading-textdim/40">Size</span>
                    </Tooltip>
                  </th>
                  <th className="text-right py-2 px-2">
                    <Tooltip content="Fill price — the market price at time of dispatch (or broker fill price in live mode)." position="bottom">
                      <span className="cursor-help border-b border-dotted border-trading-textdim/40">Price</span>
                    </Tooltip>
                  </th>
                  <th className="text-left py-2 px-2">
                    <Tooltip content="Short excerpt from the Portfolio Manager's executive summary explaining why this trade was made." position="bottom">
                      <span className="cursor-help border-b border-dotted border-trading-textdim/40">Reason</span>
                    </Tooltip>
                  </th>
                  <th className="text-left py-2 px-2">
                    <Tooltip content="Link to the full multi-agent analysis that produced this signal, including all analyst reports and the bull/bear debate." position="bottom">
                      <span className="cursor-help border-b border-dotted border-trading-textdim/40">Analysis</span>
                    </Tooltip>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredTrades.map((t) => {
                  const isExpanded = expandedTrade === t.order_id;
                  return (
                    <React.Fragment key={t.order_id}>
                      <tr
                        onClick={() => setExpandedTrade(isExpanded ? null : t.order_id)}
                        className="border-b border-trading-border/50 hover:bg-trading-surface2 cursor-pointer transition-colors"
                      >
                        <td className="py-2 px-2 text-trading-textdim font-mono">{formatTime(t.timestamp)}</td>
                        <td className="py-2 px-2">
                          <a
                            href={`https://finviz.com/quote.ashx?t=${t.ticker.replace(/[=X]/g, '')}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="font-mono text-trading-emerald hover:text-trading-text transition-colors underline"
                          >
                            {t.ticker}
                          </a>
                        </td>
                        <td className="py-2 px-2"><SignalBadge signal={t.action} size="sm" /></td>
                        <td className="py-2 px-2 text-right font-mono text-trading-text">{formatNotional(t.size_notional)}</td>
                        <td className="py-2 px-2 text-right font-mono text-trading-textdim">{t.fill_price?.toFixed(4) || '—'}</td>
                        <td className="py-2 px-2 text-trading-textdim max-w-48 truncate">{t.reason}</td>
                        <td className="py-2 px-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/competition/analysis/${t.analysis_id || t.ticker}`);
                            }}
                            className={`flex items-center gap-1 text-xs transition-colors ${t.analysis_id ? 'text-trading-emerald hover:text-trading-text' : 'text-trading-textdim hover:text-trading-amber'}`}
                            title={t.analysis_id ? 'View full analysis' : 'View latest analysis for this ticker'}
                          >
                            <ExternalLink className="w-3 h-3" />
                            {t.analysis_id ? 'View' : 'View Latest'}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-trading-surface2/50 border-b border-trading-border/50">
                          <td colSpan={7} className="py-3 px-4">
                            <div className="space-y-2 text-xs">
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <p className="text-trading-textdim font-semibold mb-1">Signal Confidence</p>
                                  <p className="font-mono text-trading-text">{(t.signal_confidence * 100).toFixed(0)}%</p>
                                </div>
                                <div>
                                  <p className="text-trading-textdim font-semibold mb-1">Status</p>
                                  <p className={`font-mono ${t.status === 'APPROVED' ? 'text-trading-emerald' : t.status === 'REJECTED' ? 'text-trading-red' : 'text-trading-amber'}`}>{t.status}</p>
                                </div>
                              </div>
                              {t.analysis_excerpt && (
                                <div>
                                  <p className="text-trading-textdim font-semibold mb-1">Analysis Excerpt</p>
                                  <p className="text-trading-textdim italic bg-trading-surface rounded p-2">{t.analysis_excerpt}</p>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ---- Footer ---- */}
      <div className="flex items-center justify-between text-xs text-trading-textdim">
        <div className="flex items-center gap-1.5">
          <Clock className="w-3 h-3" />
          <span>Engine uptime: {uptime || '—'}</span>
        </div>
        <span>Last updated: {formatTime(state.last_updated)} · refreshes every 2s</span>
      </div>
    </div>
  );
}

// ---- Small helper component ----
function ScoreCard({ icon: Icon, label, value, color, sub, tooltip }: {
  icon: any; label: string; value: string; color: string; sub?: string; tooltip?: string;
}) {
  return (
    <div className="bg-trading-surface border border-trading-border rounded-xl p-3 flex items-center gap-3">
      <Icon className={`w-5 h-5 shrink-0 ${color}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1">
          <span className="text-xs text-trading-textdim truncate">{label}</span>
          {tooltip && (
            <Tooltip content={tooltip} position="bottom" maxWidth={220}>
              <Info className="w-3 h-3 text-trading-border hover:text-trading-textdim cursor-help shrink-0 transition-colors" />
            </Tooltip>
          )}
        </div>
        <div className={`text-sm font-bold font-mono truncate ${color}`}>{value}</div>
        {sub && <div className="text-xs text-trading-amber">{sub}</div>}
      </div>
    </div>
  );
}
