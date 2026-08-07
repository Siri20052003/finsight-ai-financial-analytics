from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROCESSED_DIR = Path("data/processed")
MODEL_DIR = Path("models")
MIN_MATURITY_DAYS = 30
RANDOM_STATE = 42

NUMERIC_FEATURES = [
    "invoice_amount",
    "payment_terms_days",
    "customer_tenure_days",
    "prior_invoice_count",
    "prior_late_rate",
    "invoice_month",
]
CATEGORICAL_FEATURES = [
    "credit_rating",
    "customer_size",
    "industry",
    "region",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "late_30_days"


def load_inputs(processed_dir=PROCESSED_DIR):
    processed_dir = Path(processed_dir)
    invoice_path = processed_dir / "invoice_analytics.csv"
    customer_path = processed_dir / "customers_clean.csv"
    if not invoice_path.exists() or not customer_path.exists():
        raise FileNotFoundError(
            "Missing processed analytics files. Run src/run_pipeline.py before training the model."
        )
    invoices = pd.read_csv(
        invoice_path,
        parse_dates=["invoice_date", "due_date", "first_payment_date", "last_payment_date"],
    )
    customers = pd.read_csv(customer_path, parse_dates=["signup_date"])
    return invoices, customers


def build_modeling_dataset(invoices, customers, as_of_date=None):
    df = invoices.copy()
    customer_cols = [
        "customer_id",
        "signup_date",
        "industry",
        "region",
        "customer_size",
        "credit_rating",
        "payment_terms_days",
    ]
    df = df.merge(customers[customer_cols], on="customer_id", how="left", validate="many_to_one")

    if as_of_date is None:
        as_of_date = pd.Timestamp(df["invoice_date"].max()).normalize()
    else:
        as_of_date = pd.Timestamp(as_of_date).normalize()

    # Only use invoices that have had at least 30 days after the contractual due
    # date to reveal whether they became seriously late. This avoids labeling
    # very recent invoices as "good" before their outcome is observable.
    maturity_cutoff = as_of_date - pd.Timedelta(days=MIN_MATURITY_DAYS)
    df = df[df["due_date"] <= maturity_cutoff].copy()
    df = df[df["net_amount_due"] > 0.01].copy()

    late_paid = (
        df["last_payment_date"].notna()
        & (df["last_payment_date"] > df["due_date"] + pd.Timedelta(days=MIN_MATURITY_DAYS))
    )
    still_open_late = df["positive_outstanding_amount"] > 0.01
    df[TARGET] = (late_paid | still_open_late).astype(int)

    df["customer_tenure_days"] = (df["invoice_date"] - df["signup_date"]).dt.days.clip(lower=0)
    df["invoice_month"] = df["invoice_date"].dt.month

    # Historical features are computed with a shift so the current invoice target
    # never leaks into its own predictors.
    df = df.sort_values(["customer_id", "invoice_date", "invoice_id"]).reset_index(drop=True)
    df["prior_invoice_count"] = df.groupby("customer_id").cumcount()
    prior_late_sum = df.groupby("customer_id")[TARGET].cumsum() - df[TARGET]
    df["prior_late_rate"] = np.where(
        df["prior_invoice_count"] > 0,
        prior_late_sum / df["prior_invoice_count"],
        np.nan,
    )
    global_rate = float(df[TARGET].mean()) if len(df) else 0.0
    df["prior_late_rate"] = df["prior_late_rate"].fillna(global_rate)

    # Keep only modeling-safe fields plus identifiers useful for audit/prediction export.
    keep = ["invoice_id", "customer_id", "invoice_date", TARGET] + FEATURES
    return df[keep].copy(), as_of_date


def chronological_split(df, train_fraction=0.80):
    if df.empty:
        raise ValueError("Modeling dataset is empty.")
    ordered = df.sort_values(["invoice_date", "invoice_id"]).reset_index(drop=True)
    split_idx = int(len(ordered) * train_fraction)
    split_idx = min(max(split_idx, 1), len(ordered) - 1)
    train = ordered.iloc[:split_idx].copy()
    test = ordered.iloc[split_idx:].copy()
    return train, test


def make_preprocessor():
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric, NUMERIC_FEATURES),
            ("cat", categorical, CATEGORICAL_FEATURES),
        ]
    )


