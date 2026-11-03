"""Parquet-backed OHLCV store.

Layout (hive-partitioned so DuckDB can read it directly):

    data/raw/exchange=binance/symbol=BTC_USDT/timeframe=1h/
        year=2024/month=01/part.parquet

Timestamps are stored as UTC epoch milliseconds (int64), which is unambiguous
and portable across pandas/pyarrow/duckdb versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from mycryptotrader.common.time import as_utc_timestamp

OHLCV_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")
STORAGE_COLUMNS: tuple[str, ...] = ("timestamp", *OHLCV_COLUMNS)

TimestampLike = str | pd.Timestamp


@dataclass(frozen=True, slots=True)
class DatasetInfo:
    exchange: str
    symbol: str
    timeframe: str
    rows: int
    start: pd.Timestamp
    end: pd.Timestamp
    path: Path


def symbol_slug(symbol: str) -> str:
    """Make an exchange symbol safe for a directory name."""
    return symbol.replace("/", "_").replace(":", "_").replace("-", "_").upper()


def dataset_dir(root: Path | str, exchange: str, symbol: str, timeframe: str) -> Path:
    return (
        Path(root)
        / "raw"
        / f"exchange={exchange}"
        / f"symbol={symbol_slug(symbol)}"
        / f"timeframe={timeframe}"
    )


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean, UTC-indexed, float64 OHLCV frame sorted by time."""
    missing = [column for column in OHLCV_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        if "timestamp" not in out.columns:
            raise ValueError("DataFrame needs a DatetimeIndex or a 'timestamp' column")
        out = out.set_index("timestamp")

    index = pd.DatetimeIndex(out.index)
    index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    index.name = "timestamp"
    out.index = index

    out = out.loc[:, list(OHLCV_COLUMNS)].astype("float64")
    out = out.sort_index()
    return out[~out.index.duplicated(keep="last")]


def _to_storage(df: pd.DataFrame) -> pd.DataFrame:
    out = df.reset_index()
    index = pd.DatetimeIndex(out["timestamp"])
    out["timestamp"] = index.as_unit("ns").asi8 // 1_000_000
    return out.loc[:, list(STORAGE_COLUMNS)]


def _from_storage(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], unit="ms", utc=True)
    return out.set_index("timestamp")


def write_ohlcv(
    df: pd.DataFrame,
    root: Path | str,
    exchange: str,
    symbol: str,
    timeframe: str,
) -> list[Path]:
    """Upsert OHLCV into monthly partitions and return the written files."""
    data = normalize_ohlcv(df)
    if data.empty:
        raise ValueError("Refusing to write an empty dataset")

    target = dataset_dir(root, exchange, symbol, timeframe)
    written: list[Path] = []

    month_periods = pd.DatetimeIndex(data.index).tz_localize(None).to_period("M")
    for period in month_periods.unique():
        year = int(period.year)
        month = int(period.month)
        chunk = data[month_periods == period]

        partition = target / f"year={year}" / f"month={month:02d}"
        partition.mkdir(parents=True, exist_ok=True)
        path = partition / "part.parquet"

        if path.exists():
            existing = _from_storage(pd.read_parquet(path))
            chunk = pd.concat([existing, chunk]).sort_index()
            chunk = chunk[~chunk.index.duplicated(keep="last")]

        _to_storage(chunk).to_parquet(path, index=False)
        written.append(path)

    return written


def read_ohlcv(
    root: Path | str,
    exchange: str,
    symbol: str,
    timeframe: str,
    start: TimestampLike | None = None,
    end: TimestampLike | None = None,
) -> pd.DataFrame:
    """Read a dataset, optionally clipped to [start, end] (inclusive)."""
    files = sorted(
        dataset_dir(root, exchange, symbol, timeframe).glob("year=*/month=*/part.parquet")
    )
    if not files:
        raise FileNotFoundError(
            f"No data for {exchange} {symbol} {timeframe} under {Path(root) / 'raw'}"
        )

    data = pd.concat([_from_storage(pd.read_parquet(path)) for path in files])
    data = data.sort_index()
    data = data[~data.index.duplicated(keep="last")]

    if start is not None:
        data = data[data.index >= as_utc_timestamp(start)]
    if end is not None:
        data = data[data.index <= as_utc_timestamp(end)]

    return data


def list_datasets(root: Path | str) -> list[DatasetInfo]:
    """Describe every dataset currently in the store."""
    base = Path(root) / "raw"
    if not base.exists():
        return []

    datasets: list[DatasetInfo] = []
    for timeframe_dir in sorted(base.glob("exchange=*/symbol=*/timeframe=*")):
        files = sorted(timeframe_dir.glob("year=*/month=*/part.parquet"))
        if not files:
            continue

        exchange = timeframe_dir.parent.parent.name.split("=", 1)[1]
        symbol = timeframe_dir.parent.name.split("=", 1)[1]
        timeframe = timeframe_dir.name.split("=", 1)[1]

        stamps = pd.concat(
            [pd.read_parquet(path, columns=["timestamp"])["timestamp"] for path in files]
        )
        datasets.append(
            DatasetInfo(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                rows=len(stamps),
                start=pd.to_datetime(int(stamps.min()), unit="ms", utc=True),
                end=pd.to_datetime(int(stamps.max()), unit="ms", utc=True),
                path=timeframe_dir,
            )
        )

    return datasets
