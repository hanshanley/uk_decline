"""CLI: fetch UK crime statistics, write tidy CSVs, and render the house-style charts.

Usage:
    python -m crime_data                       # fetch both sources + CSVs + charts
    python -m crime_data --sources csew        # only the CSEW long-run trend
    python -m crime_data --from-csv            # rebuild charts from existing CSVs (no fetch)
"""

from __future__ import annotations

import argparse
import csv
import pathlib

from . import charts, csew, homicide

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CSEW_CSV = DATA / "crime_csew_long.csv"
HOMICIDE_CSV = DATA / "crime_homicide_long.csv"
CHARTS_DIR = ROOT / "outputs" / "crime"

_CSEW_FIELDS = ["region", "offence_group", "level", "period", "date", "year",
                "metric", "value", "unit", "source"]
_HOMICIDE_FIELDS = ["iso3", "country", "year", "metric", "value", "unit", "source"]


def _write_csv(rows: list[dict], path: pathlib.Path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="UK crime statistics (CSEW trend + homicide).")
    p.add_argument("--sources", nargs="+", choices=["csew", "homicide"],
                   default=["csew", "homicide"], help="Which sources to fetch.")
    p.add_argument("--from-csv", action="store_true",
                   help="Skip fetching; build charts from existing CSVs.")
    p.add_argument("--charts-dir", default=str(CHARTS_DIR), help="Chart output directory.")
    args = p.parse_args(argv)

    csew_src = homicide_src = None

    if args.from_csv:
        if CSEW_CSV.exists():
            csew_src = str(CSEW_CSV)
        if HOMICIDE_CSV.exists():
            homicide_src = str(HOMICIDE_CSV)
        print(f"[crime_data] using existing CSVs in {DATA}")
    else:
        if "csew" in args.sources:
            rows = csew.build_rows()
            _write_csv(rows, CSEW_CSV, _CSEW_FIELDS)
            print(f"[crime_data] wrote {len(rows)} CSEW rows -> {CSEW_CSV}")
            csew_src = str(CSEW_CSV)
        if "homicide" in args.sources:
            rows = homicide.build_rows()
            _write_csv(rows, HOMICIDE_CSV, _HOMICIDE_FIELDS)
            print(f"[crime_data] wrote {len(rows)} homicide rows -> {HOMICIDE_CSV}")
            homicide_src = str(HOMICIDE_CSV)

    written = charts.make_charts(csew_src, homicide_src, args.charts_dir)
    for path in written:
        print(f"[crime_data] chart -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
