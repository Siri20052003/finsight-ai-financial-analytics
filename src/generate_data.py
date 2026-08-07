import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config import GenerationConfig

INDUSTRIES = ["Technology", "Healthcare", "Financial Services", "Retail", "Manufacturing", "Logistics"]
REGIONS = ["Northeast", "South", "Midwest", "West"]
SIZES = ["SMB", "Mid-Market", "Enterprise"]
CREDIT = ["A", "B", "C", "D"]
PAYMENT_TERMS = [15, 30, 45, 60]
DEPARTMENTS = ["Sales", "Marketing", "Operations", "Finance", "Engineering", "Customer Success"]
EXPENSE_CATEGORIES = ["Payroll", "Software", "Travel", "Professional Services", "Cloud", "Facilities", "Marketing"]
ADJUSTMENT_TYPES = ["credit", "refund", "write_off", "reversal"]


def random_dates(rng, start, end, n):
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    days = (end_ts - start_ts).days
    return start_ts + pd.to_timedelta(rng.integers(0, days + 1, n), unit="D")


def build_customers(cfg, rng):
    n = cfg.n_customers
    return pd.DataFrame({
        "customer_id": [f"CUST_{i:06d}" for i in range(1, n + 1)],
        "company_name": [f"NovaEdge Client {i:05d}" for i in range(1, n + 1)],
        "industry": rng.choice(INDUSTRIES, n),
        "region": rng.choice(REGIONS, n),
        "customer_size": rng.choice(SIZES, n, p=[0.55, 0.30, 0.15]),
        "signup_date": random_dates(rng, "2021-01-01", cfg.end_date, n),
        "credit_rating": rng.choice(CREDIT, n, p=[0.40, 0.35, 0.20, 0.05]),
        "payment_terms_days": rng.choice(PAYMENT_TERMS, n, p=[0.10, 0.60, 0.20, 0.10]),
    })


def build_invoices(cfg, customers, rng):
    n = cfg.n_invoices
    sampled = customers.sample(n=n, replace=True, random_state=cfg.seed).reset_index(drop=True)
    invoice_date = pd.Series(random_dates(rng, cfg.start_date, cfg.end_date, n))
    due_date = invoice_date + pd.to_timedelta(sampled["payment_terms_days"], unit="D")
    subtotal = np.round(rng.lognormal(mean=8.0, sigma=0.8, size=n), 2)
    tax = np.round(subtotal * rng.choice([0.00, 0.05, 0.0825], n, p=[0.15, 0.20, 0.65]), 2)
    df = pd.DataFrame({
        "invoice_id": [f"INV_{i:07d}" for i in range(1, n + 1)],
        "customer_id": sampled["customer_id"],
        "invoice_date": invoice_date,
        "due_date": due_date,
        "subtotal_amount": subtotal,
        "tax_amount": tax,
        "invoice_amount": subtotal + tax,
    })

    # Intentional source-system defects for the data-quality workflow.
    missing_idx = rng.choice(df.index, size=max(1, int(n * 0.005)), replace=False)
    df.loc[missing_idx, "customer_id"] = None
    invalid_idx = rng.choice(df.index.difference(missing_idx), size=max(1, int(n * 0.003)), replace=False)
    df.loc[invalid_idx, "due_date"] = df.loc[invalid_idx, "invoice_date"] - pd.to_timedelta(5, unit="D")
    dupes = df.sample(n=max(1, int(n * 0.004)), random_state=cfg.seed + 1)
    return pd.concat([df, dupes], ignore_index=True)


def _payment_outcome_probabilities(days_past_due_at_cutoff):
    """Return realistic payment-state probabilities at the reporting cutoff.

    Older invoices are much more likely to have settled. Recent and not-yet-due
    invoices are more likely to remain open, which prevents an unrealistic AR
    portfolio dominated by very old unpaid invoices.
    """
    if days_past_due_at_cutoff > 90:
        return [0.88, 0.07, 0.03, 0.02]  # full, partial, over, unpaid
    if days_past_due_at_cutoff > 30:
        return [0.76, 0.14, 0.04, 0.06]
    if days_past_due_at_cutoff >= 0:
        return [0.55, 0.20, 0.03, 0.22]
    return [0.25, 0.15, 0.02, 0.58]


