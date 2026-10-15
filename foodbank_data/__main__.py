"""Build the Trussell food-bank parcel dataset, charts, and summary.

Usage:
    python -m foodbank_data
    python -m foodbank_data --refresh
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path

import pandas as pd
from . import charts, fetch, history, parse, summary
from .sources import (
    CALENDAR_SOURCE,
    ACCESSED_DATE,
    DATA_DIR,
    FISCAL_ARCHIVE,
    FISCAL_SLIDES_SOURCE,
    MIDYEAR_SOURCE,
    OUTPUT_DIR,
    RAW_DIR,
    Source,
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
    manifest = args.outputs_dir / "calendar_source.json"
    saved = json.loads(manifest.read_text()) if manifest.exists() else {}
    calendar_source = Source(**saved["source"]) if saved else CALENDAR_SOURCE
    accessed_date = saved.get("accessed_date", ACCESSED_DATE)

    if args.refresh:
        calendar_source = fetch.discover_calendar_source()
        accessed_date = date.today().isoformat()
        for path in fetch.refresh(args.raw_dir, calendar_source=calendar_source):
            print(f"[foodbank_data] downloaded -> {path}")
    else:
        fetch.ensure_sources(args.raw_dir, calendar_source=calendar_source)

    annual = parse.parse_calendar_years(
        calendar_source.path(args.raw_dir), source_url=calendar_source.url,
        accessed_date=accessed_date,
    )
    previous_csv = args.data_dir / "food_bank_calendar_year.csv"
    if previous_csv.exists():
        previous = parse.validate(pd.read_csv(previous_csv))
        if not set(previous["year"]).issubset(annual["year"]):
            raise ValueError("Trussell refresh lost previously published calendar-year coverage")
    midyear = parse.parse_midyear(MIDYEAR_SOURCE.path(args.raw_dir), accessed_date=accessed_date)
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
    manifest.write_text(json.dumps({
        "source": asdict(calendar_source), "accessed_date": accessed_date,
    }, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
