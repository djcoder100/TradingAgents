# Competition Trading Engine

TradingAgents as a signal generator behind a strict risk-containment firewall, built for the June 21–24 trading competition.

## What it does

```
┌─────────────────────────────────────────────────────────────────┐
│  Every 7s:  Poll broker → check exits → check entries → audit   │
│  Every 15m: Record equity snapshot, refresh LLM signals,        │
│             compute Return / MaxDD / Sharpe, check compliance   │
└─────────────────────────────────────────────────────────────────┘
```

**Two signal modes:**

| Mode | Flag | How it works |
|---|---|---|
| **LLM signals** | *(default)* | Runs TradingAgents multi-agent pipeline every 15 min on the top 5 instruments. Portfolio Manager produces directional calls (Buy/Sell) + price targets. Entry/exit timing uses RSI, MACD, Bollinger Bands. |
| **Indicator-only** | `--no-llm` | No LLM calls. SMA5/SMA20 crossover for direction. Same RSI/MACD/BB entry timing. No API key needed. |

**Risk firewall:** Every order passes through `ExecutionEngine.verify_and_route()` before dispatch. Leverage capped at 25x (penalty at 28x). Margin blocked at 80% (penalty at 90%). Nothing reaches the broker without passing these checks.

## Competition instruments

The competition is **FX, metals, and crypto only** — no equities. The final list drops when the system goes live on June 21.

| Category | Count | Examples |
|---|---|---|
| Forex majors | 7 | EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD |
| Forex crosses | 18 | EURGBP, EURJPY, GBPJPY, EURCHF, AUDJPY, NZDJPY, CADJPY, etc. |
| Precious metals | 2 | XAUUSD (Gold), XAGUSD (Silver) |
| Crypto/USD | 5 | BTCUSD, ETHUSD, SOLUSD, XRPUSD, DOGEUSD |
| **Total** | **30+** | Full list confirmed when system goes live |

**Priority per strategy brief:** Gold (XAUUSD) first, then FX majors, then crypto.

```bash
# Test with priority instruments
uv run competition --mock --dry-run --instruments XAUUSD
uv run competition --mock --dry-run --instruments XAUUSD,EURUSD,GBPUSD

# Full competition set (all 30+ from config)
uv run competition --mock --dry-run
```

## Quick start

```bash
# 1. No API key needed — indicator-only mode with simulated trading
uv run competition --mock --dry-run --no-llm --instruments XAUUSD,EURUSD

# 2. With LLM signals — reads provider/key from .env automatically
uv run competition --mock --dry-run --instruments XAUUSD,EURUSD

# 3. Live mock trading (simulated fills, real P&L tracking)
uv run competition --mock --no-llm --instruments XAUUSD --log-level DEBUG
```

## Environment setup

The engine uses the same `.env` file as TradingAgents (project root). See `.env.example` for the full template.

### `.env` — LLM provider configuration

```bash
# Pick one provider — uncomment its block and set the API key.

# --- DeepSeek ---
DEEPSEEK_API_KEY=sk-...
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_QUICK_THINK_LLM=deepseek-v4-flash      # analysts, trader
TRADINGAGENTS_DEEP_THINK_LLM=deepseek-v4-pro          # research mgr, portfolio mgr

# --- Anthropic ---
#ANTHROPIC_API_KEY=sk-ant-...
#TRADINGAGENTS_LLM_PROVIDER=anthropic
#TRADINGAGENTS_QUICK_THINK_LLM=claude-sonnet-4-6
#TRADINGAGENTS_DEEP_THINK_LLM=claude-opus-4-8

# --- OpenAI ---
#OPENAI_API_KEY=sk-...
#TRADINGAGENTS_LLM_PROVIDER=openai
#TRADINGAGENTS_QUICK_THINK_LLM=gpt-5.4-mini
#TRADINGAGENTS_DEEP_THINK_LLM=gpt-5.5
```

The `.env` is loaded automatically when the engine starts — no need to `source` or `export`. Full model catalog at `tradingagents/llm_clients/model_catalog.py`.

### Environment variable overrides

All `TRADINGAGENTS_*` env vars from the main project work here too:

| Variable | Controls |
|---|---|
| `TRADINGAGENTS_LLM_PROVIDER` | Provider: `openai`, `anthropic`, `deepseek`, `google`, `xai`, etc. |
| `TRADINGAGENTS_QUICK_THINK_LLM` | Model for analysts and trader |
| `TRADINGAGENTS_DEEP_THINK_LLM` | Model for research manager and portfolio manager |
| `TRADINGAGENTS_LLM_BACKEND_URL` | Custom API endpoint (proxy, Ollama, etc.) |
| `TRADINGAGENTS_TEMPERATURE` | Sampling temperature (e.g. `0.0` for more deterministic) |
| `TRADINGAGENTS_MAX_DEBATE_ROUNDS` | Bull/bear debate depth (default: 1) |
| `TRADINGAGENTS_MAX_RISK_ROUNDS` | Risk analyst debate depth (default: 1) |
| `COMPETITION_INSTRUMENTS` | Comma-separated instrument override (e.g. `XAUUSD,EURUSD`) |

