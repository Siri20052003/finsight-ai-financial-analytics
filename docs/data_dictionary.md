# Data Dictionary

## customers.csv

| Field | Meaning |
|---|---|
| customer_id | Synthetic customer identifier |
| company_name | Synthetic company name |
| industry | Customer industry |
| region | U.S. operating region |
| customer_size | SMB, Mid-Market, or Enterprise |
| signup_date | Customer relationship start date |
| credit_rating | Synthetic internal credit grade A-D |
| payment_terms_days | Contractual payment terms in days |

## invoices.csv

| Field | Meaning |
|---|---|
| invoice_id | Synthetic invoice identifier |
| customer_id | Customer reference; some values intentionally missing |
| invoice_date | Invoice issue date |
| due_date | Contractual due date; some dates intentionally invalid |
| subtotal_amount | Pre-tax invoice value |
| tax_amount | Synthetic tax amount |
| invoice_amount | Total invoice value |

## payments.csv

| Field | Meaning |
|---|---|
| payment_id | Synthetic payment identifier |
| invoice_id | Invoice reference; some orphan references are intentionally injected |
| customer_id | Customer making payment |
| payment_date | Payment posting date |
| payment_amount | Amount received |
| payment_method | ACH, Wire, Card, or Check |

## expenses.csv

| Field | Meaning |
|---|---|
| expense_id | Synthetic expense identifier |
| department | Owning department |
| vendor | Synthetic vendor name |
| expense_category | Spend category |
| expense_date | Posting date |
| amount | Expense amount; a small set of unusually large values is intentionally injected |

## budgets.csv

| Field | Meaning |
|---|---|
| department | Department name |
| month | Budget month |
| budget_amount | Approved monthly budget |

## adjustments.csv

| Field | Meaning |
|---|---|
| adjustment_id | Synthetic adjustment identifier |
| invoice_id | Related invoice |
| adjustment_date | Adjustment date |
| adjustment_type | credit, refund, write_off, or reversal |
| adjustment_amount | Signed adjustment value |
| reason | Business reason for adjustment |
