from pathlib import Path
import json

import numpy as np
import pandas as pd

from validate_data import load_tables

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
TOLERANCE = 0.01


def build_curated(tables):
    customers = tables["customers"].copy()
    invoices_raw = tables["invoices"].copy()
    payments_raw = tables["payments"].copy()
    expenses = tables["expenses"].copy()
    budgets = tables["budgets"].copy()
    adjustments_raw = tables["adjustments"].copy()

    # 1) Preserve duplicate evidence, then keep the first occurrence of each invoice ID.
    duplicate_invoice_rows = invoices_raw[invoices_raw.duplicated("invoice_id", keep="first")].copy()
    invoices = invoices_raw.drop_duplicates("invoice_id", keep="first").copy()

    # 2) Quarantine invoices that cannot be tied to a valid customer master record.
    valid_customer_ids = set(customers["customer_id"].dropna())
    bad_customer_mask = invoices["customer_id"].isna() | ~invoices["customer_id"].isin(valid_customer_ids)
    quarantined_invoices = invoices[bad_customer_mask].copy()
    quarantined_invoices["quarantine_reason"] = np.where(
        quarantined_invoices["customer_id"].isna(),
        "missing_customer_id",
        "unknown_customer_id",
    )
    clean_invoices = invoices[~bad_customer_mask].copy()

    # 3) Repair invalid due dates from the customer master payment terms.
    payment_terms = customers[["customer_id", "payment_terms_days"]]
    clean_invoices = clean_invoices.merge(payment_terms, on="customer_id", how="left", validate="many_to_one")
    clean_invoices["due_date_repaired"] = clean_invoices["due_date"] < clean_invoices["invoice_date"]
    clean_invoices.loc[clean_invoices["due_date_repaired"], "due_date"] = (
        clean_invoices.loc[clean_invoices["due_date_repaired"], "invoice_date"]
        + pd.to_timedelta(clean_invoices.loc[clean_invoices["due_date_repaired"], "payment_terms_days"], unit="D")
    )

    # 4) Treat payments with no trusted invoice as unapplied cash rather than deleting them.
    trusted_invoice_ids = set(clean_invoices["invoice_id"])
    unapplied_payments = payments_raw[~payments_raw["invoice_id"].isin(trusted_invoice_ids)].copy()
    clean_payments = payments_raw[payments_raw["invoice_id"].isin(trusted_invoice_ids)].copy()

    # 5) Keep only adjustments that can be tied to a trusted invoice; preserve the rest separately.
    orphan_adjustments = adjustments_raw[~adjustments_raw["invoice_id"].isin(trusted_invoice_ids)].copy()
    clean_adjustments = adjustments_raw[adjustments_raw["invoice_id"].isin(trusted_invoice_ids)].copy()

    # 6) Create one invoice-level financial reconciliation record.
    payment_summary = (
        clean_payments.groupby("invoice_id", as_index=False)
        .agg(
            paid_amount=("payment_amount", "sum"),
            payment_count=("payment_id", "count"),
            first_payment_date=("payment_date", "min"),
            last_payment_date=("payment_date", "max"),
        )
    )

    adjustment_summary = (
        clean_adjustments.groupby("invoice_id", as_index=False)
        .agg(
            adjustment_amount=("adjustment_amount", "sum"),
            adjustment_count=("adjustment_id", "count"),
        )
    )

    reconciliation = (
        clean_invoices.merge(payment_summary, on="invoice_id", how="left", validate="one_to_one")
        .merge(adjustment_summary, on="invoice_id", how="left", validate="one_to_one")
    )

    reconciliation["paid_amount"] = reconciliation["paid_amount"].fillna(0.0)
    reconciliation["payment_count"] = reconciliation["payment_count"].fillna(0).astype(int)
    reconciliation["adjustment_amount"] = reconciliation["adjustment_amount"].fillna(0.0)
    reconciliation["adjustment_count"] = reconciliation["adjustment_count"].fillna(0).astype(int)
    reconciliation["net_amount_due"] = (
        reconciliation["invoice_amount"] + reconciliation["adjustment_amount"]
    ).round(2)
    reconciliation["outstanding_amount"] = (
        reconciliation["net_amount_due"] - reconciliation["paid_amount"]
    ).round(2)

    conditions = [
        reconciliation["outstanding_amount"] < -TOLERANCE,
        reconciliation["outstanding_amount"].abs() <= TOLERANCE,
        (reconciliation["paid_amount"] > TOLERANCE) & (reconciliation["outstanding_amount"] > TOLERANCE),
        (reconciliation["paid_amount"] <= TOLERANCE) & (reconciliation["outstanding_amount"] > TOLERANCE),
    ]
    choices = ["OVERPAID", "PAID", "PARTIALLY_PAID", "UNPAID"]
    reconciliation["reconciliation_status"] = np.select(conditions, choices, default="REVIEW")

    reconciliation["days_to_last_payment"] = (
        reconciliation["last_payment_date"] - reconciliation["invoice_date"]
    ).dt.days
    reconciliation["paid_late"] = (
        reconciliation["last_payment_date"].notna()
        & (reconciliation["last_payment_date"] > reconciliation["due_date"])
    )

    outputs = {
        "customers_clean": customers,
        "invoices_clean": clean_invoices,
        "payments_clean": clean_payments,
        "adjustments_clean": clean_adjustments,
        "expenses_clean": expenses,
        "budgets_clean": budgets,
        "duplicate_invoice_rows": duplicate_invoice_rows,
        "quarantined_invoices": quarantined_invoices,
        "unapplied_payments": unapplied_payments,
        "orphan_adjustments": orphan_adjustments,
        "invoice_reconciliation": reconciliation,
    }

    summary = {
        "raw_invoice_rows": int(len(invoices_raw)),
        "unique_invoice_ids": int(invoices_raw["invoice_id"].nunique()),
        "duplicate_rows_removed": int(len(duplicate_invoice_rows)),
        "invoices_quarantined": int(len(quarantined_invoices)),
        "due_dates_repaired": int(clean_invoices["due_date_repaired"].sum()),
        "unapplied_payments": int(len(unapplied_payments)),
        "orphan_adjustments": int(len(orphan_adjustments)),
        "trusted_invoice_rows": int(len(clean_invoices)),
        "reconciliation_rows": int(len(reconciliation)),
        "reconciled_paid": int((reconciliation["reconciliation_status"] == "PAID").sum()),
        "reconciled_partial": int((reconciliation["reconciliation_status"] == "PARTIALLY_PAID").sum()),
        "reconciled_unpaid": int((reconciliation["reconciliation_status"] == "UNPAID").sum()),
        "reconciled_overpaid": int((reconciliation["reconciliation_status"] == "OVERPAID").sum()),
        "total_invoice_value": round(float(reconciliation["invoice_amount"].sum()), 2),
        "total_paid_value": round(float(reconciliation["paid_amount"].sum()), 2),
        "total_outstanding_value": round(float(reconciliation["outstanding_amount"].sum()), 2),
        "unapplied_cash_value": round(float(unapplied_payments["payment_amount"].sum()), 2),
    }
    return outputs, summary


def save_outputs(outputs, summary, output_dir=OUT_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in outputs.items():
        df.to_csv(output_dir / f"{name}.csv", index=False)
    (output_dir / "curation_summary.json").write_text(json.dumps(summary, indent=2))


def main():
    tables = load_tables(RAW_DIR)
    outputs, summary = build_curated(tables)
    save_outputs(outputs, summary, OUT_DIR)

    print("FinSight AI curated-layer summary")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key:30s}: {value:,.2f}")
        else:
            print(f"{key:30s}: {value:,}")
    print(f"\nProcessed files written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
