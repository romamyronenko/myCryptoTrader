from __future__ import annotations

import pandas as pd
import pytest

from mycryptotrader.data.synthetic import make_ohlcv


@pytest.fixture()
def ohlcv() -> pd.DataFrame:
    return make_ohlcv(periods=3000, timeframe="1h", seed=7)
