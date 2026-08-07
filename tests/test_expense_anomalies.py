from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from detect_expense_anomalies import build_features, score_anomalies, summarize


def sample_expenses():
    rng = np.random.default_rng(7)
    n = 500
    amounts = rng.lognormal(mean=6.5, sigma=0.45, size=n)
    amounts[:5] = [15000, 18000, 22000, 25000, 30000]
    return pd.DataFrame({
        "expense_id": [f"EXP_{i:05d}" for i in range(n)],
        "department": rng.choice(["Finance", "Operations", "Engineering"], n),
        "vendor": rng.choice([f"Vendor {i:02d}" for i in range(20)], n),
        "expense_category": rng.choice(["Software", "Travel", "Cloud"], n),
        "expense_date": pd.date_range("2025-01-01", periods=n, freq="D"),
        "amount": amounts,
    })


def test_feature_builder_returns_finite_features():
    scored, features = build_features(sample_expenses())
    assert len(scored) == len(features)
    assert np.isfinite(features.to_numpy()).all()


def test_anomaly_queue_is_small_and_ranked():
    scored, queue, model, cutoff = score_anomalies(sample_expenses(), review_fraction=0.02)
    assert len(queue) >= 1
    assert len(queue) <= 15
    assert queue["review_flag"].all()
    assert queue["expense_risk_score"].is_monotonic_decreasing
    assert cutoff > 0


def test_summary_values_are_consistent():
    scored, queue, model, cutoff = score_anomalies(sample_expenses(), review_fraction=0.02)
    summary = summarize(scored, queue, cutoff)
    assert summary["expense_rows"] == 500
    assert summary["review_rows"] == len(queue)
    assert 0 < summary["review_value_share"] < 1
    assert summary["median_review_amount"] > summary["median_nonreview_amount"]
