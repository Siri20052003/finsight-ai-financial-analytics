# FinSight AI — Financial Intelligence, Revenue Leakage & Risk Analytics

FinSight AI is a portfolio-grade financial analytics platform built to demonstrate practical Data Analyst, BI, Financial Analytics, and AI/ML skills in one end-to-end project.

The project models a fictional B2B technology company, **NovaEdge Technologies**, and focuses on a realistic finance problem: reconciling invoices and payments, detecting data-quality issues, monitoring accounts receivable, analyzing expenses and budgets, and later adding machine-learning risk models and an AI-assisted analytics layer.

> **Important:** All data in this repository is synthetic. No real customer, employee, or company financial data is used.

## Project goals

FinSight AI will eventually support:

- Invoice-to-payment reconciliation
- Revenue leakage and exception analysis
- Accounts receivable aging and collection KPIs
- Budget vs. actual analysis
- Data-quality monitoring and audit controls
- Late-payment risk prediction
- Financial anomaly detection
- Cash collection / revenue forecasting
- Power BI executive reporting
- BigQuery + dbt transformation workflows
- Grounded natural-language financial analysis

## Current milestone: Foundation + synthetic data pipeline

The first working milestone includes:

- Reproducible synthetic financial data generation
- Six core source tables
- Intentional data-quality defects for realistic analysis
- Automated validation rules
- BigQuery-ready SQL for reconciliation, AR aging, and core KPIs
- Unit tests for reproducibility and defect injection
- CI-ready project structure

With the default configuration, the generator produces approximately **143K rows** across customers, invoices, payments, expenses, budgets, and adjustments.

The invoice dataset deliberately contains duplicates, missing customer IDs, and invalid due dates. Payments also include orphan invoice references. These issues are intentional and will later be detected, quantified, cleaned, and documented as part of the analytics workflow.

## Repository structure

```text
finsight-ai-financial-analytics/
├── data/
│   ├── raw/
│   └── processed/
├── docs/
│   ├── business_requirements.md
│   └── data_dictionary.md
├── sql/
│   ├── reconciliation.sql
│   ├── ar_aging.sql
│   └── financial_kpis.sql
├── src/
│   ├── config.py
│   ├── generate_data.py
│   ├── validate_data.py
│   └── run_pipeline.py
├── tests/
│   └── test_data_generation.py
├── .github/workflows/
│   └── tests.yml
├── .gitignore
├── requirements.txt
└── README.md
```

## Quick start

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Generate data:

```bash
python src/generate_data.py
```

Validate it:

```bash
python src/validate_data.py
```

Run the local pipeline:

```bash
python src/run_pipeline.py
```

Run tests:

```bash
pytest -q
```

## Core data model

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

## Intentional data-quality scenarios

- Duplicate invoice IDs
- Missing customer references
- Due dates earlier than invoice dates
- Partial payments
- Overpayments
- Unpaid invoices
- Orphan payment records
- Large anomalous expenses
- Credits, refunds, write-offs, and reversals

These are analyst investigation cases, not accidental generator bugs.

## Roadmap

- [x] Project architecture
- [x] Synthetic finance data generator
- [x] Data-quality validation framework
- [x] Reconciliation SQL
- [x] AR aging SQL
- [x] Core KPI SQL
- [x] Unit tests
- [ ] Clean / curated analytics layer
- [ ] BigQuery ingestion
- [ ] dbt staging and marts
- [ ] Power BI semantic model
- [ ] Executive finance dashboard
- [ ] Late-payment prediction model
- [ ] Financial anomaly detection
- [ ] Cash collection forecasting
- [ ] AI financial insight assistant
- [ ] Portfolio case study and demo

Results reported in the final case study will be derived from generated data and reproducible analysis rather than invented business outcomes.
