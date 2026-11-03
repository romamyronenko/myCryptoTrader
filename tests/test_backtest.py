from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mycryptotrader.research.backtest import (
    BacktestConfig,
    run_backtest,
    signals_to_position,
)


def _frame(periods: int = 6) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="h", tz="UTC", name="timestamp")
    base = np.arange(periods, dtype=float)
    return pd.DataFrame(
        {
            "open": 100.0 + base * 10.0,
            "high": 106.0 + base * 10.0,
            "low": 99.0 + base * 10.0,
            "close": 105.0 + base * 10.0,
            "volume": 1_000.0,
        },
        index=index,
    )


def _signals(index: pd.Index, periods: int, entry: int, exit_bar: int) -> pd.DataFrame:
    enter = np.zeros(periods, dtype=np.int8)
    exit_signal = np.zeros(periods, dtype=np.int8)
    enter[entry] = 1
    exit_signal[exit_bar] = 1
    return pd.DataFrame(
        {"enter_long": enter, "exit_long": exit_signal},
        index=index,
    )


def test_signals_to_position_persists_until_exit() -> None:
    enter = np.array([1, 0, 0, 0], dtype=np.int8)
    exit_signal = np.array([0, 0, 1, 0], dtype=np.int8)
    assert signals_to_position(enter, exit_signal).tolist() == [1, 1, 0, 0]


def test_execution_uses_next_bar_open() -> None:
    frame = _frame()
    signals = _signals(frame.index, len(frame), entry=0, exit_bar=2)

    result = run_backtest(frame, signals, BacktestConfig(fee=0.0, initial_capital=1_000.0))
    trade = result.trades.iloc[0]

    assert trade["entry_price"] == pytest.approx(frame["open"].iloc[1])
    assert trade["exit_price"] == pytest.approx(frame["open"].iloc[3])
    assert trade["return"] == pytest.approx(130.0 / 110.0 - 1.0)


def test_fees_are_charged_on_both_sides() -> None:
    frame = _frame()
    signals = _signals(frame.index, len(frame), entry=0, exit_bar=2)

    result = run_backtest(frame, signals, BacktestConfig(fee=0.001, initial_capital=1_000.0))
    expected = (1.0 - 0.001) ** 2 * (130.0 / 110.0) - 1.0

    assert result.trades.iloc[0]["return"] == pytest.approx(expected)
    assert result.metrics["fees_paid"] > 0.0


def test_backtest_is_causal() -> None:
    frame = _frame()
    signals = _signals(frame.index, len(frame), entry=0, exit_bar=2)

    full = run_backtest(frame, signals, BacktestConfig(fee=0.0))
    partial = run_backtest(
        frame.iloc[:4],
        signals.iloc[:4],
        BacktestConfig(fee=0.0),
    )

    np.testing.assert_allclose(
        full.equity.iloc[:4].to_numpy(),
        partial.equity.to_numpy(),
    )


def test_open_position_is_realised_at_last_close() -> None:
    frame = _frame(periods=3)
    signals = _signals(frame.index, 3, entry=0, exit_bar=2)

    result = run_backtest(frame, signals, BacktestConfig(fee=0.0))
    trade = result.trades.iloc[0]

    assert trade["exit_reason"] == "end_of_data"
    assert trade["exit_price"] == pytest.approx(frame["close"].iloc[-1])


def test_exit_before_entry_is_ignored_while_flat() -> None:
    enter = np.array([0, 0, 1, 0, 0], dtype=np.int8)
    exit_signal = np.array([1, 0, 0, 0, 0], dtype=np.int8)
    assert signals_to_position(enter, exit_signal).tolist() == [0, 0, 1, 1, 1]


def test_misaligned_signals_are_rejected() -> None:
    frame = _frame()
    signals = _signals(frame.index[: len(frame) - 1], len(frame) - 1, entry=0, exit_bar=1)
    with pytest.raises(ValueError):
        run_backtest(frame, signals)
