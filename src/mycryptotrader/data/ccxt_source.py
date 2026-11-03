"""ccxt-based historical downloader (public market data, no keys required)."""

from __future__ import annotations

import pandas as pd

from mycryptotrader.common.time import to_ms
from mycryptotrader.data.store import OHLCV_COLUMNS, normalize_ohlcv


def download_ohlcv(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    since: str,
    until: str,
    limit: int = 1000,
) -> pd.DataFrame:
    """Download paginated OHLCV from an exchange via ccxt.

    Only public endpoints are used, so API keys are not required. For bulk
    history prefer the exchange's public archives (e.g. data.binance.vision)
    and load them with :func:`mycryptotrader.data.store.write_ohlcv`.
    """
    import ccxt

    exchange_class = getattr(ccxt, exchange_id, None)
    if exchange_class is None:
        raise ValueError(f"Unknown ccxt exchange {exchange_id!r}")

    since_ms = to_ms(since)
    until_ms = to_ms(until)
    if since_ms >= until_ms:
        raise ValueError("'since' must be earlier than 'until'")

    exchange = exchange_class({"enableRateLimit": True})
    rows: list[list[float]] = []
    cursor = since_ms

    try:
        while cursor < until_ms:
            batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
            if not batch:
                break
            rows.extend(batch)
            last = int(batch[-1][0])
            if last < cursor:
                break
            cursor = last + 1
    finally:
        close = getattr(exchange, "close", None)
        if callable(close):
            close()

    if not rows:
        raise RuntimeError(
            f"{exchange_id} returned no candles for {symbol} {timeframe} "
            f"between {since} and {until}"
        )

    frame = pd.DataFrame(rows, columns=["timestamp", *OHLCV_COLUMNS])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"].astype("int64"), unit="ms", utc=True)
    frame = frame.set_index("timestamp")
    frame = frame[frame.index < pd.Timestamp(until_ms, unit="ms", tz="UTC")]

    return normalize_ohlcv(frame)
