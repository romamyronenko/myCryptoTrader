from __future__ import annotations

import json
from pathlib import Path

from mycryptotrader.cli import main
from mycryptotrader.data.query import query
from mycryptotrader.data.store import write_ohlcv
from mycryptotrader.data.synthetic import make_ohlcv


def test_demo_then_backtest(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run"

    assert main(["--data-dir", str(data_dir), "data", "demo", "--days", "120"]) == 0
    assert main(["--data-dir", str(data_dir), "backtest", "--out", str(run_dir)]) == 0

    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "equity.parquet").exists()
    assert (run_dir / "trades.parquet").exists()
    assert (run_dir / "run.json").exists()

    manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert manifest["strategy"] == "TaBaseline"


def test_backtest_can_select_another_strategy(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run-rsi"

    assert main(["--data-dir", str(data_dir), "data", "demo", "--days", "120"]) == 0
    assert (
        main(
            [
                "--data-dir",
                str(data_dir),
                "backtest",
                "--strategy",
                "RsiReversion",
                "--out",
                str(run_dir),
            ]
        )
        == 0
    )

    manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert manifest["strategy"] == "RsiReversion"


def test_duckdb_sees_the_store(tmp_path: Path) -> None:
    frame = make_ohlcv(periods=100, start="2024-01-01")
    write_ohlcv(frame, tmp_path, "binance", "BTC/USDT", "1h")

    result = query("SELECT count(*) AS n FROM ohlcv", tmp_path)

    assert int(result["n"].iloc[0]) == 100
