"""Deterministic synthetic OHLCV, for tests and offline demos."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mycryptotrader.common.time import as_utc_timestamp, timeframe_to_pandas_freq
from mycryptotrader.data.store import normalize_ohlcv


def make_ohlcv(
    *,
    start: str = "2024-01-01",
    periods: int = 2000,
    timeframe: str = "1h",
    seed: int = 42,
    start_price: float = 100.0,
    drift: float = 0.0,
    volatility: float = 0.01,
) -> pd.DataFrame:
    """Generate a geometric-random-walk OHLCV frame with a consistent shape."""
    if periods < 2:
        raise ValueError("periods must be >= 2")
    if start_price <= 0:
        raise ValueError("start_price must be positive")
    if volatility <= 0:
        raise ValueError("volatility must be positive")

    rng = np.random.default_rng(seed)
    index = pd.date_range(
        start=as_utc_timestamp(start),
        periods=periods,
        freq=timeframe_to_pandas_freq(timeframe),
        name="timestamp",
    )

    log_returns = rng.normal(drift, volatility, periods)
    close = start_price * np.exp(np.cumsum(log_returns))

    open_ = np.empty(periods, dtype=float)
    open_[0] = start_price
    open_[1:] = close[:-1]

    wick = np.abs(rng.normal(0.0, volatility / 2.0, periods))
    high = np.maximum(open_, close) * (1.0 + wick)
    low = np.maximum(np.minimum(open_, close) * (1.0 - wick), 1e-8)
    volume = rng.lognormal(mean=6.0, sigma=1.0, size=periods)

    frame = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )
    return normalize_ohlcv(frame)
