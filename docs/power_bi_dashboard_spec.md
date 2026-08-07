# FinSight AI Power BI Dashboard Specification

## Purpose

The Power BI layer turns FinSight AI's validated financial, collections-risk, anomaly, budget, and forecast outputs into an executive-facing decision system. The dashboard should make it possible to move from portfolio-level KPIs to individual invoices or expense transactions requiring attention.

## Semantic model

The local export script `src/build_bi_model.py` creates the following Power BI-ready tables in `data/bi/`:

- `dim_customer.csv`
- `dim_date.csv`
- `fact_invoice.csv`
- `fact_expense.csv`
- `fact_budget.csv`
- `fact_collection_risk.csv`
- `fact_cash_forecast.csv`

### Recommended relationships

| From | Column | To | Column | Cardinality |
| --- | --- | --- | --- | --- |
| dim_customer | customer_id | fact_invoice | customer_id | 1:* |
| dim_customer | customer_id | fact_collection_risk | customer_id | 1:* |
| dim_date | date | fact_invoice | invoice_date | 1:* |
| dim_date | date | fact_expense | expense_date | 1:* |
| dim_date | date | fact_budget | month | 1:* |
| dim_date | date | fact_collection_risk | invoice_date | 1:* |
| dim_date | date | fact_cash_forecast | week | 1:* |

Use single-direction filtering from dimensions to facts. For due-date analysis, create an inactive relationship from `dim_date[date]` to `fact_invoice[due_date]` and activate it inside specific DAX measures with `USERELATIONSHIP`.

## Dashboard pages

### 1. Executive Overview

Primary KPIs:

- Total Invoice Value
- Total Collections
- Gross Outstanding AR
- Overdue AR
- Overdue AR %
- Total Expense
- Budget Variance
- 8-Week Forecast Net Cash Flow

Recommended visuals:

- KPI cards across the top
- monthly collections vs invoice value trend
- AR aging stacked bar
- budget vs actual by department
- forecast collections, expenses, and net cash flow line/column combination

### 2. AR & Collections

Primary questions:

- How much AR is overdue?
- Which aging buckets contain the most exposure?
- Which customers account for the largest overdue balances?
- Which invoices should collections teams work first?

Recommended visuals:

- AR aging waterfall or stacked bar
- overdue AR by customer / industry / region
- reconciliation status distribution
- detailed open-invoice table

Suggested drill-through fields:

- customer_id
- invoice_id
- invoice_amount
- paid_amount
- positive_outstanding_amount
- days_past_due
- aging_bucket
- reconciliation_status

### 3. Payment Risk

The current operating threshold is 0.35 for broad collections screening.

Primary KPIs:

- Priority Review Invoices
- Average Risk Probability
- High-Risk Invoice Value
- Actual Late Rate in Evaluation Sample

Recommended visuals:

- risk probability histogram
- risk percentile vs invoice value scatter plot
- priority-review invoice table
- risk by credit rating / industry / customer size

Important interpretation:

The model is a prioritization aid, not an automated credit or customer-treatment decision. A 0.35 threshold was chosen to achieve approximately 70%+ recall in the evaluation portfolio and intentionally accepts more false positives in exchange for catching more late-payment cases.

### 4. Expense & Anomaly Review

Primary KPIs:

- Total Expense
- Review Queue Count
- Review Queue Value
- Review Queue % of Spend

Recommended visuals:

- anomaly score vs amount scatter plot
- anomaly spend by department
- anomaly spend by vendor
- review transaction table with review_reason

The anomaly model identifies transactions requiring review. It must not be labeled as a fraud-detection system.

### 5. Budget vs Actual

Primary KPIs:

- Total Budget
- Total Actual Expense
- Variance Amount
- Over-Budget Department-Months

Recommended visuals:

- variance by department
- monthly budget vs actual
- department-month heatmap using variance_pct
- over-budget exception table

### 6. Cash-Flow Outlook

FinSight uses target-specific forecasting methods:

- Collections: rolling 4-week average baseline
- Expenses: Gradient Boosting model

Primary KPIs:

- Forecast Collections
- Forecast Expenses
- Forecast Net Cash Flow

Recommended visuals:

- 8-week collections and expenses forecast
- 8-week net cash-flow trend
- cumulative forecast net cash flow

## Core DAX measures

```DAX
Total Invoice Value =
SUM ( fact_invoice[invoice_amount] )

Total Collections =
SUM ( fact_invoice[paid_amount] )

Gross Outstanding AR =
SUM ( fact_invoice[positive_outstanding_amount] )

Overdue AR =
CALCULATE (
    [Gross Outstanding AR],
    fact_invoice[is_overdue] = TRUE ()
)

Overdue AR % =
DIVIDE ( [Overdue AR], [Gross Outstanding AR] )

Total Expense =
SUM ( fact_expense[amount] )

Review Queue Value =
CALCULATE (
    [Total Expense],
    fact_expense[review_flag] = TRUE ()
)

Review Queue % of Spend =
DIVIDE ( [Review Queue Value], [Total Expense] )

Budget Amount =
SUM ( fact_budget[budget_amount] )

Budget Actual =
SUM ( fact_budget[actual_expense] )

Budget Variance =
[Budget Actual] - [Budget Amount]

Priority Collection Invoice Count =
CALCULATE (
    COUNTROWS ( fact_collection_risk ),
    fact_collection_risk[collection_priority] = "PRIORITY_REVIEW"
)

Forecast Collections =
SUM ( fact_cash_forecast[forecast_collections] )

Forecast Expenses =
SUM ( fact_cash_forecast[forecast_expenses] )

Forecast Net Cash Flow =
SUM ( fact_cash_forecast[forecast_net_cash_flow] )
```

## Design principles

- Keep the executive page concise and decision-focused.
- Use drill-through rather than placing every detail on the overview page.
- Keep risk/anomaly terminology precise: "priority review" and "requires review," not "will default" or "fraud."
- Display model-driven metrics alongside operational financial KPIs, not as a separate AI showcase.
- Make every headline metric traceable to a fact table and reproducible calculation.

## Next deployment step

The same star-schema outputs will later be loaded into BigQuery and transformed through dbt so Power BI can be connected to a cloud warehouse rather than local CSV files. The local CSV semantic model exists first so relationships, measures, and dashboard logic can be validated before cloud deployment.
