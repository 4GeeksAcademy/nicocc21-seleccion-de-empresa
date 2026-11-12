#!/usr/bin/env python3
"""Validate that the generated dataset matches the documented patterns."""

from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "raw" / "brasaland_sales.csv"

df = pd.read_csv(CSV_PATH, parse_dates=["month"])
cons = df[df["market"] == "consolidated"].copy()
cons = cons.sort_values("month").reset_index(drop=True)

print("=" * 60)
print("VALIDATION: Dataset Patterns vs Documented Spec")
print("=" * 60)

expected = pd.date_range(start="2016-01-01", end="2025-12-01", freq="MS")
assert len(cons) == 120, f"Expected 120 rows, got {len(cons)}"
print(f"Rows: {len(cons)} (expect 120)")
assert (cons["revenue_usd"] > 0).all(), "Non-positive revenue!"
print(f"Revenue range: ${cons['revenue_usd'].min():,.2f} — ${cons['revenue_usd'].max():,.2f}")

print("\n--- Annual Growth Rates (spec: 3-7%) ---")
for yr in range(2016, 2026):
    yr_data = cons[cons["month"].dt.year == yr]
    if len(yr_data) == 0:
        continue
    prev_yr = cons[cons["month"].dt.year == yr - 1]
    if len(prev_yr) == 0:
        print(f"  {yr}: N/A (first year)")
        continue
    prev_avg = prev_yr["revenue_usd"].mean()
    curr_avg = yr_data["revenue_usd"].mean()
    growth = (curr_avg - prev_avg) / prev_avg * 100
    status = "OK" if 3.0 <= growth <= 7.0 else "FAIL"
    print(f"  {status} {yr}: {growth:.2f}%")

print("\n--- January Drop Analysis (spec: 12-18%) ---")
for yr in range(2017, 2026):
    jan_row = cons[(cons["month"].dt.year == yr) & (cons["month"].dt.month == 1)]
    prev_year = cons[cons["month"].dt.year == yr - 1]
    if len(jan_row) == 0 or len(prev_year) == 0:
        continue
    prev_avg = prev_year["revenue_usd"].mean()
    jan_val = jan_row["revenue_usd"].values[0]
    drop = (1 - jan_val / prev_avg) * 100
    status = "OK" if 12.0 <= drop <= 18.0 else "FAIL"
    print(f"  {status} Jan {yr}: {drop:.2f}% drop")

print("\n--- December Rise Analysis (spec: 20-30%) ---")
for yr in range(2016, 2025):
    dec_row = cons[(cons["month"].dt.year == yr) & (cons["month"].dt.month == 12)]
    if len(dec_row) == 0:
        continue
    prev_year = cons[cons["month"].dt.year == yr - 1] if yr > 2016 else cons[cons["month"].dt.year == yr]
    if yr > 2016:
        prev_avg = prev_year["revenue_usd"].mean()
    else:
        prev_avg = cons[cons["month"].dt.year == 2016]["revenue_usd"].mean()
    dec_val = dec_row["revenue_usd"].values[0]
    rise = (dec_val / prev_avg - 1) * 100
    status = "OK" if 20.0 <= rise <= 30.0 else "FAIL"
    print(f"  {status} Dec {yr}: {rise:.2f}% rise")

print("\n" + "=" * 60)
print("Validation complete.")
print("=" * 60)
