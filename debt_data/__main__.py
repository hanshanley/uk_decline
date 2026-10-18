"""Refresh public debt and government-bond yields, or rebuild from saved CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import charts, interest, sources

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data/debt_borrowing_long.csv"
DEFAULT_DAILY_CSV = ROOT / "data/uk_gilt_yields_daily.csv"
DEFAULT_INTEREST_CSV = ROOT / "data/debt_interest_budget.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--daily-csv", type=Path, default=DEFAULT_DAILY_CSV)
    parser.add_argument("--interest-csv", type=Path, default=DEFAULT_INTEREST_CSV)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/debt")
    args = parser.parse_args(argv)
    if args.from_csv:
        frame = sources.validate(pd.read_csv(args.from_csv))
        daily = sources.validate_daily(pd.read_csv(args.daily_csv))
        budget = interest.validate(pd.read_csv(args.interest_csv))
        print(f"[debt_data] using existing CSV: {args.from_csv}")
    else:
        previous = pd.read_csv(args.csv) if args.csv.exists() else None
        frame = sources.validate(sources.fetch(), previous=previous)
        previous_budget = pd.read_csv(args.interest_csv) if args.interest_csv.exists() else None
        budget = interest.validate(interest.fetch(), previous=previous_budget)
        previous_daily = pd.read_csv(args.daily_csv) if args.daily_csv.exists() else None
        daily = sources.validate_daily(
            sources.fetch_daily(), previous=previous_daily, require_recent=True,
        )
    outputs = charts.make_charts(frame, args.out, daily=daily, budget=budget)
    if not args.from_csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False, date_format="%Y-%m-%d")
        print(f"[debt_data] wrote {len(frame)} observations -> {args.csv}")
        args.daily_csv.parent.mkdir(parents=True, exist_ok=True)
        daily.to_csv(args.daily_csv, index=False, date_format="%Y-%m-%d")
        print(f"[debt_data] wrote {len(daily)} daily observations -> {args.daily_csv}")
        args.interest_csv.parent.mkdir(parents=True, exist_ok=True)
        budget.to_csv(args.interest_csv, index=False)
        print(f"[debt_data] wrote {len(budget)} annual interest shares -> {args.interest_csv}")
    for path in outputs:
        print(f"[debt_data] chart -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