def build_payments(cfg, invoices, rng):
    valid = invoices.drop_duplicates("invoice_id").dropna(subset=["customer_id"]).copy()
    cutoff = pd.Timestamp(cfg.end_date).normalize()
    records = []
    payment_counter = 1

    for row in valid.itertuples(index=False):
        invoice_date = pd.Timestamp(row.invoice_date).normalize()
        due_date = pd.Timestamp(row.due_date).normalize()
        # Invalid due dates are source defects. Use a temporary operational due date
        # for simulation; the curated layer later repairs the source field explicitly.
        effective_due = due_date if due_date >= invoice_date else invoice_date + pd.Timedelta(days=30)
        days_past_due_at_cutoff = int((cutoff - effective_due).days)

        outcome = rng.choice(
            ["full", "partial", "over", "unpaid"],
            p=_payment_outcome_probabilities(days_past_due_at_cutoff),
        )
        if outcome == "unpaid":
            continue

        total = float(row.invoice_amount)
        pieces = [total]
        if outcome == "partial":
            first = round(total * rng.uniform(0.30, 0.75), 2)
            pieces = [first]
            if rng.random() < 0.55:
                pieces.append(round(total - first, 2))
        elif outcome == "over":
            pieces = [round(total * rng.uniform(1.01, 1.08), 2)]

        # Payment timing centers around the contractual due date. Never create
        # payments before the invoice date or after the dataset reporting cutoff.
        base_date = effective_due + pd.to_timedelta(int(rng.normal(4, 18)), unit="D")
        base_date = max(base_date, invoice_date)

        for j, amount in enumerate(pieces):
            payment_date = base_date + pd.to_timedelta(j * 7, unit="D")
            if payment_date > cutoff:
                continue
            records.append({
                "payment_id": f"PAY_{payment_counter:08d}",
                "invoice_id": row.invoice_id,
                "customer_id": row.customer_id,
                "payment_date": payment_date,
                "payment_amount": amount,
                "payment_method": rng.choice(["ACH", "Wire", "Card", "Check"], p=[0.50, 0.20, 0.20, 0.10]),
            })
            payment_counter += 1

    payments = pd.DataFrame(records)
    if payments.empty:
        return payments

    # Intentional unapplied cash: payment rows whose invoice reference does not exist.
    orphan_n = max(1, int(len(payments) * 0.002))
    orphans = payments.sample(orphan_n, random_state=7).copy()
    orphans["payment_id"] = [f"PAY_ORPHAN_{i:05d}" for i in range(1, orphan_n + 1)]
    orphans["invoice_id"] = [f"INV_MISSING_{i:05d}" for i in range(1, orphan_n + 1)]
    return pd.concat([payments, orphans], ignore_index=True)


def build_expenses(cfg, rng):
    n = cfg.n_expenses
    amounts = np.round(rng.lognormal(mean=7.1, sigma=0.9, size=n), 2)
    anomaly_idx = rng.choice(np.arange(n), size=max(1, int(n * 0.006)), replace=False)
    amounts[anomaly_idx] *= rng.uniform(6, 15, len(anomaly_idx))
    return pd.DataFrame({
        "expense_id": [f"EXP_{i:07d}" for i in range(1, n + 1)],
        "department": rng.choice(DEPARTMENTS, n),
        "vendor": [f"Vendor {x:03d}" for x in rng.integers(1, 151, n)],
        "expense_category": rng.choice(EXPENSE_CATEGORIES, n),
        "expense_date": random_dates(rng, cfg.start_date, cfg.end_date, n),
        "amount": np.round(amounts, 2),
    })


