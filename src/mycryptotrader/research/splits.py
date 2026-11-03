"""Walk-forward splits with purge/embargo.

Overlapping labels leak information across a naive train/test boundary. The
embargo gap removes the overlap; keep it at least as large as the label horizon.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Split:
    """Positional indices, half-open intervals: [start, end)."""

    train_start: int
    train_end: int
    test_start: int
    test_end: int


def walk_forward_splits(
    n_samples: int,
    train_size: int,
    test_size: int,
    *,
    step: int | None = None,
    embargo: int = 0,
) -> list[Split]:
    """Generate rolling train/test windows over ``n_samples`` rows."""
    if n_samples <= 0:
        raise ValueError("n_samples must be positive")
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    if embargo < 0:
        raise ValueError("embargo must be >= 0")
    if step is None:
        step = test_size
    if step <= 0:
        raise ValueError("step must be positive")

    splits: list[Split] = []
    start = 0
    while True:
        train_end = start + train_size
        test_start = train_end + embargo
        test_end = test_start + test_size
        if test_end > n_samples:
            break
        splits.append(
            Split(
                train_start=start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        start += step

    if not splits:
        raise ValueError("Not enough samples for a single split")
    return splits
