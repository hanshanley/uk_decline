"""CLI: fetch ORR rail performance, write the tidy CSV, and render the London charts.

Usage:
    python -m rail_data                                  # fetch + CSV + charts
    python -m rail_data --from-csv data/rail_performance.csv   # charts only (no fetch)
"""

from __future__ import annotations

import argparse
import csv
import pathlib

from . import charts, orr

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "rail_performance.csv"
DEFAULT_CHARTS = ROOT / "outputs" / "rail"
_FIELDS = ["region", "period", "date", "year", "quarter", "metric", "value", "unit", "source"]


def _write_csv(rows: list[dict], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="London rail performance (ORR PPM & CaSL).")
    p.add_argument("--csv", default=str(DEFAULT_CSV), help="Tidy CSV output path.")
    p.add_argument("--charts-dir", default=str(DEFAULT_CHARTS), help="Chart output dir.")
    p.add_argument("--from-csv", metavar="PATH",
                   help="Skip fetching; build charts from an existing tidy CSV.")
    args = p.parse_args(argv)

    if args.from_csv:
        source = args.from_csv
        print(f"[rail_data] using existing CSV: {source}")
    else:
        rows = orr.build_rows()
        _write_csv(rows, pathlib.Path(args.csv))
        print(f"[rail_data] wrote {len(rows)} rows -> {args.csv}")
        source = args.csv

    written = charts.make_charts(source, args.charts_dir)
    for path in written:
        print(f"[rail_data] chart -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
