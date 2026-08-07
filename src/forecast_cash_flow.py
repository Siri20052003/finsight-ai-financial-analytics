from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

PROCESSED_DIR = Path("data/processed")
MODEL_DIR = Path("models")
FORECAST_HORIZON_WEEKS = 8
TEST_WEEKS = 16
RANDOM_STATE = 42


def load_inputs(processed_dir=PROCESSED_DIR):
    processed_dir = Path(processed_dir)
    payments_path = processed_dir / "payments_clean.csv"
    expenses_path = processed_dir / "expenses_clean.csv"
    if not payments_path.exists() or not expenses_path.exists():
        raise FileNotFoundError(
            "Missing processed payment/expense files. Run src/run_pipeline.py first."
        )
    payments = pd.read_csv(payments_path, parse_dates=["payment_date"])
    expenses = pd.read_csv(expenses_path, parse_dates=["expense_date"])
    return payments, expenses


def build_weekly_series(payments, expenses):
    collection_weekly = (
        payments.assign(week=payments["payment_date"].dt.to_period("W-SUN").dt.start_time)
        .groupby("week", as_index=False)
        .agg(collections=("payment_amount", "sum"))
    )
    expense_weekly = (
        expenses.assign(week=expenses["expense_date"].dt.to_period("W-SUN").dt.start_time)
        .groupby("week", as_index=False)
        .agg(expenses=("amount", "sum"))
    )

    start = min(collection_weekly["week"].min(), expense_weekly["week"].min())
    end = max(collection_weekly["week"].max(), expense_weekly["week"].max())
    calendar = pd.DataFrame({"week": pd.date_range(start, end, freq="W-MON")})

    weekly = (
        calendar.merge(collection_weekly, on="week", how="left")
        .merge(expense_weekly, on="week", how="left")
        .fillna({"collections": 0.0, "expenses": 0.0})
        .sort_values("week")
        .reset_index(drop=True)
    )
    weekly["net_cash_flow"] = weekly["collections"] - weekly["expenses"]
    return weekly


def add_time_features(df, target):
    out = df[["week", target]].copy()
    for lag in [1, 2, 4, 8]:
        out[f"lag_{lag}"] = out[target].shift(lag)
    out["rolling_4"] = out[target].shift(1).rolling(4).mean()
    out["rolling_8"] = out[target].shift(1).rolling(8).mean()
    week_num = out["week"].dt.isocalendar().week.astype(int)
    out["sin_week"] = np.sin(2 * np.pi * week_num / 52.0)
    out["cos_week"] = np.cos(2 * np.pi * week_num / 52.0)
    out["trend"] = np.arange(len(out))
    return out.dropna().reset_index(drop=True)


FEATURES = [
    "lag_1",
    "lag_2",
    "lag_4",
    "lag_8",
    "rolling_4",
    "rolling_8",
    "sin_week",
    "cos_week",
    "trend",
]


def evaluate_model(series, target, test_weeks=TEST_WEEKS):
    featured = add_time_features(series, target)
    if len(featured) <= test_weeks + 10:
        raise ValueError("Not enough weekly history to train and evaluate forecasting model.")

    train = featured.iloc[:-test_weeks].copy()
    test = featured.iloc[-test_weeks:].copy()

    model = GradientBoostingRegressor(
        n_estimators=250,
        learning_rate=0.03,
        max_depth=3,
        random_state=RANDOM_STATE,
        loss="huber",
    )
    model.fit(train[FEATURES], train[target])
    prediction = model.predict(test[FEATURES])

    # Baseline: use prior 4-week average available at each test observation.
    baseline = test["rolling_4"].to_numpy()
    actual = test[target].to_numpy()

    def metrics(pred):
        mae = mean_absolute_error(actual, pred)
        rmse = np.sqrt(mean_squared_error(actual, pred))
        mape = np.mean(np.abs((actual - pred) / np.maximum(np.abs(actual), 1.0)))
        return {
            "mae": round(float(mae), 2),
            "rmse": round(float(rmse), 2),
            "mape": round(float(mape), 4),
        }

    return model, train, test, prediction, baseline, metrics(prediction), metrics(baseline)


