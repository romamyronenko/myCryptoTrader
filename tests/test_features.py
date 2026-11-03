from __future__ import annotations

import pandas as pd

from mycryptotrader.features.pipeline import FEATURE_COLUMNS, build_features


def test_features_have_expected_columns(ohlcv: pd.DataFrame) -> None:
    result = build_features(ohlcv)
    for column in FEATURE_COLUMNS:
        assert column in result.columns
    assert len(result) == len(ohlcv)
    assert result.index.equals(ohlcv.index)


def test_features_are_causal(ohlcv: pd.DataFrame) -> None:
    """Truncating the input must not change past feature values."""
    full = build_features(ohlcv)
    cut = 400
    partial = build_features(ohlcv.iloc[:cut])
    pd.testing.assert_frame_equal(full.iloc[:cut], partial)
