from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

PROCESSED_DIR = Path("data/processed")
MODEL_DIR = Path("models")
RANDOM_STATE = 42
REVIEW_FRACTION = 0.01
EPSILON = 1e-9


def load_expenses(processed_dir=PROCESSED_DIR):
    path = Path(processed_dir) / "expenses_clean.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run src/run_pipeline.py before anomaly detection."
        )
    return pd.read_csv(path, parse_dates=["expense_date"])


def _median_and_mad(df, group_col):
    med = df.groupby(group_col)["amount"].transform("median")
    abs_dev = (df["amount"] - med).abs()
    mad = abs_dev.groupby(df[group_col]).transform("median")
    global_mad = float((df["amount"] - df["amount"].median()).abs().median())
    mad = mad.replace(0, np.nan).fillna(global_mad if global_mad > 0 else 1.0)
    return med, mad


def _robust_z(amount, median, mad):
    # 0.6745 scales MAD to be comparable with a standard deviation under normality.
    return 0.6745 * (amount - median) / (mad + EPSILON)


def build_features(expenses):
    df = expenses.copy()
    if (df["amount"] <= 0).any():
        raise ValueError("Expense anomaly model expects strictly positive amounts.")

    vendor_median, vendor_mad = _median_and_mad(df, "vendor")
    category_median, category_mad = _median_and_mad(df, "expense_category")
    department_median, department_mad = _median_and_mad(df, "department")

    df["vendor_median_amount"] = vendor_median
    df["category_median_amount"] = category_median
    df["department_median_amount"] = department_median
    df["vendor_robust_z"] = _robust_z(df["amount"], vendor_median, vendor_mad)
    df["category_robust_z"] = _robust_z(df["amount"], category_median, category_mad)
    df["department_robust_z"] = _robust_z(df["amount"], department_median, department_mad)
    df["vendor_ratio"] = df["amount"] / (vendor_median + EPSILON)
    df["category_ratio"] = df["amount"] / (category_median + EPSILON)
    df["department_ratio"] = df["amount"] / (department_median + EPSILON)
    df["log_amount"] = np.log1p(df["amount"])

    feature_cols = [
        "log_amount",
        "vendor_robust_z",
        "category_robust_z",
        "department_robust_z",
        "vendor_ratio",
        "category_ratio",
        "department_ratio",
    ]
    features = df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return df, features


def score_anomalies(expenses, review_fraction=REVIEW_FRACTION):
    if not 0 < review_fraction < 1:
        raise ValueError("review_fraction must be between 0 and 1.")

    df, features = build_features(expenses)
    model = IsolationForest(
        n_estimators=350,
        contamination=review_fraction,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(features)

    # sklearn's score_samples is lower for more abnormal observations.
    raw = -model.score_samples(features)
    df["isolation_anomaly_score"] = raw
    df["isolation_percentile"] = pd.Series(raw).rank(pct=True, method="average")

    robust_signal = df[["vendor_robust_z", "category_robust_z", "department_robust_z"]].clip(lower=0).max(axis=1)
    df["robust_signal_percentile"] = robust_signal.rank(pct=True, method="average")

    # Blend an unsupervised multivariate score with transparent peer-group statistics.
    df["expense_risk_score"] = (
        0.65 * df["isolation_percentile"] + 0.35 * df["robust_signal_percentile"]
    ).round(6)

    cutoff = float(df["expense_risk_score"].quantile(1 - review_fraction))
    df["review_flag"] = df["expense_risk_score"] >= cutoff

    def reason(row):
        reasons = []
        if row["vendor_ratio"] >= 4:
            reasons.append(f"{row['vendor_ratio']:.1f}x vendor median")
        if row["category_ratio"] >= 4:
            reasons.append(f"{row['category_ratio']:.1f}x category median")
        if row["department_ratio"] >= 4:
            reasons.append(f"{row['department_ratio']:.1f}x department median")
        if row["isolation_percentile"] >= 0.99:
            reasons.append("top 1% multivariate anomaly score")
        return "; ".join(reasons) if reasons else "unusual peer-group pattern"

    df["review_reason"] = df.apply(reason, axis=1)
    queue = df[df["review_flag"]].sort_values("expense_risk_score", ascending=False).copy()
    return df, queue, model, cutoff


def summarize(scored, queue, cutoff):
    total_value = float(scored["amount"].sum())
    review_value = float(queue["amount"].sum())
    nonreview = scored[~scored["review_flag"]]
    return {
        "expense_rows": int(len(scored)),
        "review_rows": int(len(queue)),
        "review_rate": round(float(len(queue) / len(scored)), 4),
        "risk_score_cutoff": round(cutoff, 6),
        "total_expense_value": round(total_value, 2),
        "review_queue_value": round(review_value, 2),
        "review_value_share": round(review_value / total_value, 4) if total_value else 0.0,
        "median_review_amount": round(float(queue["amount"].median()), 2) if len(queue) else None,
        "median_nonreview_amount": round(float(nonreview["amount"].median()), 2) if len(nonreview) else None,
        "max_review_amount": round(float(queue["amount"].max()), 2) if len(queue) else None,
    }


def save_artifacts(scored, queue, model, summary):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    scored.to_csv(PROCESSED_DIR / "expense_anomaly_scores.csv", index=False)
    queue.to_csv(PROCESSED_DIR / "expense_anomaly_review_queue.csv", index=False)
    (MODEL_DIR / "expense_anomaly_metrics.json").write_text(json.dumps(summary, indent=2))


def main():
    expenses = load_expenses()
    scored, queue, model, cutoff = score_anomalies(expenses)
    summary = summarize(scored, queue, cutoff)
    save_artifacts(scored, queue, model, summary)

    print("FinSight AI expense anomaly detection")
    print(f"Expense rows                 : {summary['expense_rows']:,}")
    print(f"Review queue                 : {summary['review_rows']:,} ({summary['review_rate']:.2%})")
    print(f"Risk score cutoff            : {summary['risk_score_cutoff']:.4f}")
    print(f"Total expense value          : ${summary['total_expense_value']:,.2f}")
    print(f"Review queue value           : ${summary['review_queue_value']:,.2f} ({summary['review_value_share']:.2%} of spend)")
    print(f"Median review amount         : ${summary['median_review_amount']:,.2f}")
    print(f"Median non-review amount     : ${summary['median_nonreview_amount']:,.2f}")
    print(f"Largest reviewed transaction : ${summary['max_review_amount']:,.2f}")
    print("\nTop 10 transactions for review")
    display_cols = [
        "expense_id",
        "expense_date",
        "department",
        "vendor",
        "expense_category",
        "amount",
        "expense_risk_score",
        "review_reason",
    ]
    print(queue[display_cols].head(10).to_string(index=False))
    print(f"\nSaved scores                 : {PROCESSED_DIR / 'expense_anomaly_scores.csv'}")
    print(f"Saved review queue           : {PROCESSED_DIR / 'expense_anomaly_review_queue.csv'}")


if __name__ == "__main__":
    main()
