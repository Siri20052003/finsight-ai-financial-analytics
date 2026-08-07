from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

PROCESSED_DIR = Path("data/processed")
MODEL_DIR = Path("models")
TARGET = "late_30_days"
PROBABILITY = "selected_risk_probability"


def load_predictions(processed_dir=PROCESSED_DIR):
    path = Path(processed_dir) / "late_payment_predictions.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run src/train_late_payment_model.py first."
        )
    return pd.read_csv(path, parse_dates=["invoice_date"])


def threshold_table(df, thresholds=None):
    if thresholds is None:
        thresholds = np.arange(0.20, 0.81, 0.05)

    rows = []
    y_true = df[TARGET].astype(int).to_numpy()
    probability = df[PROBABILITY].astype(float).to_numpy()

    for threshold in thresholds:
        pred = (probability >= threshold).astype(int)
        tp = int(((pred == 1) & (y_true == 1)).sum())
        fp = int(((pred == 1) & (y_true == 0)).sum())
        fn = int(((pred == 0) & (y_true == 1)).sum())
        tn = int(((pred == 0) & (y_true == 0)).sum())
        rows.append(
            {
                "threshold": round(float(threshold), 2),
                "flagged_invoices": int(pred.sum()),
                "precision": float(precision_score(y_true, pred, zero_division=0)),
                "recall": float(recall_score(y_true, pred, zero_division=0)),
                "f1": float(f1_score(y_true, pred, zero_division=0)),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
            }
        )
    return pd.DataFrame(rows)


def choose_operating_threshold(table, minimum_recall=0.70):
    eligible = table[table["recall"] >= minimum_recall].copy()
    if eligible.empty:
        return table.loc[table["recall"].idxmax()].to_dict()

    # Collections teams usually care about catching a large share of risky invoices,
    # but they also have finite outreach capacity. Among thresholds meeting the
    # recall floor, choose the one with the best precision; F1 breaks ties.
    eligible = eligible.sort_values(["precision", "f1", "threshold"], ascending=[False, False, False])
    return eligible.iloc[0].to_dict()


def concentration_metrics(df, fractions=(0.05, 0.10, 0.20)):
    ranked = df.sort_values(PROBABILITY, ascending=False).reset_index(drop=True)
    total_late = int(ranked[TARGET].sum())
    total_invoice_value = float(ranked["invoice_amount"].sum())
    base_rate = float(ranked[TARGET].mean())

    rows = []
    for fraction in fractions:
        n = max(1, int(np.ceil(len(ranked) * fraction)))
        segment = ranked.head(n)
        late_found = int(segment[TARGET].sum())
        segment_rate = float(segment[TARGET].mean())
        rows.append(
            {
                "portfolio_fraction": float(fraction),
                "invoice_count": int(n),
                "late_invoices_captured": late_found,
                "late_capture_rate": late_found / total_late if total_late else 0.0,
                "segment_late_rate": segment_rate,
                "lift_vs_average": segment_rate / base_rate if base_rate else 0.0,
                "invoice_value_reviewed": float(segment["invoice_amount"].sum()),
                "portfolio_value_share": (
                    float(segment["invoice_amount"].sum()) / total_invoice_value
                    if total_invoice_value
                    else 0.0
                ),
            }
        )
    return pd.DataFrame(rows)


def main():
    df = load_predictions()
    table = threshold_table(df)
    recommendation = choose_operating_threshold(table, minimum_recall=0.70)
    concentration = concentration_metrics(df)

    table.to_csv(PROCESSED_DIR / "late_payment_threshold_analysis.csv", index=False)
    concentration.to_csv(PROCESSED_DIR / "late_payment_risk_concentration.csv", index=False)

    summary = {
        "recommended_threshold": round(float(recommendation["threshold"]), 2),
        "minimum_recall_policy": 0.70,
        "precision_at_threshold": round(float(recommendation["precision"]), 4),
        "recall_at_threshold": round(float(recommendation["recall"]), 4),
        "f1_at_threshold": round(float(recommendation["f1"]), 4),
        "flagged_invoices": int(recommendation["flagged_invoices"]),
        "true_positives": int(recommendation["tp"]),
        "false_positives": int(recommendation["fp"]),
        "false_negatives": int(recommendation["fn"]),
    }
    (MODEL_DIR / "collection_strategy.json").write_text(json.dumps(summary, indent=2))

    print("FinSight AI collection strategy")
    print(f"Recommended threshold        : {summary['recommended_threshold']:.2f}")
    print(f"Precision                    : {summary['precision_at_threshold']:.2%}")
    print(f"Recall                       : {summary['recall_at_threshold']:.2%}")
    print(f"F1                           : {summary['f1_at_threshold']:.4f}")
    print(f"Invoices flagged             : {summary['flagged_invoices']:,}")
    print(f"True positives               : {summary['true_positives']:,}")
    print(f"False positives              : {summary['false_positives']:,}")
    print(f"False negatives              : {summary['false_negatives']:,}")
    print("\nRisk concentration")
    printable = concentration.copy()
    for col in ["portfolio_fraction", "late_capture_rate", "segment_late_rate", "portfolio_value_share"]:
        printable[col] = printable[col].map(lambda x: f"{x:.2%}")
    printable["lift_vs_average"] = printable["lift_vs_average"].map(lambda x: f"{x:.2f}x")
    printable["invoice_value_reviewed"] = printable["invoice_value_reviewed"].map(lambda x: f"${x:,.0f}")
    print(printable.to_string(index=False))
    print("\nSaved threshold analysis     : data/processed/late_payment_threshold_analysis.csv")
    print("Saved concentration analysis : data/processed/late_payment_risk_concentration.csv")


if __name__ == "__main__":
    main()
