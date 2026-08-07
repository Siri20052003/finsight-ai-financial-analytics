from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from build_analytics import build_analytics
from build_curated import build_curated
from config import GenerationConfig
from generate_data import generate_all
from train_late_payment_model import FEATURES, TARGET, build_modeling_dataset, chronological_split


def model_config(seed=321):
    return GenerationConfig(
        seed=seed,
        n_customers=250,
        n_invoices=3_000,
        n_expenses=1_000,
        start_date="2024-01-01",
        end_date="2025-12-31",
        output_dir=Path("data/raw"),
    )


def build_small_modeling_data():
    cfg = model_config()
    generated = generate_all(cfg)
    curated_outputs, _ = build_curated(generated)
    analytics_inputs = {
        "reconciliation": curated_outputs["invoice_reconciliation"],
        "customers": curated_outputs["customers_clean"],
        "expenses": curated_outputs["expenses_clean"],
        "budgets": curated_outputs["budgets_clean"],
        "unapplied_payments": curated_outputs["unapplied_payments"],
    }
    analytics_outputs, _ = build_analytics(analytics_inputs, as_of_date=cfg.end_date)
    modeling, _ = build_modeling_dataset(
        analytics_outputs["invoice_analytics"],
        curated_outputs["customers_clean"],
        as_of_date=cfg.end_date,
    )
    return modeling


def test_modeling_dataset_has_required_features_and_binary_target():
    modeling = build_small_modeling_data()
    assert len(modeling) > 1_000
    assert set(FEATURES).issubset(modeling.columns)
    assert TARGET in modeling.columns
    assert set(modeling[TARGET].unique()).issubset({0, 1})
    assert modeling[TARGET].nunique() == 2


def test_prior_history_feature_does_not_use_current_target():
    modeling = build_small_modeling_data().sort_values(["customer_id", "invoice_date", "invoice_id"])
    first = modeling.groupby("customer_id", as_index=False).head(1)
    # First invoices have no customer history; they receive the portfolio-level
    # prior rather than their own current outcome.
    assert (first["prior_invoice_count"] == 0).all()
    assert first["prior_late_rate"].between(0, 1).all()


def test_chronological_split_keeps_future_rows_out_of_training():
    modeling = build_small_modeling_data()
    train, test = chronological_split(modeling)
    assert len(train) > 0 and len(test) > 0
    assert pd.to_datetime(train["invoice_date"]).max() <= pd.to_datetime(test["invoice_date"]).max()
    assert set(train["invoice_id"]).isdisjoint(set(test["invoice_id"]))
