"""Best-effort automated pull of EU tuition-fee data (Eurostat / Eurydice).

The EU reference for domestic tuition is the Eurydice report "National Student Fee and
Support Systems in European Higher Education", which is published as a PDF/figure set,
not a queryable Eurostat dataset. Eurostat's education-finance collections
(``educ_uoe_fine*``) cover expenditure, not per-student statutory fees. This script
therefore checks Eurostat availability and, absent a clean fee series, defers to the
curated ``data/raw/manual_tuition.csv`` (hybrid approach), reporting which EU-27
countries would need manual fill (all of them, by design).

Usage:
    python fetch_eurostat.py
"""

from __future__ import annotations

import csv
import os

from tuition import config
from tuition.http import get_json

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


def eurostat_reachable() -> bool:
    """Ping a small Eurostat dataset to confirm the dissemination API is up."""
    try:
        payload = get_json(
            f"{EUROSTAT_BASE}/educ_uoe_fine06",
            params={"format": "JSON", "sinceTimePeriod": "2020", "untilTimePeriod": "2021"},
        )
        return isinstance(payload, dict)
    except Exception as exc:
        print(f"[eurostat] API unreachable: {exc}")
        return False


def main() -> None:
    os.makedirs(config.RAW_DIR, exist_ok=True)

    reachable = eurostat_reachable()
    if reachable:
        print("[eurostat] dissemination API reachable, but no per-student statutory "
              "tuition-fee series is published (only expenditure aggregates).")
    print(f"[eurostat] EU-27 domestic fees taken from curated data. Reference: {config.EURYDICE_HINT}")

    eu27 = [c.name for c in config.EU27]
    print(f"[eurostat] {len(eu27)} EU-27 countries covered via manual curation: "
          f"{', '.join(eu27[:5])}, ...")

    # Write an (empty) raw file so build_dataset's fill step has a consistent shape.
    fields = ["iso3", "country", "region", "annual_tuition_local", "currency", "year", "source"]
    with open(config.EUROSTAT_CSV, "w", newline="") as fh:
        csv.DictWriter(fh, fieldnames=fields).writeheader()
    print(f"[eurostat] wrote header-only {config.EUROSTAT_CSV} (no automated fee rows).")


if __name__ == "__main__":
    main()
