from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GenerationConfig:
    seed: int = 42
    n_customers: int = 5_000
    n_invoices: int = 50_000
    n_expenses: int = 30_000
    start_date: str = "2024-01-01"
    end_date: str = "2025-12-31"
    output_dir: Path = Path("data/raw")


DEFAULT_CONFIG = GenerationConfig()
