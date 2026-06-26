# MT5 Integration Guide

This guide explains how to connect the competition trading engine to a live MetaTrader 5 account.

## Quick Start

### 1. Install MetaTrader5 Python Package

```bash
pip install MetaTrader5>=5.0.45
# or
uv pip install MetaTrader5
```

### 2. Set Environment Variables

Add to your `.env` file (or set as shell env vars):

```bash
# Required
MT5_ACCOUNT_NUMBER=your_numeric_account_id
MT5_PASSWORD=your_account_password
MT5_SERVER=broker.metatrader5.com       # Your broker's MT5 server

# Optional (with defaults)
MT5_ACCOUNT_TYPE=demo                   # 'demo' (default) or 'live'
MT5_TIMEOUT_S=10                        # Connection timeout
MT5_TERMINAL_PATH=/path/to/terminal     # If custom MT5 installation location

# Symbol overrides (if your broker uses different naming)
MT5_SYMBOL_OVERRIDES=BARUSD=HBAR        # Comma-separated: engine_symbol=broker_symbol
```

### 3. Run the Engine with MT5

```bash
# Start with real MT5 account (dry-run mode — no orders sent)
uv run competition --broker mt5 --dry-run --instruments XAUUSD,EURUSD

# Start with real MT5 account AND send real orders
uv run competition --broker mt5 --instruments XAUUSD,EURUSD
```

## Architecture

The MT5 integration follows the existing broker abstraction pattern:

```
┌─────────────────────────┐
│   CompetitionEngine     │  (generic, broker-agnostic)
│  (order logic, signals) │
└───────────┬─────────────┘
            │
    ┌───────┴─────────┐
    │                 │
┌───▼────────────┐  ┌─▼──────────────────┐
│ MockBrokerClient  │ MT5Client          │  (implements AbstractBrokerClient)
│ (simulated)       │ (live trading)      │
└────────────────┘  └──────┬─────────────┘
                           │
                    ┌──────┴──────────────┐
                    │                     │
                ┌───▼──────────┐  ┌──────▼───────┐
                │ MT5SymbolMapper│ MT5FillPoller │ (helper components)
                │ (BARUSD→HBAR) │ (async fills) │
                └───────────────┘  └──────────────┘
```

## Components

### `MT5Client` (main broker adapter)

Implements `AbstractBrokerClient` interface:
- `get_account_state()` — Returns equity, margin, leverage
- `get_positions()` — Returns open positions
- `get_prices()` — Returns bid/ask midpoints
- `place_order()` — Submits buy/sell orders
- `cancel_order()` — Cancels pending limit orders
- `get_order_status()` — Checks order fill status

Built-in resilience:
- `is_connected()` — Health checks every 30s
- `reconnect()` — Auto-reconnect on network failure
- `call_with_retry()` — Exponential backoff (2s → 4s → 8s... capped at 30s)

### `MT5SymbolMapper`

Handles broker-specific symbol naming:
1. Check explicit overrides (e.g., `BARUSD=HBAR`)
2. Use default mappings (EURUSD → EURUSD, XAUUSD → XAUUSD)
3. Fall back to engine ticker as-is

Example:
```python
mapper.engine_to_mt5("BARUSD")  # Returns "HBAR" (if override set)
mapper.engine_to_mt5("EURUSD")  # Returns "EURUSD" (default)
```

### `MT5FillPoller`

