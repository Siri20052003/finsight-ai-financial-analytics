-- BigQuery Standard SQL
-- Replace `YOUR_PROJECT.YOUR_DATASET` before running in BigQuery.

WITH invoice_base AS (
    SELECT
        invoice_id,
        ANY_VALUE(customer_id) AS customer_id,
        MIN(invoice_date) AS invoice_date,
        MAX(due_date) AS due_date,
        MAX(invoice_amount) AS invoice_amount
    FROM `YOUR_PROJECT.YOUR_DATASET.invoices`
    GROUP BY invoice_id
),
payment_totals AS (
    SELECT
        invoice_id,
        SUM(payment_amount) AS paid_amount,
        MAX(payment_date) AS last_payment_date
    FROM `YOUR_PROJECT.YOUR_DATASET.payments`
    GROUP BY invoice_id
),
adjustment_totals AS (
    SELECT
        invoice_id,
        SUM(adjustment_amount) AS adjustment_amount
    FROM `YOUR_PROJECT.YOUR_DATASET.adjustments`
    GROUP BY invoice_id
)
SELECT
    i.invoice_id,
    i.customer_id,
    i.invoice_date,
    i.due_date,
    i.invoice_amount,
    COALESCE(a.adjustment_amount, 0) AS adjustment_amount,
    i.invoice_amount + COALESCE(a.adjustment_amount, 0) AS net_amount_due,
    COALESCE(p.paid_amount, 0) AS paid_amount,
    (i.invoice_amount + COALESCE(a.adjustment_amount, 0)) - COALESCE(p.paid_amount, 0) AS outstanding_amount,
    p.last_payment_date,
    CASE
        WHEN COALESCE(p.paid_amount, 0) = 0 THEN 'UNPAID'
        WHEN COALESCE(p.paid_amount, 0) < i.invoice_amount + COALESCE(a.adjustment_amount, 0) THEN 'PARTIALLY_PAID'
        WHEN COALESCE(p.paid_amount, 0) = i.invoice_amount + COALESCE(a.adjustment_amount, 0) THEN 'FULLY_RECONCILED'
        WHEN COALESCE(p.paid_amount, 0) > i.invoice_amount + COALESCE(a.adjustment_amount, 0) THEN 'OVERPAID'
        ELSE 'REVIEW'
    END AS reconciliation_status
FROM invoice_base i
LEFT JOIN payment_totals p USING (invoice_id)
LEFT JOIN adjustment_totals a USING (invoice_id);
