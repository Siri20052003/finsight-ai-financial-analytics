from pathlib import Path
import json

import numpy as np
import pandas as pd

PROCESSED_DIR = Path("data/processed")
TOLERANCE = 0.01


def load_processed(processed_dir=PROCESSED_DIR):
    processed_dir = Path(processed_dir)

    def read_csv(name, date_cols=None):
        path = processed_dir / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}. Run src/build_curated.py before building analytics."
            )
        return pd.read_csv(path, parse_dates=date_cols or [])

    return {
        "reconciliation": read_csv(
            "invoice_reconciliation",
            ["invoice_date", "due_date", "first_payment_date", "last_payment_date"],
        ),
        "customers": read_csv("customers_clean", ["signup_date"]),
        "expenses": read_csv("expenses_clean", ["expense_date"]),
        "budgets": read_csv("budgets_clean", ["month"]),
        "unapplied_payments": read_csv("unapplied_payments", ["payment_date"]),
    }


def add_ar_aging(reconciliation, as_of_date=None):
    df = reconciliation.copy()
    if as_of_date is None:
        # Use the final invoice date in the generated dataset as a reproducible reporting cutoff.
        as_of_date = pd.Timestamp(df["invoice_date"].max()).normalize()
    else:
        as_of_date = pd.Timestamp(as_of_date).normalize()

    df["positive_outstanding_amount"] = df["outstanding_amount"].clip(lower=0).round(2)
    df["credit_balance_amount"] = (-df["outstanding_amount"].clip(upper=0)).round(2)
    df["days_past_due"] = (as_of_date - df["due_date"]).dt.days
    df["days_past_due"] = np.where(
        df["positive_outstanding_amount"] > TOLERANCE,
        df["days_past_due"],
        np.nan,
    )

    conditions = [
        df["positive_outstanding_amount"] <= TOLERANCE,
        df["days_past_due"] <= 0,
        df["days_past_due"].between(1, 30, inclusive="both"),
        df["days_past_due"].between(31, 60, inclusive="both"),
        df["days_past_due"].between(61, 90, inclusive="both"),
        df["days_past_due"] > 90,
    ]
    choices = ["CLOSED_OR_CREDIT", "CURRENT", "1-30", "31-60", "61-90", "90+"]
    df["aging_bucket"] = np.select(conditions, choices, default="REVIEW")
    df["is_overdue"] = (
        (df["positive_outstanding_amount"] > TOLERANCE)
        & (df["due_date"] < as_of_date)
    )
    return df, as_of_date


def build_budget_variance(expenses, budgets):
    monthly_expense = (
        expenses.assign(month=expenses["expense_date"].dt.to_period("M").dt.to_timestamp())
        .groupby(["department", "month"], as_index=False)
        .agg(actual_expense=("amount", "sum"))
    )
    variance = budgets.merge(monthly_expense, on=["department", "month"], how="left")
    variance["actual_expense"] = variance["actual_expense"].fillna(0.0).round(2)
    variance["variance_amount"] = (variance["actual_expense"] - variance["budget_amount"]).round(2)
    variance["variance_pct"] = np.where(
        variance["budget_amount"].abs() > TOLERANCE,
        variance["variance_amount"] / variance["budget_amount"],
        np.nan,
    )
    variance["budget_status"] = np.where(
        variance["variance_amount"] > TOLERANCE, "OVER_BUDGET", "AT_OR_UNDER_BUDGET"
    )
    return variance


def build_customer_ar(aged_reconciliation, customers):
    customer = (
        aged_reconciliation.groupby("customer_id", as_index=False)
        .agg(
            invoice_count=("invoice_id", "count"),
            invoice_value=("invoice_amount", "sum"),
            net_amount_due=("net_amount_due", "sum"),
            paid_amount=("paid_amount", "sum"),
            outstanding_ar=("positive_outstanding_amount", "sum"),
            credit_balance=("credit_balance_amount", "sum"),
            overdue_ar=("positive_outstanding_amount", lambda s: s[aged_reconciliation.loc[s.index, "is_overdue"]].sum()),
            late_paid_invoices=("paid_late", "sum"),
            avg_days_to_last_payment=("days_to_last_payment", "mean"),
        )
    )
    customer = customer.merge(
        customers[["customer_id", "company_name", "industry", "region", "customer_size", "credit_rating", "payment_terms_days"]],
        on="customer_id",
        how="left",
        validate="one_to_one",
    )
    customer["overdue_share"] = np.where(
        customer["outstanding_ar"] > TOLERANCE,
        customer["overdue_ar"] / customer["outstanding_ar"],
        0.0,
    )
    return customer


