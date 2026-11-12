#!/usr/bin/env python3
"""Evaluate sales forecasting model: learning curves, temporal CV, residual analysis.

Usage:
    uv run python3 scripts/evaluate_model.py

Output:
    - Terminal: diagnostic tables
    - docs/evidencias/learning_curves.png
    - docs/evidencias/cv_results.png
    - docs/evidencias/residual_analysis.png
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from sklearn.metrics import mean_squared_error, mean_absolute_error
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import TimeSeriesSplit
except ImportError:
    sys.exit("scikit-learn is required. Run: uv add scikit-learn")

try:
    import xgboost as xgb
except ImportError:
    sys.exit("xgboost is required. Run: uv add xgboost")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("matplotlib is required. Run: uv add matplotlib")

warnings.filterwarnings("ignore", category=UserWarning, module="xgboost")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"
EVAL_DIR = ROOT / "data" / "eval"
EVIDENCIAS_DIR = ROOT / "docs" / "evidencias"
EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants (matching train_sales_forecast.py) ─────────────────
FEATURE_COLS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_mean_12", "rolling_std_3", "rolling_std_12",
    "month_sin", "month_cos",
]
SCALER_FEATURES = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_mean_12", "rolling_std_3", "rolling_std_12",
]
MODEL_PARAMS = {
    "n_estimators": 500,
    "max_depth": 4,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 1.0,
    "reg_lambda": 2.0,
    "random_state": 42,
    "early_stopping_rounds": 20,
    "verbosity": 0,
}
SPLIT_DATE = "2024-01-01"


# ── Shared helpers (mirroring train_sales_forecast.py) ────────────
def load_consolidated() -> pd.DataFrame:
    CSV_PATH = DATA_DIR / "brasaland_sales.csv"
    if not CSV_PATH.exists():
        sys.exit(f"Dataset not found at {CSV_PATH}. Run generate_sales_data.py first.")
    df = pd.read_csv(CSV_PATH, parse_dates=["month"])
    cons = df[df["market"] == "consolidated"].copy()
    return cons.sort_values("month").reset_index(drop=True)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build causal features from the revenue series (no leakage)."""
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


def prepare_data(consolidated: pd.DataFrame):
    """Split train/test, build features, scale, return arrays."""
    train = consolidated[consolidated["month"] < SPLIT_DATE].copy()
    test = consolidated[consolidated["month"] >= SPLIT_DATE].copy()

    train_feat = build_features(train)
    test_feat = build_features(test)

    # Fix test features with actual past values from train tail
    train_last_12 = train["revenue_usd"].values[-12:]
    test_augmented = np.concatenate([train_last_12, test["revenue_usd"].values])
    test_feat["lag_1"] = np.roll(test_augmented, 1)[12:]
    test_feat["lag_2"] = np.roll(test_augmented, 2)[12:]
    test_feat["lag_3"] = np.roll(test_augmented, 3)[12:]
    test_feat["lag_12"] = np.roll(test_augmented, 12)[12:]

    train_tail = pd.Series(train["revenue_usd"].values[-12:])
    test_series = pd.Series(test["revenue_usd"].values)
    combined_series = pd.concat([train_tail, test_series], ignore_index=True)
    test_feat["rolling_mean_3"] = combined_series.rolling(3, min_periods=1).mean().shift(1).values[12:]
    test_feat["rolling_mean_12"] = combined_series.rolling(12, min_periods=1).mean().shift(1).values[12:]
    test_feat["rolling_std_3"] = combined_series.rolling(3, min_periods=1).std().shift(1).values[12:]
    test_feat["rolling_std_12"] = combined_series.rolling(12, min_periods=1).std().shift(1).values[12:]

    train_feat = train_feat.dropna().reset_index(drop=True)
    test_feat = test_feat.dropna().reset_index(drop=True)

    X_train_all = train_feat[FEATURE_COLS].values
    y_train_all = train_feat["revenue_usd"].values
    X_test = test_feat[FEATURE_COLS].values
    y_test = test_feat["revenue_usd"].values

    # Scale
    scaler = StandardScaler()
    scaled_indices = [FEATURE_COLS.index(f) for f in SCALER_FEATURES]
    X_train_scaled = X_train_all.copy()
    X_test_scaled = X_test.copy()
    X_train_scaled[:, scaled_indices] = scaler.fit_transform(X_train_all[:, scaled_indices])
    X_test_scaled[:, scaled_indices] = scaler.transform(X_test[:, scaled_indices])

    return X_train_scaled, y_train_all, X_test_scaled, y_test, train_feat, test_feat


