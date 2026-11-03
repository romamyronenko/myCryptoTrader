from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mycryptotrader.features.indicators import atr, ema, rsi, sma


def test_sma_matches_manual_value() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = sma(series, 3)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[4] == pytest.approx(4.0)


def test_ema_of_constant_series_is_constant() -> None:
    series = pd.Series([5.0] * 100)
    assert np.allclose(ema(series, 10).dropna(), 5.0)


def test_rsi_is_bounded(ohlcv: pd.DataFrame) -> None:
    values = rsi(ohlcv["close"], 14).dropna()
    assert (values >= 0.0).all()
    assert (values <= 100.0).all()


def test_rsi_saturates_on_monotonic_series() -> None:
    increasing = pd.Series(np.arange(1.0, 101.0))
    decreasing = pd.Series(np.arange(100.0, 0.0, -1.0))
    assert (rsi(increasing, 14).dropna() > 99.0).all()
    assert (rsi(decreasing, 14).dropna() < 1.0).all()


def test_atr_of_constant_range() -> None:
    high = pd.Series([2.0] * 50)
    low = pd.Series([1.0] * 50)
    close = pd.Series([1.5] * 50)
    assert np.allclose(atr(high, low, close, 14).dropna(), 1.0)


def test_indicators_reject_invalid_periods() -> None:
    series = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        ema(series, 0)
    with pytest.raises(ValueError):
        rsi(series, -1)
