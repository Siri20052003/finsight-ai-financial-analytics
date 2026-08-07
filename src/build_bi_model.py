from pathlib import Path
import json

import numpy as np
import pandas as pd

PROCESSED_DIR = Path("data/processed")
BI_DIR = Path("data/bi")
COLLECTION_PRIORITY_THRESHOLD = 0.35


def _read_csv(name, date_cols=None, processed_dir=PROCESSED_DIR):
    path = Path(processed_dir) / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run the analytics/ML pipeline first.")
    return pd.read_csv(path, parse_dates=date_cols or [])


def load_inputs(processed_dir=PROCESSED_DIR):
    processed_dir = Path(processed_dir)
    return {
        "customers": _read_csv("customers_clean", ["signup_date"], processed_dir),
        "invoices": _read_csv(
            "invoice_analytics",
            ["invoice_date", "due_date", "first_payment_date", "last_payment_date"],
            processed_dir,
        ),
        "expenses": _read_csv("expense_anomaly_scores", ["expense_date"], processed_dir),
        "budgets": _read_csv("budget_variance", ["month"], processed_dir),
        "collection_risk": _read_csv("late_payment_predictions", ["invoice_date"], processed_dir),
        "forecast": _read_csv("cash_flow_forecast", ["week"], processed_dir),
    }


def build_dim_customer(customers):
    cols = [
        "customer_id",
        "company_name",
        "industry",
        "region",
        "customer_size",
        "signup_date",
        "credit_rating",
        "payment_terms_days",
    ]
    dim = customers[cols].drop_duplicates("customer_id").copy()
    if dim["customer_id"].duplicated().any():
        raise ValueError("dim_customer requires one row per customer_id.")
    return dim.sort_values("customer_id").reset_index(drop=True)


def build_dim_date(inputs):
    dates = []
    date_specs = {
        "invoices": ["invoice_date", "due_date", "first_payment_date", "last_payment_date"],
        "expenses": ["expense_date"],
        "budgets": ["month"],
        "collection_risk": ["invoice_date"],
        "forecast": ["week"],
    }
    for table_name, columns in date_specs.items():
        df = inputs[table_name]
        for col in columns:
            if col in df.columns:
                values = pd.to_datetime(df[col], errors="coerce").dropna()
                if not values.empty:
                    dates.append(values)

    if not dates:
        raise ValueError("No valid dates found for dim_date.")

    all_dates = pd.concat(dates, ignore_index=True)
    start = all_dates.min().normalize()
    end = all_dates.max().normalize()
    date = pd.Series(pd.date_range(start, end, freq="D"), name="date")
    dim = pd.DataFrame({"date": date})
    dim["date_key"] = dim["date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"] = dim["date"].dt.year
    dim["quarter"] = "Q" + dim["date"].dt.quarter.astype(str)
    dim["month_number"] = dim["date"].dt.month
    dim["month_name"] = dim["date"].dt.month_name()
    dim["year_month"] = dim["date"].dt.strftime("%Y-%m")
    dim["week_number"] = dim["date"].dt.isocalendar().week.astype(int)
    dim["week_start"] = dim["date"] - pd.to_timedelta(dim["date"].dt.weekday, unit="D")
    dim["day_name"] = dim["date"].dt.day_name()
    dim["is_weekend"] = dim["date"].dt.weekday >= 5
    return dim


def build_fact_invoice(invoices):
    wanted = [
        "invoice_id",
        "customer_id",
        "invoice_date",
        "due_date",
        "invoice_amount",
        "adjustment_amount",
        "net_amount_due",
        "paid_amount",
        "outstanding_amount",
        "positive_outstanding_amount",
        "credit_balance_amount",
        "payment_count",
        "days_to_last_payment",
        "paid_late",
        "days_past_due",
        "aging_bucket",
        "is_overdue",
        "reconciliation_status",
    ]
    cols = [c for c in wanted if c in invoices.columns]
    fact = invoices[cols].copy()
    if fact["invoice_id"].duplicated().any():
        raise ValueError("fact_invoice requires one row per invoice_id.")
    return fact.sort_values("invoice_id").reset_index(drop=True)


def build_fact_expense(expenses):
    wanted = [
        "expense_id",
        "expense_date",
        "department",
        "vendor",
        "expense_category",
        "amount",
        "expense_risk_score",
        "review_flag",
        "review_reason",
        "vendor_ratio",
        "category_ratio",
        "department_ratio",
    ]
    cols = [c for c in wanted if c in expenses.columns]
    fact = expenses[cols].copy()
    if fact["expense_id"].duplicated().any():
        raise ValueError("fact_expense requires one row per expense_id.")
    return fact.sort_values(["expense_date", "expense_id"]).reset_index(drop=True)


def build_fact_budget(budgets):
    wanted = [
        "department",
        "month",
        "budget_amount",
        "actual_expense",
        "variance_amount",
        "variance_pct",
        "budget_status",
    ]
    cols = [c for c in wanted if c in budgets.columns]
    fact = budgets[cols].copy()
    fact["budget_key"] = fact["department"].astype(str) + "|" + fact["month"].dt.strftime("%Y-%m")
    if fact["budget_key"].duplicated().any():
        raise ValueError("fact_budget requires one row per department-month.")
    return fact.sort_values(["month", "department"]).reset_index(drop=True)