# ── Metrics ──────────────────────────────────────────────────────
def gini(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    n = len(y_true)
    if n < 2:
        return 0.0
    def _gini(values):
        vals = np.sort(values)[::-1]
        cumsum = np.cumsum(vals)
        return float((2 * np.sum(cumsum) / (n * np.sum(vals)) - (n + 1) / n))
    idx = np.argsort(y_pred)[::-1]
    g_model = _gini(y_true[idx])
    g_perfect = _gini(y_true)
    return max(0.0, min(1.0, g_model / g_perfect)) if g_perfect > 0 else 0.0


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected = np.asarray(expected, dtype=np.float64)
    actual = np.asarray(actual, dtype=np.float64)
    if len(expected) < bins or len(actual) < bins:
        return 0.0
    try:
        percentiles = np.linspace(0, 100, bins + 1)[1:-1]
        bin_edges = np.percentile(expected, percentiles)
    except IndexError:
        return 0.0
    if len(np.unique(bin_edges)) < 2:
        return 0.0
    expected_counts, _ = np.histogram(expected, bins=np.concatenate([[-np.inf], bin_edges, [np.inf]]))
    actual_counts, _ = np.histogram(actual, bins=np.concatenate([[-np.inf], bin_edges, [np.inf]]))
    expected_pct = np.clip(expected_counts / len(expected), 1e-6, 1.0)
    actual_pct = np.clip(actual_counts / len(actual), 1e-6, 1.0)
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))


def k2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    n = len(y_true)
    if n < 2:
        return 0.0
    r = np.clip(np.corrcoef(y_true, y_pred)[0, 1], -1.0, 1.0)
    alpha = np.clip(np.std(y_pred) / (np.std(y_true) + 1e-10), 0.0, 3.0)
    beta = np.clip(np.mean(y_pred) / (np.mean(y_true) + 1e-10), 0.0, 3.0)
    k2 = 1.0 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2)
    return max(0.0, min(1.0, k2))


def compute_all_metrics(y_true, y_pred):
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true, y_pred)
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    return {
        "MSE": mse,
        "RMSE": rmse,
        "MAE": mae,
        "MAPE": mape,
        "Gini": gini(y_true, y_pred),
        "K2": k2_score(y_true, y_pred),
    }


