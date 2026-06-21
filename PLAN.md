# Competition Engine — Development Plan & Change Log

This file tracks every design decision, bug fix, and feature addition to the competition engine and its web dashboard. Newest entries are at the top.

---

## 2026-06-21 — Startup Scripts & Documentation

### [FEATURE] Simple Start/Stop Scripts for Local Development
**Why**: Running engine + API + frontend manually in separate terminals is error-prone and hard to manage. A unified script handles startup order, port conflicts, process tracking, logging, and cleanup.

**Scripts created**:
- `scripts/competition-start.sh` — Main startup script with multiple modes:
  - `./scripts/competition-start.sh` — Start everything (engine + API + frontend), open browser
  - `./scripts/competition-start.sh --engine-only` — Engine only (for overnight runs or background testing)
  - `./scripts/competition-start.sh --web-only` — Dashboard only (view historical trades while engine is separate)
  - `./scripts/competition-start.sh --status` — Check which processes are running
  - `./scripts/competition-start.sh --stop` — Stop all processes cleanly
  
- `scripts/competition-stop.sh` — Convenience wrapper that calls `competition-start.sh --stop`

**Features**:
- Auto-saves PIDs to `.competition.pids` file for tracking
- Logs to `.logs/` directory (engine, web, frontend each get separate files)
- Auto-kills port conflicts before starting (graceful or forced)
- Waits for each service to be ready before proceeding (with health checks)
- Opens browser to dashboard automatically
- Graceful shutdown on Ctrl+C (cleans up all child processes)
- Loads config from `.env` automatically (centralizes all settings in one place)

**Files created**:
- `scripts/competition-start.sh` — Main startup orchestrator
- `scripts/competition-stop.sh` — Simple stop wrapper
- `COMPETITION_STARTUP.md` — User guide with examples and troubleshooting

**Usage**:
```bash
# Edit .env to configure (instruments, dry-run mode, which analysts, etc)
nano .env

# Start everything (loads all config from .env)
./scripts/competition-start.sh

# Engine only (for overnight runs)
./scripts/competition-start.sh --engine-only

# Check status
./scripts/competition-start.sh --status

# Stop
./scripts/competition-stop.sh
```

---

## 2026-06-21 — Enhanced Frontend Logging & Connection Status

### [FEATURE] Better Logging & Connection Diagnostics
**Why**: When the API is unavailable or slow, users see silent failures in Vite. Now all connection issues, retries, timeouts, and reconnects are logged to the browser console and displayed on screen.

**Console logging** (open browser DevTools: F12 → Console tab):
- `[Competition] Dashboard mounted, starting data poll` — on page load
- `[Competition] ✓ Connected to API (123ms)` — when connection succeeds  
- `[Competition] Connection refused (attempt 3) — Is the API running?` — on connection failure
- `[Competition] Request timeout (>10s) — API may be slow or unresponsive` — on timeout
- `[CompetitionAnalysis] Loading analysis: XAUUSD-8deef118` — when clicking into a trade's analysis
- `[CompetitionAnalysis] ✓ Loaded in 1234ms` — when analysis loads

**On-screen UI enhancements**:
- Live connection status badge in dashboard header (green dot = connected, amber pulsing = reconnecting with retry count)
- Error screen shows:
  - Last error message + timestamp
  - Troubleshooting steps (which commands to run)
  - Expected API endpoint URL
  - Note to check browser console for detailed logs

**Request reliability**:
- Added 10-second timeout on all API calls (prevents hanging on unresponsive servers)
- Track retry count and expose it in the UI
- Distinguish between connection refused vs timeout vs HTTP errors with specific messages

**Files changed**:
- `frontend/src/pages/Competition.tsx`:
  - Added `isConnected`, `lastError`, `retryCount` state tracking
  - Enhanced `fetchState()` with detailed error classification (ECONNREFUSED, timeout, HTTP errors)
  - Console logging on every state change and error
  - Added connection status badge in header (shows "Connected" or "Reconnecting (N)")
  - Improved error screen with last error, timestamp, and troubleshooting steps
