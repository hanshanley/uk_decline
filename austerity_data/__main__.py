"""CLI for the UK austerity spending and investment analysis."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

from . import charts, summary, treasury

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "austerity_spending.csv"


def _write_rows(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=treasury.ROW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chart UK austerity-era public spending and investment."
    )
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Tidy CSV output path.")
    parser.add_argument(
        "--from-csv",
        metavar="PATH",
        help="Skip the network fetch and render from an existing tidy CSV.",
    )
    parser.add_argument(
        "--output",
        default=str(charts.DEFAULT_OUTPUT),
        help="Chart output path.",
    )
    parser.add_argument(
        "--summary",
        default=str(summary.DEFAULT_SUMMARY),
        help="Markdown summary output path.",
    )
    args = parser.parse_args(argv)

    if args.from_csv:
        frame = pd.read_csv(args.from_csv)
        print(f"[austerity_data] using existing CSV: {args.from_csv}")
    else:
        rows = treasury.build_rows()
        _write_rows(rows, Path(args.csv))
        frame = pd.DataFrame(rows)
        print(f"[austerity_data] wrote {len(rows)} rows -> {args.csv}")

    chart_path = charts.make_chart(frame, args.output)
    summary_path = summary.build_summary(frame, args.summary)
    print(f"[austerity_data] chart -> {chart_path}")
    print(f"[austerity_data] summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

