from __future__ import annotations

import pandas as pd

from mycryptotrader.data.validate import validate_ohlcv


def test_clean_dataset_passes(ohlcv: pd.DataFrame) -> None:
    report = validate_ohlcv(ohlcv, "1h")
    assert report.ok
    assert report.missing_bars == 0
    assert report.duplicates == 0


def test_missing_bar_is_detected(ohlcv: pd.DataFrame) -> None:
    broken = ohlcv.drop(ohlcv.index[10])
    report = validate_ohlcv(broken, "1h")
    assert report.missing_bars == 1
    assert not report.ok


def test_duplicate_timestamp_is_detected(ohlcv: pd.DataFrame) -> None:
    duplicated = pd.concat([ohlcv, ohlcv.iloc[[5]]]).sort_index()
    report = validate_ohlcv(duplicated, "1h")
    assert report.duplicates == 1
    assert not report.ok


def test_bad_ohlc_row_is_detected(ohlcv: pd.DataFrame) -> None:
    broken = ohlcv.copy()
    broken.iloc[3, broken.columns.get_loc("high")] = broken.iloc[3]["low"] - 1.0
    report = validate_ohlcv(broken, "1h")
    assert report.bad_ohlc >= 1
    assert not report.ok
