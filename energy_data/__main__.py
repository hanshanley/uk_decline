"""Fetch official energy prices or rebuild the figure from the saved annual data."""

import argparse
from pathlib import Path

import pandas as pd

from . import charts, sources

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "data/household_energy_prices.csv"
INDUSTRIAL_SAVED = ROOT / "data/industrial_electricity_prices.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=SAVED)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--industrial-csv", type=Path, default=INDUSTRIAL_SAVED)
    parser.add_argument("--industrial-from-csv", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/energy")
    args = parser.parse_args(argv)
    if args.industrial_from_csv and not args.from_csv:
        parser.error("--industrial-from-csv requires --from-csv")
    industry = None
    if args.from_csv:
        frame = sources.validate(pd.read_csv(args.from_csv))
        if args.industrial_from_csv:
            industry = sources.validate(pd.read_csv(args.industrial_from_csv), industrial=True)
    else:
        previous = pd.read_csv(args.csv) if args.csv.exists() else None
        frame = sources.fetch(previous=previous)
        previous_industry = pd.read_csv(args.industrial_csv) if args.industrial_csv.exists() else None
        industry = sources.fetch(previous=previous_industry, industrial=True)
    outputs = charts.make_charts(frame, args.out)
    if industry is not None:
        outputs.extend(charts.make_charts(industry, args.out, industrial=True))
    if not args.from_csv:
        if industry is None:
            raise RuntimeError("Industrial electricity inputs were not fetched")
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False, date_format="%Y-%m-%d")
        args.industrial_csv.parent.mkdir(parents=True, exist_ok=True)
        industry.to_csv(args.industrial_csv, index=False, date_format="%Y-%m-%d")
    total = len(frame) + (len(industry) if industry is not None else 0)
    print(f"[energy_data] {total} published annual energy prices -> {outputs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
