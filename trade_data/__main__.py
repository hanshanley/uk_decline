"""CLI for trade as a share of GDP."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

from . import charts, worldbank

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "trade_share_gdp.csv"


def _write(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=worldbank.ROW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trade as a share of GDP.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--output", type=Path, default=charts.DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if args.from_csv:
        frame = pd.read_csv(args.from_csv)
        print(f"[trade_data] using existing CSV: {args.from_csv}")
    else:
        rows = worldbank.fetch()
        _write(rows, args.csv)
        frame = pd.DataFrame(rows)
        print(f"[trade_data] wrote {len(rows)} rows -> {args.csv}")

    output = charts.make_chart(frame, args.output)
    print(f"[trade_data] chart -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

