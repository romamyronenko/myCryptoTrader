"""Strategy registry: one name, one signal builder, used by CLI and Freqtrade."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from mycryptotrader.signals.rsi_reversion import add_signals as add_rsi_reversion_signals
from mycryptotrader.signals.ta_baseline import add_signals as add_ta_baseline_signals

SignalBuilder = Callable[[pd.DataFrame], pd.DataFrame]

SIGNAL_BUILDERS: dict[str, SignalBuilder] = {
    "TaBaseline": add_ta_baseline_signals,
    "RsiReversion": add_rsi_reversion_signals,
}


def get_signal_builder(name: str) -> SignalBuilder:
    try:
        return SIGNAL_BUILDERS[name]
    except KeyError:
        available = ", ".join(sorted(SIGNAL_BUILDERS))
        raise ValueError(f"Unknown strategy {name!r}. Available: {available}") from None