- `frontend/src/pages/CompetitionAnalysis.tsx`:
  - Added console logging for analysis fetch lifecycle
  - Request timeout: 30 seconds (longer than state updates since analyses can be large)
  - Error classification and logging

---

## 2026-06-21 — Persistent Trade History & Web-Only Dashboard

### [FEATURE] Trade History Persists Across Engine Restarts
**Why**: Trade history was stored only in memory (`CompetitionStateBus`), so every engine restart cleared the dashboard. Now you can stop/start the engine and still see all past trades.

**How it works**:
- Trade history automatically saves to `~/.tradingagents/trade_history.json` whenever a trade is added
- On startup, `CompetitionStateBus` loads the persisted history from disk
- Last 500 trades are kept (in memory and on disk)

**Files changed**:
- `competition/state_bus.py`:
  - Added `_load_trade_history()` — loads trades from disk on init
  - Added `_save_trade_history()` — persists to JSON file
  - `add_trade()` now also calls `_save_trade_history()` (outside lock to avoid blocking)

### [FEATURE] `--web-only` Mode — View Dashboard While Engine Runs Separately
**Why**: You may want to run the engine in one terminal and the web dashboard in another, or keep the dashboard running while restarting the engine. The `--web-only` flag does exactly that.

**How to use**:
```bash
# Terminal 1: Run the engine (no web server)
uv run competition --instruments EURUSD,GBPUSD,XAUUSD

# Terminal 2: Run the web dashboard only (reads persisted state)
uv run competition --web-only
# Opens on http://0.0.0.0:8000
# Then: cd frontend && npm run dev (opens http://localhost:5173/competition)
```

**Files changed**:
- `competition/main.py`:
  - Added `--web-only` argument
  - Added early-exit logic: if `--web-only` is set, create state bus (loads persisted trades), start web server, exit
  - State bus is created fresh so it loads all historical trades from `~/.tradingagents/trade_history.json`

**Verified**:
- Trade history persists end-to-end: add trade → saved to disk → new instance loads it
- `--web-only` flag appears in CLI help
- Persisted files live at `~/.tradingagents/` (auto-created if needed)

### [FIX] Analysis Markdown Not Showing When Dashboard Runs Separately
**Why**: When running `--web-only`, the dashboard loaded historical trades but not the analysis markdown that produced them. Both `full_analysis` (detailed analysis per run) and `active_analysis` (latest markdown per ticker) were in-memory only.

**Fix**: Persist analysis to disk just like trade history:
- `full_analysis` (dict of `analysis_id → full TA output`) → `~/.tradingagents/full_analysis.json`
- `active_analysis` (dict of `ticker → latest PM markdown`) → `~/.tradingagents/active_analysis.json`

**Files changed**:
- `competition/state_bus.py`:
  - Added `_load_full_analysis()`, `_save_full_analysis()` (persists analysis markdown to disk)
  - Added `_load_active_analysis()`, `_save_active_analysis()` (persists latest-per-ticker markdown to disk)
  - `_init()` now loads all three: trade history, full analyses, and active analyses
  - `set_full_analysis()` and `set_analysis()` now also save to disk (outside lock to avoid blocking)

**Result**: 
- Engine writes analysis to disk as it runs
- `--web-only` dashboard loads persisted analysis on startup
- You can now restart the engine and still see all analysis + trades on the dashboard

---

## 2026-06-19 — Doubleword Inference Integration (Free Hackathon Credits)

### [FEATURE] Doubleword as LLM Backend via Pydantic AI / Logfire Gateway

**Why**: TradingAgents runs 12 LLM pipeline stages per instrument every 15 minutes. At competition pace (12 instruments × 4 analysts × ~15 min cadence) the OpenAI/DeepSeek direct API cost adds up quickly. Doubleword provides hackathon credits accessible through the Pydantic AI Logfire gateway — same OpenAI-compatible call shape, free for the competition.

