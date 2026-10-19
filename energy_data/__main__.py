"""Fetch official energy prices or rebuild the figure from the saved annual data."""

import argparse
from pathlib import Path

import pandas as pd

from . import charts, sources

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "data/household_energy_prices.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=SAVED)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/energy")
    args = parser.parse_args(argv)
    if args.from_csv:
        frame = sources.validate(pd.read_csv(args.from_csv))
    else:
        previous = pd.read_csv(args.csv) if args.csv.exists() else None
        frame = sources.fetch(previous=previous)
    outputs = charts.make_charts(frame, args.out)
    if not args.from_csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False, date_format="%Y-%m-%d")
    print(f"[energy_data] {len(frame)} published annual energy prices -> {outputs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
