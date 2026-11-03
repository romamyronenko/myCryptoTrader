"""Command line entrypoints for data management and research backtests."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

import pandas as pd

from mycryptotrader.common.time import timeframe_to_bars_per_year, timeframe_to_ms, utc_now
from mycryptotrader.config import Settings
from mycryptotrader.data.query import query
from mycryptotrader.data.store import list_datasets, read_ohlcv, write_ohlcv
from mycryptotrader.data.synthetic import make_ohlcv
from mycryptotrader.data.validate import validate_ohlcv
from mycryptotrader.research.backtest import BacktestConfig, BacktestResult, run_backtest
from mycryptotrader.signals.registry import SIGNAL_BUILDERS, get_signal_builder


def _add_dataset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exchange", default=None, help="ccxt exchange id (default: $EXCHANGE)")
    parser.add_argument("--symbol", default=None, help="trading pair (default: first of $SYMBOLS)")
    parser.add_argument("--timeframe", default=None, help="candle timeframe (default: $TIMEFRAME)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mycryptotrader",
        description="Research and data tooling for myCryptoTrader",
    )
    parser.add_argument("--data-dir", type=Path, default=None, help="override $DATA_DIR")

    subparsers = parser.add_subparsers(dest="command", required=True)

    data = subparsers.add_parser("data", help="manage the local OHLCV store")
    data_sub = data.add_subparsers(dest="data_command", required=True)

    demo = data_sub.add_parser("demo", help="generate synthetic candles (offline)")
    _add_dataset_args(demo)
    demo.add_argument("--days", type=int, default=365)
    demo.add_argument("--start", default="2024-01-01")
    demo.add_argument("--seed", type=int, default=42)
    demo.set_defaults(handler=_cmd_data_demo)

    download = data_sub.add_parser("download", help="download public OHLCV via ccxt")
    _add_dataset_args(download)
    download.add_argument("--since", required=True, help="ISO date/datetime, UTC")
    download.add_argument("--until", required=True, help="ISO date/datetime, UTC")
    download.set_defaults(handler=_cmd_data_download)

    validate = data_sub.add_parser("validate", help="check a stored dataset for gaps/dupes")
    _add_dataset_args(validate)
    validate.set_defaults(handler=_cmd_data_validate)

    list_command = data_sub.add_parser("list", help="list stored datasets")
    list_command.set_defaults(handler=_cmd_data_list)

    sql = data_sub.add_parser("sql", help="run SQL over the parquet store (DuckDB)")
    sql.add_argument("query", help="SELECT statement; the view is called ohlcv")
    sql.set_defaults(handler=_cmd_data_sql)

    backtest = subparsers.add_parser("backtest", help="run a research backtest")
    _add_dataset_args(backtest)
    backtest.add_argument(
        "--strategy",
        default="TaBaseline",
        choices=sorted(SIGNAL_BUILDERS),
        help="signal builder to evaluate",
    )
    backtest.add_argument("--fee", type=float, default=None, help="per-side fee, e.g. 0.001")
    backtest.add_argument("--capital", type=float, default=None)
    backtest.add_argument("--out", type=Path, default=None, help="artifact directory")
    backtest.set_defaults(handler=_cmd_backtest)

    return parser


def _resolve_dataset(args: argparse.Namespace, settings: Settings) -> tuple[str, str, str]:
    exchange = args.exchange or settings.exchange
    symbol = args.symbol or (settings.symbols[0] if settings.symbols else "BTC/USDT")
    timeframe = args.timeframe or settings.timeframe
    return exchange, symbol, timeframe


def _cmd_data_demo(args: argparse.Namespace, settings: Settings) -> int:
    exchange, symbol, timeframe = _resolve_dataset(args, settings)
    if args.days <= 0:
        print("--days must be positive", file=sys.stderr)
        return 2

    periods = max(2, int(args.days * 86_400_000 // timeframe_to_ms(timeframe)))
    frame = make_ohlcv(
        start=args.start,
        periods=periods,
        timeframe=timeframe,
        seed=args.seed,
    )
    paths = write_ohlcv(frame, settings.data_dir, exchange, symbol, timeframe)

    print(f"Wrote {len(frame)} synthetic candles: {exchange} {symbol} {timeframe}")
    print(f"  range      : {frame.index[0]} -> {frame.index[-1]}")
    print(f"  partitions : {len(paths)}")
    return 0


def _cmd_data_download(args: argparse.Namespace, settings: Settings) -> int:
    from mycryptotrader.data.ccxt_source import download_ohlcv

    exchange, symbol, timeframe = _resolve_dataset(args, settings)
    try:
        frame = download_ohlcv(
            exchange_id=exchange,
            symbol=symbol,
            timeframe=timeframe,
            since=args.since,
            until=args.until,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 2

    paths = write_ohlcv(frame, settings.data_dir, exchange, symbol, timeframe)
    print(f"Downloaded {len(frame)} candles: {exchange} {symbol} {timeframe}")
    print(f"  range      : {frame.index[0]} -> {frame.index[-1]}")
    print(f"  partitions : {len(paths)}")
    return 0


def _cmd_data_validate(args: argparse.Namespace, settings: Settings) -> int:
    exchange, symbol, timeframe = _resolve_dataset(args, settings)
    try:
        frame = read_ohlcv(settings.data_dir, exchange, symbol, timeframe)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report = validate_ohlcv(frame, timeframe)
    print(report.summary())
    return 0 if report.ok else 2


def _cmd_data_list(args: argparse.Namespace, settings: Settings) -> int:
    datasets = list_datasets(settings.data_dir)
    if not datasets:
        print(f"No datasets under {settings.data_dir / 'raw'}")
        return 0

    header = f"{'EXCHANGE':<10} {'SYMBOL':<14} {'TF':<6} {'ROWS':>8}  RANGE"
    print(header)
    print("-" * len(header))
    for dataset in datasets:
        print(
            f"{dataset.exchange:<10} {dataset.symbol:<14} {dataset.timeframe:<6} "
            f"{dataset.rows:>8}  {dataset.start:%Y-%m-%d} -> {dataset.end:%Y-%m-%d}"
        )
    return 0


def _cmd_data_sql(args: argparse.Namespace, settings: Settings) -> int:
    try:
        frame = query(args.query, settings.data_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    with pd.option_context("display.max_rows", 200, "display.width", 200):
        print(frame.to_string(index=False))
    return 0


def _git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _data_fingerprint(frame: pd.DataFrame) -> str:
    payload = (
        f"{len(frame)}|{frame.index[0].isoformat()}|{frame.index[-1].isoformat()}|"
        f"{float(frame['close'].sum()):.8f}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _print_backtest(
    strategy: str,
    exchange: str,
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    result: BacktestResult,
    out_dir: Path,
) -> None:
    metrics = result.metrics
    print(f"\nBacktest {strategy} | {symbol} {timeframe} on {exchange}")
    print(f"  bars            : {len(frame)}")
    print(f"  total return    : {metrics['total_return']:+.2%}")
    print(f"  CAGR            : {metrics['cagr']:+.2%}")
    print(f"  Sharpe          : {metrics['sharpe']:.2f}")
    print(f"  Sortino         : {metrics['sortino']:.2f}")
    print(f"  max drawdown    : {metrics['max_drawdown']:.2%}")
    print(f"  exposure        : {metrics['exposure']:.1%}")
    print(f"  trades          : {int(metrics['trades'])}")
    print(f"  win rate        : {metrics['win_rate']:.1%}")
    print(f"  profit factor   : {metrics['profit_factor']:.2f}")
    print(f"  fees paid       : {metrics['fees_paid']:.2f}")
    print(f"  buy & hold      : {metrics['buy_and_hold_return']:+.2%}")
    print(f"  artifacts       : {out_dir}")


def _cmd_backtest(args: argparse.Namespace, settings: Settings) -> int:
    exchange, symbol, timeframe = _resolve_dataset(args, settings)

    try:
        frame = read_ohlcv(settings.data_dir, exchange, symbol, timeframe)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        print("Hint: run `make data-demo` or `make data-download` first.", file=sys.stderr)
        return 2

    report = validate_ohlcv(frame, timeframe)
    if not report.ok:
        print(report.summary(), file=sys.stderr)
        print("Refusing to backtest invalid data. Fix gaps/duplicates first.", file=sys.stderr)
        return 2

    signals = get_signal_builder(args.strategy)(frame)
    fee = args.fee if args.fee is not None else settings.fee
    capital = args.capital if args.capital is not None else settings.initial_capital
    config = BacktestConfig(
        fee=fee,
        initial_capital=capital,
        bars_per_year=timeframe_to_bars_per_year(timeframe),
    )
    result = run_backtest(frame, signals, config)

    out_dir = args.out or Path("research/runs") / f"{utc_now():%Y%m%dT%H%M%SZ}"
    out_dir.mkdir(parents=True, exist_ok=True)

    result.equity.to_frame("equity").to_parquet(out_dir / "equity.parquet")
    result.trades.to_parquet(out_dir / "trades.parquet", index=False)
    (out_dir / "metrics.json").write_text(
        json.dumps(result.metrics, indent=2, sort_keys=True), encoding="utf-8"
    )

    manifest = {
        "generated_at": utc_now().isoformat(),
        "git_sha": _git_sha(),
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": len(frame),
        "start": pd.Timestamp(frame.index[0]).isoformat(),
        "end": pd.Timestamp(frame.index[-1]).isoformat(),
        "data_fingerprint": _data_fingerprint(frame),
        "fee": fee,
        "initial_capital": capital,
        "strategy": args.strategy,
    }
    (out_dir / "run.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    _print_backtest(args.strategy, exchange, symbol, timeframe, frame, result, out_dir)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if args.data_dir is not None:
        settings = replace(settings, data_dir=args.data_dir)

    handler = cast(Callable[[argparse.Namespace, Settings], int], args.handler)
    return handler(args, settings)


if __name__ == "__main__":
    sys.exit(main())