**How it works**:
- Provider stays `deepseek` → TradingAgents uses `DeepSeekChatOpenAI` (handles chain-of-thought reasoning content correctly)
- `TRADINGAGENTS_LLM_BACKEND_URL` overrides the DeepSeek default endpoint to point at the Logfire gateway
- `DEEPSEEK_API_KEY` holds the Logfire key (`pylf_v2_eu_...`)
- Model IDs use Doubleword's catalog format (`deepseek-ai/DeepSeek-V4-Flash`, not `deepseek-v4-flash`)

**Key finding — gateway URL**: The Pydantic AI SDK uses `base_url + "/openai/" + route` internally, but the raw OpenAI SDK (and LangChain ChatOpenAI) needs `base_url = "https://gateway-eu.pydantic.dev/proxy/doubleword"` directly.

**Files changed**:
- `.env` — Updated provider config:
  ```
  TRADINGAGENTS_LLM_PROVIDER=deepseek
  TRADINGAGENTS_LLM_BACKEND_URL=https://gateway-eu.pydantic.dev/proxy/doubleword
  DEEPSEEK_API_KEY=pylf_v2_eu_...   # Logfire/Doubleword key — rotate after competition
  TRADINGAGENTS_QUICK_THINK_LLM=deepseek-ai/DeepSeek-V4-Flash
  TRADINGAGENTS_DEEP_THINK_LLM=deepseek-ai/DeepSeek-V4-Pro
  ```
  Old DeepSeek direct keys kept as comments for fallback.
- `tradingagents/llm_clients/model_catalog.py` — Added `deepseek-ai/DeepSeek-V4-Flash` and `deepseek-ai/DeepSeek-V4-Pro` to the `deepseek` provider known-model list (suppresses warn_if_unknown_model warning).

**Model assignments**:
| Role | Model | Reason |
|---|---|---|
| Quick (analysts, trader, risk) | `DeepSeek-V4-Flash` | Fast reasoning, cheap, sufficient for analysis |
| Deep (PM, Research Manager) | `DeepSeek-V4-Pro` | Higher reasoning quality for final decisions |

**Verified**: Both models respond correctly through TradingAgents' `create_llm_client` factory → `DeepSeekChatOpenAI` → Logfire gateway → Doubleword.

---

## 2026-06-19 — Engine Cleanup, Dashboard & Reconnect

### [FIX] Engine Bug Fixes (engine.py)
- **Dead variable**: Removed unused `status_label = result.status` (assigned but never read).
- **Redundant guard**: Inner `if self.state_bus and result.status == "FILLED":` check inside the outer `if result.status == "FILLED":` block was redundant — removed the inner check.
- **Wrong return type**: `_dispatch` annotated as `Optional[object]` — changed to `Optional[OrderResult]`. Added `OrderResult` to imports.
- **Missing pending-limit cleanup in `_generate_indicator_signals`**: Expired signals were pruned without cancelling their resting limit orders. Fixed to call `_cancel_pending_for_ticker(ticker)` before deletion.
- **FINAL log format mismatch**: Format string had 8 `%` placeholders but only 6 args (missing `intervals_needed` and `round_trip_count`). Fixed to include both.
- **Files changed**: `competition/engine.py`

### [FEATURE] Round-Trip Counter Exposed to Dashboard
- **Why**: `round_trip_count` was tracked in the engine but never surfaced to the web dashboard, so there was no way to know if you were on track for the Best Sharpe ≥30 gate.
- **Files changed**:
  - `competition/state_bus.py` — Added `round_trip_count: int = 0` field, `set_round_trip_count()` writer, and included `round_trip_count` in `snapshot()`.
  - `competition/engine.py` — `_publish_state()` now calls `bus.set_round_trip_count(self.round_trip_count)`.
  - `frontend/src/pages/Competition.tsx` — Added `round_trip_count` to `CompetitionState` type, added `Repeat2` icon import, replaced the Uptime ScoreCard with a **Round-trips N/30** card (amber at 15+, green at 30+, with tooltip). Uptime moved to the footer bar alongside "Last updated".

