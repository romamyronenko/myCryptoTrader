from __future__ import annotations

import pytest

from mycryptotrader.signals.registry import SIGNAL_BUILDERS, get_signal_builder


def test_registry_lists_available_strategies() -> None:
    assert set(SIGNAL_BUILDERS) == {"TaBaseline", "RsiReversion"}


def test_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError, match="Unknown strategy"):
        get_signal_builder("NoSuchStrategy")
