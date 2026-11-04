"""Generate the demo CSV datasets used to try DataLens.

The output is deterministic: the same seed and row counts always produce the
same files, byte for byte. Every value is synthetic. Nothing is read from the
network or from real records.

Each dataset has deliberate quality problems, so every DataLens feature has
something to show: missing values, exact duplicate rows, inconsistent text
(case and whitespace), mixed boolean spellings, and a few out-of-range values.
Some relationships are built in on purpose (for example, pressure rises with
temperature), so the correlation views have real signal to report.

Usage (from the repository root, with the backend virtualenv active):

    python sample_data/generate_sample_data.py
    python sample_data/generate_sample_data.py --manufacturing-rows 50000 --output-dir C:\\tmp\\demo

Requires only pandas and numpy, which the backend already depends on.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_SEED = 42
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent


def make_manufacturing(rows: int, rng: np.random.Generator) -> pd.DataFrame:
    """Production test records: sensor readings, a result, and an error code."""
    line = rng.choice(["Line A", "Line B", "Line C"], size=rows, p=[0.4, 0.35, 0.25])
    offset = np.select([line == "Line A", line == "Line B"], [0.0, 1.5], default=-1.0)

    start = pd.Timestamp("2025-01-01 06:00:00")
    minutes = np.cumsum(rng.integers(8, 25, size=rows))
    timestamps = start + pd.to_timedelta(minutes, unit="min")

    temperature = rng.normal(70.0, 4.0, size=rows) + offset
    pressure = 30.0 + 0.25 * (temperature - 70.0) + rng.normal(0.0, 0.6, size=rows)
    test_duration = np.round(
        rng.normal(120.0, 9.0, size=rows) + 0.9 * (temperature - 70.0), 1
    ).clip(min=20.0)

    # Failures become more likely as temperature and pressure drift high.
    risk = 1 / (1 + np.exp(-(temperature - 76.0) / 1.5)) * 0.6 + 0.02
    failed = rng.random(rows) < risk
    retest = (~failed) & (rng.random(rows) < 0.03)
    result = np.where(failed, "FAIL", np.where(retest, "RETEST", "PASS")).astype(object)
    error_codes = np.array(["E101", "E204", "E317", "E450"], dtype=object)
    error_code = np.where(
        failed | retest, error_codes[rng.integers(0, len(error_codes), size=rows)], None
    )

    frame = pd.DataFrame(
        {
            "serial_number": [f"SN-{i:06d}" for i in range(1, rows + 1)],
            "production_line": line,
            "timestamp": timestamps.strftime("%Y-%m-%d %H:%M:%S"),
            "temperature": np.round(temperature, 1),
            "pressure": np.round(pressure, 2),
            "test_duration": test_duration,
            "result": result,
            "error_code": error_code,
        }
    )

    # Imperfections a real export would have.
    _blank(frame, "temperature", rng, 0.03)
    _blank(frame, "pressure", rng, 0.02)
    _blank(frame, "test_duration", rng, 0.01)
    lowercase = rng.random(rows) < 0.02
    frame.loc[lowercase, "result"] = frame.loc[lowercase, "result"].str.lower()
    padded = rng.random(rows) < 0.01
    frame.loc[padded, "result"] = " " + frame.loc[padded, "result"]
    return _add_duplicates(frame, rng, 0.015)


def make_employees(rows: int, rng: np.random.Generator) -> pd.DataFrame:
    """Fictional staff records with typical HR-style quality problems."""
    department = rng.choice(
        ["Engineering", "Sales", "Marketing", "Finance", "HR", "Operations"],
        size=rows,
        p=[0.3, 0.2, 0.12, 0.12, 0.08, 0.18],
    )
    base_salary = {
        "Engineering": 105_000,
        "Sales": 78_000,
        "Marketing": 74_000,
        "Finance": 82_000,
        "HR": 67_000,
        "Operations": 62_000,
    }
    salary = np.array([base_salary[d] for d in department], dtype=float)
    salary = np.round(salary * rng.lognormal(0.0, 0.14, size=rows), -3)

    hire_start = pd.Timestamp("2012-01-01")
    hire_days = rng.integers(0, 13 * 365, size=rows)
    hire_date = (hire_start + pd.to_timedelta(hire_days, unit="D")).strftime("%Y-%m-%d")

    frame = pd.DataFrame(
        {
            "employee_id": [f"EMP-{1000 + i}" for i in range(1, rows + 1)],
            "department": department,
            "age": rng.integers(22, 64, size=rows),
            "salary": salary,
            "hire_date": hire_date,
            "location": rng.choice(
                ["New York", "Chicago", "Austin", "Seattle", "Remote"], size=rows
            ),
            "active": np.where(rng.random(rows) < 0.93, "Yes", "No"),
        }
    )

    lowercase = rng.random(rows) < 0.03
    frame.loc[lowercase, "department"] = frame.loc[lowercase, "department"].str.lower()
    _blank(frame, "salary", rng, 0.05)
    _blank(frame, "hire_date", rng, 0.02)
    padded = rng.random(rows) < 0.02
    frame.loc[padded, "location"] = " " + frame.loc[padded, "location"]
    abbreviated = rng.random(rows) < 0.03
    frame.loc[abbreviated, "active"] = frame.loc[abbreviated, "active"].map({"Yes": "Y", "No": "N"})

    # Two impossible ages, the kind a typo or a bad import produces.
    frame.loc[rng.choice(rows, size=2, replace=False), "age"] = [212, 7]
    return _add_duplicates(frame, rng, 0.005)


def make_sales(rows: int, rng: np.random.Generator) -> pd.DataFrame:
    """Order lines with a date, region, product, quantity, and price."""
    catalogue = {
        "Electronics": [("Monitor 24in", 189.0), ("Wireless Keyboard", 49.0), ("USB Hub", 29.0)],
        "Office Supplies": [("Notebook Pack", 12.0), ("Desk Organizer", 24.0), ("Stapler", 9.5)],
        "Furniture": [("Ergonomic Chair", 249.0), ("Standing Desk", 399.0), ("Bookshelf", 129.0)],
        "Apparel": [("Staff Hoodie", 44.0), ("Work Jacket", 79.0), ("Cap", 18.0)],
    }
    categories = rng.choice(list(catalogue), size=rows, p=[0.35, 0.3, 0.15, 0.2])
    products = []
    prices = np.empty(rows)
    for i, category in enumerate(categories):
        name, base = catalogue[category][rng.integers(0, 3)]
        products.append(name)
        prices[i] = base

    order_start = pd.Timestamp("2024-01-01")
    order_days = np.sort(rng.integers(0, 545, size=rows))
    quantity = rng.poisson(3.0, size=rows) + 1
    unit_price = np.round(prices * rng.uniform(0.95, 1.05, size=rows), 2)
    revenue = np.round(quantity * unit_price, 2)

    frame = pd.DataFrame(
        {
            "order_id": [f"ORD-{100_000 + i}" for i in range(1, rows + 1)],
            "order_date": (order_start + pd.to_timedelta(order_days, unit="D")).strftime("%Y-%m-%d"),
            "region": rng.choice(["North", "South", "East", "West"], size=rows, p=[0.3, 0.25, 0.25, 0.2]),
            "product_category": categories,
            "product": products,
            "customer_type": rng.choice(
                ["Consumer", "Small Business", "Enterprise"], size=rows, p=[0.5, 0.35, 0.15]
            ),
            "salesperson": [f"S-{n:02d}" for n in rng.integers(1, 13, size=rows)],
            "quantity": quantity,
            "unit_price": unit_price,
            "revenue": revenue,
        }
    )
    _blank(frame, "revenue", rng, 0.02)
    _blank(frame, "unit_price", rng, 0.01)
    _blank(frame, "region", rng, 0.015)
    return _add_duplicates(frame, rng, 0.01)


def _blank(frame: pd.DataFrame, column: str, rng: np.random.Generator, share: float) -> None:
    """Leave `share` of a column's cells empty, as a real export often does."""
    frame.loc[rng.random(len(frame)) < share, column] = None


