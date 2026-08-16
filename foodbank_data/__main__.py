"""Build the Trussell food-bank parcel dataset, charts, and summary.

Usage:
    python -m foodbank_data
    python -m foodbank_data --refresh
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import charts, fetch, history, parse, summary
from .sources import (
    CALENDAR_SOURCE,
    DATA_DIR,
    FISCAL_ARCHIVE,
    FISCAL_SLIDES_SOURCE,
    MIDYEAR_SOURCE,
    OUTPUT_DIR,
    RAW_DIR,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="foodbank_data",
        description="Reproduce the Trussell food-bank parcel analysis.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="redownload both official Trussell XLSX workbooks",
    )
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--outputs-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    if args.refresh:
        for path in fetch.refresh(args.raw_dir):
            print(f"[foodbank_data] downloaded -> {path}")
    else:
        fetch.ensure_sources(args.raw_dir)

    annual = parse.parse_calendar_years(CALENDAR_SOURCE.path(args.raw_dir))
    midyear = parse.parse_midyear(MIDYEAR_SOURCE.path(args.raw_dir))
    fiscal = history.build_fiscal_history(
        FISCAL_ARCHIVE,
        FISCAL_SLIDES_SOURCE.path(args.raw_dir),
    )

    args.data_dir.mkdir(parents=True, exist_ok=True)
    annual_csv = args.data_dir / "food_bank_calendar_year.csv"
    midyear_csv = args.data_dir / "food_bank_midyear.csv"
    fiscal_csv = args.data_dir / "food_bank_fiscal_year.csv"
    annual.to_csv(annual_csv, index=False)
    midyear.to_csv(midyear_csv, index=False)
    fiscal.to_csv(fiscal_csv, index=False)
    print(f"[foodbank_data] wrote {len(annual)} rows -> {annual_csv}")
    print(f"[foodbank_data] wrote {len(midyear)} rows -> {midyear_csv}")
    print(f"[foodbank_data] wrote {len(fiscal)} rows -> {fiscal_csv}")

    for path in charts.make_charts(annual, midyear, fiscal, args.outputs_dir):
        print(f"[foodbank_data] chart -> {path}")
    summary_path = summary.build_summary(
        annual,
        midyear,
        fiscal,
        args.outputs_dir / "summary.md",
    )
    print(f"[foodbank_data] summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
