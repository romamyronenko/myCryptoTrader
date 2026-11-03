"""The Freqtrade wrappers must reuse the exact shared signal code."""

from __future__ import annotations

import importlib
import sys
import types

import pandas as pd
import pytest


@pytest.mark.parametrize(
    ("module_name", "class_name", "expected_tag"),
    [
        ("mycryptotrader.strategies.ta_baseline", "TaBaseline", "ema_cross"),
        ("mycryptotrader.strategies.rsi_reversion", "RsiReversion", "rsi_reversion"),
    ],
)
def test_strategy_wrapper_delegates_to_shared_signals(
    monkeypatch: pytest.MonkeyPatch,
    ohlcv: pd.DataFrame,
    module_name: str,
    class_name: str,
    expected_tag: str,
) -> None:
    fake_package = types.ModuleType("freqtrade")
    fake_strategy = types.ModuleType("freqtrade.strategy")

    class IStrategy:
        pass

    fake_strategy.IStrategy = IStrategy  # type: ignore[attr-defined]
    fake_package.strategy = fake_strategy  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "freqtrade", fake_package)
    monkeypatch.setitem(sys.modules, "freqtrade.strategy", fake_strategy)
    monkeypatch.delitem(sys.modules, module_name, raising=False)

    module = importlib.import_module(module_name)
    strategy = getattr(module, class_name)()

    enriched = strategy.populate_indicators(ohlcv, {})

    assert set(enriched["enter_long"].unique()) <= {0, 1}
    assert set(enriched["exit_long"].unique()) <= {0, 1}
    assert int(enriched["enter_long"].sum()) > 0

    entries = strategy.populate_entry_trend(enriched, {})
    exits = strategy.populate_exit_trend(entries, {})

    assert exits["enter_long"].dtype == "int8"
    assert exits["exit_long"].dtype == "int8"
    assert (exits.loc[exits["enter_long"] == 1, "enter_tag"] == expected_tag).all()
