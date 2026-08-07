# Cash-Flow Forecast Model Card

## Purpose

FinSight AI forecasts weekly collections and operating expenses over an 8-week horizon. The forecasting layer is intended for planning and scenario support, not as a substitute for treasury judgment.

## Data

- Frequency: weekly
- Historical window in the current synthetic portfolio: 105 weeks
- Targets: collections and expenses
- Forecast horizon: 8 weeks
- Evaluation holdout: final 16 weeks

## Candidate methods

1. Gradient Boosting Regressor with lag, rolling-average, seasonal, and trend features.
2. Rolling 4-week average baseline.

The deployed method is selected independently for each target using out-of-sample MAE. A more complex model is not selected unless it beats the simple baseline.

## Current evaluation

### Collections

| Metric | Gradient Boosting | 4-week baseline |
| --- | ---: | ---: |
| MAE | $297,236.82 | $194,157.76 |
| RMSE | $404,097.73 | $295,568.31 |
| MAPE | 24.60% | 16.94% |

**Deployment decision:** use the rolling 4-week baseline for collections. The ML model underperforms the baseline materially on all three reported error metrics.

### Expenses

| Metric | Gradient Boosting | 4-week baseline |
| --- | ---: | ---: |
| MAE | $63,845.27 | $66,089.73 |
| RMSE | $92,285.25 | $98,526.10 |
| MAPE | 16.53% | 17.85% |

**Deployment decision:** use Gradient Boosting for expenses. It provides a modest but consistent improvement over the baseline.

## Governance rule

FinSight uses a champion-vs-baseline policy:

- select the lower-MAE method separately for collections and expenses;
- retain the simple baseline whenever ML does not improve holdout performance;
- store the selected method and evaluation metrics with the forecast artifact;
- do not describe an ML forecast as superior when the validation evidence does not support that claim.

## Interpretation

The current results show that model complexity is target-dependent. Collections are better handled by a simple recent-history baseline, while expenses contain enough lag/seasonal structure for the Gradient Boosting model to add modest predictive value.

## Limitations

- The dataset is synthetic and spans roughly two years, limiting long-cycle seasonality.
- Forecast uncertainty intervals are not yet implemented.
- Macroeconomic, contract-renewal, billing-calendar, and known future commitment features are not included.
- Recursive multi-step forecasting can compound error across the 8-week horizon.

## Next improvements

- add prediction intervals;
- evaluate rolling-origin backtests instead of a single holdout;
- incorporate invoice due schedules and open AR into collections forecasting;
- incorporate committed spend and budget calendar features into expense forecasting;
- compare with additional statistical baselines where justified.
