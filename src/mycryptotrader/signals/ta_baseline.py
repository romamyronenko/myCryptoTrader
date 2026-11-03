"""EMA-cross baseline: the first strategy worth measuring.

Entry: fast EMA crosses above slow EMA while RSI is below the entry ceiling.
Exit: fast EMA crosses below slow EMA, or RSI becomes overbought.

The signal on bar ``t`` is computed from the close of bar ``t``. Execution is
assumed at the open of ``t + 1`` (see research.backtest).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mycryptotrader.features.indicators import ema, rsi


@dataclass(frozen=True, slots=True)
class TaBaselineParams:
    fast: int = 20
    slow: int = 50
    rsi_period: int = 14
    rsi_entry_max: float = 70.0
    rsi_exit_min: float = 80.0


def add_signals(df: pd.DataFrame, params: TaBaselineParams | None = None) -> pd.DataFrame:
    """Return a copy of ``df`` with indicator and signal columns."""
    p = params or TaBaselineParams()
    if p.fast >= p.slow:
        raise ValueError("fast EMA period must be shorter than slow EMA period")

    required = ("open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    out = df.copy()
    close = out["close"]

    fast = ema(close, p.fast)
    slow = ema(close, p.slow)
    rsi_values = rsi(close, p.rsi_period)

    out["ema_fast"] = fast
    out["ema_slow"] = slow
    out["rsi"] = rsi_values

    previous_fast = fast.shift(1)
    previous_slow = slow.shift(1)

    cross_up = (previous_fast <= previous_slow) & (fast > slow)
    cross_down = (previous_fast >= previous_slow) & (fast < slow)
    ready = slow.notna() & rsi_values.notna()

    enter = cross_up & ready & (rsi_values < p.rsi_entry_max)
    exit_ = (cross_down & ready) | (rsi_values > p.rsi_exit_min)

    out["enter_long"] = enter.astype("int8")
    out["exit_long"] = exit_.astype("int8")
    out["enter_tag"] = np.where(enter, "ema_cross", "")
    return out
