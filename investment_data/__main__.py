"""Refresh five investment/funding measures, or rebuild offline from their saved CSV."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import charts, sources

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data/investment_funding_long.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/investment")
    args = parser.parse_args(argv)
    if args.from_csv:
        frame = sources.validate(pd.read_csv(args.from_csv))
        print(f"[investment_data] using saved observations: {args.from_csv}")
    else:
        previous = pd.read_csv(args.csv) if args.csv.exists() else None
        frame = sources.validate(sources.fetch(), previous=previous)
    paths = charts.make_charts(frame, args.out)
    if not args.from_csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False)
        print(f"[investment_data] wrote {len(frame)} source-backed observations -> {args.csv}")
    for path in paths:
        print(f"[investment_data] chart -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
