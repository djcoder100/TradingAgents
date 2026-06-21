# competition/indicator_signals.py
"""Fast technical indicator-based entry/exit timing.

No LLM calls — uses yfinance + stockstats for sub-second indicator lookup.
Confirms or gates the TradingAgents signal based on short-term price action.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from competition.models import TradeSignal, RegulatedOrder, Position, OrderAction
from competition.config import RSI_OVERSOLD, RSI_OVERBOUGHT, ATR_STOP_MULTIPLIER

logger = logging.getLogger(__name__)


class IndicatorSignals:
    """Confirms LLM-generated TradeSignals with technical timing indicators."""

    # ------------------------------------------------------------------
    # Entry gating
    # ------------------------------------------------------------------

    @staticmethod
    def get_fast_signal(
        ticker: str, signal: TradeSignal
    ) -> Optional[RegulatedOrder]:
        """Check whether now is a good time to enter based on the signal.

        Returns a RegulatedOrder if entry conditions are met, None to wait.
        """
        if signal.is_expired():
            logger.debug("Signal for %s expired, skipping entry check", ticker)
            return None

        df = _fetch_recent_data(ticker, period="5d", interval="1m")
        if df is None or df.empty:
            return None  # can't confirm — wait for next tick

        latest = df.iloc[-1]
        rsi = _calc_rsi(df, period=14)
        macd, macd_signal_line = _calc_macd(df)
        bb_upper, bb_middle, bb_lower = _calc_bollinger(df)

        if signal.action == OrderAction.BUY:
            if not _confirm_buy(rsi, macd, macd_signal_line, latest, bb_lower):
                return None
        elif signal.action == OrderAction.SELL:
            if not _confirm_sell(rsi, macd, macd_signal_line, latest, bb_upper):
                return None
        else:
            return None

        # Entry confirmed — use a resting LIMIT order at the signal's entry target
        # (or slightly inside the mid price) to get a better fill than a market order.
        # Per competition rules, resting limit orders are permitted and fill by queue position.
        mid = float(latest["Close"])
        if signal.entry_price_target is not None:
            limit_px = signal.entry_price_target
        elif signal.action == OrderAction.BUY:
            limit_px = round(mid * 0.9999, 6)   # post ~1 pip below mid
        else:
            limit_px = round(mid * 1.0001, 6)   # post ~1 pip above mid

        return RegulatedOrder(
            action=signal.action,
            ticker=ticker,
            order_size_notional=signal.order_size_notional,
            order_type="LIMIT",
            limit_price=limit_px,
        )

    # ------------------------------------------------------------------
    # Exit conditions
    # ------------------------------------------------------------------

    @staticmethod
    def check_exit_conditions(
        position: Position,
        current_px: float,
        signal: Optional[TradeSignal] = None,
    ) -> Optional[RegulatedOrder]:
        """Return a closing order if any exit condition is met.

        Exit priority (first match wins):
          1. Hard stop-loss (PM-provided explicit price)
          2. Take-profit (PM-provided target)
          3. ATR trailing stop — always active, with or without a PM stop price.
             Uses avg_entry_price ± ATR*multiplier as the floor/ceiling so every
             position has a backstop even when the LLM gives no stop price.
          4. Time-stop: signal expired and position is losing money.
        """
        if position.direction == OrderAction.BUY:
            exit_action = OrderAction.SELL
        else:
            exit_action = OrderAction.BUY  # close short

        def _exit():
            return RegulatedOrder(
                action=exit_action,
                ticker=position.ticker,
                order_size_notional=position.size_notional,
            )

        # 1. Hard stop-loss (explicit price from PM markdown)
        if signal and signal.stop_loss:
            if position.direction == OrderAction.BUY and current_px <= signal.stop_loss:
                logger.debug("%s hard stop-loss hit at %.5f (stop=%.5f)", position.ticker, current_px, signal.stop_loss)
                return _exit()
            elif position.direction == OrderAction.SELL and current_px >= signal.stop_loss:
                logger.debug("%s hard stop-loss hit at %.5f (stop=%.5f)", position.ticker, current_px, signal.stop_loss)
                return _exit()

        # 2. Take-profit hit
        if signal and signal.take_profit:
            if position.direction == OrderAction.BUY and current_px >= signal.take_profit:
                logger.debug("%s take-profit hit at %.5f (tp=%.5f)", position.ticker, current_px, signal.take_profit)
                return _exit()
            elif position.direction == OrderAction.SELL and current_px <= signal.take_profit:
                logger.debug("%s take-profit hit at %.5f (tp=%.5f)", position.ticker, current_px, signal.take_profit)
                return _exit()

        # 3. ATR trailing stop — always fires regardless of whether signal has stop_loss.
        #    Anchors from avg_entry_price so the stop can only move in the profitable
        #    direction (ratchet), keeping max loss bounded to ~ATR*multiplier from entry.
        df = _fetch_recent_data(position.ticker, period="5d", interval="1m")
        if df is not None and not df.empty:
            atr = _calc_atr(df, period=14)
            if atr:
                trail_distance = atr * ATR_STOP_MULTIPLIER
                if position.direction == OrderAction.BUY:
                    # Floor = best of (entry - trail) and (hard stop if given)
                    floor = position.avg_entry_price - trail_distance
                    if signal and signal.stop_loss:
                        floor = max(floor, signal.stop_loss)
                    trailing_stop = max(floor, current_px - trail_distance)
                    if current_px <= trailing_stop:
                        logger.debug(
                            "%s ATR trailing stop hit at %.5f (trail=%.5f, atr=%.5f)",
                            position.ticker, current_px, trailing_stop, atr,
                        )
                        return _exit()
                else:  # SELL / short
                    ceiling = position.avg_entry_price + trail_distance
                    if signal and signal.stop_loss:
                        ceiling = min(ceiling, signal.stop_loss)
                    trailing_stop = min(ceiling, current_px + trail_distance)
                    if current_px >= trailing_stop:
                        logger.debug(
                            "%s ATR trailing stop hit at %.5f (trail=%.5f, atr=%.5f)",
                            position.ticker, current_px, trailing_stop, atr,
                        )
                        return _exit()

        # 4. Time-stop: signal expired and position is flat or losing
        if signal and signal.is_expired():
            if position.unrealized_pnl is not None and position.unrealized_pnl <= 0:
                logger.debug("%s time-stop: signal expired, pnl=%.2f", position.ticker, position.unrealized_pnl)
                return _exit()

        return None


# ---------------------------------------------------------------------------
# Internal: data fetching + indicator calculation
# ---------------------------------------------------------------------------

def _fetch_recent_data(
    ticker: str, period: str = "5d", interval: str = "1m"
) -> Optional[pd.DataFrame]:
    """Fetch recent OHLCV data. Returns DataFrame or None on failure."""
    try:
        import yfinance as yf
        from tradingagents.dataflows.symbol_utils import normalize_symbol

        canonical = normalize_symbol(ticker)
        t = yf.Ticker(canonical)
        df = t.history(period=period, interval=interval)
        if df.empty:
            return None
        return df
    except Exception as exc:
        logger.debug("Failed to fetch %s data for indicators: %s", ticker, exc)
        return None


def _calc_rsi(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """Compute RSI for the most recent bar."""
    if len(df) < period + 1:
        return None
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    val = rsi.iloc[-1]
    return float(val) if not pd.isna(val) else None


def _calc_macd(df: pd.DataFrame) -> tuple[Optional[float], Optional[float]]:
    """Return (MACD line, signal line) for the most recent bar."""
    if len(df) < 26:
        return None, None
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return (
        float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None,
        float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else None,
    )


def _calc_bollinger(
    df: pd.DataFrame, period: int = 20, num_std: float = 2.0
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (upper, middle, lower) Bollinger Band values."""
    if len(df) < period:
        return None, None, None
    middle = df["Close"].rolling(window=period).mean()
    std = df["Close"].rolling(window=period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return (
        float(upper.iloc[-1]) if not pd.isna(upper.iloc[-1]) else None,
        float(middle.iloc[-1]) if not pd.isna(middle.iloc[-1]) else None,
        float(lower.iloc[-1]) if not pd.isna(lower.iloc[-1]) else None,
    )


def _calc_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """Compute Average True Range."""
    if len(df) < period + 1:
        return None
    high, low, close = df["High"], df["Low"], df["Close"].shift(1)
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    val = atr.iloc[-1]
    return float(val) if not pd.isna(val) else None


# ---------------------------------------------------------------------------
# Entry confirmation rules
# ---------------------------------------------------------------------------

def _confirm_buy(
    rsi: Optional[float],
    macd: Optional[float],
    macd_signal: Optional[float],
    latest: pd.Series,
    bb_lower: Optional[float],
) -> bool:
    """Return True if conditions favor a BUY entry."""
    score = 0

    # RSI: oversold bounce
    if rsi is not None and rsi < RSI_OVERSOLD:
        score += 2
    elif rsi is not None and rsi < 50:
        score += 1

    # MACD: bullish cross or above signal
    if macd is not None and macd_signal is not None and macd > macd_signal:
        score += 1

    # Price near lower Bollinger → support
    if bb_lower is not None and latest["Close"] <= bb_lower * 1.01:
        score += 1

    return score >= 2


def _confirm_sell(
    rsi: Optional[float],
    macd: Optional[float],
    macd_signal: Optional[float],
    latest: pd.Series,
    bb_upper: Optional[float],
) -> bool:
    """Return True if conditions favor a SELL entry."""
    score = 0

    # RSI: overbought
    if rsi is not None and rsi > RSI_OVERBOUGHT:
        score += 2
    elif rsi is not None and rsi > 55:
        score += 1

    # MACD: bearish cross or below signal
    if macd is not None and macd_signal is not None and macd < macd_signal:
        score += 1

    # Price near upper Bollinger → resistance
    if bb_upper is not None and latest["Close"] >= bb_upper * 0.99:
        score += 1

    return score >= 2
