#!/usr/bin/env python3
"""Generate deterministic sales dataset for Brasaland.

Creates data/raw/brasaland_sales.csv with 10 years of monthly sales data
for consolidated, colombia, and florida markets.

Patterns (documented in CONTEXT.md):
- Base annual growth X=5%, variation Y=2%, alternating 7%/3% year over year
- January: -12% to -18% from prev year monthly avg
- December: +20% to +30% from prev year monthly avg
- Other months: ±5% around that year's monthly average
- Seed 42 for reproducibility

Design — two-phase generation:
  Phase 1 — Build target yearly averages with alternating growth.
  Phase 2 — For each year, set Jan and Dec relative to the previous year's
            average, then solve for the remaining 10 months so the 12-month
            mean equals the target yearly average.  This simultaneously
            guarantees all three pattern specs are met.

Usage:
    python3 scripts/generate_sales_data.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Configuration ────────────────────────────────────────────────
RANDOM_SEED = 42
START_YEAR = 2016
END_YEAR = 2025  # inclusive
MONTHS_IN_PERIOD = (END_YEAR - START_YEAR + 1) * 12

BASE_REVENUE = 850_000.0  # consolidated Jan 2016 baseline
X_GROWTH = 0.05  # base annual growth
Y_VAR = 0.02     # variation around growth
RNG = np.random.default_rng(RANDOM_SEED)

# ── Build monthly index ──────────────────────────────────────────
dates = pd.date_range(start=f"{START_YEAR}-01-01", end=f"{END_YEAR}-12-01", freq="MS")
assert len(dates) == MONTHS_IN_PERIOD, f"Expected {MONTHS_IN_PERIOD} months, got {len(dates)}"

# ── Phase 1: Yearly average revenue with alternating growth ──────
year_labels = list(range(START_YEAR, END_YEAR + 1))
growth_rates: dict[int, float] = {}
for i, yr in enumerate(year_labels):
    growth_rates[yr] = X_GROWTH + Y_VAR if i % 2 == 0 else X_GROWTH - Y_VAR

yearly_avg: dict[int, float] = {}
avg = float(BASE_REVENUE)
for yr in year_labels:
    yearly_avg[yr] = round(avg, 2)
    avg *= 1.0 + growth_rates[yr]

# ── Phase 2: Month-level revenue that satisfies all pattern specs ─
revenue = np.empty(MONTHS_IN_PERIOD, dtype=np.float64)

for yr_idx, yr in enumerate(year_labels):
    mask = dates.year == yr
    n_months = mask.sum()
    assert n_months == 12, f"Expected 12 months for {yr}, got {n_months}"

    target_avg = yearly_avg[yr]

    # Previous year's average (for Jan/Dec relative computation)
    if yr_idx == 0:
        prev_avg = target_avg  # first year: no previous, use same year
    else:
        prev_avg = yearly_avg[year_labels[yr_idx - 1]]

    # Jan: 12-18% below prev_avg
    jan_drop = RNG.uniform(0.12, 0.18)
    jan_val = prev_avg * (1.0 - jan_drop)

    # Dec: 20-30% above prev_avg
    dec_rise = RNG.uniform(0.20, 0.30)
    dec_val = prev_avg * (1.0 + dec_rise)

    # The remaining 10 months must sum to: 12 * target_avg - jan - dec
    sum_other = 12.0 * target_avg - jan_val - dec_val
    other_mean = sum_other / 10.0

    # Generate 10 values with ±5% noise around other_mean
    raw_other = other_mean * RNG.uniform(0.95, 1.05, size=10)
    # Scale them so they sum exactly to sum_other
    raw_other = raw_other * (sum_other / raw_other.sum())
    raw_other = np.round(raw_other, 2)

    # Fix any rounding discrepancy (≤ 0.02) by adjusting the largest value
    diff = sum_other - raw_other.sum()
    if abs(diff) > 0.001:
        raw_other[np.argmax(np.abs(raw_other))] += diff
    raw_other = np.round(raw_other, 2)

    # Assemble the 12 months for this year
    yr_values = np.empty(12, dtype=np.float64)
    yr_values[0] = round(jan_val, 2)   # Jan (month=1)
    yr_values[1:11] = raw_other        # Feb–Nov
    yr_values[11] = round(dec_val, 2)  # Dec (month=12)

    # Ensure non-negative
    yr_values = np.maximum(yr_values, 1.0)

    revenue[mask] = yr_values

# ── Derived columns ──────────────────────────────────────────────
avg_ticket = np.full(MONTHS_IN_PERIOD, 35.0)
avg_ticket += RNG.uniform(-2, 2, size=MONTHS_IN_PERIOD)
avg_ticket = np.clip(avg_ticket, 25.0, 50.0).round(2)

covers_served = (revenue / avg_ticket).astype(np.int64)
covers_served = np.maximum(covers_served, 1)

# ── Build market-level rows ──────────────────────────────────────
consolidated = pd.DataFrame({
    "month": dates,
    "revenue_usd": revenue,
    "covers_served": covers_served,
    "avg_ticket_usd": avg_ticket,
    "market": "consolidated",
})

colombia_rev = revenue * RNG.uniform(0.72, 0.78, size=MONTHS_IN_PERIOD)
colombia_ticket = avg_ticket * RNG.uniform(0.90, 1.0, size=MONTHS_IN_PERIOD)
colombia = pd.DataFrame({
    "month": dates,
    "revenue_usd": colombia_rev.round(2),
    "covers_served": (colombia_rev / colombia_ticket).astype(np.int64),
    "avg_ticket_usd": colombia_ticket.round(2),
    "market": "colombia",
})

florida_rev = revenue * RNG.uniform(0.22, 0.28, size=MONTHS_IN_PERIOD)
florida_ticket = avg_ticket * RNG.uniform(0.95, 1.10, size=MONTHS_IN_PERIOD)
florida = pd.DataFrame({
    "month": dates,
    "revenue_usd": florida_rev.round(2),
    "covers_served": (florida_rev / florida_ticket).astype(np.int64),
    "avg_ticket_usd": florida_ticket.round(2),
    "market": "florida",
})

# ── Combine and save ─────────────────────────────────────────────
df = pd.concat([consolidated, colombia, florida], ignore_index=True)
df = df.sort_values(["month", "market"]).reset_index(drop=True)

OUT = DATA_DIR / "brasaland_sales.csv"
df.to_csv(OUT, index=False)
print(f"Dataset generated at {OUT}")
print(f"  Shape: {df.shape}")
print(f"  Markets: {df['market'].unique().tolist()}")
print(f"  Date range: {df['month'].min()} to {df['month'].max()}")
print(f"  Consolidated rows: {(df['market']=='consolidated').sum()}")
print(f"  Total rows: {len(df)}")
