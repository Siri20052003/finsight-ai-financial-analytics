from config import DEFAULT_CONFIG
from generate_data import generate_all, save_all
from validate_data import load_tables, validate


def main():
    print("[1/2] Generating synthetic financial data...")
    save_all(generate_all(DEFAULT_CONFIG), DEFAULT_CONFIG.output_dir)
    print("\n[2/2] Running data-quality checks...")
    report = validate(load_tables(DEFAULT_CONFIG.output_dir))
    for key, value in report.items():
        print(f"{key:32s}: {value:,}")
    print("\nFoundation pipeline complete.")


if __name__ == "__main__":
    main()
