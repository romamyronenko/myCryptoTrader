from __future__ import annotations

import json
from pathlib import Path

import pytest

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "freqtrade"
CONFIG_NAMES = ("config.dryrun.json", "config.live.json")


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_configs_are_valid_json(name: str) -> None:
    payload = json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))

    assert payload["trading_mode"] == "spot"
    assert payload["exchange"]["name"] in {"binance", "bybit"}
    assert payload["timeframe"] == "1h"
    assert payload["pairlists"][0]["method"] == "StaticPairList"


def test_dryrun_config_is_safe() -> None:
    payload = json.loads((CONFIG_DIR / "config.dryrun.json").read_text(encoding="utf-8"))

    assert payload["dry_run"] is True
    assert payload["exchange"]["key"] == ""
    assert payload["exchange"]["secret"] == ""


def test_live_config_reads_keys_from_environment() -> None:
    payload = json.loads((CONFIG_DIR / "config.live.json").read_text(encoding="utf-8"))

    assert payload["dry_run"] is False
    assert payload["exchange"]["key"] == "${BINANCE_API_KEY}"
    assert payload["exchange"]["secret"] == "${BINANCE_API_SECRET}"
    assert payload["max_open_trades"] <= 2