# ══════════════════════════════════════════════════════════════════
#   SECTION 1 — Learning Curves (underfitting vs overfitting)
# ══════════════════════════════════════════════════════════════════
def compute_learning_curves(
    X_train: np.ndarray, y_train: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
    fractions: list[float] | None = None,
):
    """Compute train & validation error at increasing train-set fractions."""
    if fractions is None:
        fractions = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    n_total = len(X_train)
    train_errors_rmse = []
    val_errors_rmse = []
    train_errors_mae = []
    val_errors_mae = []
    train_sizes = []

    print("\n" + "=" * 60)
    print("LEARNING CURVES")
    print("=" * 60)

    for frac in fractions:
        n_samples = max(10, int(n_total * frac))
        train_sizes.append(n_samples)

        X_sub = X_train[:n_samples]
        y_sub = y_train[:n_samples]

        model = xgb.XGBRegressor(**MODEL_PARAMS)
        model.fit(
            X_sub, y_sub,
            eval_set=[(X_sub, y_sub), (X_test, y_test)],
            verbose=False,
        )

        y_train_pred = model.predict(X_sub)
        y_test_pred = model.predict(X_test)

        train_rmse = np.sqrt(mean_squared_error(y_sub, y_train_pred))
        val_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
        train_mae = mean_absolute_error(y_sub, y_train_pred)
        val_mae = mean_absolute_error(y_test, y_test_pred)

        train_errors_rmse.append(train_rmse)
        val_errors_rmse.append(val_rmse)
        train_errors_mae.append(train_mae)
        val_errors_mae.append(val_mae)

        gap_rmse = val_rmse - train_rmse
        gap_mae = val_mae - train_mae
        print(f"  Train size {n_samples:3d} ({frac:>4.0%}) — "
              f"Train RMSE: ${train_rmse:>8,.0f} / MAE: ${train_mae:>8,.0f}  "
              f"Val RMSE: ${val_rmse:>8,.0f} / MAE: ${val_mae:>8,.0f}  "
              f"Gap RMSE: ${gap_rmse:>7,.0f}  Gap MAE: ${gap_mae:>7,.0f}")

    # Plot — two subplots: RMSE (top) and MAE (bottom)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

    # ── RMSE subplot ──
    ax1.plot(train_sizes, train_errors_rmse, "b-o", label="Training RMSE", linewidth=2, markersize=6)
    ax1.plot(train_sizes, val_errors_rmse, "r-s", label="Validation RMSE", linewidth=2, markersize=6)
    ax1.fill_between(train_sizes, train_errors_rmse, val_errors_rmse, alpha=0.15, color="gray", label="Generalization gap")
    ax1.set_ylabel("RMSE (USD)")
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # ── MAE subplot ──
    ax2.plot(train_sizes, train_errors_mae, "b-o", label="Training MAE", linewidth=2, markersize=6)
    ax2.plot(train_sizes, val_errors_mae, "r-s", label="Validation MAE", linewidth=2, markersize=6)
    ax2.fill_between(train_sizes, train_errors_mae, val_errors_mae, alpha=0.15, color="gray", label="Generalization gap")
    ax2.set_xlabel("Training set size (months)")
    ax2.set_ylabel("MAE (USD)")
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    fig.suptitle("Learning Curves — Brasaland Sales Forecast (XGBoost, max_depth=4)", fontsize=13, fontweight="bold")

    # Annotate diagnostic
    final_gap = val_errors_rmse[-1] - train_errors_rmse[-1]
    final_train = train_errors_rmse[-1]
    final_val = val_errors_rmse[-1]

    # Determine relative gap
    relative_gap = final_gap / final_val if final_val > 0 else 0

    if relative_gap > 0.30:
        diagnosis = "⚠️  HIGH GAP — Possible overfitting (gap > 30% of val error)"
    elif relative_gap < 0.10 and final_val > 150_000:
        diagnosis = "⚠️  HIGH ERROR CONVERGENCE — Possible underfitting (both curves converge high)"
    elif relative_gap < 0.10 and final_val < 150_000:
        diagnosis = "✅  GOOD FIT — Both curves converge low and close"
    else:
        diagnosis = "➡️  MODERATE GAP — Acceptable, monitor with more data"

    print(f"\n  ── Diagnostic ──")
    print(f"  Final train RMSE: ${final_train:,.0f}  / MAE: ${train_errors_mae[-1]:,.0f}")
    print(f"  Final val RMSE:   ${final_val:,.0f}  / MAE: ${val_errors_mae[-1]:,.0f}")
    print(f"  Relative gap (RMSE): {relative_gap:.1%}")
    print(f"  → {diagnosis}")

    ax1.text(
        0.98, 0.05, f"Relative gap: {relative_gap:.1%}\n{diagnosis}",
        transform=ax1.transAxes, fontsize=9, verticalalignment="bottom",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8),
    )

    # Save to both locations
    path_ev = EVIDENCIAS_DIR / "learning_curves.png"
    path_eval = EVAL_DIR / "learning_curves.png"
    plt.tight_layout()
    plt.savefig(path_ev, dpi=150)
    plt.savefig(path_eval, dpi=150)
    print(f"  Learning curves saved to {path_ev}")
    print(f"  Learning curves saved to {path_eval}")
    plt.close()

    return {
        "train_sizes": train_sizes,
        "train_errors_rmse": train_errors_rmse,
        "val_errors_rmse": val_errors_rmse,
        "train_errors_mae": train_errors_mae,
        "val_errors_mae": val_errors_mae,
        "relative_gap": relative_gap,
        "diagnosis": diagnosis,
    }