## CLI reference

```
uv run competition [flags]
```

| Flag | Default | Description |
|---|---|---|
| `--mock` | on | Use simulated broker ($1M account, synthetic prices) |
| `--dry-run` | off | Run loop but don't place orders — log what *would* happen |
| `--no-llm` | off | Skip TradingAgents LLM calls, use indicator-only signals |
| `--instruments XAUUSD,...` | 30+ pairs | Comma-separated instrument list |
| `--max-positions N` | 8 | Maximum concurrent open positions |
| `--log-level LEVEL` | INFO | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--llm-provider X` | from .env | Override provider |
| `--quick-model X` | from .env | Override quick-thinking model |
| `--deep-model X` | from .env | Override deep-thinking model |
| `--backend-url URL` | from .env | Override API endpoint |

## Architecture

```
competition/
├── main.py              # Entry point, arg parsing, component wiring
├── engine.py            # Main loop: fetch → exits → entries → refresh → audit
├── risk_firewall.py     # ExecutionEngine — pre-trade leverage/margin enforcement
├── signal_adapter.py    # TradingAgents PortfolioDecision → TradeSignal
├── indicator_signals.py # RSI/MACD/Bollinger entry/exit timing (no LLM)
├── api_client.py        # AbstractBrokerClient + MockBrokerClient
├── state_tracker.py     # Positions, 15-min equity snapshots, compliance audit
├── scheduler.py         # Time-based cadence (7s poll, 15min refresh)
├── config.py            # Risk limits, instrument list, competition schedule
└── models.py            # Pydantic schemas (AccountState, RegulatedOrder, etc.)
```

## Analyst configuration

Control which TradingAgents analysts run via `.env`:

```bash
# Default (fast — market + fundamentals only)
COMPETITION_ANALYSTS=market,fundamentals

# Full suite (slower — all four analysts + news/sentiment data)
COMPETITION_ANALYSTS=market,social,news,fundamentals

# Minimal (fastest — market only)
COMPETITION_ANALYSTS=market
```

| Analyst | What it does | Speed |
|---|---|---|
| `market` | Price action, technicals, trend analysis | Fast |
| `fundamentals` | Balance sheet, income, cash flow, ratios | Fast |
| `social` | Social media sentiment (Reddit, StockTwits) | Slow — adds 30-60s, rate-limited |
| `news` | News articles and insider transactions | Slow — adds 30-60s |

All four analysts feed into the same debate → trader → risk → portfolio manager pipeline. The research and risk teams always run regardless of analyst selection.

## Web dashboard

No extra env settings needed — the dashboard reads whatever provider/keys are already in your root `.env`.

**Terminal 1 — Engine + API server:**
```bash
uv run competition --mock --dry-run --web --instruments XAUUSD,EURUSD --no-llm
```

**Terminal 2 — Frontend dev server:**
```bash
cd frontend && npm run dev
```

Then open **http://localhost:5173/competition**

The `--no-llm` flag skips LLM costs for testing. Remove it when you want real TradingAgents signals:

```bash
uv run competition --mock --dry-run --web --instruments XAUUSD,EURUSD
```

The dashboard shows:
- **Scoreboard** — Return %, MaxDD %, Sharpe, equity, leverage, margin, snapshots, uptime
- **Active signals** — ticker, direction, confidence, size, expiry countdown, expandable analysis
- **Open positions** — ticker, P&L, entry/current price
- **Trade history** — every executed trade with the analysis that produced it
- **Compliance alerts** — penalty/disqualification warnings

### Competition rules enforced

| Rule | Limit | Firewall behavior |
|---|---|---|
| Leverage > 28x | 20-point penalty | MUTATE: cap order size to stay under 25x |
| Leverage > 30x | Disqualification | MUTATE + alert logged |
| Margin > 90% for 30 min | 20-point penalty | REJECT: block order at 80% |
| < 8 15-min snapshots | Sharpe capped at 50 | WARNING logged every 15 min |
| 500 req/s API limit | Safe harbor | 7s polling = 0.14 req/s |

### Scoring visibility

Every 15 minutes the engine logs your live competition metrics:

```
SCORING | Return: +2.35% | MaxDD: -1.12% | Sharpe: 1.84 | Snapshots: 12/8 | Leverage: 3.2x | Margin: 42.0% | Uptime: 02:15:03
```

## Running before the competition

Until the competition system goes live (June 21, 22:00 BST), run with `--mock` to test against simulated prices:

```bash
# Full dry run — test the whole pipeline without LLM costs
uv run competition --mock --dry-run --no-llm --log-level DEBUG

# With LLM signals — costs tokens but validates the full stack
uv run competition --mock --dry-run --instruments XAUUSD,EURUSD,BTCUSD
```

The mock broker starts with $1M equity and simulates fills at synthetic prices with realistic volatility per instrument class.
