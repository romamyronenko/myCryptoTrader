"""Runtime settings, loaded from environment variables with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SYMBOLS: tuple[str, ...] = ("BTC/USDT", "ETH/USDT", "SOL/USDT")


def _parse_symbols(raw: str) -> tuple[str, ...]:
    symbols = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not symbols:
        raise ValueError("SYMBOLS must contain at least one symbol")
    return symbols


@dataclass(frozen=True, slots=True)
class Settings:
    exchange: str = "binance"
    stake_currency: str = "USDT"
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS
    timeframe: str = "1h"
    data_dir: Path = Path("data")
    user_data_dir: Path = Path("user_data")
    fee: float = 0.001
    initial_capital: float = 10_000.0

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            exchange=os.getenv("EXCHANGE", "binance"),
            stake_currency=os.getenv("STAKE_CURRENCY", "USDT"),
            symbols=_parse_symbols(os.getenv("SYMBOLS", ",".join(DEFAULT_SYMBOLS))),
            timeframe=os.getenv("TIMEFRAME", "1h"),
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            user_data_dir=Path(os.getenv("USER_DATA_DIR", "user_data")),
            fee=float(os.getenv("FEE", "0.001")),
            initial_capital=float(os.getenv("INITIAL_CAPITAL", "10000")),
        )
