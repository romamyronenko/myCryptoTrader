"""The Freqtrade wrapper must reuse the exact shared signal code."""

from __future__ import annotations

import sys
import types

import pandas as pd
import pytest


def test_strategy_wrapper_delegates_to_shared_signals(
    monkeypatch: pytest.MonkeyPatch,
    ohlcv: pd.DataFrame,
) -> None:
    fake_package = types.ModuleType("freqtrade")
    fake_strategy = types.ModuleType("freqtrade.strategy")

    class IStrategy:
        pass

    fake_strategy.IStrategy = IStrategy  # type: ignore[attr-defined]
    fake_package.strategy = fake_strategy  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "freqtrade", fake_package)
    monkeypatch.setitem(sys.modules, "freqtrade.strategy", fake_strategy)
    monkeypatch.delitem(sys.modules, "mycryptotrader.strategies.ta_baseline", raising=False)

    from mycryptotrader.strategies.ta_baseline import TaBaseline

    strategy = TaBaseline()
    enriched = strategy.populate_indicators(ohlcv, {})

    assert "ema_fast" in enriched.columns
    assert set(enriched["enter_long"].unique()) <= {0, 1}
    assert set(enriched["exit_long"].unique()) <= {0, 1}

    entries = strategy.populate_entry_trend(enriched, {})
    exits = strategy.populate_exit_trend(entries, {})

    assert exits["enter_long"].dtype == "int8"
    assert exits["exit_long"].dtype == "int8"
    assert "enter_tag" in exits.columns
