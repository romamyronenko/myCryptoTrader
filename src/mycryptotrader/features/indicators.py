"""Causal indicators.

Every function here only uses information available at or before the current
bar. That property is what keeps backtests honest, so do not introduce
centred windows, negative shifts or future peeking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    if period <= 0:
        raise ValueError("period must be positive")
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    if period <= 0:
        raise ValueError("period must be positive")
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    if period <= 0:
        raise ValueError("period must be positive")

    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False, min_periods=period).mean()

    relative_strength = avg_gain / avg_loss.replace(0.0, np.nan)
    result = 100.0 - 100.0 / (1.0 + relative_strength)

    result = result.mask((avg_loss == 0.0) & (avg_gain > 0.0), 100.0)
    result = result.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
    result = result.mask((avg_gain == 0.0) & (avg_loss == 0.0), 50.0)
    return result


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Average True Range."""
    if period <= 0:
        raise ValueError("period must be positive")

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def rolling_volatility(returns: pd.Series, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("window must be positive")
    return returns.rolling(window=window, min_periods=window).std(ddof=0)
