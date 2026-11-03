"""Single source of truth for features.

The Freqtrade strategy and the research notebooks both call ``build_features``.
Never duplicate this logic in a notebook: train/serve skew is the fastest way
to make a backtest lie.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mycryptotrader.features.indicators import atr, ema, rolling_volatility, rsi

FEATURE_COLUMNS: tuple[str, ...] = (
    "log_ret_1",
    "ema_fast",
    "ema_slow",
    "ema_ratio",
    "rsi_14",
    "atr_14",
    "atr_pct",
    "vol_20",
)

FAST_PERIOD = 20
SLOW_PERIOD = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
VOL_WINDOW = 20


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add causal feature columns to an OHLCV frame."""
    required = ("open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    out = df.copy()
    close = out["close"]

    out["log_ret_1"] = np.log(close / close.shift(1))
    out["ema_fast"] = ema(close, FAST_PERIOD)
    out["ema_slow"] = ema(close, SLOW_PERIOD)
    out["ema_ratio"] = out["ema_fast"] / out["ema_slow"] - 1.0
    out["rsi_14"] = rsi(close, RSI_PERIOD)
    out["atr_14"] = atr(out["high"], out["low"], close, ATR_PERIOD)
    out["atr_pct"] = out["atr_14"] / close
    out["vol_20"] = rolling_volatility(out["log_ret_1"], VOL_WINDOW)

    return out