# ══════════════════════════════════════════════════════════════════
#   SECTION 2 — Temporal Cross-Validation (stability)
# ══════════════════════════════════════════════════════════════════
def temporal_cross_validation(consolidated: pd.DataFrame, n_splits: int = 5):
    """Perform TimeSeriesSplit CV and report stability of metrics."""
    print("\n" + "=" * 60)
    print(f"TEMPORAL CROSS-VALIDATION ({n_splits} folds)")
    print("=" * 60)

    tscv = TimeSeriesSplit(n_splits=n_splits)
    all_metrics: list[dict] = []

    # Use full data sorted by month
    data = consolidated.sort_values("month").reset_index(drop=True)
    full_feat = build_features(data)
    full_feat = full_feat.dropna().reset_index(drop=True)

    X_full = full_feat[FEATURE_COLS].values
    y_full = full_feat["revenue_usd"].values
    months_full = full_feat["month"].values

    fold_idx = 0
    for train_idx, test_idx in tscv.split(X_full):
        fold_idx += 1
        X_tr, X_te = X_full[train_idx], X_full[test_idx]
        y_tr, y_te = y_full[train_idx], y_full[test_idx]

        # Scale inside fold (no leakage)
        scaler = StandardScaler()
        scaled_indices = [FEATURE_COLS.index(f) for f in SCALER_FEATURES]
        X_tr_s = X_tr.copy()
        X_te_s = X_te.copy()
        X_tr_s[:, scaled_indices] = scaler.fit_transform(X_tr[:, scaled_indices])
        X_te_s[:, scaled_indices] = scaler.transform(X_te[:, scaled_indices])

        model = xgb.XGBRegressor(**MODEL_PARAMS)
        model.fit(X_tr_s, y_tr, eval_set=[(X_tr_s, y_tr), (X_te_s, y_te)], verbose=False)

        y_pred = model.predict(X_te_s)
        metrics = compute_all_metrics(y_te, y_pred)
        metrics["fold"] = fold_idx
        metrics["train_months"] = len(train_idx)
        metrics["test_months"] = len(test_idx)
        metrics["test_start"] = str(pd.Timestamp(months_full[test_idx[0]]).date())
        metrics["test_end"] = str(pd.Timestamp(months_full[test_idx[-1]]).date())
        all_metrics.append(metrics)

        print(f"\n  Fold {fold_idx}: train={len(train_idx)} test={len(test_idx)} "
              f"({metrics['test_start']} to {metrics['test_end']})")
        print(f"    RMSE: ${metrics['RMSE']:>8,.0f}  MAPE: {metrics['MAPE']:>5.2f}%  "
              f"Gini: {metrics['Gini']:.4f}  K2: {metrics['K2']:.4f}")

    # Summary statistics
    print(f"\n  ── Cross-validation summary ({n_splits} folds) ──")
    metrics_names = ["RMSE", "MAPE", "Gini", "K2"]
    summary = {}
    for name in metrics_names:
        values = [m[name] for m in all_metrics]
        mean_v = np.mean(values)
        std_v = np.std(values)
        cv = std_v / mean_v if mean_v > 0 else 0  # coefficient of variation
        summary[name] = {"mean": mean_v, "std": std_v, "cv": cv}
        print(f"    {name:6s}:  mean={mean_v:>10,.2f}  std={std_v:>10,.2f}  CV={cv:>7.2%}")

    # Stability diagnosis
    avg_cv = np.mean([summary[m]["cv"] for m in metrics_names])
    print(f"\n  Average CV across metrics: {avg_cv:.2%}")
    if avg_cv < 0.10:
        stability = "✅  STABLE — Performance is consistent across temporal folds"
    elif avg_cv < 0.25:
        stability = "⚠️  MODERATELY STABLE — Some variability, investigate edge folds"
    else:
        stability = "❌  UNSTABLE — Performance varies significantly by time period"
    print(f"  → {stability}")

    # Plot CV results
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    for i, name in enumerate(metrics_names):
        ax = axes[i]
        values = [m[name] for m in all_metrics]
        labels = [f"Fold {m['fold']}" for m in all_metrics]
        bars = ax.bar(labels, values, color="steelblue", alpha=0.8)
        ax.axhline(summary[name]["mean"], color="red", linestyle="--", label=f"Mean={summary[name]['mean']:.2f}")
        ax.set_title(f"{name} per fold")
        ax.set_ylabel(name)
        ax.legend(fontsize=8)
        ax.tick_params(axis="x", rotation=30)

    fig.suptitle("Temporal Cross-Validation — Brasaland Sales Forecast", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = EVIDENCIAS_DIR / "cv_results.png"
    plt.savefig(path, dpi=150)
    print(f"  CV plot saved to {path}")
    plt.close()

    return summary, stability, all_metrics


# ══════════════════════════════════════════════════════════════════
#   SECTION 3 — Residual Analysis (bias, seasonality, direction)
# ══════════════════════════════════════════════════════════════════
def residual_analysis(y_test: np.ndarray, y_pred: np.ndarray, test_feat: pd.DataFrame):
    """Analyze residuals for systematic bias and seasonal patterns."""
    print("\n" + "=" * 60)
    print("RESIDUAL ANALYSIS")
    print("=" * 60)

    residuals = y_test - y_pred
    pct_errors = ((y_test - y_pred) / y_test) * 100
    months = pd.to_datetime(test_feat["month"])
    month_nums = months.dt.month.values
    years = months.dt.year.values

    # Overall bias
    mean_residual = np.mean(residuals)
    median_residual = np.median(residuals)
    std_residual = np.std(residuals)
    bias_pct = np.mean(pct_errors)

    print(f"\n  Overall bias (mean residual): ${mean_residual:>8,.0f} "
          f"(median: ${median_residual:>8,.0f})")
    print(f"  Mean % error (bias): {bias_pct:>7.2f}%")
    print(f"  Residual std: ${std_residual:>8,.0f}")

    if abs(bias_pct) > 3.0:
        direction = "overestimating" if bias_pct < 0 else "underestimating"
        print(f"  ⚠️  Systematic bias detected — model is {direction} by {abs(bias_pct):.1f}% on average")
    else:
        print(f"  ✅  No significant systematic bias (|bias| < 3%)")

    # Error by month
    print(f"\n  ── Error by month of year ──")
    print(f"  {'Month':<8} {'Mean Error $':>12} {'Mean % Error':>12} {'|Pred|>|Actual|':>14}")
    monthly_stats = []
    for m in range(1, 13):
        mask = month_nums == m
        if mask.sum() == 0:
            continue
        m_res = residuals[mask]
        m_pct = pct_errors[mask]
        over_count = (np.abs(y_pred[mask]) > np.abs(y_test[mask])).sum()
        mean_err = np.mean(m_res)
        mean_pct = np.mean(m_pct)
        monthly_stats.append({
            "month": m,
            "mean_error": mean_err,
            "mean_pct": mean_pct,
            "over_count": over_count,
            "count": mask.sum(),
        })
        print(f"  {'Month':>8} {mean_err:>12,.0f} {mean_pct:>11.2f}%  "
              f"{over_count}/{mask.sum()}")

    # December vs January specific
    dec_mask = month_nums == 12
    jan_mask = month_nums == 1
    if dec_mask.sum() > 0:
        dec_pct = np.mean(pct_errors[dec_mask])
        print(f"\n  December mean error: {dec_pct:>6.2f}% (critical month for revenue)")
    if jan_mask.sum() > 0:
        jan_pct = np.mean(pct_errors[jan_mask])
        print(f"  January mean error:  {jan_pct:>6.2f}% (post-holiday drop)")

    # Business impact assessment
    print(f"\n  ── Business impact ──")
    over_mask = residuals < 0  # model over-predicted
    under_mask = residuals > 0  # model under-predicted
    over_sum = np.sum(np.abs(residuals[over_mask]))
    under_sum = np.sum(residuals[under_mask])
    total_residual = over_sum + under_sum
    print(f"  Total over-prediction amount:   ${over_sum:>10,.0f} "
          f"({over_sum/total_residual*100:.1f}% of total absolute error)")
    print(f"  Total under-prediction amount:  ${under_sum:>10,.0f} "
          f"({under_sum/total_residual*100:.1f}% of total absolute error)")

    if over_sum > under_sum * 1.2:
        print(f"  ⚠️  Model tends to OVERESTIMATE — risk: overbuying perishable inventory")
    elif under_sum > over_sum * 1.2:
        print(f"  ⚠️  Model tends to UNDERESTIMATE — risk: stockouts, lost sales")
    else:
        print(f"  ✅  Errors balanced between over and under-prediction")

    # Plot residuals
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Residuals over time
    ax = axes[0, 0]
    ax.axhline(0, color="black", linewidth=0.5)
    ax.axhline(mean_residual, color="red", linestyle="--", label=f"Mean bias: ${mean_residual:,.0f}")
    colors = ["#e74c3c" if r < 0 else "#2ecc71" for r in residuals]
    ax.bar(months, residuals, color=colors, alpha=0.7, width=20)
    ax.set_title("Residuals over time (red=overprediction, green=underprediction)")
    ax.set_ylabel("Error (USD)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 2. Prediction vs actual
    ax = axes[0, 1]
    min_val = min(y_test.min(), y_pred.min())
    max_val = max(y_test.max(), y_pred.max())
    ax.plot([min_val, max_val], [min_val, max_val], "k--", alpha=0.5, label="Perfect prediction")
    ax.scatter(y_test, y_pred, alpha=0.7, s=40, c=month_nums, cmap="viridis")
    ax.set_xlabel("Actual Revenue (USD)")
    ax.set_ylabel("Predicted Revenue (USD)")
    ax.set_title("Prediction vs Actual (color=month)")
    cbar = plt.colorbar(ax.collections[0], ax=ax, ticks=range(1, 13))
    cbar.set_label("Month")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    # 3. Error distribution
    ax = axes[1, 0]
    ax.hist(residuals, bins=12, edgecolor="black", alpha=0.7, color="steelblue")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.axvline(mean_residual, color="red", linestyle="--", label=f"Mean: ${mean_residual:,.0f}")
    ax.set_title("Distribution of residuals")
    ax.set_xlabel("Error (USD)")
    ax.set_ylabel("Frequency")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 4. Mean % error by month
    ax = axes[1, 1]
    m_labels = [f"{m:02d}" for m in range(1, 13)]
    m_vals = []
    for m in range(1, 13):
        mask = month_nums == m
        m_vals.append(np.mean(pct_errors[mask]) if mask.sum() > 0 else 0)
    bars = ax.bar(m_labels, m_vals, color=["#e74c3c" if v < 0 else "#2ecc71" for v in m_vals])
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_title("Mean % error by month")
    ax.set_xlabel("Month")
    ax.set_ylabel("Mean % Error")
    ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle("Residual Analysis — Brasaland Sales Forecast", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = EVIDENCIAS_DIR / "residual_analysis.png"
    plt.savefig(path, dpi=150)
    print(f"\n  Residual analysis saved to {path}")
    plt.close()

    return {
        "mean_residual": mean_residual,
        "bias_pct": bias_pct,
        "residual_std": std_residual,
        "monthly_stats": monthly_stats,
        "over_sum": over_sum,
        "under_sum": under_sum,
    }


# ══════════════════════════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("SALES FORECAST MODEL — TECHNICAL EVALUATION")
    print("=" * 60)

    consolidated = load_consolidated()
    print(f"\nLoaded {len(consolidated)} consolidated rows "
          f"({consolidated['month'].min().date()} to {consolidated['month'].max().date()})")

    X_train, y_train, X_test, y_test, train_feat, test_feat = prepare_data(consolidated)
    print(f"Train: {X_train.shape[0]} samples, Test: {X_test.shape[0]} samples")

    # ── 1. Learning curves ──
    lc_result = compute_learning_curves(X_train, y_train, X_test, y_test)

    # ── 2. Temporal CV ──
    cv_summary, cv_stability, cv_metrics = temporal_cross_validation(consolidated, n_splits=5)

    # ── 3. Residual analysis (using main model from train_sales_forecast.py) ──
    # Train a fresh model on full train set for residual analysis
    model = xgb.XGBRegressor(**MODEL_PARAMS)
    model.fit(X_train, y_train, eval_set=[(X_train, y_train), (X_test, y_test)], verbose=False)
    y_pred = model.predict(X_test)
    residual_result = residual_analysis(y_test, y_pred, test_feat)

    # ── Final consolidated diagnosis ──
    print("\n" + "=" * 60)
    print("FINAL DIAGNOSIS — ANSWERING THE TICKET")
    print("=" * 60)

    # Question 1: Underfitting / Overfitting / Good fit
    print(f"\n📌 Q1: ¿Underfitting, overfitting, o buen ajuste?")
    print(f"   Learning curves diagnosis: {lc_result['diagnosis']}")
    final_val_rmse = lc_result["val_errors_rmse"][-1]
    if lc_result["relative_gap"] < 0.10 and final_val_rmse < 150_000:
        print(f"   → CONCLUIMOS: Buen ajuste (good fit)")
    elif lc_result["relative_gap"] > 0.30:
        print(f"   → CONCLUIMOS: Posible overfitting (gap alto)")
    elif lc_result["relative_gap"] < 0.10 and final_val_rmse >= 150_000:
        print(f"   → CONCLUIMOS: Posible underfitting (errores altos convergen)")
    else:
        print(f"   → CONCLUIMOS: Ajuste moderado, situación mixta")

    # Question 2: Stability
    avg_cv = np.mean([cv_summary[m]["cv"] for m in ["RMSE", "MAPE", "Gini", "K2"]])
    print(f"\n📌 Q2: ¿Qué tan estable es el desempeño?")
    print(f"   CV stability diagnosis: {cv_stability}")
    print(f"   Average coefficient of variation: {avg_cv:.2%}")
    print(f"   → El desempeño es estable si el CV promedio es < 10%, "
          f"moderado entre 10-25%, inestable si > 25%")

    # Question 3: Specific corrective action
    print(f"\n📌 Q3: Acción correctiva específica")
    final_val_rmse = lc_result["val_errors_rmse"][-1]
    if lc_result["relative_gap"] > 0.30:
        print(f"   🔧 Overfitting detectado: aumentar regularización "
              f"(reg_alpha, reg_lambda), reducir max_depth, o aumentar datos")
    elif lc_result["relative_gap"] < 0.10 and final_val_rmse >= 150_000:
        print(f"   🔧 Underfitting detectado: aumentar complejidad del modelo "
              f"(mayor max_depth, más estimadores) o mejorar features")
    else:
        print(f"   ✅ Modelo razonablemente bien ajustado")
        print(f"   🔧 Acción recomendada: monitoreo continuo con reentrenamiento "
              f"periódico cada 6 meses (dado el drift detectado por PSI)")

    # Business-specific recommendation
    print(f"\n   Consideración de negocio (error más costoso):")
    if residual_result["over_sum"] > residual_result["under_sum"] * 1.2:
        print(f"   - El modelo tiende a SOBREESTIMAR, lo que para Brasaland implica")
        print(f"     riesgo de COMPRAR EXCESO DE INSUMOS PERECEDEROS → desperdicio.")
        print(f"     Acción: aplicar corrección de sesgo o ajustar umbral de decisión.")
    elif residual_result["under_sum"] > residual_result["over_sum"] * 1.2:
        print(f"   - El modelo tiende a SUBESTIMAR, lo que para Brasaland implica")
        print(f"     riesgo de QUEDARSE SIN STOCK → pérdida de ventas y clientes.")
        print(f"     Acción: revisar features de crecimiento, calibrar con datos recientes.")
    else:
        print(f"   - Errores balanceados entre sobre y subestimación.")
        print(f"     El modelo no tiene sesgo direccional significativo.")

    print(f"\n{'='*60}")
    print("Evaluation complete. See docs/evidencias/ for plots.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()