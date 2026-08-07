from datetime import timedelta
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from forecast_cash_flow import build_weekly_series, add_time_features, build_forecast_report


def sample_inputs():
    weeks = pd.date_range("2024-01-01", periods=110, freq="W-MON")
    payment_rows = []
    expense_rows = []
    rng = np.random.default_rng(7)

    for i, week in enumerate(weeks):
        base_collections = 100_000 + i * 350 + 10_000 * np.sin(2 * np.pi * i / 52)
        base_expenses = 78_000 + i * 220 + 7_500 * np.cos(2 * np.pi * i / 52)
        for j in range(4):
            offset = timedelta(days=int(j))
            payment_rows.append({
                "payment_date": week + offset,
                "payment_amount": max(1.0, base_collections / 4 + rng.normal(0, 1500)),
            })
            expense_rows.append({
                "expense_date": week + offset,
                "amount": max(1.0, base_expenses / 4 + rng.normal(0, 1200)),
            })

    return pd.DataFrame(payment_rows), pd.DataFrame(expense_rows)


def test_weekly_series_contains_cash_flow_columns():
    payments, expenses = sample_inputs()
    weekly = build_weekly_series(payments, expenses)
    assert {"week", "collections", "expenses", "net_cash_flow"}.issubset(weekly.columns)
    assert len(weekly) >= 100
    assert np.allclose(weekly["net_cash_flow"], weekly["collections"] - weekly["expenses"])


def test_time_features_are_lagged_without_nulls():
    payments, expenses = sample_inputs()
    weekly = build_weekly_series(payments, expenses)
    featured = add_time_features(weekly, "collections")
    assert not featured.isna().any().any()
    assert "lag_8" in featured.columns
    assert "rolling_8" in featured.columns


def test_forecast_report_returns_eight_weeks_and_selects_method():
    payments, expenses = sample_inputs()
    weekly = build_weekly_series(payments, expenses)
    forecast, results = build_forecast_report(weekly)
    assert len(forecast) == 8
    assert (forecast["forecast_collections"] >= 0).all()
    assert (forecast["forecast_expenses"] >= 0).all()
    assert results["forecast_horizon_weeks"] == 8
    assert results["collections"]["selected_method"] in {"gradient_boosting", "rolling_4_baseline"}
    assert results["expenses"]["selected_method"] in {"gradient_boosting", "rolling_4_baseline"}