Background thread that polls for order fills:
- Checks order status every 1 second
- Detects when limit orders fill
- Invokes callback to update order status
- Runs in daemon thread (stops when engine stops)

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MT5_ACCOUNT_NUMBER` | Yes | — | Numeric account ID (e.g., `123456`) |
| `MT5_PASSWORD` | Yes | — | Account password |
| `MT5_SERVER` | Yes | — | Broker server (e.g., `MetaQuotes-Demo` or `broker.metatrader5.com`) |
| `MT5_ACCOUNT_TYPE` | No | `demo` | `demo` or `live` |
| `MT5_TIMEOUT_S` | No | `10` | Connection timeout in seconds |
| `MT5_TERMINAL_PATH` | No | None | Path to MetaTrader5 terminal (auto-detect if None) |
| `MT5_SYMBOL_OVERRIDES` | No | None | Comma-separated overrides: `BARUSD=HBAR,CUSTOM=NATIVE` |

### Command-Line Flags

```bash
uv run competition --broker mt5           # Use MT5 broker
uv run competition --broker mt5 --dry-run # MT5 but don't send orders
uv run competition --instruments XAUUSD,EURUSD  # Trade only these symbols
```

## Error Handling

### Common Issues

**"Failed to initialize MT5 connection"**
- Check `MT5_ACCOUNT_NUMBER`, `MT5_PASSWORD`, `MT5_SERVER` are set correctly
- Ensure MetaTrader5 is installed: `pip install MetaTrader5`
- Verify your broker's MT5 server address

**"Symbol not found on broker: EURUSD"**
- Check symbol name is correct for your broker
- Use `MT5_SYMBOL_OVERRIDES` to map to broker's symbol name
- Example: `MT5_SYMBOL_OVERRIDES=EURUSD=EURUSD=X` (if broker uses `=X` suffix)

**"Order rejected: Insufficient margin"**
- Reduce `--max-positions` or increase account equity
- Position sizing respects the firewall's margin rules
- Watch for margin warnings in logs

**"Limit order never fills"**
- Check price is within bid/ask spread
- Review order status: `get_order_status(order_id)`
- Verify broker allows pending orders (some restrict at certain times)

## Testing

### Demo Account Testing (Recommended)

1. Create a demo account on your broker
2. Set `MT5_ACCOUNT_TYPE=demo` in `.env`
3. Run with `--dry-run` first:
   ```bash
   uv run competition --broker mt5 --dry-run --instruments XAUUSD
   ```
4. Verify signals and order logic without risking funds
5. Once confident, remove `--dry-run` for paper trading

### Dry-Run Mode

Even with MT5 broker, `--dry-run` prevents orders from being sent:
```bash
uv run competition --broker mt5 --dry-run
```

This is useful for:
- Testing order placement logic
- Debugging symbol mapping issues
- Verifying connection resilience
- Before switching to real trading

## Monitoring

### Live Logs

The engine logs all MT5 operations:

```
[INFO] ✓ Connected to MT5: Demo Account (equity=10000.00, margin_free=9999.50)
[INFO] Placing MARKET order: BUY XAUUSD 0.10 @ 2350.50 (notional: $235.05)
[INFO] ✓ Order placed: XAUUSD (order_id=12345678)
[INFO] ✓ Order 12345678 filled: XAUUSD @ 2350.52
[INFO] ✓ Connected to MT5: Demo Account (health check passed)
```

### Web Dashboard

The web dashboard (http://localhost:5173/competition) shows:
- **Signals**: Active buy/sell/hold signals with analysis
- **Positions**: Open positions with entry price, P&L
- **Trades**: Historical trades with execution price and status
- **Account**: Equity, margin usage, leverage

Run alongside engine:
```bash
uv run competition --broker mt5 --web --instruments XAUUSD
```

Then open http://localhost:5173/competition in browser.

## Production Checklist

Before going live on MT5:

- [ ] Test on demo account first (set `MT5_ACCOUNT_TYPE=demo`)
- [ ] Run with `--dry-run` to verify order logic
- [ ] Verify symbol mapping is correct for your broker
- [ ] Check margin requirements (firewall will reject over-leveraged orders)
- [ ] Monitor logs for connection issues (auto-reconnect should handle brief disconnections)
- [ ] Start with 1 instrument (`--instruments XAUUSD`) before expanding
- [ ] Verify dashboard is accessible (http://localhost:8000/api/competition/state)
- [ ] Set up log monitoring/alerting for errors
- [ ] Define max positions and position sizing via firewall config
- [ ] Create backup plan if connection drops (manual intervention?)

## Advanced: Custom Symbol Mapping

If your broker uses non-standard symbol names, map them explicitly:

```bash
# In .env
MT5_SYMBOL_OVERRIDES=BARUSD=HBAR,EURUSD=EUR/USD,GOLD=XAUUSD
```

The mapper will:
1. Translate engine ticker to broker symbol before API calls
2. Cache contract specs (volume min, tick size, etc.)
3. Fall back to engine ticker if symbol not found

## Troubleshooting

### Enable Debug Logging

```bash
uv run competition --broker mt5 --log-level DEBUG
```

This shows:
- Every MT5 API call
- Order placement details
- Symbol mapping decisions
- Fill detection events

### Check MT5 Connection Status

Add this to your terminal:
```bash
python3 -c "
import MetaTrader5 as mt5
if mt5.initialize():
    info = mt5.account_info()
    print(f'Connected: {info.name if info else \"No account info\"}')
else:
    print('Not connected')
"
```

### Verify Symbol is Tradeable

```bash
python3 -c "
import MetaTrader5 as mt5
mt5.initialize()
info = mt5.symbol_info('XAUUSD')
if info:
    print(f'Symbol found: {info.name}')
    print(f'  Bid: {info.bid}, Ask: {info.ask}')
    print(f'  Min volume: {info.volume_min}, Max: {info.volume_max}')
else:
    print('Symbol not found on this broker')
"
```

## Support

For issues:

1. **Enable DEBUG logs** → paste relevant logs
2. **Check MT5 directly** → verify connection outside the engine
3. **Verify credentials** → `MT5_ACCOUNT_NUMBER`, `MT5_PASSWORD`, `MT5_SERVER`
4. **Check .env** → make sure env vars are loaded correctly

---

**Ready to trade live?** Run:
```bash
uv run competition --broker mt5 --instruments XAUUSD,EURUSD,BARUSD
```

The engine will connect to MT5, refresh signals every 15 minutes, and send approved orders to your broker.
