"""CLI: fetch UK immigration data, write CSVs, and render summary charts.

Usage:
    python -m uk_migration.run                 # fetch all, combine, render charts
    python -m uk_migration.run --no-charts     # data only
    python -m uk_migration.run --only visas asylum
"""

from __future__ import annotations

import argparse
import shutil

from . import charts, combine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UK immigration over time: fetch + chart.")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=list(combine.SOURCES),
        help="restrict to specific sources (default: all)",
    )
    parser.add_argument("--no-charts", action="store_true", help="skip chart rendering")
    args = parser.parse_args(argv)

    print(f"Fetching sources: {args.only or 'all'} ...")
    rows = combine.run(args.only)
    print(f"Wrote {len(rows)} rows -> {combine.COMBINED_CSV}")

    if not args.no_charts:
        paths = charts.render_all()
        # Copy the combined data next to the charts so the outputs/ showcase is
        # self-contained and committable (data/processed/*.csv is git-ignored).
        charts.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        data_copy = charts.FIGURES_DIR / combine.COMBINED_CSV.name
        shutil.copyfile(combine.COMBINED_CSV, data_copy)
        print("Wrote charts + sources + data to outputs:")
        for path in [*paths, data_copy]:
            print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
