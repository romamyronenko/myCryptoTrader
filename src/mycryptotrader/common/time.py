"""Timeframe and timestamp helpers. Everything is UTC, always."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pandas as pd

_YEAR_MS = 365 * 24 * 60 * 60 * 1000

_TF_RE = re.compile(r"^(?P<count>\d+)(?P<unit>[mhdw])$")

_UNIT_MS = {
    "m": 60_000,
    "h": 3_600_000,
    "d": 86_400_000,
    "w": 604_800_000,
}

_PANDAS_UNIT = {
    "m": "min",
    "h": "h",
    "d": "D",
    "w": "W",
}


def _parse_timeframe(timeframe: str) -> tuple[int, str]:
    match = _TF_RE.match(timeframe)
    if match is None:
        raise ValueError(
            f"Unsupported timeframe {timeframe!r}; expected e.g. '1m', '15m', '1h', '1d'"
        )
    return int(match.group("count")), match.group("unit")


def timeframe_to_ms(timeframe: str) -> int:
    """Convert a ccxt/Freqtrade timeframe string to milliseconds."""
    count, unit = _parse_timeframe(timeframe)
    return count * _UNIT_MS[unit]


def timeframe_to_pandas_freq(timeframe: str) -> str:
    """Convert a timeframe to a pandas offset alias."""
    count, unit = _parse_timeframe(timeframe)
    return f"{count}{_PANDAS_UNIT[unit]}"


def timeframe_to_bars_per_year(timeframe: str) -> float:
    """Number of candles in a 365-day year. Used to annualise metrics."""
    return _YEAR_MS / timeframe_to_ms(timeframe)


def to_ms(value: datetime | str | pd.Timestamp) -> int:
    """Convert an ISO string / datetime / Timestamp to UTC epoch milliseconds."""
    ts = pd.Timestamp(value)
    ts = as_utc_timestamp(ts)
    return int(ts.value // 1_000_000)


def as_utc_timestamp(value: datetime | str | pd.Timestamp) -> pd.Timestamp:
    """Return a timezone-aware UTC pandas Timestamp."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize(UTC)
    return ts.tz_convert(UTC)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)
