# Late-Payment Risk Model Card

## Business objective
Prioritize invoices for proactive collections outreach by estimating the probability that an invoice will become 30+ days late.

## Target definition
An invoice is labeled `late_30_days = 1` when it is paid more than 30 days after its contractual due date or remains open after 30 days past due.

## Modeling design
- Chronological train/test split to mimic future scoring rather than random resampling.
- Only sufficiently mature invoices are labeled, preventing very recent invoices from being incorrectly treated as good outcomes.
- Historical customer behavior uses shifted aggregates so the current invoice target does not leak into its own predictors.
- Candidate models: Logistic Regression and Random Forest.
- Primary selection metric: PR-AUC, because late-payment risk is an imbalanced classification problem where precision/recall trade-offs matter more than raw accuracy.

## Current evaluation snapshot
Test set: 8,040 invoices

### Logistic Regression
- ROC-AUC: 0.7083
- PR-AUC: 0.4316
- Precision at 0.50: 0.4160
- Recall at 0.50: 0.5396
- F1 at 0.50: 0.4698

### Random Forest
- ROC-AUC: 0.7006
- PR-AUC: 0.4334
- Precision at 0.50: 0.4471
- Recall at 0.50: 0.4863
- F1 at 0.50: 0.4659

Random Forest is retained as the selected model because it has the slightly higher PR-AUC, but the difference is small. Logistic Regression remains a competitive benchmark and provides higher recall at the default 0.50 threshold.

## Collection strategy
A 0.35 operating threshold produces:
- Precision: 33.76%
- Recall: 72.84%
- F1: 0.4613
- 4,091 invoices flagged
- 1,381 true positives
- 2,710 false positives
- 515 false negatives

This threshold is best interpreted as a broad screening rule, not a manual-contact queue, because it flags roughly half of the test portfolio.

## Risk concentration
The ranked model is more operationally useful for prioritization:

- Top 5% of invoices capture 12.55% of late-payment cases, with a 2.51x lift over the portfolio average.
- Top 10% capture 22.94% of late-payment cases, with a 2.29x lift.
- Top 20% capture 40.08% of late-payment cases, with a 2.00x lift.

For a collections team with limited capacity, the recommended operating design is to use ranked risk tiers (for example top 10% or top 20%) rather than contacting every invoice above 0.35.

## Limitations
- The dataset is synthetic and calibrated for portfolio learning; model quality should not be interpreted as real-world credit performance.
- The model predicts late-payment behavior, not default probability or expected credit loss.
- The synthetic generator currently encodes simplified customer-risk relationships and does not include macroeconomic, contract, product, or behavioral event data.
- No causal claim should be made from the model scores.

## Portfolio takeaway
The model demonstrates an end-to-end decision workflow: define a finance target, build leakage-safe features, use a time-based validation split, compare model families, evaluate precision/recall trade-offs, and convert probability scores into a constrained collections-prioritization strategy.
