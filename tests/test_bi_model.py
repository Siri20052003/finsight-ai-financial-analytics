from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from build_bi_model import build_bi_model


def sample_inputs():
    customers = pd.DataFrame({
        "customer_id": ["C1", "C2"],
        "company_name": ["Alpha", "Beta"],
        "industry": ["Technology", "Retail"],
        "region": ["South", "West"],
        "customer_size": ["SMB", "Enterprise"],
        "signup_date": pd.to_datetime(["2023-01-01", "2023-02-01"]),
        "credit_rating": ["A", "C"],
        "payment_terms_days": [30, 45],
    })
    invoices = pd.DataFrame({
        "invoice_id": ["I1", "I2"],
        "customer_id": ["C1", "C2"],
        "invoice_date": pd.to_datetime(["2025-01-01", "2025-01-08"]),
        "due_date": pd.to_datetime(["2025-01-31", "2025-02-22"]),
        "first_payment_date": pd.to_datetime(["2025-01-20", None]),
        "last_payment_date": pd.to_datetime(["2025-01-20", None]),
        "invoice_amount": [1000.0, 2000.0],
        "adjustment_amount": [0.0, 0.0],
        "net_amount_due": [1000.0, 2000.0],
        "paid_amount": [1000.0, 0.0],
        "outstanding_amount": [0.0, 2000.0],
        "positive_outstanding_amount": [0.0, 2000.0],
        "credit_balance_amount": [0.0, 0.0],
        "payment_count": [1, 0],
        "days_to_last_payment": [19.0, None],
        "paid_late": [False, False],
        "days_past_due": [None, 40.0],
        "aging_bucket": ["CLOSED_OR_CREDIT", "31-60"],
        "is_overdue": [False, True],
        "reconciliation_status": ["PAID", "UNPAID"],
    })
    expenses = pd.DataFrame({
        "expense_id": ["E1", "E2"],
        "expense_date": pd.to_datetime(["2025-01-05", "2025-01-12"]),
        "department": ["Finance", "Sales"],
        "vendor": ["V1", "V2"],
        "expense_category": ["Software", "Travel"],
        "amount": [500.0, 5000.0],
        "expense_risk_score": [0.2, 0.99],
        "review_flag": [False, True],
        "review_reason": ["normal", "high peer ratio"],
        "vendor_ratio": [1.0, 8.0],
        "category_ratio": [1.0, 7.0],
        "department_ratio": [1.0, 6.0],
    })
    budgets = pd.DataFrame({
        "department": ["Finance", "Sales"],
        "month": pd.to_datetime(["2025-01-01", "2025-01-01"]),
        "budget_amount": [1000.0, 6000.0],
        "actual_expense": [500.0, 5000.0],
        "variance_amount": [-500.0, -1000.0],
        "variance_pct": [-0.5, -0.1667],
        "budget_status": ["AT_OR_UNDER_BUDGET", "AT_OR_UNDER_BUDGET"],
    })
    collection_risk = pd.DataFrame({
        "invoice_id": ["I1", "I2"],
        "customer_id": ["C1", "C2"],
        "invoice_date": pd.to_datetime(["2025-01-01", "2025-01-08"]),
        "late_30_days": [0, 1],
        "invoice_amount": [1000.0, 2000.0],
        "selected_model": ["random_forest", "random_forest"],
        "selected_risk_probability": [0.10, 0.70],
    })
    forecast = pd.DataFrame({
        "week": pd.to_datetime(["2026-01-05", "2026-01-12"]),
        "forecast_collections": [1000.0, 1200.0],
        "forecast_expenses": [600.0, 700.0],
        "forecast_net_cash_flow": [400.0, 500.0],
    })
    return {
        "customers": customers,
        "invoices": invoices,
        "expenses": expenses,
        "budgets": budgets,
        "collection_risk": collection_risk,
        "forecast": forecast,
    }


def test_bi_model_builds_expected_star_schema_tables():
    tables, summary = build_bi_model(sample_inputs())
    assert set(tables) == {
        "dim_customer",
        "dim_date",
        "fact_invoice",
        "fact_expense",
        "fact_budget",
        "fact_collection_risk",
        "fact_cash_forecast",
    }
    assert summary["dim_customer_rows"] == 2
    assert summary["fact_invoice_rows"] == 2
    assert summary["fact_cash_forecast_rows"] == 2


def test_bi_model_applies_collection_priority_threshold():
    tables, summary = build_bi_model(sample_inputs())
    risk = tables["fact_collection_risk"].set_index("invoice_id")
    assert risk.loc["I1", "collection_priority"] == "STANDARD"
    assert risk.loc["I2", "collection_priority"] == "PRIORITY_REVIEW"
    assert summary["priority_collection_rows"] == 1


def test_date_dimension_covers_forecast_horizon():
    tables, summary = build_bi_model(sample_inputs())
    assert tables["dim_date"]["date"].min() <= pd.Timestamp("2025-01-01")
    assert tables["dim_date"]["date"].max() >= pd.Timestamp("2026-01-12")
    assert summary["forecast_net_cash_flow"] == 900.0
