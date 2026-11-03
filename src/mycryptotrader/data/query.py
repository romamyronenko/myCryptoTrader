"""DuckDB access over the Hive-partitioned parquet store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def connect(root: Path | str) -> Any:
    """Open an in-memory DuckDB connection with an ``ohlcv`` view."""
    import duckdb

    raw_dir = Path(root) / "raw"
    if not raw_dir.exists() or not any(raw_dir.rglob("*.parquet")):
        raise FileNotFoundError(f"No parquet files under {raw_dir}")

    parquet_glob = (raw_dir / "**" / "*.parquet").as_posix()
    connection = duckdb.connect()
    connection.execute(
        f"CREATE OR REPLACE VIEW ohlcv AS "
        f"SELECT * FROM read_parquet('{parquet_glob}', hive_partitioning = true)"
    )
    return connection


def query(sql: str, root: Path | str) -> pd.DataFrame:
    """Run SQL against the store and return a DataFrame."""
    connection = connect(root)
    try:
        result: pd.DataFrame = connection.execute(sql).fetch_df()
        return result
    finally:
        connection.close()