def recursive_forecast(series, target, horizon=FORECAST_HORIZON_WEEKS):
    history = series[["week", target]].copy().sort_values("week").reset_index(drop=True)
    featured = add_time_features(history, target)
    model = GradientBoostingRegressor(
        n_estimators=250,
        learning_rate=0.03,
        max_depth=3,
        random_state=RANDOM_STATE,
        loss="huber",
    )
    model.fit(featured[FEATURES], featured[target])

    forecasts = []
    for _ in range(horizon):
        next_week = history["week"].max() + pd.Timedelta(days=7)
        extended = pd.concat(
            [history, pd.DataFrame({"week": [next_week], target: [np.nan]})],
            ignore_index=True,
        )

        row = {
            "lag_1": float(extended[target].iloc[-2]),
            "lag_2": float(extended[target].iloc[-3]),
            "lag_4": float(extended[target].iloc[-5]),
            "lag_8": float(extended[target].iloc[-9]),
            "rolling_4": float(extended[target].iloc[-5:-1].mean()),
            "rolling_8": float(extended[target].iloc[-9:-1].mean()),
            "sin_week": float(np.sin(2 * np.pi * int(next_week.isocalendar().week) / 52.0)),
            "cos_week": float(np.cos(2 * np.pi * int(next_week.isocalendar().week) / 52.0)),
            "trend": float(len(history)),
        }
        next_value = float(max(0.0, model.predict(pd.DataFrame([row])[FEATURES])[0]))
        history = pd.concat(
            [history, pd.DataFrame({"week": [next_week], target: [next_value]})],
            ignore_index=True,
        )
        forecasts.append({"week": next_week, f"forecast_{target}": round(next_value, 2)})

    return pd.DataFrame(forecasts), model


def build_forecast_report(weekly):
    results = {}
    forecast_frames = []

    for target in ["collections", "expenses"]:
        _, _, test, prediction, baseline, model_metrics, baseline_metrics = evaluate_model(weekly, target)
        forecast, _ = recursive_forecast(weekly, target)
        results[target] = {
            "model": model_metrics,
            "baseline": baseline_metrics,
            "test_start": test["week"].min().strftime("%Y-%m-%d"),
            "test_end": test["week"].max().strftime("%Y-%m-%d"),
        }
        forecast_frames.append(forecast)

    forecast = forecast_frames[0].merge(forecast_frames[1], on="week", how="inner")
    forecast["forecast_net_cash_flow"] = (
        forecast["forecast_collections"] - forecast["forecast_expenses"]
    ).round(2)

    results["forecast_horizon_weeks"] = FORECAST_HORIZON_WEEKS
    results["forecast_start"] = forecast["week"].min().strftime("%Y-%m-%d")
    results["forecast_end"] = forecast["week"].max().strftime("%Y-%m-%d")
    results["forecast_total_collections"] = round(float(forecast["forecast_collections"].sum()), 2)
    results["forecast_total_expenses"] = round(float(forecast["forecast_expenses"].sum()), 2)
    results["forecast_net_cash_flow"] = round(float(forecast["forecast_net_cash_flow"].sum()), 2)

    return forecast, results


def save_outputs(weekly, forecast, results):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    weekly.to_csv(PROCESSED_DIR / "weekly_cash_flow_history.csv", index=False)
    forecast.to_csv(PROCESSED_DIR / "cash_flow_forecast.csv", index=False)
    (MODEL_DIR / "cash_flow_forecast_metrics.json").write_text(json.dumps(results, indent=2))


def main():
    payments, expenses = load_inputs()
    weekly = build_weekly_series(payments, expenses)
    forecast, results = build_forecast_report(weekly)
    save_outputs(weekly, forecast, results)

    print("FinSight AI cash-flow forecasting")
    print(f"Weekly history                : {len(weekly):,} weeks")
    print(f"Forecast horizon              : {results['forecast_horizon_weeks']} weeks")
    print()

    for target in ["collections", "expenses"]:
        print(target)
        print(f"  Model MAE                   : ${results[target]['model']['mae']:,.2f}")
        print(f"  Baseline MAE                : ${results[target]['baseline']['mae']:,.2f}")
        print(f"  Model RMSE                  : ${results[target]['model']['rmse']:,.2f}")
        print(f"  Baseline RMSE               : ${results[target]['baseline']['rmse']:,.2f}")
        print(f"  Model MAPE                  : {results[target]['model']['mape']:.2%}")
        print(f"  Baseline MAPE               : {results[target]['baseline']['mape']:.2%}")
        print()

    print("8-week forward outlook")
    print(forecast.to_string(index=False, formatters={
        'forecast_collections': lambda x: f'${x:,.2f}',
        'forecast_expenses': lambda x: f'${x:,.2f}',
        'forecast_net_cash_flow': lambda x: f'${x:,.2f}',
    }))
    print()
    print(f"Forecast collections total    : ${results['forecast_total_collections']:,.2f}")
    print(f"Forecast expenses total       : ${results['forecast_total_expenses']:,.2f}")
    print(f"Forecast net cash flow        : ${results['forecast_net_cash_flow']:,.2f}")
    print(f"\nSaved forecast                : {PROCESSED_DIR / 'cash_flow_forecast.csv'}")


if __name__ == "__main__":
    main()
