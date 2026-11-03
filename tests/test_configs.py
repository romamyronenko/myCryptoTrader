from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "freqtrade"
CONFIG_NAMES = ("config.dryrun.json", "config.live.json")


def _load(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))
    return payload


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_configs_are_valid_json(name: str) -> None:
    payload = _load(name)

    assert payload["trading_mode"] == "spot"
    assert payload["exchange"]["name"] in {"binance", "bybit"}
    assert payload["timeframe"] == "1h"
    assert payload["pairlists"][0]["method"] == "StaticPairList"
    # Freqtrade 2026.10 rejects protections in config; they live on the strategy.
    assert "protections" not in payload


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_configs_have_no_unresolved_placeholders(name: str) -> None:
    # Freqtrade does not expand ${VAR} from the environment.
    text = (CONFIG_DIR / name).read_text(encoding="utf-8")
    assert "${" not in text


def test_dryrun_config_is_safe() -> None:
    payload = _load("config.dryrun.json")

    assert payload["dry_run"] is True
    assert payload["exchange"]["key"] == ""
    assert payload["exchange"]["secret"] == ""
    assert len(payload["api_server"]["jwt_secret_key"]) >= 32


def test_live_config_contains_no_secrets() -> None:
    payload = _load("config.live.json")

    assert payload["dry_run"] is False
    assert payload["exchange"]["key"] == ""
    assert payload["exchange"]["secret"] == ""
    assert payload["max_open_trades"] <= 2


def test_private_config_example_is_valid() -> None:
    payload = _load("config.private.example.json")

    assert payload["exchange"]["key"]
    assert payload["exchange"]["secret"]
    assert "jwt_secret_key" in payload["api_server"]
