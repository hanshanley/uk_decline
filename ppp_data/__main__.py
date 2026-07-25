"""CLI entrypoint: fetch the PPP data, validate it, write CSVs, and render the figures.

Usage::

    python -m ppp_data                          # fetch -> validate -> combine -> charts
    python -m ppp_data --start 1990 --end 2024
    python -m ppp_data --from-csv               # re-chart from data/ppp_long.csv
    python -m ppp_data --no-charts              # data and validation only

Validation runs before anything is written. If a check fails at ``error`` level the run
stops with a non-zero exit code rather than producing figures from data it cannot vouch
for; pass ``--skip-validation`` only when deliberately inspecting a broken fetch.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys

from . import charts, combine, maddison, paths, validate, worldbank


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="ppp_data", description=__doc__)
    p.add_argument("--start", type=int, default=worldbank.PPP_FIRST_YEAR,
                   help="first year for the World Bank PPP series (default: 1990, when it begins)")
    p.add_argument("--end", type=int, default=_dt.date.today().year,
                   help="last year (inclusive)")
    p.add_argument("--maddison-start", type=int, default=1970,
                   help="first year for the long-run Maddison chart")
    p.add_argument("--from-csv", action="store_true",
                   help="skip fetching and re-chart from the existing long CSV")
    p.add_argument("--no-charts", dest="charts", action="store_false", help="skip charts")
    p.add_argument("--skip-validation", dest="validate", action="store_false",
                   help="render even if the data fails its sanity checks (not recommended)")
    p.set_defaults(charts=True, validate=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start > args.end:
        print("error: --start must be <= --end", file=sys.stderr)
        return 2

    if args.from_csv:
        if not paths.LONG_CSV.exists():
            print(f"error: {paths.LONG_CSV} does not exist; run without --from-csv first",
                  file=sys.stderr)
            return 2
        rows = combine.load_long()
        print(f"[ppp_data] loaded {len(rows)} rows from {paths.LONG_CSV}")
    else:
        print(f"[ppp_data] fetching World Bank series {args.start}-{args.end} ...")
        rows = worldbank.fetch(args.start, args.end)
        print(f"[ppp_data] fetching Maddison long-run series {args.maddison_start}-{args.end} ...")
        rows += maddison.fetch(args.maddison_start, args.end)
        print(f"[ppp_data] {len(rows)} rows")

    if args.validate:
        checks = validate.run_all(rows)
        print("[ppp_data] validation:")
        print(validate.report(checks))
        failed = validate.failures(checks)
        if failed:
            print(f"[ppp_data] {len(failed)} check(s) failed; refusing to publish figures "
                  "from data that does not pass its sanity checks.", file=sys.stderr)
            return 1

    if not args.from_csv:
        written = combine.write_all(rows, extra_manifest={
            "requested_start": args.start,
            "requested_end": args.end,
            "validation": [c._asdict() for c in validate.run_all(rows)],
        })
        for name, path in written.items():
            print(f"[ppp_data] wrote {name:9s} {path}")

    if args.charts:
        figures = charts.make_charts(rows)
        print(f"[ppp_data] wrote {len(figures)} figures to {paths.CHART_DIR}/:")
        for path in figures:
            print(f"    {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