### [FEATURE] MT5 Reconnect Pattern on AbstractBrokerClient
- **Why**: Duncan confirmed that if the MT5 terminal disconnects, open positions remain open. The engine needs to handle transient disconnects gracefully rather than crashing or blocking.
- **Files changed**:
  - `competition/api_client.py` — Added three methods to `AbstractBrokerClient`:
    - `is_connected() -> bool` — override to check broker connection state.
    - `reconnect() -> bool` — override with broker-specific reconnect logic (e.g., MT5 `initialize()`).
    - `call_with_retry(fn, ..., max_attempts=3, backoff_s=2.0)` — wraps any broker call with exponential backoff (2s → 4s → 8s, capped at 30s). Calls `reconnect()` on each `ConnectionError`/`OSError`/`TimeoutError`. Concrete `MT5BrokerClient` should wrap every API call with this.

---

## 2026-06-19 — Competition Rules Compliance & Strategic Improvements

### [RULES] Limit Order Support (resting limits allowed per Duncan's clarification)
- **Why**: Duncan confirmed resting limit orders are permitted and fill by queue position. Previously we only fired market orders, paying the full spread on every entry. Limit orders save ~half-spread per trade and can collect the spread as maker.
- **Files changed**:
  - `competition/models.py` — Added `order_type: str = "MARKET"` and `limit_price: Optional[float] = None` to `RegulatedOrder`
  - `competition/indicator_signals.py` — `get_fast_signal()` now returns LIMIT orders using `signal.entry_price_target` as limit price, or mid ± 1 pip when no target is set. Exit orders remain MARKET (immediate close).
  - `competition/api_client.py` — `MockBrokerClient` gains a `_pending_limits` queue. LIMIT orders park there and fill on `tick_prices()` when the price crosses the limit. `cancel_order()` removes from pending queue. Market orders now simulate bid/ask half-spread (0.5 pip EURUSD, $0.15 Gold, $2 crypto).
  - `competition/engine.py` — Tracks pending limit orders per ticker in `_pending_limits`. Cancels stale limits before placing a new one for the same ticker. Cancels all pending limits when a signal expires.

### [RULES] Round-Trip Counter for Best Sharpe ≥30 Gate
- **Why**: Duncan confirmed Best Sharpe category requires ≥30 completed round-trips. No counter existed.
- **Files changed**:
  - `competition/engine.py` — Added `self.round_trip_count`. Incremented on every closing fill (`is_close=True`). Logged every 5 round-trips. Shown in 15-min SCORING line as `RoundTrips: N/30`.

### [RULES] Round Boundary Reset
- **Why**: Duncan confirmed Risk Discipline resets at the start of each round. Violations were accumulating forever.
- **Files changed**:
  - `competition/engine.py` — Added `reset_round()` method: clears `tracker.violations`, resets `round_trip_count`, cancels all pending limits. Call this when the organiser publishes exact round-start times.

### [RULES] BARUSD = HBAR/Hedera Added
- **Why**: Duncan confirmed BARUSD is the competition symbol for HBAR (Hedera). Was missing from all instrument lists.
- **Files changed**:
  - `competition/config.py` — Added `BARUSD` to `TEAM_A_INSTRUMENTS`. **Pending**: confirm exact contract_size, tick_size, volume_min from MT5 at login before trading it.
  - `competition/api_client.py` — Added mock seed price `BARUSD: 0.085` (placeholder — confirm at MT5 login).

### [STRATEGY] Instrument List Reorganised — Forex-First (Team A)
- **Why**: Default instrument list previously included BTCUSD, ETHUSD, SOLUSD which are Team B volatility territory. A single 15-min ±20% crypto spike will crush the Std denominator and tank the Sharpe score, even if total return is higher.
- **Files changed**:
  - `competition/config.py` — Split into two lists:
    - `TEAM_A_INSTRUMENTS` (new default): 10 Forex majors/crosses + XAUUSD + BARUSD. High liquidity, low intraday vol, smooth equity curve → high Sharpe.
    - `ALL_INSTRUMENTS`: full universe including crypto.
  - Set `DEFAULT_INSTRUMENTS = TEAM_A_INSTRUMENTS`.
  - `COMPETITION_INSTRUMENTS=ALL` env var restores the full universe.

