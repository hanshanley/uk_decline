"""CLI for the sterling exchange-rate analysis."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import charts, ecb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "sterling_exchange_rates.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chart how much foreign currency one pound buys."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--output", type=Path, default=charts.DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if args.from_csv:
        frame = pd.read_csv(args.from_csv)
        print(f"[sterling_data] using existing CSV: {args.from_csv}")
    else:
        frame = ecb.build_annual()
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False)
        print(f"[sterling_data] wrote {len(frame)} rows -> {args.csv}")

    output = charts.make_chart(frame, args.output)
    print(f"[sterling_data] chart -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