def build_budgets(cfg, expenses, rng):
    """Create department-month budgets around expected monthly spend.

    The first version used arbitrary $120K-$650K budgets, which made every small
    test month appear under budget. Here we simulate planning error around actual
    monthly spend so the portfolio contains a realistic mix of favorable and
    unfavorable variances. This is synthetic calibration, not historical leakage.
    """
    months = pd.date_range(pd.Timestamp(cfg.start_date).replace(day=1), pd.Timestamp(cfg.end_date), freq="MS")
    monthly = (
        expenses.assign(month=expenses["expense_date"].dt.to_period("M").dt.to_timestamp())
        .groupby(["department", "month"], as_index=False)
        .agg(actual_expense=("amount", "sum"))
    )
    actual_lookup = monthly.set_index(["department", "month"])["actual_expense"].to_dict()
    dept_typical = monthly.groupby("department")["actual_expense"].median().to_dict()

    rows = []
    for month in months:
        for dept in DEPARTMENTS:
            baseline = float(actual_lookup.get((dept, month), dept_typical.get(dept, 50_000.0)))
            # Roughly 30% of department-months are intentionally planned tightly
            # enough to end over budget; the remainder retain a modest cushion.
            if rng.random() < 0.30:
                planning_factor = rng.uniform(0.82, 0.98)
            else:
                planning_factor = rng.uniform(1.02, 1.22)
            rows.append({
                "department": dept,
                "month": month,
                "budget_amount": round(max(1_000.0, baseline * planning_factor), 2),
            })
    return pd.DataFrame(rows)


def build_adjustments(cfg, invoices, rng):
    unique = invoices.drop_duplicates("invoice_id")
    n = max(1, int(len(unique) * 0.05))
    sampled = unique.sample(n=n, random_state=11)
    cutoff = pd.Timestamp(cfg.end_date).normalize()
    rows = []

    for i, row in enumerate(sampled.itertuples(index=False), 1):
        invoice_date = pd.Timestamp(row.invoice_date).normalize()
        remaining_days = int((cutoff - invoice_date).days)
        if remaining_days < 1:
            continue
        delay = int(rng.integers(1, min(120, remaining_days) + 1))
        kind = rng.choice(ADJUSTMENT_TYPES, p=[0.45, 0.20, 0.20, 0.15])
        amount = round(float(row.invoice_amount) * rng.uniform(0.02, 0.35), 2)
        if kind in {"credit", "refund", "write_off"}:
            amount = -amount
        rows.append({
            "adjustment_id": f"ADJ_{i:06d}",
            "invoice_id": row.invoice_id,
            "adjustment_date": invoice_date + pd.to_timedelta(delay, unit="D"),
            "adjustment_type": kind,
            "adjustment_amount": amount,
            "reason": rng.choice(["Pricing correction", "Service credit", "Dispute", "Duplicate charge", "Collection decision"]),
        })
    return pd.DataFrame(rows)


def generate_all(cfg):
    rng = np.random.default_rng(cfg.seed)
    customers = build_customers(cfg, rng)
    invoices = build_invoices(cfg, customers, rng)
    payments = build_payments(cfg, invoices, rng)
    expenses = build_expenses(cfg, rng)
    budgets = build_budgets(cfg, expenses, rng)
    adjustments = build_adjustments(cfg, invoices, rng)
    return {
        "customers": customers,
        "invoices": invoices,
        "payments": payments,
        "expenses": expenses,
        "budgets": budgets,
        "adjustments": adjustments,
    }


def save_all(data, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in data.items():
        df.to_csv(output_dir / f"{name}.csv", index=False)
        print(f"{name:12s} {len(df):>8,} rows -> {output_dir / (name + '.csv')}")


def parse_args():
    p = argparse.ArgumentParser(description="Generate synthetic NovaEdge financial data")
    p.add_argument("--customers", type=int, default=5_000)
    p.add_argument("--invoices", type=int, default=50_000)
    p.add_argument("--expenses", type=int, default=30_000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="data/raw")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = GenerationConfig(
        seed=args.seed,
        n_customers=args.customers,
        n_invoices=args.invoices,
        n_expenses=args.expenses,
        output_dir=Path(args.output),
    )
    save_all(generate_all(cfg), cfg.output_dir)
