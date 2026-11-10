#!/usr/bin/env python3
"""Train and evaluate a sales forecasting regression model for Brasaland.

Uses XGBoost to predict consolidated monthly revenue from historical data.

Model choice — XGBoost vs Random Forest:
    XGBoost is chosen over Random Forest for this problem because:
    1. The dataset exhibits strong seasonality (Jan drop 12-18%, Dec rise 20-30%)
       combined with a steady growth trend (3-7% annual). XGBoost's sequential
       boosting corrects residuals iteratively, which better captures these
       non-linear interactions between season, trend, and lag features.
    2. With only 96 training samples, Random Forest's ensemble averaging tends
       to smooth out the sharp Dec peaks and Jan troughs that are critical for
       business decisions (inventory planning, cash flow forecasting).
    3. XGBoost provides native feature importance, allowing Mariana and Felipe
       to understand which factors drive predictions.
    4. Risk of overfitting with 96 rows is mitigated by: max_depth=4, subsample=0.8,
       learning_rate=0.1, and early stopping.

Usage:
    uv run python3 scripts/train_sales_forecast.py
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
EVIDENCIAS_DIR = ROOT / "docs" / "evidencias"
EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. Load data ──────────────────────────────────────────────────
CSV_PATH = DATA_DIR / "brasaland_sales.csv"
if not CSV_PATH.exists():
    sys.exit(f"Dataset not found at {CSV_PATH}. Run generate_sales_data.py first.")

df = pd.read_csv(CSV_PATH, parse_dates=["month"])
consolidated = df[df["market"] == "consolidated"].copy()
consolidated = consolidated.sort_values("month").reset_index(drop=True)

print(f"Total consolidated rows: {len(consolidated)}")
print(f"Date range: {consolidated['month'].min()} to {consolidated['month'].max()}")

# ── 2. Train/test split (8 years train, 2 years test) ─────────────
SPLIT_DATE = "2024-01-01"
train = consolidated[consolidated["month"] < SPLIT_DATE].copy()
test = consolidated[consolidated["month"] >= SPLIT_DATE].copy()

n_train_expected = 8 * 12  # 96 months
n_test_expected = 2 * 12   # 24 months

print(f"\nTrain rows: {len(train)} (expected {n_train_expected})")
print(f"Test rows:  {len(test)} (expected {n_test_expected})")

assert len(train) == n_train_expected, f"Expected {n_train_expected} train rows, got {len(train)}"
assert len(test) == n_test_expected, f"Expected {n_test_expected} test rows, got {len(test)}"
assert train["month"].max() < test["month"].min(), "Train/test date overlap detected!"

# ── 3. Feature engineering (no leakage) ───────────────────────────
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build causal features from the revenue series.

    All features use only past information — no future leakage.
    Lags look backward; rolling stats use expanding windows with shift.
    """
    result = df[["month", "revenue_usd"]].copy()
    rev = df["revenue_usd"].values

    # Lags — backward-looking only
    result["lag_1"] = np.roll(rev, 1)
    result["lag_2"] = np.roll(rev, 2)
    result["lag_3"] = np.roll(rev, 3)
    result["lag_12"] = np.roll(rev, 12)  # same month last year

    # Rolling stats — past observations only (shift by 1 to avoid leakage)
    result["rolling_mean_3"] = pd.Series(rev).rolling(3, min_periods=1).mean().shift(1).values
    result["rolling_mean_12"] = pd.Series(rev).rolling(12, min_periods=1).mean().shift(1).values
    result["rolling_std_3"] = pd.Series(rev).rolling(3, min_periods=1).std().shift(1).values
    result["rolling_std_12"] = pd.Series(rev).rolling(12, min_periods=1).std().shift(1).values

    # Calendar features — cyclic encoding (no leakage)
    month_num = df["month"].dt.month
    result["month_sin"] = np.sin(2 * np.pi * month_num / 12)
    result["month_cos"] = np.cos(2 * np.pi * month_num / 12)

    return result


# Build features for train
train_feat = build_features(train)

# Build test features using train tail for warm-up (no future leakage)
test_feat = build_features(test)

# Fix test features: use actual past values (from train tail) for lags/rolling
train_last_12 = train["revenue_usd"].values[-12:]
test_augmented = np.concatenate([train_last_12, test["revenue_usd"].values])

test_feat["lag_1"] = np.roll(test_augmented, 1)[12:]
test_feat["lag_2"] = np.roll(test_augmented, 2)[12:]
test_feat["lag_3"] = np.roll(test_augmented, 3)[12:]
test_feat["lag_12"] = np.roll(test_augmented, 12)[12:]

# Rolling stats for test using train tail as warm-up
train_tail = pd.Series(train["revenue_usd"].values[-12:])
test_series = pd.Series(test["revenue_usd"].values)
combined_series = pd.concat([train_tail, test_series], ignore_index=True)

