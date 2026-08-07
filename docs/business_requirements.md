# Business Requirements — FinSight AI

## Business context

NovaEdge Technologies is a fictional B2B technology company with customers across multiple industries and regions. Finance leadership needs a reliable way to reconcile invoices and payments, monitor collections, understand budget performance, and identify transactions requiring investigation.

## Primary stakeholders

- CFO / Finance leadership
- Accounts Receivable team
- Finance analysts
- Department managers
- Business intelligence team

## Core business questions

1. How much invoiced revenue has been collected?
2. How much remains outstanding?
3. Which invoices are unpaid, partially paid, or overpaid?
4. Which customers are creating the highest AR exposure?
5. How old are outstanding receivables?
6. Which departments are over or under budget?
7. Which financial records fail data-quality rules?
8. Which expenses or payments appear anomalous?
9. Which invoices are most likely to be paid late?
10. What are expected collections in future periods?

## Initial KPI definitions

### Invoiced Revenue
Sum of invoice amounts after deduplicating invoice IDs.

### Cash Collected
Sum of recorded customer payment amounts.

### Outstanding AR
Positive net invoice balance remaining after payments and applicable adjustments.

### Collection Rate
Cash collected divided by invoiced revenue for the selected reporting period.

### Budget Variance
Actual expense minus approved budget. Positive values indicate overspend.

### Reconciliation Status
Each invoice is categorized as fully reconciled, partially paid, unpaid, overpaid, or requiring review based on invoice value, adjustments, and recorded payments.

## Data-quality requirements

The analytics layer must test at minimum:

- Invoice ID uniqueness
- Required customer references
- Valid customer foreign keys
- Due date >= invoice date
- Valid payment-to-invoice references
- Positive payment values
- Positive expense values

## Future ML requirements

Late-payment prediction must be evaluated using precision, recall, F1, ROC-AUC, and business-oriented error costs rather than accuracy alone.

Anomaly detection must expose a human-readable reason or contributing signal so that flagged transactions can be reviewed by a finance analyst.

## AI requirement

Any natural-language financial assistant must explain previously calculated and validated metrics. The LLM must not be the system of record for financial calculations.
