-- BigQuery Standard SQL
-- Depends on the reconciliation logic/materialized output.

SELECT
    invoice_id,
    customer_id,
    due_date,
    outstanding_amount,
    DATE_DIFF(CURRENT_DATE(), DATE(due_date), DAY) AS days_past_due,
    CASE
        WHEN outstanding_amount <= 0 THEN 'CLOSED'
        WHEN CURRENT_DATE() <= DATE(due_date) THEN 'CURRENT'
        WHEN DATE_DIFF(CURRENT_DATE(), DATE(due_date), DAY) BETWEEN 1 AND 30 THEN '1-30 DAYS'
        WHEN DATE_DIFF(CURRENT_DATE(), DATE(due_date), DAY) BETWEEN 31 AND 60 THEN '31-60 DAYS'
        WHEN DATE_DIFF(CURRENT_DATE(), DATE(due_date), DAY) BETWEEN 61 AND 90 THEN '61-90 DAYS'
        ELSE '90+ DAYS'
    END AS aging_bucket
FROM `YOUR_PROJECT.YOUR_DATASET.invoice_reconciliation`;
