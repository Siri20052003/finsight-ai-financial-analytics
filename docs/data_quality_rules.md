# FinSight AI Data Quality Decisions

This document records how the curated finance layer handles source-data defects. The goal is to make every transformation auditable and explainable rather than silently deleting or changing records.

## 1. Duplicate invoice IDs

**Observed issue:** More than one source row can share the same `invoice_id`.

**Decision:** Preserve the extra rows in `duplicate_invoice_rows.csv`, then keep the first source occurrence in the trusted invoice table.

**Why:** The synthetic generator creates exact duplicate source rows to simulate ingestion duplication. Preserving the duplicate evidence supports auditability while preventing double counting in financial metrics.

## 2. Missing or unknown customer references

**Observed issue:** Some invoices cannot be tied to a valid customer master record.

**Decision:** Move these records to `quarantined_invoices.csv`. Do not include them in trusted customer-level reporting until the reference is resolved.

**Why:** Customer identity should not be guessed or imputed in a financial workflow.

## 3. Invalid invoice due dates

**Observed issue:** Some due dates occur before their invoice dates.

**Decision:** For invoices with a valid customer, rebuild the due date from the invoice date plus the customer's master `payment_terms_days`. The field `due_date_repaired` records whether the correction occurred.

**Why:** Payment terms are available in the trusted customer master and provide a defensible deterministic repair rule.

## 4. Payments referencing unknown invoices

**Observed issue:** Some payment rows reference invoice IDs that are not present in the trusted invoice population.

**Decision:** Preserve them in `unapplied_payments.csv` and exclude them from invoice-level reconciliation until they can be matched.

**Why:** A payment with an unresolved invoice reference may still represent real cash. Deleting it would understate cash received, while assigning it to an invoice without evidence would corrupt reconciliation.

## 5. Adjustments referencing untrusted invoices

**Observed issue:** An adjustment may reference an invoice that was quarantined or is otherwise absent from the trusted invoice set.

**Decision:** Preserve it in `orphan_adjustments.csv` and exclude it from trusted reconciliation.

## 6. Reconciliation status rules

At the invoice level:

- `PAID`: net amount due and total payments differ by no more than $0.01.
- `PARTIALLY_PAID`: some payment exists but a positive balance remains.
- `UNPAID`: no material payment exists and a positive balance remains.
- `OVERPAID`: payments exceed the net amount due by more than $0.01.
- `REVIEW`: any state that does not fit the explicit rules above.

`net_amount_due = invoice_amount + adjustment_amount`

`outstanding_amount = net_amount_due - paid_amount`

## Audit principle

Raw files are never overwritten. Clean, quarantined, and exception datasets are written separately under `data/processed/` so an analyst can trace every decision back to the source layer.
