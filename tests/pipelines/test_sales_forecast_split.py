"""Unit tests for the 8/2 train-test split of Brasaland sales data."""

from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "data" / "raw" / "brasaland_sales.csv"
SPLIT_DATE = pd.Timestamp("2024-01-01")


@pytest.fixture(scope="module")
def consolidated() -> pd.DataFrame:
    """Load and filter consolidated rows."""
    if not CSV_PATH.exists():
        pytest.skip(f"Dataset not found at {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, parse_dates=["month"])
    cons = df[df["market"] == "consolidated"].copy()
    return cons.sort_values("month").reset_index(drop=True)


def test_train_has_96_rows(consolidated: pd.DataFrame) -> None:
    """Train set (Jan 2016 - Dec 2023) must have exactly 96 rows."""
    train = consolidated[consolidated["month"] < SPLIT_DATE]
    assert len(train) == 96, f"Train has {len(train)} rows, expected 96"


def test_test_has_24_rows(consolidated: pd.DataFrame) -> None:
    """Test set (Jan 2024 - Dec 2025) must have exactly 24 rows."""
    test = consolidated[consolidated["month"] >= SPLIT_DATE]
    assert len(test) == 24, f"Test has {len(test)} rows, expected 24"


def test_no_date_overlap(consolidated: pd.DataFrame) -> None:
    """Train and test dates must not overlap."""
    train = consolidated[consolidated["month"] < SPLIT_DATE]
    test = consolidated[consolidated["month"] >= SPLIT_DATE]
    assert train["month"].max() < test["month"].min(), (
        f"Overlap: train max {train['month'].max()} >= test min {test['month'].min()}"
    )


def test_total_rows_120(consolidated: pd.DataFrame) -> None:
    """Total consolidated rows must be 120 (10 years x 12 months)."""
    assert len(consolidated) == 120, f"Total {len(consolidated)} rows, expected 120"


def test_no_missing_months(consolidated: pd.DataFrame) -> None:
    """Must have exactly one row per month with no gaps."""
    expected = pd.date_range(start="2016-01-01", end="2025-12-01", freq="MS")
    actual = consolidated["month"].sort_values().unique()
    assert len(actual) == len(expected), (
        f"Expected {len(expected)} unique months, got {len(actual)}"
    )
    assert (pd.DatetimeIndex(actual) == expected).all(), (
        "Month sequence has gaps or mismatches"
    )


def test_all_revenue_positive(consolidated: pd.DataFrame) -> None:
    """All revenue values must be strictly positive."""
    assert (consolidated["revenue_usd"] > 0).all(), (
        "Found non-positive revenue values"
    )


def test_split_exhaustive(consolidated: pd.DataFrame) -> None:
    """Train + test rows must equal total rows."""
    train = consolidated[consolidated["month"] < SPLIT_DATE]
    test = consolidated[consolidated["month"] >= SPLIT_DATE]
    assert len(train) + len(test) == len(consolidated), (
        "Train + test != total rows"
    )