### [STRATEGY] Sharpe-Aware Position Sizing
- **Why**: MoMQ rules strategy guide explicitly describes this feedback loop: if Sharpe < 1.0, scale down sizes to reduce equity volatility (the Std denominator). Was not implemented.
- **Files changed**:
  - `competition/engine.py` — `_check_entries()` reads live `metrics.sharpe_ratio` on every entry tick. When `sharpe_ratio < 1.0`, all new order sizes are multiplied by 0.5 before firewall check. Logged at DEBUG level.

### [BUG] ATR Trailing Stop Was Dead Code Without a PM Stop Price
- **Why**: `check_exit_conditions()` only applied the ATR trailing stop when `signal.stop_loss` was already set. If the Portfolio Manager's markdown output didn't contain a stop-loss price (regex failed to parse one), neither the hard stop nor the trailing stop would ever fire — position had no downside protection.
- **Fix**: Restructured exit logic. ATR trailing stop now ALWAYS fires, anchored from `position.avg_entry_price ± ATR*multiplier`. Hard stop (if set) acts as an additional floor/ceiling but is no longer a prerequisite.
- **Files changed**:
  - `competition/indicator_signals.py` — Complete rewrite of `check_exit_conditions()`. Priority: (1) hard stop, (2) take-profit, (3) ATR trailing stop (unconditional), (4) time-stop on expiry.

---

## 2026-06-18 — Sharpe Formula & Scoring Corrections

### [BUG CRITICAL] Sharpe Formula Was Annualised — Should Be Raw
- **Why**: MoMQ §7 defines `Sharpe_i = Mean(r) / Std(r)` — a plain non-annualised ratio on 15-min returns. The code was multiplying by `sqrt(35040)` (annualisation factor for 15-min periods/year), producing a number ~187x too large. This would have given a wildly inflated Sharpe number that doesn't match the organiser's formula.
- **Files changed**:
  - `competition/state_tracker.py` line ~198: Removed `* math.sqrt(35040)`. Now: `sharpe = mean_ret / math.sqrt(var)`.

### [BUG] Sharpe Cap Counted Snapshots Instead of Return Observations
- **Why**: The MoMQ rule says "fewer than 8 valid 15-minute return observations". The first snapshot is a baseline (no return). So 9 snapshots = 8 returns. Code checked `n < 8` (snapshot count) meaning it would stop capping one return observation too early.
- **Files changed**:
  - `competition/state_tracker.py` — `sharpe_capped = len(returns) < MIN_15MIN_INTERVALS` (returns, not snapshots). `intervals_recorded` now reports `len(returns)` so the dashboard "2/8" display is meaningful against the 8-return threshold.

### [BUG] Dashboard Tooltip Weights Were Wrong
- **Why**: The dashboard tooltips said Return=50 pts, MaxDD=25 pts, Sharpe=25 pts. Actual MoMQ weights: Return=70%, MaxDD=15%, Sharpe=10%.
- **Files changed**:
  - `frontend/src/pages/Competition.tsx` — Corrected all three ScoreCard tooltips.

---

## 2026-06-18 — Competition Dashboard Tooltips

### [FEATURE] Hover Tooltips on All Competition Dashboard Labels
- **Why**: Metrics like MaxDD, Sharpe, Margin, Leverage are finance terms that need explanation for team members who aren't quants. Also helps during the competition to understand what each number means for the score.
- **New component**: `frontend/src/components/shared/Tooltip.tsx` — portal-based tooltip (no dependencies), supports top/bottom/left/right positioning, renders via `createPortal` so it's never clipped by overflow:hidden containers.
- **Files changed**:
  - `frontend/src/pages/Competition.tsx` — `ScoreCard` now accepts a `tooltip` prop. Added `ⓘ` Info icons to all 8 scoreboard cards, 5 section headers (Alerts, LLM Progress, Active Signals, Positions, Trade History), signal row inline values (confidence, notional, expiry), position row values (size, entry/current, unrealised PnL), and trade history column headers.

