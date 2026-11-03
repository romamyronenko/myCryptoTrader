"""Performance metrics. Always evaluated after fees."""

from __future__ import annotations

import numpy as np
import pandas as pd


def equity_metrics(equity: pd.Series, bars_per_year: float) -> dict[str, float]:
    """Risk/return metrics from an equity curve."""
    if len(equity) < 2:
        raise ValueError("Need at least two equity points")
    if bars_per_year <= 0:
        raise ValueError("bars_per_year must be positive")

    values = equity.to_numpy(dtype=float)
    if values[0] <= 0:
        raise ValueError("Initial equity must be positive")

    series = pd.Series(values, index=equity.index)
    returns = series.pct_change().dropna()

    total_return = float(values[-1] / values[0] - 1.0)
    years = (len(values) - 1) / bars_per_year
    if years > 0 and values[-1] > 0:
        cagr = float((values[-1] / values[0]) ** (1.0 / years) - 1.0)
    else:
        cagr = 0.0

    volatility = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / volatility * np.sqrt(bars_per_year)) if volatility > 0 else 0.0

    negative = returns[returns < 0]
    downside = float(negative.std(ddof=1)) if len(negative) > 1 else 0.0
    sortino = float(returns.mean() / downside * np.sqrt(bars_per_year)) if downside > 0 else 0.0

    running_max = np.maximum.accumulate(values)
    drawdowns = values / running_max - 1.0
    max_drawdown = float(np.min(drawdowns))
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0

    return {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
    }


def trade_metrics(trades: pd.DataFrame) -> dict[str, float]:
    """Win rate, average return and profit factor over closed trades."""
    if trades.empty:
        return {
            "trades": 0.0,
            "win_rate": 0.0,
            "avg_trade_return": 0.0,
            "profit_factor": 0.0,
        }

    returns = trades["return"].astype(float)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    return {
        "trades": float(len(returns)),
        "win_rate": float(len(wins) / len(returns)),
        "avg_trade_return": float(returns.mean()),
        "profit_factor": float(profit_factor),
    }
