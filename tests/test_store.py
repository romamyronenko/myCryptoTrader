from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mycryptotrader.data.store import list_datasets, read_ohlcv, write_ohlcv
from mycryptotrader.data.synthetic import make_ohlcv


def test_write_read_roundtrip(tmp_path: Path) -> None:
    frame = make_ohlcv(periods=200, timeframe="1h", start="2024-01-01")
    write_ohlcv(frame, tmp_path, "binance", "BTC/USDT", "1h")

    restored = read_ohlcv(tmp_path, "binance", "BTC/USDT", "1h")

    pd.testing.assert_frame_equal(frame, restored, check_freq=False)


def test_write_is_idempotent(tmp_path: Path) -> None:
    frame = make_ohlcv(periods=200, timeframe="1h", start="2024-01-01")
    write_ohlcv(frame, tmp_path, "binance", "BTC/USDT", "1h")
    write_ohlcv(frame, tmp_path, "binance", "BTC/USDT", "1h")

    restored = read_ohlcv(tmp_path, "binance", "BTC/USDT", "1h")
    assert len(restored) == len(frame)


def test_data_is_partitioned_by_month(tmp_path: Path) -> None:
    frame = make_ohlcv(periods=1_500, timeframe="1h", start="2024-01-01")
    paths = write_ohlcv(frame, tmp_path, "binance", "BTC/USDT", "1h")
    assert len(paths) >= 2


def test_read_range_is_inclusive(tmp_path: Path) -> None:
    frame = make_ohlcv(periods=200, timeframe="1h", start="2024-01-01")
    write_ohlcv(frame, tmp_path, "binance", "BTC/USDT", "1h")

    subset = read_ohlcv(
        tmp_path,
        "binance",
        "BTC/USDT",
        "1h",
        start=frame.index[10],
        end=frame.index[20],
    )

    assert len(subset) == 11
    assert subset.index[0] == frame.index[10]
    assert subset.index[-1] == frame.index[20]


def test_missing_dataset_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_ohlcv(tmp_path, "binance", "NOPE/USDT", "1h")


def test_list_datasets(tmp_path: Path) -> None:
    frame = make_ohlcv(periods=200, timeframe="1h", start="2024-01-01")
    write_ohlcv(frame, tmp_path, "binance", "BTC/USDT", "1h")

    datasets = list_datasets(tmp_path)

    assert len(datasets) == 1
    assert datasets[0].exchange == "binance"
    assert datasets[0].symbol == "BTC_USDT"
    assert datasets[0].timeframe == "1h"
    assert datasets[0].rows == len(frame)
