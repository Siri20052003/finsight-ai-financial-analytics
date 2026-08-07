-- BigQuery Standard SQL

WITH invoices AS (
    SELECT SUM(invoice_amount) AS invoiced_revenue
    FROM `YOUR_PROJECT.YOUR_DATASET.invoices`
),
payments AS (
    SELECT SUM(payment_amount) AS cash_collected
    FROM `YOUR_PROJECT.YOUR_DATASET.payments`
),
open_ar AS (
    SELECT SUM(GREATEST(outstanding_amount, 0)) AS outstanding_ar
    FROM `YOUR_PROJECT.YOUR_DATASET.invoice_reconciliation`
),
expenses AS (
    SELECT SUM(amount) AS total_expenses
    FROM `YOUR_PROJECT.YOUR_DATASET.expenses`
),
budgets AS (
    SELECT SUM(budget_amount) AS total_budget
    FROM `YOUR_PROJECT.YOUR_DATASET.budgets`
)
SELECT
    invoiced_revenue,
    cash_collected,
    outstanding_ar,
    total_expenses,
    total_budget,
    total_expenses - total_budget AS budget_variance_amount,
    SAFE_DIVIDE(total_expenses - total_budget, total_budget) AS budget_variance_pct,
    SAFE_DIVIDE(cash_collected, invoiced_revenue) AS collection_rate
FROM invoices
CROSS JOIN payments
CROSS JOIN open_ar
CROSS JOIN expenses
CROSS JOIN budgets;
