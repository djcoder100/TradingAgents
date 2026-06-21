# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test

```bash
pip install .                          # install the package
pytest                                 # run all tests
pytest tests/test_memory_log.py        # run a single test file
pytest tests/ -k "structured"          # run tests matching a keyword
```

The test suite uses three markers (`unit`, `integration`, `smoke`) and auto-sets dummy API keys via `conftest.py` so tests don't hang waiting for real credentials. Tests that need live LLM calls or network data should mock at the `create_llm_client` boundary (see the `mock_llm_client` fixture).

There is no lint or type-check step configured in the repo — only pytest.

## Architecture

TradingAgents is a **LangGraph**-based multi-agent trading simulation. Each trading day run executes a fixed pipeline of LLM agents, each backed by tool-calling nodes that fetch real market data. The pipeline is assembled as a `StateGraph(AgentState)` and compiled at startup; an invoke/stream call runs one ticker×date simulation end-to-end.

### Core pipeline order

1. **Analysts** (sequential, user-selectable subset of 4):
   - Market Analyst → Sentiment Analyst → News Analyst → Fundamentals Analyst
   - Each analyst uses `quick_thinking_llm` with tool-calling loops (conditional edges between agent ↔ tools → clear).
   - Each writes a prose report into `state["market_report"]`, `state["sentiment_report"]`, etc.
2. **Researcher debate** — Bull Researcher ↔ Bear Researcher loop (controlled by `max_debate_rounds`), then Research Manager synthesizes an investment plan using `deep_thinking_llm`.
3. **Trader** — Translates the investment plan into a concrete trade proposal (`quick_thinking_llm`).
4. **Risk debate** — Aggressive ↔ Conservative ↔ Neutral analysts loop (`max_risk_discuss_rounds`).
5. **Portfolio Manager** — Final approve/reject decision (`deep_thinking_llm`), writes `state["final_trade_decision"]`.

The debate loops are governed by `ConditionalLogic` in `tradingagents/graph/conditional_logic.py`. The graph wiring is in `tradingagents/graph/setup.py`.

### Key architectural facts

- **Two LLM instances**: `deep_thinking_llm` for complex reasoning (Research Manager, Portfolio Manager) and `quick_thinking_llm` for everything else. Both always use the same provider configured in `config["llm_provider"]`.
- **Structured output**: The three decision agents (Research Manager, Trader, Portfolio Manager) use Pydantic schemas (`tradingagents/agents/schemas.py`) with provider-native structured-output modes. A render helper converts the parsed model back to markdown so downstream agents and reports consume the same format.
- **Data vendor routing**: `tradingagents/dataflows/interface.py` routes all data calls through a vendor abstraction (yfinance default, alpha_vantage optional) with automatic fallback. Tool-level vendor config overrides category-level config.
- **Memory/reflection**: After each run, the final decision is logged to `~/.tradingagents/memory/trading_memory.md`. The next run for the same ticker resolves past decisions against actual returns, generates reflections, and injects them into the Portfolio Manager prompt.
- **Checkpoint resume** (opt-in via `checkpoint_enabled` config): Uses LangGraph's `SqliteSaver` per ticker so a crashed run can resume from the last successful node. Checkpoints are cleared on successful completion.
- **Instrument identity**: Before any agent runs, `resolve_instrument_identity()` does a deterministic yfinance lookup (cached) to establish what company the ticker actually refers to. This context string is injected into every agent prompt to prevent hallucinated company identities.
- **Configuration**: `tradingagents/default_config.py` is the single source of truth. `TRADINGAGENTS_*` env vars override corresponding config keys (the mapping is the `_ENV_OVERRIDES` dict). The CLI can also set overrides.
- **Multi-market benchmarks**: `benchmark_map` in config auto-resolves the alpha benchmark per exchange suffix (Nikkei for `.T`, Nifty for `.NS`, etc.) so the memory log reflection computes alpha vs the correct regional index. `benchmark_ticker` overrides for all tickers.

### Directory map

| Directory | Purpose |
|---|---|
| `tradingagents/graph/` | LangGraph graph assembly, conditional routing, state init, reflection |
| `tradingagents/agents/analysts/` | 4 analyst agent factories (market, sentiment, news, fundamentals) |
| `tradingagents/agents/researchers/` | Bull/bear debate agent factories |
| `tradingagents/agents/managers/` | Research Manager and Portfolio Manager agent factories |
| `tradingagents/agents/risk_mgmt/` | Aggressive/conservative/neutral risk debater factories |
| `tradingagents/agents/trader/` | Trader agent factory |
| `tradingagents/agents/utils/` | Shared state types, tool definitions, memory log, rating enum, structured-output helpers |
| `tradingagents/dataflows/` | Data vendor abstraction layer (yfinance + alpha_vantage + fallback routing) |
| `tradingagents/llm_clients/` | Provider-specific LLM client factories (OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen, GLM, MiniMax, OpenRouter, Ollama, Azure) |
| `cli/` | Typer-based interactive CLI with Rich TUI, message buffering, and progress display |
| `tests/` | Pytest suite with conftest fixtures for dummy API keys and mock LLM clients |

### Configuration keys worth knowing

- `llm_provider`, `deep_think_llm`, `quick_think_llm` — provider and model selection
- `backend_url` — override the API endpoint (set per-provider by the CLI; `None` = use provider default)
- `max_debate_rounds`, `max_risk_discuss_rounds` — control debate loop depth
- `data_vendors` / `tool_vendors` — per-category and per-tool vendor routing (e.g., `"fundamental_data": "alpha_vantage"`)
- `output_language` — language for analyst reports and final decision (internal agent debate stays in English)
- `news_article_limit`, `global_news_article_limit`, `global_news_lookback_days` — control prompt token usage
- `benchmark_ticker`, `benchmark_map` — alpha calculation baseline
- `temperature` — cross-provider sampling temperature (forwarded to every LLM client when set)

### Adding a new analyst

1. Create the agent factory in `tradingagents/agents/analysts/` (returns a callable node).
2. Register it in `tradingagents/agents/__init__.py`.
3. Add a spec entry in `tradingagents/graph/analyst_execution.py` (`ANALYST_NODE_SPECS`).
4. Add factory + wiring in `tradingagents/graph/setup.py`.
5. Add a conditional edge method in `tradingagents/graph/conditional_logic.py`.
6. Add the report field to `AgentState` in `tradingagents/agents/utils/agent_states.py`.
7. Update `tradingagents/graph/trading_graph.py` state logging.

### Adding a new LLM provider

1. Create a client class in `tradingagents/llm_clients/` extending `base_client.BaseLLMClient` (implements `get_llm()`).
2. Register in `tradingagents/llm_clients/factory.py`'s provider dispatch.
3. Add `api_key_env` mapping in `tradingagents/llm_clients/api_key_env.py` for auto-detection.
4. Add models to `tradingagents/llm_clients/model_catalog.py`.