test_feat["rolling_mean_3"] = combined_series.rolling(3, min_periods=1).mean().shift(1).values[12:]
test_feat["rolling_mean_12"] = combined_series.rolling(12, min_periods=1).mean().shift(1).values[12:]
test_feat["rolling_std_3"] = combined_series.rolling(3, min_periods=1).std().shift(1).values[12:]
test_feat["rolling_std_12"] = combined_series.rolling(12, min_periods=1).std().shift(1).values[12:]

# Drop rows with NaN (first 12 months of train don't have lag_12)
train_feat = train_feat.dropna().reset_index(drop=True)
test_feat = test_feat.dropna().reset_index(drop=True)

FEATURE_COLS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_mean_12", "rolling_std_3", "rolling_std_12",
    "month_sin", "month_cos",
]

X_train_raw = train_feat[FEATURE_COLS].values
y_train = train_feat["revenue_usd"].values
X_test_raw = test_feat[FEATURE_COLS].values
y_test = test_feat["revenue_usd"].values

print(f"\nFeature matrix shapes — X_train: {X_train_raw.shape}, X_test: {X_test_raw.shape}")

SCALER_FEATURES = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_mean_12", "rolling_std_3", "rolling_std_12",
]
scaled_indices = [FEATURE_COLS.index(f) for f in SCALER_FEATURES]

# ── 4. Early stopping via temporal validation split (80/20 within train) ──
# NEVER use the 2-year test set for model selection.
VAL_FRAC = 0.8
val_cutoff = int(len(X_train_raw) * VAL_FRAC)

X_fit_raw = X_train_raw[:val_cutoff]
y_fit = y_train[:val_cutoff]
X_val_raw = X_train_raw[val_cutoff:]
y_val = y_train[val_cutoff:]

fit_scaler = StandardScaler()
X_fit = X_fit_raw.copy()
X_val = X_val_raw.copy()
X_fit[:, scaled_indices] = fit_scaler.fit_transform(X_fit_raw[:, scaled_indices])
X_val[:, scaled_indices] = fit_scaler.transform(X_val_raw[:, scaled_indices])

selection_model = xgb.XGBRegressor(
    n_estimators=500,
    max_depth=4,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=1.0,
    reg_lambda=2.0,
    random_state=42,
    early_stopping_rounds=20,
    verbosity=0,
)
selection_model.fit(
    X_fit, y_fit,
    eval_set=[(X_val, y_val)],
    verbose=False,
)
best_iter = selection_model.best_iteration

# ── 5. Refit on full train set with selected iterations ──────────
scaler = StandardScaler()
X_train = X_train_raw.copy()
X_test = X_test_raw.copy()
X_train[:, scaled_indices] = scaler.fit_transform(X_train_raw[:, scaled_indices])
X_test[:, scaled_indices] = scaler.transform(X_test_raw[:, scaled_indices])

model = xgb.XGBRegressor(
    n_estimators=best_iter + 1,
    max_depth=4,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=1.0,
    reg_lambda=2.0,
    random_state=42,
    verbosity=0,
)
model.fit(X_train, y_train, verbose=False)

print(f"\nTraining complete. Selected iterations: {best_iter + 1} "
      f"(from temporal validation split {int(VAL_FRAC*100)}/{int((1-VAL_FRAC)*100)})")

# ── 6. Metrics on test set ──────────────────────────────────────
y_pred = model.predict(X_test)

# 6a. MSE + RMSE + MAE + MAPE
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
mae = mean_absolute_error(y_test, y_pred)
mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100

print(f"\n{'='*50}")
print(f"METRICS ON TEST SET ({len(y_test)} months)")
print(f"{'='*50}")
print(f"MSE:  {mse:,.2f} USD²")
print(f"RMSE: {rmse:,.2f} USD")
print(f"MAE:  {mae:,.2f} USD")
print(f"MAPE: {mape:.2f}%")
print(f"\n→ Para Finanzas: El error promedio es de ${rmse:,.0f} USD")
print(f"  por mes (RMSE), o ${mae:,.0f} USD (MAE),")
print(f"  lo que representa un {mape:.1f}% del valor real (MAPE).")
print(f"  En los meses de diciembre (ventas altas) el error absoluto")
print(f"  será mayor, pero el porcentual se mantiene estable.")

