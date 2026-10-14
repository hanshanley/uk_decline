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

ROOT = Path(__file__).resolve().parents[1]
STEPS = {
    "gdp-income": (
        ("-m", "europe_data.fetch_data"),
        ("-m", "europe_data.plot_uk_decline"),
    ),
    "markets": (("-m", "markets_data"),),
    "sterling": (("-m", "sterling_data"),),
    "trade": (("-m", "trade_data"),),
    "ageing": (("-m", "age_data.fetch_age"),),
    "trust": (("-m", "trust_data.fetch_trust", "--charts", "--summary"),),
    "tax": (("-m", "tax.fetch_tax"),),
    "nhs": (("-m", "nhs_data"),),
    "rail": (("-m", "rail_data"),),
    "london": (("-m", "london_data"),),
    "crime": (("-m", "crime_data"),),
    "migration": (("-m", "uk_migration.run"),),
    "public-spending": (("-m", "austerity_data"),),
    "food-banks": (("-m", "foodbank_data", "--refresh"),),
    "tuition": (
        ("-m", "tuition.cpi"),
        ("-m", "tuition.fetch_collegeboard"),
        ("-m", "tuition.build_dataset"),
        ("-m", "tuition.analyze"),
        ("-m", "tuition.plot_tuition"),
        ("-m", "tuition.plot_tuition", "--real"),
        ("-m", "tuition.build_history"),
        ("-m", "tuition.plot_history"),
    ),
    "purchasing-power": (("-m", "ppp_data"),),
}
FAILURE_NOTICE = re.compile(r"\bWARNING:|\busing (?:manual )?fallback\b", re.IGNORECASE)
CURATED_INPUTS = (
    "LSE monthly factsheet selection and historical coverage",
    "National tuition schedules and publisher workbook editions",
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
    if FAILURE_NOTICE.search(result.stdout):
        raise RuntimeError(
            f"{' '.join(command)} reported an incomplete source or fallback; refusing publication"
        )


def nhs_coverage(root: Path) -> dict[tuple[str, str], str]:
    """Record the published series so a source cannot silently disappear or regress."""
    path = root / "outputs/nhs/nhs_waiting_times.csv"
    coverage: dict[tuple[str, str], str] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["value"] in ("", None):
                continue
            key = row["nation_code"], row["metric"]
            coverage[key] = max(coverage.get(key, ""), row["date"])
    if not coverage:
        raise ValueError("Published NHS data contains no observations")
    return coverage


def refresh(root: Path = ROOT, only: list[str] | None = None) -> None:
    selected = list(STEPS) if only is None else only
    baseline = nhs_coverage(root) if "nhs" in selected else {}
    for name in selected:
        for command in STEPS[name]:
            run(command, root)
        if name == "nhs":
            current = nhs_coverage(root)
            regressed = [key for key, end in baseline.items() if current.get(key, "") < end]
            if regressed:
                raise RuntimeError(f"NHS refresh lost published series or date coverage: {regressed}")
    run(("scorecard.py",), root)
    if only is None:
        status = root / "data/site/refresh.json"
        status.parent.mkdir(parents=True, exist_ok=True)
        status.write_text(json.dumps({
            "last_successful_refresh_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "automated_analyses": selected,
            "curated_inputs": CURATED_INPUTS,
        }, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only", nargs="+", choices=STEPS,
        help="Refresh selected analyses; a partial run does not advance the full-refresh date.",
    )
    args = parser.parse_args()
    refresh(only=args.only)


if __name__ == "__main__":
    main()