def build_fact_collection_risk(predictions):
    fact = predictions.copy()
    required = {"invoice_id", "customer_id", "invoice_date", "selected_risk_probability"}
    missing = required.difference(fact.columns)
    if missing:
        raise ValueError(f"Collection-risk export missing columns: {sorted(missing)}")

    fact["priority_threshold"] = COLLECTION_PRIORITY_THRESHOLD
    fact["collection_priority"] = np.where(
        fact["selected_risk_probability"] >= COLLECTION_PRIORITY_THRESHOLD,
        "PRIORITY_REVIEW",
        "STANDARD",
    )
    fact["risk_percentile"] = fact["selected_risk_probability"].rank(pct=True, method="average").round(6)
    return fact.sort_values("selected_risk_probability", ascending=False).reset_index(drop=True)


def build_fact_cash_forecast(forecast):
    wanted = [
        "week",
        "forecast_collections",
        "forecast_expenses",
        "forecast_net_cash_flow",
    ]
    cols = [c for c in wanted if c in forecast.columns]
    fact = forecast[cols].copy()
    return fact.sort_values("week").reset_index(drop=True)


def build_bi_model(inputs):
    tables = {
        "dim_customer": build_dim_customer(inputs["customers"]),
        "dim_date": build_dim_date(inputs),
        "fact_invoice": build_fact_invoice(inputs["invoices"]),
        "fact_expense": build_fact_expense(inputs["expenses"]),
        "fact_budget": build_fact_budget(inputs["budgets"]),
        "fact_collection_risk": build_fact_collection_risk(inputs["collection_risk"]),
        "fact_cash_forecast": build_fact_cash_forecast(inputs["forecast"]),
    }

    customer_ids = set(tables["dim_customer"]["customer_id"])
    bad_invoice_fk = (~tables["fact_invoice"]["customer_id"].isin(customer_ids)).sum()
    bad_risk_fk = (~tables["fact_collection_risk"]["customer_id"].isin(customer_ids)).sum()
    if bad_invoice_fk or bad_risk_fk:
        raise ValueError(
            f"Customer foreign-key validation failed: invoice={bad_invoice_fk}, risk={bad_risk_fk}."
        )

    summary = {
        "dim_customer_rows": int(len(tables["dim_customer"])),
        "dim_date_rows": int(len(tables["dim_date"])),
        "fact_invoice_rows": int(len(tables["fact_invoice"])),
        "fact_expense_rows": int(len(tables["fact_expense"])),
        "fact_budget_rows": int(len(tables["fact_budget"])),
        "fact_collection_risk_rows": int(len(tables["fact_collection_risk"])),
        "fact_cash_forecast_rows": int(len(tables["fact_cash_forecast"])),
        "date_start": tables["dim_date"]["date"].min().strftime("%Y-%m-%d"),
        "date_end": tables["dim_date"]["date"].max().strftime("%Y-%m-%d"),
        "priority_collection_rows": int(
            (tables["fact_collection_risk"]["collection_priority"] == "PRIORITY_REVIEW").sum()
        ),
        "expense_review_rows": int(tables["fact_expense"]["review_flag"].sum()),
        "forecast_net_cash_flow": round(
            float(tables["fact_cash_forecast"]["forecast_net_cash_flow"].sum()), 2
        ),
    }
    return tables, summary


def save_bi_model(tables, summary, output_dir=BI_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(output_dir / f"{name}.csv", index=False)
    (output_dir / "bi_model_summary.json").write_text(json.dumps(summary, indent=2))


def main():
    inputs = load_inputs(PROCESSED_DIR)
    tables, summary = build_bi_model(inputs)
    save_bi_model(tables, summary, BI_DIR)

    print("FinSight AI Power BI semantic export")
    print(f"Customer dimension           : {summary['dim_customer_rows']:,} rows")
    print(f"Date dimension               : {summary['dim_date_rows']:,} rows")
    print(f"Invoice fact                 : {summary['fact_invoice_rows']:,} rows")
    print(f"Expense fact                 : {summary['fact_expense_rows']:,} rows")
    print(f"Budget fact                  : {summary['fact_budget_rows']:,} rows")
    print(f"Collection-risk fact         : {summary['fact_collection_risk_rows']:,} rows")
    print(f"Cash-forecast fact           : {summary['fact_cash_forecast_rows']:,} rows")
    print(f"Model date range             : {summary['date_start']} to {summary['date_end']}")
    print(f"Priority collection invoices : {summary['priority_collection_rows']:,}")
    print(f"Expense review transactions  : {summary['expense_review_rows']:,}")
    print(f"8-week forecast net cash     : ${summary['forecast_net_cash_flow']:,.2f}")
    print(f"\nPower BI-ready files written to: {BI_DIR}")


if __name__ == "__main__":
    main()
