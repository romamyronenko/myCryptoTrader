"""Shared risk protections for Freqtrade strategies.

Since Freqtrade 2026.10 protections must be defined on the strategy (as a
``protections`` property), not in ``config.json``. Keeping the defaults here
avoids duplicating the same dicts in every strategy.
"""

from __future__ import annotations

from typing import Any


def default_protections(*, max_drawdown: float = 0.15) -> list[dict[str, Any]]:
    return [
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 24,
            "trade_limit": 2,
            "stop_duration_candles": 12,
            "only_per_pair": False,
        },
        {
            "method": "MaxDrawdown",
            "calculation_mode": "equity",
            "lookback_period_candles": 200,
            "trade_limit": 10,
            "stop_duration_candles": 24,
            "max_allowed_drawdown": max_drawdown,
        },
    ]