---

## 2026-06-18 — Analysis Detail Page & Stage Counter Fixes

### [BUG] Analysis Detail Page Returned 404 Despite Completed Pipeline
- **Why**: `web/api/competition.py` called `bus.get_full_analysis(ticker.upper())`, which converted `XAUUSD-8deef118` to `XAUUSD-8DEEF118`. The stored key uses lowercase hex from `uuid.uuid4().hex`. Lookup always missed.
- **Fix**: Removed `.upper()` from API call. `get_full_analysis()` already handles ticker-as-fallback with its own `.upper()` logic on the ticker portion.
- **Files changed**: `web/api/competition.py`

### [BUG] Stage Counter Went Over Total (Market Analyst Counted 5 Times)
- **Why**: LangGraph analyst nodes fire N+1 times per analyst (tool-calling loop: Analyst → tools → Analyst → tools → ... → Msg Clear). The progress callback was incrementing on every firing, causing "5/12 — Market Analyst" then immediately hitting the cap.
- **Fix**: Track `last_node[0]`. Only increment `step_counter` when the node name changes. Same analyst firing again (consecutive tool-calling loop iterations) updates the dashboard label but does not advance the counter.
- **Files changed**: `competition/signal_adapter.py` — Added `last_node = [None]` closure, changed `step_counter[0] = min(step_counter[0] + 1, total_stages)` to be conditional on `node_name != last_node[0]`.
- **Verified**: Simulated exact log sequence (Market×5, Sentiment×1, News×2, Fundamentals×2, Bull, Bear, RM, Trader, Aggressive, Conservative, Neutral, PM) → outputs 1–12 cleanly.

---

## 2026-06-18 — Analysis ID Tracking & Detail Page

### [FEATURE] Unique Analysis ID Per Pipeline Run
- **Why**: The URL `/competition/analysis/XAUUSD` is ambiguous — there could be many analyses for the same instrument. We need a unique ID per run so signal rows and trade history rows link to the exact analysis that produced them.
- **ID format**: `f"{ticker}-{uuid.uuid4().hex[:8]}"` e.g. `XAUUSD-8deef118`
- **Files changed**:
  - `competition/signal_adapter.py` — Generates `analysis_id`, builds full analysis result via `_build_full_analysis()`, stores in `state_bus.set_full_analysis(analysis_id, data)`. Returns `analysis_id` in the decision dict.
  - `competition/models.py` — `TradeSignal.analysis_id`, `TradeRecord.analysis_id` fields added.
  - `competition/engine.py` — Sets `signal.analysis_id` from decision; passes to `TradeRecord`.
  - `competition/state_bus.py` — `set_full_analysis(analysis_id, data)` stores by ID; `latest_analysis_id[ticker]` tracks the most recent run per ticker. `get_full_analysis()` looks up by analysis_id first, then falls back to ticker → latest ID.

### [FEATURE] Analysis Detail Page (`/competition/analysis/:analysisId`)
- **New page**: `frontend/src/pages/CompetitionAnalysis.tsx` — fetches `/api/competition/analysis/{analysisId}`, renders the full TradingAgents output via `<ResultsDashboard>`. Shows instrument name, signal badge, analysts used, research team credits.
- **Files changed**:
  - `frontend/src/App.tsx` — Added route `competition/analysis/:analysisId`.
  - `frontend/src/pages/Competition.tsx` — Signal rows navigate to `/competition/analysis/${s.analysis_id || s.ticker}`. Trade history rows have "View" button to the same URL.
  - `web/api/competition.py` — Added `GET /competition/analysis/{ticker}` endpoint.

---

## 2026-06-18 — LLM Analysis Progress Indicators