def _add_duplicates(frame: pd.DataFrame, rng: np.random.Generator, share: float) -> pd.DataFrame:
    """Append exact copies of some rows at the end, like a batch exported twice.

    Appending (rather than shuffling) keeps the original rows in time order, so
    the datetime trend charts still show the intended pattern.
    """
    copies = frame.sample(n=max(1, int(len(frame) * share)), random_state=int(rng.integers(0, 2**31)))
    return pd.concat([frame, copies], ignore_index=True)


def write_all(output_dir: Path, seed: int, manufacturing: int, employees: int, sales: int) -> dict[str, int]:
    """Write the three datasets and return the row count written for each."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    datasets = {
        "manufacturing_data.csv": make_manufacturing(manufacturing, rng),
        "employee_data.csv": make_employees(employees, rng),
        "sales_data.csv": make_sales(sales, rng),
    }
    written = {}
    for filename, frame in datasets.items():
        frame.to_csv(output_dir / filename, index=False, lineterminator="\n")
        written[filename] = len(frame)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic DataLens demo datasets.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--manufacturing-rows", type=int, default=1500)
    parser.add_argument("--employee-rows", type=int, default=400)
    parser.add_argument("--sales-rows", type=int, default=2000)
    args = parser.parse_args()

    for name, rows in {
        "--manufacturing-rows": args.manufacturing_rows,
        "--employee-rows": args.employee_rows,
        "--sales-rows": args.sales_rows,
    }.items():
        if rows < 10:
            parser.error(f"{name} must be at least 10")

    written = write_all(
        args.output_dir, args.seed, args.manufacturing_rows, args.employee_rows, args.sales_rows
    )
    for filename, rows in written.items():
        print(f"{filename}: {rows:,} rows (includes the appended duplicate rows)")


if __name__ == "__main__":
    main()
