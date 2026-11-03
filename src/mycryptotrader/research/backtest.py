"""Minimal long-only spot backtester.

Deliberately small and explicit rather than "realistic": one position, full
capital, execution at the next bar's open, fees on both sides. Use Freqtrade's
engine for order-book-level simulation; use this one to iterate on ideas in
seconds and to keep the research loop honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from mycryptotrader.research.evaluate import equity_metrics, trade_metrics

TRADE_COLUMNS: tuple[str, ...] = (
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "bars",
    "invested",
    "pnl",
    "return",
    "exit_reason",
)


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    fee: float = 0.001
    initial_capital: float = 10_000.0
    bars_per_year: float = 8_760.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.fee < 1.0:
            raise ValueError("fee must be in [0, 1)")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.bars_per_year <= 0:
            raise ValueError("bars_per_year must be positive")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    equity: pd.Series
    positions: pd.Series
    trades: pd.DataFrame
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class _OpenTrade:
    entry_time: pd.Timestamp
    entry_price: float
    entry_bar: int
    invested: float


def signals_to_position(
    enter: npt.NDArray[np.int8],
    exit_signal: npt.NDArray[np.int8],
) -> npt.NDArray[np.int8]:
    """Turn momentary entry/exit events into a persistent 0/1 position series.

    Causal by construction: the value at ``i`` only depends on bars ``<= i``.
    """
    if enter.shape != exit_signal.shape:
        raise ValueError("enter and exit arrays must have the same shape")

    position = np.zeros(len(enter), dtype=np.int8)
    current = 0
    for i in range(len(enter)):
        if enter[i]:
            current = 1
        elif exit_signal[i]:
            current = 0
        position[i] = current
    return position


def _close_trade(
    open_trade: _OpenTrade,
    exit_time: pd.Timestamp,
    exit_price: float,
    exit_bar: int,
    proceeds: float,
    reason: str,
) -> dict[str, Any]:
    pnl = proceeds - open_trade.invested
    return {
        "entry_time": open_trade.entry_time,
        "exit_time": exit_time,
        "entry_price": open_trade.entry_price,
        "exit_price": exit_price,
        "bars": exit_bar - open_trade.entry_bar,
        "invested": open_trade.invested,
        "pnl": pnl,
        "return": pnl / open_trade.invested,
        "exit_reason": reason,
    }


def run_backtest(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a long-only backtest.

    ``signals`` must contain ``enter_long``/``exit_long`` aligned with ``df``.
    Execution happens at the open of the bar *after* the signal bar.
    """
    cfg = config or BacktestConfig()

    if df.empty:
        raise ValueError("Cannot backtest an empty frame")
    if len(signals) != len(df):
        raise ValueError("signals must be aligned with df")
    for column in ("open", "close"):
        if column not in df.columns:
            raise ValueError(f"Missing OHLCV column {column!r}")
    for column in ("enter_long", "exit_long"):
        if column not in signals.columns:
            raise ValueError(f"Missing signal column {column!r}")

    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    enter = signals["enter_long"].to_numpy(dtype=np.int8)
    exit_signal = signals["exit_long"].to_numpy(dtype=np.int8)

    position = signals_to_position(enter, exit_signal)
    periods = len(df)

    equity = np.empty(periods, dtype=float)
    held = np.zeros(periods, dtype=np.int8)
    equity[0] = cfg.initial_capital

    cash = cfg.initial_capital
    units = 0.0
    fees_paid = 0.0
    open_trade: _OpenTrade | None = None
    trades: list[dict[str, Any]] = []

    for i in range(1, periods):
        target = int(position[i - 1])
        price = float(opens[i])

        if target == 1 and units == 0.0 and cash > 0.0 and price > 0.0:
            invested = cash
            fee = invested * cfg.fee
            fees_paid += fee
            units = (invested - fee) / price
            cash = 0.0
            open_trade = _OpenTrade(
                entry_time=pd.Timestamp(df.index[i]),
                entry_price=price,
                entry_bar=i,
                invested=invested,
            )
        elif target == 0 and units > 0.0:
            gross = units * price
            fee = gross * cfg.fee
            fees_paid += fee
            cash = gross - fee
            if open_trade is not None:
                trades.append(
                    _close_trade(
                        open_trade,
                        pd.Timestamp(df.index[i]),
                        price,
                        i,
                        cash,
                        "signal",
                    )
                )
                open_trade = None
            units = 0.0

        held[i] = 1 if units > 0.0 else 0
        equity[i] = cash + units * float(closes[i])

    # Realise any still-open position at the last close so metrics are complete.
    if units > 0.0 and open_trade is not None:
        price = float(closes[-1])
        gross = units * price
        fee = gross * cfg.fee
        fees_paid += fee
        cash = gross - fee
        equity[-1] = cash
        trades.append(
            _close_trade(
                open_trade,
                pd.Timestamp(df.index[-1]),
                price,
                periods - 1,
                cash,
                "end_of_data",
            )
        )
        units = 0.0
        held[-1] = 0

    equity_series = pd.Series(equity, index=df.index, name="equity")
    trades_frame = pd.DataFrame(trades, columns=list(TRADE_COLUMNS))

    metrics = equity_metrics(equity_series, cfg.bars_per_year)
    metrics.update(trade_metrics(trades_frame))
    metrics["fees_paid"] = float(fees_paid)
    metrics["exposure"] = float(held.mean())
    metrics["buy_and_hold_return"] = float(closes[-1] / closes[0] - 1.0) if closes[0] > 0 else 0.0

    return BacktestResult(
        equity=equity_series,
        positions=pd.Series(held, index=df.index, name="position"),
        trades=trades_frame,
        metrics=metrics,
    )
