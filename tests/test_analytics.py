from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from config import GenerationConfig
from generate_data import generate_all
from build_curated import build_curated
from build_analytics import build_analytics


def small_tables():
    cfg = GenerationConfig(
        seed=321,
        n_customers=100,
        n_invoices=1_000,
        n_expenses=500,
        start_date="2024-01-01",
        end_date="2024-12-31",
        output_dir=Path("data/raw"),
    )
    raw = generate_all(cfg)
    curated, _ = build_curated(raw)
    return {
        "reconciliation": curated["invoice_reconciliation"],
        "customers": curated["customers_clean"],
        "expenses": curated["expenses_clean"],
        "budgets": curated["budgets_clean"],
        "unapplied_payments": curated["unapplied_payments"],
    }


def test_aging_reconciles_to_gross_ar():
    outputs, kpis = build_analytics(small_tables(), as_of_date="2024-12-31")
    aging_total = outputs["ar_aging_summary"]["outstanding_amount"].sum()
    assert round(float(aging_total), 2) == round(float(kpis["gross_outstanding_ar"]), 2)


def test_budget_variance_math_is_consistent():
    outputs, _ = build_analytics(small_tables(), as_of_date="2024-12-31")
    df = outputs["budget_variance"]
    expected = (df["actual_expense"] - df["budget_amount"]).round(2)
    pd.testing.assert_series_equal(df["variance_amount"].reset_index(drop=True), expected.reset_index(drop=True), check_names=False)


def test_customer_ar_never_has_negative_outstanding():
    outputs, _ = build_analytics(small_tables(), as_of_date="2024-12-31")
    assert (outputs["customer_ar_summary"]["outstanding_ar"] >= 0).all()
