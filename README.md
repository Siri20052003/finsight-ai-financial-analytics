# FinSight AI — Financial Intelligence, Revenue Leakage & Risk Analytics

FinSight AI is an end-to-end financial analytics portfolio project for Data Analyst, BI Analyst, Financial Data Analyst, and AI/ML-assisted analytics roles.

The project models a fictional B2B technology company, **NovaEdge Technologies**, and combines financial reconciliation, accounts receivable, budget analysis, data-quality controls, machine learning, anomaly detection, forecasting, and business intelligence in one reproducible workflow.

> **Important:** All data is synthetic. No real customer, employee, or company financial data is used.

## What FinSight AI does

- Generates reproducible multi-table financial data with intentional source-system defects
- Validates duplicates, missing references, invalid due dates, and orphan payments
- Builds a curated invoice-to-payment reconciliation layer
- Calculates AR aging, overdue balances, collections, credit balances, and budget variance
- Predicts 30+ day late-payment risk using Logistic Regression and Random Forest
- Converts model probabilities into a collections-prioritization strategy
- Detects unusual expense transactions using Isolation Forest and robust peer-group statistics
- Forecasts weekly collections and expenses using champion-vs-baseline model selection
- Exports a Power BI-ready star schema
- Provides BigQuery-ready SQL for financial analytics

## Current reproducible results

### Late-payment risk

The evaluation portfolio contains 8,040 holdout invoices. Random Forest was selected on PR-AUC, while Logistic Regression remained competitive on ROC-AUC, recall, and F1.

At a 0.35 collections-screening threshold:

- Recall: **72.84%**
- Precision: **33.76%**
- True positives: **1,381**
- False negatives: **515**

Risk concentration provides the stronger operational use case:

- Highest-risk 5% captured **12.55%** of late cases, **2.51x lift**
- Highest-risk 10% captured **22.94%** of late cases, **2.29x lift**
- Highest-risk 20% captured **40.08%** of late cases, **2.00x lift**

### Expense anomaly review

- Expense transactions analyzed: **30,000**
- Review queue: **300 transactions (1%)**
- Total expense value: **$56.78M**
- Review queue value: **$5.52M**
- Top 1% of transactions represented **9.73% of total spend**
- Median reviewed transaction: **$14.7K** vs **$1.2K** for non-reviewed transactions

The model identifies transactions requiring investigation; it is not labeled as a fraud detector.

### Cash-flow forecasting

FinSight evaluates Gradient Boosting against a 4-week moving-average baseline and deploys the lower-MAE method independently for each target.

- **Collections:** rolling 4-week baseline selected; Gradient Boosting MAE was 53.09% worse
- **Expenses:** Gradient Boosting selected; MAE improved 3.40% over baseline

Current 8-week outlook:

- Forecast collections: **$9.54M**
- Forecast expenses: **$3.12M**
- Forecast net cash flow: **$6.42M**

This champion-vs-baseline policy prevents the project from claiming ML superiority when validation evidence does not support it.

## Architecture

```text
Synthetic Sources
      │
      ▼
Data Quality Validation
      │
      ▼
Curated Reconciliation Layer
      │
      ├──────────────► AR / Budget / KPI Analytics
      │
      ├──────────────► Late-Payment Risk Model
      │
      ├──────────────► Expense Anomaly Detection
      │
      └──────────────► Cash-Flow Forecasting
                              │
                              ▼
                    Power BI Semantic Export
                              │
                              ▼
                    BigQuery + dbt + Power BI
```

## Core source model

```text
CUSTOMERS
    │
    └──< INVOICES
            │
            ├──< PAYMENTS
            │
            └──< ADJUSTMENTS

DEPARTMENTS
    ├──< EXPENSES
    └──< BUDGETS
```

## Repository structure

```text
finsight-ai-financial-analytics/
├── docs/
│   ├── business_requirements.md
│   ├── data_dictionary.md
│   ├── late_payment_model_card.md
│   ├── forecast_model_card.md
│   └── power_bi_dashboard_spec.md
├── sql/
│   ├── reconciliation.sql
│   ├── ar_aging.sql
│   └── financial_kpis.sql
├── src/
│   ├── config.py
│   ├── generate_data.py
│   ├── validate_data.py
│   ├── build_curated.py
│   ├── build_analytics.py
│   ├── train_late_payment_model.py
│   ├── evaluate_collection_strategy.py
│   ├── detect_expense_anomalies.py
│   ├── forecast_cash_flow.py
│   ├── build_bi_model.py
│   └── run_pipeline.py
├── tests/
├── models/
├── data/
│   ├── raw/
│   ├── processed/
│   └── bi/
├── .github/workflows/tests.yml
├── requirements.txt
└── README.md
```

Generated raw/processed data and local model artifacts are intentionally excluded from Git where appropriate.

## Quick start

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

Windows users who do not want to change PowerShell execution policy can invoke the virtual-environment interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the core financial pipeline:

```powershell
.\.venv\Scripts\python.exe src\run_pipeline.py
```

Train and evaluate the late-payment model:

```powershell
.\.venv\Scripts\python.exe src\train_late_payment_model.py
.\.venv\Scripts\python.exe src\evaluate_collection_strategy.py
```

Run expense anomaly detection and forecasting:

```powershell
.\.venv\Scripts\python.exe src\detect_expense_anomalies.py
.\.venv\Scripts\python.exe src\forecast_cash_flow.py
```

Build Power BI-ready star-schema files:

```powershell
.\.venv\Scripts\python.exe src\build_bi_model.py
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Power BI semantic layer

`src/build_bi_model.py` exports:

- `dim_customer.csv`
- `dim_date.csv`
- `fact_invoice.csv`
- `fact_expense.csv`
- `fact_budget.csv`
- `fact_collection_risk.csv`
- `fact_cash_forecast.csv`

See `docs/power_bi_dashboard_spec.md` for recommended relationships, dashboard pages, drill-through design, and core DAX measures.

## Intentional data-quality scenarios

- Duplicate invoice IDs
- Missing customer references
- Due dates earlier than invoice dates
- Partial payments
- Overpayments
- Unpaid invoices
- Orphan payment records / unapplied cash
- Large anomalous expenses
- Credits, refunds, write-offs, and reversals

These are analyst investigation cases, not accidental generator bugs.

## Roadmap

- [x] Project architecture
- [x] Synthetic finance data generator
- [x] Data-quality validation framework
- [x] Curated reconciliation layer
- [x] AR aging and financial KPI analytics
- [x] Budget-vs-actual analysis
- [x] Late-payment prediction
- [x] Collections threshold and concentration analysis
- [x] Expense anomaly detection
- [x] Champion-vs-baseline cash-flow forecasting
- [x] Power BI semantic export layer
- [ ] Build Power BI executive dashboard
- [ ] BigQuery ingestion
- [ ] dbt staging and marts
- [ ] Connect Power BI to cloud warehouse
- [ ] Grounded AI financial insight assistant
- [ ] Portfolio case study and demo

All reported outcomes are derived from generated data and reproducible analysis rather than invented business results.
