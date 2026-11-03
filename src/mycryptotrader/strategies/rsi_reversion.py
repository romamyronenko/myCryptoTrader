"""Freqtrade wrapper for the RSI mean-reversion strategy.

Signal logic lives in ``mycryptotrader.signals.rsi_reversion``.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd
from freqtrade.strategy import IStrategy

from mycryptotrader.signals.rsi_reversion import RsiReversionParams, add_signals


class RsiReversion(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    startup_candle_count = 250
    can_short = False

    # Exits are signal-driven; ROI effectively disabled.
    minimal_roi: ClassVar[dict[str, float]] = {"0": 10.0}
    stoploss = -0.05
    trailing_stop = False
    process_only_new_candles = True
    use_exit_signal = True

    def populate_indicators(
        self, dataframe: pd.DataFrame, metadata: dict[str, Any]
    ) -> pd.DataFrame:
        return add_signals(dataframe, RsiReversionParams())

    def populate_entry_trend(
        self, dataframe: pd.DataFrame, metadata: dict[str, Any]
    ) -> pd.DataFrame:
        dataframe["enter_long"] = dataframe["enter_long"].fillna(0).astype("int8")
        dataframe["enter_tag"] = dataframe.get("enter_tag", "rsi_reversion")
        return dataframe

    def populate_exit_trend(
        self, dataframe: pd.DataFrame, metadata: dict[str, Any]
    ) -> pd.DataFrame:
        dataframe["exit_long"] = dataframe["exit_long"].fillna(0).astype("int8")
        return dataframe
