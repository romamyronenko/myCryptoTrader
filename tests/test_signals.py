from __future__ import annotations

import pandas as pd
import pytest

from mycryptotrader.signals.ta_baseline import TaBaselineParams, add_signals


def test_signals_are_binary_and_present(ohlcv: pd.DataFrame) -> None:
    result = add_signals(ohlcv)
    assert set(result["enter_long"].unique()) <= {0, 1}
    assert set(result["exit_long"].unique()) <= {0, 1}
    assert int(result["enter_long"].sum()) > 0


def test_signals_are_causal(ohlcv: pd.DataFrame) -> None:
    full = add_signals(ohlcv)
    partial = add_signals(ohlcv.iloc[:400])
    pd.testing.assert_frame_equal(full.iloc[:400], partial)


def test_invalid_ema_periods_are_rejected(ohlcv: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        add_signals(ohlcv, TaBaselineParams(fast=50, slow=20))