def build_analytics(tables, as_of_date=None):
    reconciliation = tables["reconciliation"]
    customers = tables["customers"]
    expenses = tables["expenses"]
    budgets = tables["budgets"]
    unapplied = tables["unapplied_payments"]

    aged, cutoff = add_ar_aging(reconciliation, as_of_date)
    budget_variance = build_budget_variance(expenses, budgets)
    customer_ar = build_customer_ar(aged, customers)

    open_mask = aged["positive_outstanding_amount"] > TOLERANCE
    overdue_mask = aged["is_overdue"]
    paid_with_date = aged["last_payment_date"].notna()

    gross_ar = float(aged["positive_outstanding_amount"].sum())
    overdue_ar = float(aged.loc[overdue_mask, "positive_outstanding_amount"].sum())
    credit_balances = float(aged["credit_balance_amount"].sum())
    net_due = float(aged["net_amount_due"].sum())
    paid = float(aged["paid_amount"].sum())

    aging_summary = (
        aged.loc[open_mask]
        .groupby("aging_bucket", as_index=False)
        .agg(
            invoice_count=("invoice_id", "count"),
            outstanding_amount=("positive_outstanding_amount", "sum"),
        )
    )
    desired_order = ["CURRENT", "1-30", "31-60", "61-90", "90+", "REVIEW"]
    aging_summary["sort_order"] = aging_summary["aging_bucket"].map(
        {name: i for i, name in enumerate(desired_order)}
    )
    aging_summary = aging_summary.sort_values("sort_order").drop(columns="sort_order")

    kpis = {
        "as_of_date": cutoff.strftime("%Y-%m-%d"),
        "trusted_invoice_count": int(len(aged)),
        "open_invoice_count": int(open_mask.sum()),
        "overdue_invoice_count": int(overdue_mask.sum()),
        "total_invoice_value": round(float(aged["invoice_amount"].sum()), 2),
        "net_amount_due": round(net_due, 2),
        "total_collections": round(paid, 2),
        "gross_outstanding_ar": round(gross_ar, 2),
        "overdue_ar": round(overdue_ar, 2),
        "customer_credit_balances": round(credit_balances, 2),
        "unapplied_cash": round(float(unapplied["payment_amount"].sum()), 2) if not unapplied.empty else 0.0,
        "cash_coverage_ratio": round(paid / net_due, 4) if abs(net_due) > TOLERANCE else None,
        "overdue_ar_share": round(overdue_ar / gross_ar, 4) if gross_ar > TOLERANCE else 0.0,
        "late_payment_rate": round(float(aged.loc[paid_with_date, "paid_late"].mean()), 4) if paid_with_date.any() else 0.0,
        "avg_days_to_last_payment": round(float(aged.loc[paid_with_date, "days_to_last_payment"].mean()), 2) if paid_with_date.any() else None,
        "total_expense": round(float(expenses["amount"].sum()), 2),
        "total_budget": round(float(budgets["budget_amount"].sum()), 2),
        "total_budget_variance": round(float(budget_variance["variance_amount"].sum()), 2),
        "over_budget_department_months": int((budget_variance["budget_status"] == "OVER_BUDGET").sum()),
    }

    outputs = {
        "invoice_analytics": aged,
        "ar_aging_summary": aging_summary,
        "customer_ar_summary": customer_ar,
        "budget_variance": budget_variance,
    }
    return outputs, kpis


def save_outputs(outputs, kpis, output_dir=PROCESSED_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in outputs.items():
        df.to_csv(output_dir / f"{name}.csv", index=False)
    (output_dir / "financial_kpis.json").write_text(json.dumps(kpis, indent=2))


def main():
    tables = load_processed(PROCESSED_DIR)
    outputs, kpis = build_analytics(tables)
    save_outputs(outputs, kpis, PROCESSED_DIR)

    print("FinSight AI financial analytics summary")
    for key, value in kpis.items():
        if isinstance(value, float):
            if key.endswith("_ratio") or key.endswith("_share") or key.endswith("_rate"):
                print(f"{key:30s}: {value:.2%}")
            else:
                print(f"{key:30s}: {value:,.2f}")
        else:
            print(f"{key:30s}: {value}")

    print("\nAR aging")
    print(outputs["ar_aging_summary"].to_string(index=False))
    print(f"\nAnalytics files written to: {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
