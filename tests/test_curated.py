from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from config import GenerationConfig
from generate_data import generate_all
from build_curated import build_curated


def config():
    return GenerationConfig(
        seed=321,
        n_customers=100,
        n_invoices=1_000,
        n_expenses=500,
        start_date="2024-01-01",
        end_date="2024-12-31",
        output_dir=Path("data/raw"),
    )


def test_curated_invoices_are_unique_and_trusted():
    outputs, summary = build_curated(generate_all(config()))
    invoices = outputs["invoices_clean"]
    assert invoices["invoice_id"].is_unique
    assert invoices["customer_id"].notna().all()
    assert (invoices["due_date"] >= invoices["invoice_date"]).all()
    assert summary["duplicate_rows_removed"] > 0
    assert summary["invoices_quarantined"] > 0
    assert summary["due_dates_repaired"] > 0


def test_unapplied_payments_are_preserved_not_deleted():
    outputs, _ = build_curated(generate_all(config()))
    clean_invoice_ids = set(outputs["invoices_clean"]["invoice_id"])
    assert len(outputs["unapplied_payments"]) > 0
    assert not outputs["unapplied_payments"]["invoice_id"].isin(clean_invoice_ids).any()
    assert outputs["payments_clean"]["invoice_id"].isin(clean_invoice_ids).all()


def test_reconciliation_has_one_row_per_trusted_invoice():
    outputs, _ = build_curated(generate_all(config()))
    reconciliation = outputs["invoice_reconciliation"]
    invoices = outputs["invoices_clean"]
    assert len(reconciliation) == len(invoices)
    assert reconciliation["invoice_id"].is_unique
    assert set(reconciliation["reconciliation_status"]).issubset(
        {"PAID", "PARTIALLY_PAID", "UNPAID", "OVERPAID", "REVIEW"}
    )