def model_candidates():
    return {
        "logistic_regression": LogisticRegression(
            max_iter=1500,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=8,
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }


def evaluate(y_true, probability, threshold=0.50):
    pred = (probability >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "roc_auc": round(float(roc_auc_score(y_true, probability)), 4),
        "pr_auc": round(float(average_precision_score(y_true, probability)), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def train_models(modeling_df):
    train, test = chronological_split(modeling_df)
    X_train, y_train = train[FEATURES], train[TARGET]
    X_test, y_test = test[FEATURES], test[TARGET]

    results = {}
    fitted = {}
    probabilities = {}

    for name, estimator in model_candidates().items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", make_preprocessor()),
                ("model", estimator),
            ]
        )
        pipeline.fit(X_train, y_train)
        probability = pipeline.predict_proba(X_test)[:, 1]
        results[name] = evaluate(y_test, probability)
        fitted[name] = pipeline
        probabilities[name] = probability

    # PR-AUC is used for selection because collection-risk events may be imbalanced
    # and precision/recall trade-offs matter more than raw accuracy.
    best_name = max(results, key=lambda name: results[name]["pr_auc"])
    return train, test, fitted, probabilities, results, best_name


def save_artifacts(modeling_df, train, test, fitted, probabilities, results, best_name, as_of_date):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    modeling_df.to_csv(PROCESSED_DIR / "late_payment_modeling_dataset.csv", index=False)

    prediction_export = test[["invoice_id", "customer_id", "invoice_date", TARGET, "invoice_amount"]].copy()
    for name, probability in probabilities.items():
        prediction_export[f"{name}_risk_probability"] = np.round(probability, 6)
    prediction_export["selected_model"] = best_name
    prediction_export["selected_risk_probability"] = np.round(probabilities[best_name], 6)
    prediction_export = prediction_export.sort_values("selected_risk_probability", ascending=False)
    prediction_export.to_csv(PROCESSED_DIR / "late_payment_predictions.csv", index=False)

    joblib.dump(fitted[best_name], MODEL_DIR / "late_payment_model.joblib")

    metrics = {
        "as_of_date": pd.Timestamp(as_of_date).strftime("%Y-%m-%d"),
        "target_definition": "Invoice paid more than 30 days after due date OR still open after 30 days past due",
        "modeling_rows": int(len(modeling_df)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_late_rate": round(float(train[TARGET].mean()), 4),
        "test_late_rate": round(float(test[TARGET].mean()), 4),
        "selected_model": best_name,
        "selection_metric": "pr_auc",
        "models": results,
    }
    (MODEL_DIR / "late_payment_metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def main():
    invoices, customers = load_inputs()
    modeling_df, as_of_date = build_modeling_dataset(invoices, customers)
    train, test, fitted, probabilities, results, best_name = train_models(modeling_df)
    metrics = save_artifacts(
        modeling_df,
        train,
        test,
        fitted,
        probabilities,
        results,
        best_name,
        as_of_date,
    )

    print("FinSight AI late-payment model")
    print(f"Modeling rows              : {metrics['modeling_rows']:,}")
    print(f"Train rows                 : {metrics['train_rows']:,}")
    print(f"Test rows                  : {metrics['test_rows']:,}")
    print(f"Train late-payment rate    : {metrics['train_late_rate']:.2%}")
    print(f"Test late-payment rate     : {metrics['test_late_rate']:.2%}")
    print()
    for name, values in results.items():
        print(name)
        print(f"  ROC-AUC                  : {values['roc_auc']:.4f}")
        print(f"  PR-AUC                   : {values['pr_auc']:.4f}")
        print(f"  Precision                : {values['precision']:.4f}")
        print(f"  Recall                   : {values['recall']:.4f}")
        print(f"  F1                       : {values['f1']:.4f}")
        print(f"  Confusion matrix         : TN={values['tn']}, FP={values['fp']}, FN={values['fn']}, TP={values['tp']}")
        print()
    print(f"Selected model             : {best_name}")
    print(f"Saved model                : {MODEL_DIR / 'late_payment_model.joblib'}")
    print(f"Saved predictions          : {PROCESSED_DIR / 'late_payment_predictions.csv'}")


if __name__ == "__main__":
    main()
