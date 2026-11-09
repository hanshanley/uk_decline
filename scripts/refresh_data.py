"""Refresh supported sources and figures; never turn a partial fetch into a publication."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time

if __package__:
    from .chart_data import validate_refresh
else:
    from chart_data import validate_refresh

ROOT = Path(__file__).resolve().parents[1]
STEPS = {
    "gdp-income": (
        ("-m", "europe_data.fetch_data"),
        ("-m", "europe_data.plot_uk_decline"),
        ("-m", "europe_data.recent_income"),
    ),
    "markets": (
        ("-m", "markets_data"),
        ("-m", "markets_data.lse_factsheets", "--latest"),
    ),
    "sterling": (("-m", "sterling_data"),),
    "trade": (("-m", "trade_data"),),
    "ageing": (("-m", "age_data.fetch_age"),),
    "trust": (("-m", "trust_data.fetch_trust", "--charts", "--summary"),),
    "tax": (("-m", "tax.fetch_tax"),),
    "nhs": (("-m", "nhs_data", "--start", "2007"),),
    "rail": (("-m", "rail_data"),),
    "london": (("-m", "london_data"),),
    "crime": (("-m", "crime_data"),),
    "migration": (("-m", "uk_migration.run"),),
    "polling": (("-m", "polling_data"),),
    "public-spending": (("-m", "austerity_data"),),
    "debt-borrowing": (("-m", "debt_data"),),
    "unemployment": (("-m", "unemployment_data"),),
    "energy-costs": (("-m", "energy_data"),),
    "investment-funding": (("-m", "investment_data"),),
    "food-banks": (("-m", "foodbank_data", "--refresh"),),
    "tuition": (
        ("-m", "tuition.cpi"),
        ("-m", "tuition.fetch_collegeboard"),
        ("-m", "tuition.build_dataset"),
        ("-m", "tuition.build_history"),
        ("-m", "tuition.common_year"),
        ("-m", "tuition.analyze"),
        ("-m", "tuition.plot_tuition"),
        ("-m", "tuition.plot_tuition", "--real"),
        ("-m", "tuition.plot_history"),
    ),
    "purchasing-power": (("-m", "ppp_data"), ("-m", "ppp_data.inflation")),
}
FAILURE_NOTICE = re.compile(
    r"^\[[^\]\r\n]+\] WARNING:|\busing (?:manual )?fallback\b",
    re.IGNORECASE | re.MULTILINE,
)
EXPECTED_NHS_OMISSION = re.compile(
    r"\[nhs_data\] WARNING: NIR cancer_62day_pct: "
    r"omitting \d+ months without all five trusts"
)
CURATED_INPUTS = (
    "National tuition schedules and cross-country fee selections",
    "Historical source URLs and manually compiled reference observations",
)


def run(command: tuple[str, ...], root: Path) -> None:
    print(f"[refresh] {sys.executable} {' '.join(command)}", flush=True)
    result = subprocess.run(
        [sys.executable, *command], cwd=root, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=3600,
    )
    print(result.stdout, end="", flush=True)
    result.check_returncode()
    # Incomplete trust aggregates are intentionally excluded; coverage is checked below.
    failure_output = "\n".join(
        line for line in result.stdout.splitlines()
        if not (command[:2] == ("-m", "nhs_data") and EXPECTED_NHS_OMISSION.fullmatch(line))
    )
    if FAILURE_NOTICE.search(failure_output):
        raise RuntimeError(
            f"{' '.join(command)} reported an incomplete source or fallback; refusing publication"
        )


def nhs_coverage(root: Path) -> dict[tuple[str, str], set[str]]:
    """Record the published series so a source cannot silently disappear or regress."""
    path = root / "outputs/nhs/nhs_waiting_times.csv"
    coverage: dict[tuple[str, str], set[str]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["value"] in ("", None):
                continue
            key = row["nation_code"], row["metric"]
            coverage.setdefault(key, set()).add(row["date"])
    if not coverage:
        raise ValueError("Published NHS data contains no observations")
    return coverage


def refresh(
    root: Path = ROOT, only: list[str] | None = None, *,
    check_all: bool = False, report: Path | None = None,
) -> None:
    started_ns = time.time_ns()
    selected = list(STEPS) if only is None else only
    results = {name: {"status": "not_checked"} for name in selected}
    diagnostic = {
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "running", "sources": results,
    }

    def write_report():
        if report is not None:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(diagnostic, indent=2) + "\n")

    write_report()
    try:
        baseline = nhs_coverage(root) if "nhs" in selected else {}
        failures = {}
        for name in selected:
            results[name] = {"status": "running"}
            write_report()
            try:
                for command in STEPS[name]:
                    run(command, root)
                if name == "nhs":
                    current = nhs_coverage(root)
                    regressed = [
                        (key, sorted(dates - current.get(key, set()))[:5])
                        for key, dates in baseline.items()
                        if not dates.issubset(current.get(key, set()))
                    ]
                    if regressed:
                        raise RuntimeError(f"NHS refresh lost published series or date coverage: {regressed}")
            except Exception as error:
                results[name] = {"status": "failure", "error": f"{type(error).__name__}: {error}"}
                failures[name] = error
                print(f"[refresh] FAILED {name}: {error}", flush=True)
                if not check_all:
                    raise
            else:
                results[name] = {"status": "success"}
            finally:
                write_report()
        if failures:
            raise RuntimeError(
                "Incomplete refresh; refusing publication. Failed sources: "
                + "; ".join(f"{name}: {error}" for name, error in failures.items())
            ) from next(iter(failures.values()))
        run(("scorecard.py",), root)
        run(("-m", "scripts.export_page_plots"), root)
        if only is None:
            validate_refresh(root, started_ns)
            status = root / "data/site/refresh.json"
            status.parent.mkdir(parents=True, exist_ok=True)
            status.write_text(json.dumps({
                "last_successful_refresh_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "automated_analyses": selected,
                "curated_inputs": CURATED_INPUTS,
            }, indent=2) + "\n")
    except Exception as error:
        diagnostic.update(status="failure", error=f"{type(error).__name__}: {error}")
        raise
    else:
        diagnostic["status"] = "success"
    finally:
        diagnostic["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        write_report()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only", nargs="+", choices=STEPS,
        help="Refresh selected analyses; a partial run does not advance the full-refresh date.",
    )
    parser.add_argument(
        "--check-all", action="store_true",
        help="Check all independent source groups even after a failure; never publish partial results.",
    )
    parser.add_argument("--report", type=Path, help="Write machine-readable source-check diagnostics.")
    args = parser.parse_args()
    refresh(only=args.only, check_all=args.check_all, report=args.report)


if __name__ == "__main__":
    main()
