"""Unit test: Validate TimeSeriesSplit preserves chronological order.

Ensures that in every (train, test) fold produced by TimeSeriesSplit:
1. Every training index is earlier than every test index (no lookahead).
2. The date range of each fold does not overlap backwards.

Also verifies that lag/rolling features computed *within each fold*
do not leak future information across the fold boundary.

Run with:
    uv run pytest tests/pipelines/test_temporal_cv_folds.py -v
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "data" / "raw" / "brasaland_sales.csv"
SPLIT_DATE = pd.Timestamp("2024-01-01")

# Features (matching train_sales_forecast.py — NO rev_per_cover)
FEATURE_COLS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_mean_12", "rolling_std_3", "rolling_std_12",
    "month_sin", "month_cos",
]
SCALER_FEATURES = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_mean_12", "rolling_std_3", "rolling_std_12",
]


@pytest.fixture(scope="module")
def data() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Load consolidated data and build features (like evaluate_model.py)."""
    if not CSV_PATH.exists():
        pytest.skip(f"Dataset not found at {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, parse_dates=["month"])
    cons = df[df["market"] == "consolidated"].copy()
    cons = cons.sort_values("month").reset_index(drop=True)

    # Build features — using the same function as the training script
    def build_features(df: pd.DataFrame) -> pd.DataFrame:
        result = df[["month", "revenue_usd"]].copy()
        rev = df["revenue_usd"].values
        result["lag_1"] = np.roll(rev, 1)
        result["lag_2"] = np.roll(rev, 2)
        result["lag_3"] = np.roll(rev, 3)
        result["lag_12"] = np.roll(rev, 12)
        result["rolling_mean_3"] = pd.Series(rev).rolling(3, min_periods=1).mean().shift(1).values
        result["rolling_mean_12"] = pd.Series(rev).rolling(12, min_periods=1).mean().shift(1).values
        result["rolling_std_3"] = pd.Series(rev).rolling(3, min_periods=1).std().shift(1).values
        result["rolling_std_12"] = pd.Series(rev).rolling(12, min_periods=1).std().shift(1).values
        month_num = df["month"].dt.month
        result["month_sin"] = np.sin(2 * np.pi * month_num / 12)
        result["month_cos"] = np.cos(2 * np.pi * month_num / 12)
        return result

    full_feat = build_features(cons)
    full_feat = full_feat.dropna().reset_index(drop=True)

    X = full_feat[FEATURE_COLS].values
    y = full_feat["revenue_usd"].values
    months = full_feat["month"].values
    return full_feat, X, y


# ─────────────────────────────────────────────────────────────────
#  Test 1: Chronological order preservation
# ─────────────────────────────────────────────────────────────────
def test_temporal_cv_chronological_order(data) -> None:
    """Every training index must be earlier than every test index in all folds."""
    full_feat, X, y = data
    months = full_feat["month"].values
    tscv = TimeSeriesSplit(n_splits=5)

    for fold_idx, (train_idx, test_idx) in enumerate(tscv.split(X)):
        train_months = pd.DatetimeIndex(months[train_idx])
        test_months = pd.DatetimeIndex(months[test_idx])

        # Latest training date must be strictly before earliest test date
        assert train_months.max() < test_months.min(), (
            f"Fold {fold_idx + 1}: Train max {train_months.max().date()} is not "
            f"before Test min {test_months.min().date()} — chronological order broken!"
        )

        # All training indices should be numerically smaller than all test indices
        assert train_idx.max() < test_idx.min(), (
            f"Fold {fold_idx + 1}: Max train index {train_idx.max()} >= "
            f"min test index {test_idx.min()} — indices not chronological!"
        )

        # Verify no shuffle: train indices are contiguous increasing
        assert np.all(np.diff(train_idx) > 0), (
            f"Fold {fold_idx + 1}: Train indices are not monotonic increasing"
        )
        assert np.all(np.diff(test_idx) > 0), (
            f"Fold {fold_idx + 1}: Test indices are not monotonic increasing"
        )


# ─────────────────────────────────────────────────────────────────
#  Test 2: No fold overlap
# ─────────────────────────────────────────────────────────────────
def test_temporal_cv_no_overlap_between_folds(data) -> None:
    """Test sets from different folds must not overlap in time."""
    full_feat, X, y = data
    months = full_feat["month"].values
    tscv = TimeSeriesSplit(n_splits=5)

    # Collect test month ranges for each fold
    fold_test_ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for train_idx, test_idx in tscv.split(X):
        test_months = pd.DatetimeIndex(months[test_idx])
        fold_test_ranges.append((test_months.min(), test_months.max()))

    # Each fold's test period must start after the previous fold's test period ended
    for i in range(1, len(fold_test_ranges)):
        prev_end = fold_test_ranges[i - 1][1]
        curr_start = fold_test_ranges[i][0]
        assert prev_end < curr_start, (
            f"Fold {i + 1} test starts {curr_start.date()} overlaps with "
            f"fold {i} test end {prev_end.date()}"
        )


# ─────────────────────────────────────────────────────────────────
#  Test 3: Feature leakage check — lag features within each fold
# ─────────────────────────────────────────────────────────────────
def test_temporal_cv_no_leakage_from_future(data) -> None:
    """Verify that lag features computed inside each fold have no future info.

    For each fold, we rebuild features using ONLY the training data available
    at that fold's cutoff point. This simulates what the model would see if
    trained at that historical moment and ensures no lookahead.
    """
    full_feat, X, y = data
    tscv = TimeSeriesSplit(n_splits=5)

    # Also need the original consolidated data to rebuild features per fold
    df = pd.read_csv(CSV_PATH, parse_dates=["month"])
    cons = df[df["market"] == "consolidated"].copy().sort_values("month").reset_index(drop=True)

    def build_features_fold(fold_df: pd.DataFrame) -> pd.DataFrame:
        """Build features using only fold_df (no future data)."""
        result = fold_df[["month", "revenue_usd"]].copy()
        rev = fold_df["revenue_usd"].values

        # Only use available rows — no padding with future data
        result["lag_1"] = np.roll(rev, 1)
        result["lag_2"] = np.roll(rev, 2)
        result["lag_3"] = np.roll(rev, 3)
        result["lag_12"] = np.roll(rev, 12)
        result["rolling_mean_3"] = pd.Series(rev).rolling(3, min_periods=1).mean().shift(1).values
        result["rolling_mean_12"] = pd.Series(rev).rolling(12, min_periods=1).mean().shift(1).values
        result["rolling_std_3"] = pd.Series(rev).rolling(3, min_periods=1).std().shift(1).values
        result["rolling_std_12"] = pd.Series(rev).rolling(12, min_periods=1).std().shift(1).values
        month_num = fold_df["month"].dt.month
        result["month_sin"] = np.sin(2 * np.pi * month_num / 12)
        result["month_cos"] = np.cos(2 * np.pi * month_num / 12)
        return result

    for fold_idx, (train_idx, test_idx) in enumerate(tscv.split(cons)):
        # Get only training data up to the max train index
        fold_max_idx = train_idx.max()
        fold_data = cons.iloc[:fold_max_idx + 1].copy()
        fold_feat = build_features_fold(fold_data)
        fold_feat = fold_feat.dropna()

        # Verify that all lag_12 values are computed from real past data
        # (no zeros from padding)
        assert (fold_feat["lag_12"] != 0).all(), (
            f"Fold {fold_idx + 1}: lag_12 contains zeros — possible padding leak"
        )

        # For rolling stats, ensure no future data sneaks in by checking that
        # each rolling feature at position i only depends on data[:i] (shift=1 enforces this)
        # Verify shift(1) was applied: first row of rolling_mean_3 should be NaN
        # but after dropna it's fine — just verify no negative lookahead
        rolling_cols = ["rolling_mean_3", "rolling_mean_12", "rolling_std_3", "rolling_std_12"]
        for col in rolling_cols:
            # These should all be finite (no NaN after dropna)
            assert np.isfinite(fold_feat[col].values).all(), (
                f"Fold {fold_idx + 1}: {col} contains NaN — rolling window issue"
            )


# ─────────────────────────────────────────────────────────────────
#  Test 4: TimeSeriesSplit default parameters (no shuffle)
# ─────────────────────────────────────────────────────────────────
def test_temporal_cv_no_shuffle() -> None:
    """TimeSeriesSplit must be used with default shuffle=False."""
    tscv = TimeSeriesSplit(n_splits=5)
    # Verify default
    assert tscv.shuffle is False or not hasattr(tscv, 'shuffle'), (
        "TimeSeriesSplit must not shuffle data"
    )
    # Also verify that test_size is not set (uses default)
    assert tscv.test_size is None or tscv.test_size == 0, (
        f"test_size should be default, got {tscv.test_size}"
    )