"""RSI mean-reversion: buy oversold dips inside an uptrend.

Entry: RSI crosses back above the oversold level while price is above the
long-term EMA (trend filter, so we do not catch a falling knife).
Exit: RSI reaches the exit level.

Signal on bar ``t``, execution on the open of ``t + 1``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mycryptotrader.features.indicators import ema, rsi


@dataclass(frozen=True, slots=True)
class RsiReversionParams:
    rsi_period: int = 14
    oversold: float = 30.0
    exit_level: float = 60.0
    trend_period: int = 200


def add_signals(df: pd.DataFrame, params: RsiReversionParams | None = None) -> pd.DataFrame:
    """Return a copy of ``df`` with RSI-reversion indicator and signal columns."""
    p = params or RsiReversionParams()
    if not 0.0 < p.oversold < p.exit_level < 100.0:
        raise ValueError("Require 0 < oversold < exit_level < 100")
    if p.rsi_period <= 0 or p.trend_period <= 0:
        raise ValueError("Periods must be positive")

    required = ("open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    out = df.copy()
    close = out["close"]

    rsi_values = rsi(close, p.rsi_period)
    trend = ema(close, p.trend_period)

    out["rsi"] = rsi_values
    out["ema_trend"] = trend

    previous_rsi = rsi_values.shift(1)
    crossed_up = (previous_rsi <= p.oversold) & (rsi_values > p.oversold)
    above_trend = close > trend
    ready = trend.notna() & rsi_values.notna()

    enter = crossed_up & above_trend & ready
    exit_ = (rsi_values >= p.exit_level) & ready

    out["enter_long"] = enter.astype("int8")
    out["exit_long"] = exit_.astype("int8")
    out["enter_tag"] = np.where(enter, "rsi_reversion", "")
    return out
