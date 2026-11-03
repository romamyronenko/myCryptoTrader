"""Data quality checks. A backtest on broken data is a fantasy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mycryptotrader.common.time import timeframe_to_ms
from mycryptotrader.data.store import OHLCV_COLUMNS


@dataclass(frozen=True, slots=True)
class ValidationReport:
    rows: int
    duplicates: int
    missing_bars: int
    nulls: int
    zero_volume: int
    bad_ohlc: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None

    @property
    def ok(self) -> bool:
        """Zero-volume candles are legal; everything else must be clean."""
        return (
            self.duplicates == 0
            and self.missing_bars == 0
            and self.nulls == 0
            and self.bad_ohlc == 0
        )

    def summary(self) -> str:
        status = "OK" if self.ok else "FAILED"
        lines = [
            f"status        : {status}",
            f"rows          : {self.rows}",
            f"range         : {self.start} -> {self.end}",
            f"duplicates    : {self.duplicates}",
            f"missing bars  : {self.missing_bars}",
            f"null values   : {self.nulls}",
            f"bad OHLC rows : {self.bad_ohlc}",
            f"zero volume   : {self.zero_volume}",
        ]
        return "\n".join(lines)


def validate_ohlcv(df: pd.DataFrame, timeframe: str) -> ValidationReport:
    """Check gaps, duplicates, nulls and inconsistent OHLC rows."""
    if df.empty:
        raise ValueError("Cannot validate an empty dataset")

    missing = [column for column in OHLCV_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    duplicates = int(df.index.duplicated().sum())

    index = pd.DatetimeIndex(df.index.drop_duplicates().sort_values())
    step_ms = timeframe_to_ms(timeframe)
    if len(index) > 1:
        # ``DatetimeIndex.asi8`` changed unit in pandas 3; convert explicitly.
        naive_index = index.tz_convert(None) if index.tz is not None else index
        timestamps_ms = naive_index.to_numpy().astype("datetime64[ms]").astype(np.int64)
        deltas_ms = np.diff(timestamps_ms)
        missing_bars = int(np.maximum(deltas_ms // step_ms - 1, 0).sum())
    else:
        missing_bars = 0

    nulls = int(df.loc[:, list(OHLCV_COLUMNS)].isna().sum().sum())

    ohlc = df.loc[:, ["open", "high", "low", "close"]]
    non_positive = (ohlc <= 0).any(axis=1)
    inconsistent = (
        (df["high"] < df["low"])
        | (df["high"] < ohlc.loc[:, ["open", "close"]].max(axis=1))
        | (df["low"] > ohlc.loc[:, ["open", "close"]].min(axis=1))
    )
    bad_ohlc = int((non_positive | inconsistent).sum())

    zero_volume = int((df["volume"] <= 0).sum())

    return ValidationReport(
        rows=int(len(df)),
        duplicates=duplicates,
        missing_bars=missing_bars,
        nulls=nulls,
        zero_volume=zero_volume,
        bad_ohlc=bad_ohlc,
        start=pd.Timestamp(index[0]) if len(index) else None,
        end=pd.Timestamp(index[-1]) if len(index) else None,
    )