### [FEATURE] Stage-by-Stage Progress on Dashboard and in Logs
- **Why**: LLM pipeline takes 5-15 minutes. With no feedback, operators can't tell if the engine is stuck or working. Need live stage labels and progress bars.
- **Pipeline stages (12 total for all-4-analyst config)**:
  1. Market Analyst, 2. Sentiment Analyst, 3. News Analyst, 4. Fundamentals Analyst, 5. Bull Researcher, 6. Bear Researcher, 7. Research Manager, 8. Trader, 9. Risk: Aggressive, 10. Risk: Conservative, 11. Risk: Neutral, 12. Portfolio Manager
- **Streaming approach**: `trading_graph.py` `propagate()` accepts `progress_callback`. Dual-mode LangGraph streaming (`stream_mode=["updates","values"]`) — "updates" gives node names, "values" gives accumulated state. Tool nodes and Msg Clear nodes are filtered out.
- **Files changed**:
  - `tradingagents/graph/trading_graph.py` — Added `progress_callback=None` parameter; dual-mode streaming block.
  - `competition/signal_adapter.py` — Added `_NODE_LABELS`, `_compute_total_stages()`, `_on_node` closure.
  - `competition/state_bus.py` — Added `analysis_progress` dict; `set_analysis_progress()`, `clear_analysis_progress()`.
  - `frontend/src/pages/Competition.tsx` — Added "LLM Analysis In Progress" panel with pulsing dot, progress bar, stage label, step counter, and elapsed timer.

---

## 2026-06-18 — All 4 Analysts Enabled

### [CONFIG] Enable All Analysts by Default
- **Why**: Fundamentals, Sentiment, News analysts were disabled by default. All 4 are needed for a thorough competition analysis and to produce the MaxDD-protecting conservative thesis.
- **Files changed**:
  - `competition/config.py` — `_ANALYSTS_ENV` default changed from `"market,fundamentals"` to `"market,social,news,fundamentals"`.
  - `.env` — `COMPETITION_ANALYSTS=market,social,news,fundamentals` uncommented.

---

## 2026-06-18 — XAUUSD 404 Symbol Normalisation Fixes

### [BUG] XAUUSD 404 in `yfinance_news.py`
- **Why**: `get_news_yfinance()` called `yf.Ticker(ticker)` with the raw broker symbol. Yahoo Finance uses `GC=F` for gold, not `XAUUSD`.
- **Files changed**: `tradingagents/dataflows/yfinance_news.py` — Added `normalize_symbol()` call before `yf.Ticker()`.

### [BUG] XAUUSD 404 in `trading_graph.py` `_fetch_returns()`
- **Why**: `_fetch_returns()` called `yf.Ticker(ticker)` and `yf.Ticker(benchmark)` directly without normalising.
- **Files changed**: `tradingagents/graph/trading_graph.py` — Wrapped both in `normalize_symbol()`.

---

## Pending / Known Gaps

| Item | Status | Notes |
|---|---|---|
| Exact round boundaries | Waiting | Wire `engine.reset_round()` to scheduler once Duncan publishes round times |
| MT5 reconnect logic | Not implemented | Add retry/backoff to live `MT5BrokerClient`; positions persist on disconnect (confirmed by Duncan) |
| BARUSD contract spec | Waiting | Confirm volume_min, tick_size, contract_size at MT5 login. Do not trade until confirmed. |
| Sharpe definition (population vs sample std) | Minor ambiguity | Using sample std (n-1) which is statistically correct; organiser hasn't specified |
| Best Sharpe ≥30 — "round-trip" definition | Waiting | Counting open+close fills; confirm whether organiser counts legs or round-trips |
| Stop-out exact mechanics | Confirmed mild | Duncan: "reaching stop-out level means effectively out." Stay below 25x leverage / 80% margin |
| Test env vs live env differences | Unknown | Duncan: "live environment may differ." Do not assume test fills = live fills |

---

*Last updated: 2026-06-19 (session 2)*
