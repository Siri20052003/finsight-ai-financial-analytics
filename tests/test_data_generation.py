from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from config import GenerationConfig
from generate_data import generate_all
from validate_data import validate


def small_config(seed=123):
    return GenerationConfig(
        seed=seed,
        n_customers=100,
        n_invoices=1_000,
        n_expenses=500,
        start_date="2024-01-01",
        end_date="2024-12-31",
        output_dir=Path("data/raw"),
    )


def test_generator_is_reproducible():
    a = generate_all(small_config(seed=99))
    b = generate_all(small_config(seed=99))
    pd.testing.assert_frame_equal(a["customers"], b["customers"])
    pd.testing.assert_frame_equal(a["invoices"], b["invoices"])


def test_expected_tables_are_created():
    data = generate_all(small_config())
    assert set(data) == {"customers", "invoices", "payments", "expenses", "budgets", "adjustments"}
    assert len(data["customers"]) == 100
    assert len(data["invoices"]) > 1_000  # intentional duplicate rows are injected


def test_quality_defects_are_detectable():
    data = generate_all(small_config())
    report = validate(data)
    assert report["duplicate_invoice_rows"] > 0
    assert report["missing_invoice_customer_id"] > 0
    assert report["invalid_invoice_due_dates"] > 0
    assert report["orphan_payment_invoice_refs"] > 0
    assert report["total_detected_issues"] > 0


def test_financial_values_are_positive_where_expected():
    data = generate_all(small_config())
    assert (data["invoices"]["invoice_amount"] > 0).all()
    assert (data["payments"]["payment_amount"] > 0).all()
    assert (data["expenses"]["amount"] > 0).all()
    assert (data["budgets"]["budget_amount"] > 0).all()


def test_transactions_do_not_extend_past_reporting_cutoff():
    cfg = small_config()
    data = generate_all(cfg)
    cutoff = pd.Timestamp(cfg.end_date)
    assert pd.to_datetime(data["payments"]["payment_date"]).max() <= cutoff
    if not data["adjustments"].empty:
        assert pd.to_datetime(data["adjustments"]["adjustment_date"]).max() <= cutoff


def test_budget_generation_has_realistic_variation():
    data = generate_all(small_config())
    expenses = data["expenses"].copy()
    budgets = data["budgets"].copy()
    expenses["month"] = pd.to_datetime(expenses["expense_date"]).dt.to_period("M").dt.to_timestamp()
    monthly = expenses.groupby(["department", "month"], as_index=False)["amount"].sum()
    merged = budgets.merge(monthly, on=["department", "month"], how="left").fillna({"amount": 0})
    over_budget = merged["amount"] > merged["budget_amount"]
    assert over_budget.any()
    assert (~over_budget).any()
