import argparse
from pathlib import Path

from config import GenerationConfig
from generate_data import generate_all, save_all
from validate_data import load_tables, validate
from build_curated import build_curated, save_outputs as save_curated_outputs
from build_analytics import load_processed, build_analytics, save_outputs as save_analytics_outputs


def parse_args():
    parser = argparse.ArgumentParser(description="Run the FinSight AI end-to-end local analytics pipeline")
    parser.add_argument("--customers", type=int, default=5_000)
    parser.add_argument("--invoices", type=int, default=50_000)
    parser.add_argument("--expenses", type=int, default=30_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--processed-dir", default="data/processed")
    return parser.parse_args()


def main():
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    processed_dir = Path(args.processed_dir)
    cfg = GenerationConfig(
        seed=args.seed,
        n_customers=args.customers,
        n_invoices=args.invoices,
        n_expenses=args.expenses,
        output_dir=raw_dir,
    )

    print("[1/4] Generating synthetic financial data...")
    save_all(generate_all(cfg), raw_dir)

    print("\n[2/4] Running data-quality checks...")
    raw_tables = load_tables(raw_dir)
    report = validate(raw_tables)
    for key, value in report.items():
        print(f"{key:32s}: {value:,}")

    print("\n[3/4] Building curated reconciliation layer...")
    curated_outputs, curation_summary = build_curated(raw_tables)
    save_curated_outputs(curated_outputs, curation_summary, processed_dir)
    for key, value in curation_summary.items():
        if isinstance(value, float):
            print(f"{key:32s}: {value:,.2f}")
        else:
            print(f"{key:32s}: {value:,}")

    print("\n[4/4] Building financial analytics layer...")
    processed_tables = load_processed(processed_dir)
    analytics_outputs, kpis = build_analytics(processed_tables)
    save_analytics_outputs(analytics_outputs, kpis, processed_dir)
    for key, value in kpis.items():
        if isinstance(value, float):
            if key.endswith("_ratio") or key.endswith("_share") or key.endswith("_rate"):
                print(f"{key:32s}: {value:.2%}")
            else:
                print(f"{key:32s}: {value:,.2f}")
        else:
            print(f"{key:32s}: {value}")

    print("\nAR aging")
    print(analytics_outputs["ar_aging_summary"].to_string(index=False))
    print("\nFinSight AI local analytics pipeline complete.")
    print(f"Raw files:       {raw_dir}")
    print(f"Processed files: {processed_dir}")


if __name__ == "__main__":
    main()
