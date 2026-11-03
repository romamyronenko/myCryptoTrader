from __future__ import annotations

from itertools import pairwise

import pytest

from mycryptotrader.research.splits import Split, walk_forward_splits


def test_walk_forward_windows() -> None:
    splits = walk_forward_splits(100, train_size=30, test_size=10, embargo=5)

    assert splits[0] == Split(0, 30, 35, 45)
    assert splits[1] == Split(10, 40, 45, 55)
    assert all(split.test_end <= 100 for split in splits)


def test_test_windows_do_not_overlap() -> None:
    splits = walk_forward_splits(200, train_size=50, test_size=20, embargo=3)
    for current, following in pairwise(splits):
        assert current.test_end <= following.test_start


def test_embargo_is_respected() -> None:
    splits = walk_forward_splits(100, train_size=30, test_size=10, embargo=7)
    for split in splits:
        assert split.test_start - split.train_end == 7


def test_invalid_configuration_is_rejected() -> None:
    with pytest.raises(ValueError):
        walk_forward_splits(10, train_size=20, test_size=5)
    with pytest.raises(ValueError):
        walk_forward_splits(100, train_size=0, test_size=5)
    with pytest.raises(ValueError):
        walk_forward_splits(100, train_size=10, test_size=5, embargo=-1)
