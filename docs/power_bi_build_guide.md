# FinSight AI — Power BI Build Guide

This guide builds the local Power BI dashboard from the validated semantic exports in `data/bi/`.

## 1. Load the seven CSV tables

Open Power BI Desktop and use **Home > Get data > Text/CSV**. Import these files one at a time from `data/bi/`:

- `dim_customer.csv`
- `dim_date.csv`
- `fact_invoice.csv`
- `fact_expense.csv`
- `fact_budget.csv`
- `fact_collection_risk.csv`
- `fact_cash_forecast.csv`

Choose **Transform Data** before loading so data types can be checked.

## 2. Check data types in Power Query

Use these types before selecting **Close & Apply**:

### dim_customer
- `customer_id`: Text
- `company_name`: Text
- `industry`: Text
- `region`: Text
- `customer_size`: Text
- `signup_date`: Date
- `credit_rating`: Text
- `payment_terms_days`: Whole Number

### dim_date
- `date`: Date
- `date_key`: Whole Number
- `year`: Whole Number
- `quarter`: Text
- `month_number`: Whole Number
- `month_name`: Text
- `year_month`: Text
- `week_number`: Whole Number
- `week_start`: Date
- `day_name`: Text
- `is_weekend`: True/False

### fact_invoice
- IDs/status/bucket columns: Text
- `invoice_date`, `due_date`: Date
- monetary columns: Fixed Decimal Number or Decimal Number
- count/day columns: Whole Number where applicable
- `paid_late`, `is_overdue`: True/False

### fact_expense
- IDs/category/vendor/department/reason: Text
- `expense_date`: Date
- `amount`, score and ratio fields: Decimal Number
- `review_flag`: True/False

### fact_budget
- `department`, `budget_status`, `budget_key`: Text
- `month`: Date
- monetary and variance fields: Decimal Number

### fact_collection_risk
- IDs/model/priority fields: Text
- `invoice_date`: Date
- risk probability/percentile/threshold fields: Decimal Number
- `late_30_days`: Whole Number

### fact_cash_forecast
- `week`: Date
- forecast fields: Decimal Number

## 3. Create the star-schema relationships

Open **Model view** and create these active relationships with **Single** cross-filter direction:

1. `dim_customer[customer_id]` 1 → * `fact_invoice[customer_id]`
2. `dim_customer[customer_id]` 1 → * `fact_collection_risk[customer_id]`
3. `dim_date[date]` 1 → * `fact_invoice[invoice_date]`
4. `dim_date[date]` 1 → * `fact_expense[expense_date]`
5. `dim_date[date]` 1 → * `fact_budget[month]`
6. `dim_date[date]` 1 → * `fact_collection_risk[invoice_date]`
7. `dim_date[date]` 1 → * `fact_cash_forecast[week]`

Also create an **inactive** relationship:

- `dim_date[date]` 1 → * `fact_invoice[due_date]`

Do not use bidirectional filtering for these relationships.

## 4. Mark the date table

Select `dim_date` in Model view, then use **Table tools > Mark as date table** and choose `dim_date[date]`.

Sort `dim_date[month_name]` by `dim_date[month_number]`.

## 5. Create the core measures

Create a dedicated empty measures table if desired, then add the measures from `powerbi/measures.dax`.

For formatting:
- currency measures: Currency, 0 or 2 decimals depending on the page
- percentage measures: Percentage, 1–2 decimals
- counts: Whole Number with thousands separator

## 6. Build page 1 — Executive Overview

Use the following layout:

### KPI cards
- Total Invoice Value
- Total Collections
- Gross Outstanding AR
- Overdue AR
- Overdue AR %
- Total Expense
- Budget Variance
- Forecast Net Cash Flow

### Visuals
1. **Line and clustered column chart**
   - Axis: `dim_date[year_month]`
   - Column: Total Invoice Value
   - Line: Total Collections

2. **Stacked bar chart — AR Aging**
   - Axis: `fact_invoice[aging_bucket]`
   - Value: Gross Outstanding AR

3. **Clustered bar chart — Budget vs Actual**
   - Axis: `fact_budget[department]`
   - Values: Budget Amount, Budget Actual

4. **Line chart — 8-Week Cash Outlook**
   - Axis: `fact_cash_forecast[week]`
   - Values: Forecast Collections, Forecast Expenses, Forecast Net Cash Flow

### Slicers
- `dim_date[year]`
- `dim_customer[industry]`
- `dim_customer[region]`
- `dim_customer[customer_size]`

## 7. Build page 2 — AR & Collections

Recommended visuals:

- KPI: Gross Outstanding AR
- KPI: Overdue AR
- KPI: Overdue AR %
- KPI: Open Invoice Count
- Bar: AR by `aging_bucket`
- Bar: Overdue AR by `company_name`
- Bar: Overdue AR by `industry`
- Donut or bar: invoice count by `reconciliation_status`
- Detail table: invoice ID, customer, due date, invoice amount, paid amount, outstanding amount, days past due, aging bucket, status

## 8. Build page 3 — Payment Risk

Recommended visuals:

- KPI: Priority Collection Invoice Count
- KPI: Average Risk Probability
- KPI: Priority Review Invoice Value
- Histogram or column chart: risk probability bins
- Scatter: risk probability vs invoice amount
- Bar: average risk by credit rating
- Bar: priority invoices by industry
- Detail table: invoice ID, customer ID, invoice amount, selected risk probability, risk percentile, collection priority

Use `0.35` only as the documented broad-screening threshold, not as a claim of default certainty.

## 9. Build page 4 — Expense & Anomaly Review

Recommended visuals:

- KPI: Total Expense
- KPI: Review Queue Count
- KPI: Review Queue Value
- KPI: Review Queue % of Spend
- Scatter: `expense_risk_score` vs `amount`
- Bar: Review Queue Value by department
- Bar: Review Queue Value by vendor
- Detail table: expense ID, date, department, vendor, category, amount, score, review reason

Use the terminology **Requires Review** or **Review Queue**. Do not label the model as fraud detection.

## 10. Build page 5 — Budget vs Actual

Recommended visuals:

- KPI: Budget Amount
- KPI: Budget Actual
- KPI: Budget Variance
- KPI: Over-Budget Department-Months
- Clustered columns: budget vs actual by department
- Line/column: monthly budget vs actual
- Matrix heatmap: department x month using `variance_pct`
- Exception table filtered to `budget_status = OVER_BUDGET`

## 11. Build page 6 — Cash-Flow Outlook

Recommended visuals:

- KPI: Forecast Collections
- KPI: Forecast Expenses
- KPI: Forecast Net Cash Flow
- Line chart: collections and expenses by forecast week
- Column chart: net cash flow by forecast week
- Optional cumulative-net-cash measure for a cumulative line

Document the deployed forecast methods on the page:
- Collections: rolling 4-week baseline
- Expenses: Gradient Boosting

## 12. Final validation

Before publishing or taking screenshots, verify:

- 5,000 rows in `dim_customer`
- 791 rows in `dim_date`
- 49,750 rows in `fact_invoice`
- 30,000 rows in `fact_expense`
- 144 rows in `fact_budget`
- 8,040 rows in `fact_collection_risk`
- 8 rows in `fact_cash_forecast`
- 4,091 priority collection invoices
- 300 expense review transactions
- 8-week forecast net cash flow of $6,416,922.94

These values are the current synthetic portfolio baseline and should reconcile to the local pipeline outputs.