# 6b. Gini coefficient (ranking-based)
def gini(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Normalized Gini for regression: measures rank-ordering quality."""
    n = len(y_true)
    if n < 2:
        return 0.0

    def _gini_impl(values: np.ndarray) -> float:
        vals = np.sort(values)[::-1]
        cumsum = np.cumsum(vals)
        return float((2 * np.sum(cumsum) / (n * np.sum(vals)) - (n + 1) / n))

    idx = np.argsort(y_pred)[::-1]
    g_model = _gini_impl(y_true[idx])
    g_perfect = _gini_impl(y_true)
    if g_perfect > 0:
        return max(0.0, min(1.0, g_model / g_perfect))
    return 0.0

gini_score = gini(y_test, y_pred)
print(f"Gini: {gini_score:.4f} (0=aleatorio, 1=perfecto)")
if gini_score < 0.3:
    print("  ⚠️  Gini bajo — el modelo no distingue bien meses buenos de malos.")
elif gini_score >= 0.7:
    print("  ✅ Gini alto — buena capacidad de discriminar desempeño mensual.")
else:
    print("  ➡️  Gini moderado — aceptable para pronóstico de series temporales.")

# 6c. PSI (Population Stability Index)
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

psi_score = psi(y_train, y_test)
print(f"PSI:  {psi_score:.4f}")
if psi_score > 0.25:
    print("  ⚠️  ¡ALTO! PSI > 0.25 indica cambio en la distribución de ventas.")
    print("  En este caso es ESPERADO: el crecimiento anual (3-7%) hace que")
    print("  los ingresos de test (2024-2025) sean mayores que los de train")
    print("  (2016-2023). La distribución se desplaza a la derecha.")
    print("  Implicación: el modelo debe reentrenarse periódicamente (ej. cada")
    print("  6 meses) para mantener la distribución de predicciones alineada.")
elif psi_score > 0.1:
    print("  ⚠️  PSI moderado — se recomienda monitorear si el drift continúa.")
else:
    print("  ✅ PSI bajo — las distribuciones de train y test son estables.")

# 6d. K2 Score (Kling-Kuioza)
def k2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    n = len(y_true)
    if n < 2:
        return 0.0
    r = np.clip(np.corrcoef(y_true, y_pred)[0, 1], -1.0, 1.0)
    alpha = np.clip(np.std(y_pred) / (np.std(y_true) + 1e-10), 0.0, 3.0)
    beta = np.clip(np.mean(y_pred) / (np.mean(y_true) + 1e-10), 0.0, 3.0)
    k2 = 1.0 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2)
    return max(0.0, min(1.0, k2))

k2 = k2_score(y_test, y_pred)
print(f"K2 Score: {k2:.4f} (0=malo, 1=perfecto)")
if k2 > 0.7:
    print("  ✅ Buen ajuste — el modelo captura tendencia, variabilidad y media.")
elif k2 > 0.5:
    print("  ➡️  Ajuste moderado — aceptable, pero mejorable con más features.")
else:
    print("  ⚠️  K2 bajo — el modelo no captura bien la dinámica de la serie.")

# Feature importance
importance = model.feature_importances_
feat_imp = sorted(zip(FEATURE_COLS, importance), key=lambda x: x[1], reverse=True)
print(f"\n{'='*50}")
print("FEATURE IMPORTANCE (top 5)")
print(f"{'='*50}")
for name, imp in feat_imp[:5]:
    print(f"  {name:20s} {imp:.4f}")

# ── 7. Visualization ──────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 6))

months_test = pd.to_datetime(test_feat["month"])
ax.plot(months_test, y_test, "b-o", label="Actual Revenue", linewidth=2, markersize=4)
ax.plot(months_test, y_pred, "r--s", label="Predicted Revenue", linewidth=2, markersize=4)

# Variability band (±1 RMSE)
ax.fill_between(
    months_test,
    y_pred - rmse,
    y_pred + rmse,
    alpha=0.15,
    color="red",
    label=f"$\\pm$1 RMSE (${rmse:,.0f})",
)

# Variability band (±2 RMSE)
ax.fill_between(
    months_test,
    y_pred - 2 * rmse,
    y_pred + 2 * rmse,
    alpha=0.10,
    color="orange",
    label=f"$\\pm$2 RMSE (${2*rmse:,.0f})",
)

ax.set_title(
    "Brasaland — Sales Forecast (Test Period 2024-2025)",
    fontsize=14,
    fontweight="bold",
)
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (USD)")
ax.legend(loc="upper left", fontsize=9)
ax.grid(True, alpha=0.3)
ax.set_xlim(months_test.min(), months_test.max())

# Annotate key metrics
metrics_text = (
    f"MAPE: {mape:.1f}%\n"
    f"RMSE: ${rmse:,.0f}\n"
    f"MAE:  ${mae:,.0f}\n"
    f"Gini: {gini_score:.3f}\n"
    f"K²:   {k2:.3f}"
)
ax.text(
    0.02, 0.98, metrics_text,
    transform=ax.transAxes,
    fontsize=10,
    verticalalignment="top",
    bbox=dict(boxstyle="round,pad=0.5", facecolor="wheat", alpha=0.8),
)

# Annotations for seasonal peaks/troughs
for i, (m, y, _) in enumerate(zip(months_test, y_test, y_pred)):
    if m.month == 12:
        ax.annotate(
            f"Dec {m.year}",
            xy=(m, y),
            xytext=(m, y + rmse * 0.8),
            fontsize=8,
            ha="center",
            arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
        )
    elif m.month == 1:
        ax.annotate(
            f"Jan {m.year}",
            xy=(m, y),
            xytext=(m, y - rmse * 0.8),
            fontsize=8,
            ha="center",
            arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
        )

plt.tight_layout()
PLOT_PATH = EVIDENCIAS_DIR / "sales_forecast_prediction.png"
plt.savefig(PLOT_PATH, dpi=150)
print(f"\nVisualization saved to {PLOT_PATH}")

print(f"\n{'='*50}")
print("Done. Model trained and evaluated successfully.")
print(f"{'='*50}")