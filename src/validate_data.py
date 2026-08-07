from pathlib import Path
import json
import pandas as pd

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")


def load_tables(raw_dir=RAW_DIR):
    tables = {}
    for name in ["customers", "invoices", "payments", "expenses", "budgets", "adjustments"]:
        path = Path(raw_dir) / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Run src/generate_data.py first.")
        tables[name] = pd.read_csv(path, parse_dates=[c for c in ["signup_date", "invoice_date", "due_date", "payment_date", "expense_date", "month", "adjustment_date"] if c in pd.read_csv(path, nrows=0).columns])
    return tables


def validate(tables):
    customers = tables["customers"]
    invoices = tables["invoices"]
    payments = tables["payments"]
    expenses = tables["expenses"]

    customer_ids = set(customers["customer_id"].dropna())
    invoice_ids = set(invoices["invoice_id"].dropna())

    checks = {
        "duplicate_invoice_rows": int(invoices.duplicated("invoice_id", keep=False).sum()),
        "missing_invoice_customer_id": int(invoices["customer_id"].isna().sum()),
        "orphan_invoice_customer_refs": int((~invoices["customer_id"].isin(customer_ids) & invoices["customer_id"].notna()).sum()),
        "invalid_invoice_due_dates": int((invoices["due_date"] < invoices["invoice_date"]).sum()),
        "orphan_payment_invoice_refs": int((~payments["invoice_id"].isin(invoice_ids)).sum()),
        "nonpositive_payments": int((payments["payment_amount"] <= 0).sum()),
        "nonpositive_expenses": int((expenses["amount"] <= 0).sum()),
    }
    checks["total_detected_issues"] = int(sum(checks.values()))
    return checks


def main():
    tables = load_tables()
    report = validate(tables)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "validation_report.json").write_text(json.dumps(report, indent=2))
    print("FinSight AI validation report")
    for key, value in report.items():
        print(f"{key:32s}: {value:,}")


if __name__ == "__main__":
    main()
