"""CLI: fetch ONS regional GDP, write the tidy CSV, and render the London charts.

Usage:
    python -m london_data                              # fetch + CSV + charts
    python -m london_data --from-csv data/london_gdp.csv   # charts only (no fetch)
"""

from __future__ import annotations

import argparse
import csv
import pathlib

from . import charts, ons

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "london_gdp.csv"
DEFAULT_CHARTS = ROOT / "outputs" / "london"
_FIELDS = ["region", "year", "metric", "value", "unit", "source"]


def _write_csv(rows: list[dict], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _require_year(years: list[int], required: int) -> None:
    latest = max(years) if years else None
    if latest is None or latest < required:
        release = ons.next_release(required)
        detail = (f"; scheduled release: {release['release_date']}"
                  if release and release.get("release_date") else "")
        raise RuntimeError(
            f"official London GDP-share data ends at {latest}; required {required}{detail}"
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="London's concentration of UK GDP (ONS).")
    p.add_argument("--csv", default=str(DEFAULT_CSV), help="Tidy CSV output path.")
    p.add_argument("--charts-dir", default=str(DEFAULT_CHARTS), help="Chart output dir.")
    p.add_argument("--from-csv", metavar="PATH",
                   help="Skip fetching; build charts from an existing tidy CSV.")
    p.add_argument("--status", action="store_true",
                   help="Report the latest official ONS edition and next scheduled release.")
    p.add_argument("--require-year", type=int, metavar="YEAR",
                   help="Fail unless the fetched official data reaches YEAR.")
    args = p.parse_args(argv)

    if args.status:
        target = args.require_year or 2024
        status = ons.availability_status(target)
        latest = status["latest_published_year"]
        print(f"[london_data] latest official ONS regional-GDP year: {latest}")
        if status["available"]:
            print(f"[london_data] requested year {target} is available")
        elif status["next_release"]:
            release = status["next_release"]
            print(f"[london_data] {target} is not published; scheduled release: "
                  f"{release['release_date']} ({release['title']})")
        else:
            print(f"[london_data] {target} is not published; no release date found")
        if args.from_csv is None and args.require_year is None:
            return 0

    if args.from_csv:
        source = args.from_csv
        print(f"[london_data] using existing CSV: {source}")
        if args.require_year is not None:
            with open(source, newline="") as f:
                years = [int(r["year"]) for r in csv.DictReader(f)
                         if r["metric"] == "share_of_uk_gdp_pct"]
            _require_year(years, args.require_year)
    else:
        rows = ons.build_rows()
        if args.require_year is not None:
            years = [int(r["year"]) for r in rows
                     if r["metric"] == "share_of_uk_gdp_pct"]
            _require_year(years, args.require_year)
        _write_csv(rows, pathlib.Path(args.csv))
        print(f"[london_data] wrote {len(rows)} rows -> {args.csv}")
        source = args.csv

    written = charts.make_charts(source, args.charts_dir)
    for path in written:
        print(f"[london_data] chart -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
