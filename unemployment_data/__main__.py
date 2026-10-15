"""Refresh UK unemployment rates, or rebuild the charts from saved official data."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import charts, references, sources

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data/unemployment_long.csv"
DEFAULT_REFERENCES = ROOT / "data/unemployment_references.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--references", type=Path, default=DEFAULT_REFERENCES)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/unemployment")
    args = parser.parse_args(argv)
    if args.from_csv:
        frame = sources.validate(pd.read_csv(args.from_csv))
        reference_frame = references.validate(pd.read_csv(args.references))
        print(f"[unemployment_data] using existing CSV: {args.from_csv}")
    else:
        previous = pd.read_csv(args.csv) if args.csv.exists() else None
        frame = sources.validate(sources.fetch(), previous=previous)
        previous_references = pd.read_csv(args.references) if args.references.exists() else None
        reference_frame = references.validate(references.fetch(), previous=previous_references)
    outputs = charts.make_charts(frame, args.out, reference_frame)
    if not args.from_csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False, date_format="%Y-%m-%d")
        args.references.parent.mkdir(parents=True, exist_ok=True)
        reference_frame.to_csv(args.references, index=False, date_format="%Y-%m-%d")
        print(f"[unemployment_data] wrote {len(frame)} observations -> {args.csv}")
        print(f"[unemployment_data] wrote {len(reference_frame)} reference observations -> {args.references}")
    for path in outputs:
        print(f"[unemployment_data] chart -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
