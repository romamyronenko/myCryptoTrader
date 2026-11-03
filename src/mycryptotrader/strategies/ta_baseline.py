"""Freqtrade wrapper for the EMA-cross baseline.

This file is intentionally thin: all signal logic lives in
``mycryptotrader.signals.ta_baseline`` so the research backtest and the live bot
run exactly the same code.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd
from freqtrade.strategy import IStrategy

from mycryptotrader.signals.ta_baseline import TaBaselineParams, add_signals
from mycryptotrader.strategies._protections import default_protections


class TaBaseline(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    startup_candle_count = 200
    can_short = False

    # Exits are signal-driven; ROI effectively disabled.
    minimal_roi: ClassVar[dict[str, float]] = {"0": 10.0}
    stoploss = -0.05
    trailing_stop = False
    process_only_new_candles = True
    use_exit_signal = True

    @property
    def protections(self) -> list[dict[str, Any]]:
        return default_protections()

    def populate_indicators(
        self, dataframe: pd.DataFrame, metadata: dict[str, Any]
    ) -> pd.DataFrame:
        return add_signals(dataframe, TaBaselineParams())

    def populate_entry_trend(
        self, dataframe: pd.DataFrame, metadata: dict[str, Any]
    ) -> pd.DataFrame:
        dataframe["enter_long"] = dataframe["enter_long"].fillna(0).astype("int8")
        dataframe["enter_tag"] = dataframe.get("enter_tag", "ema_cross")
        return dataframe

    def populate_exit_trend(
        self, dataframe: pd.DataFrame, metadata: dict[str, Any]
    ) -> pd.DataFrame:
        dataframe["exit_long"] = dataframe["exit_long"].fillna(0).astype("int8")
        return dataframe
