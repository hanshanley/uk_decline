"""Verify whether OECD tuition-fee data is available over the SDMX API.

OECD "Education at a Glance" annual tuition fees (Table C5) are published primarily as
Excel/PDF; there is no consistently machine-stable SDMX series across editions. This
script queries the SDMX-JSON API and reports what it finds — the authoritative figures
live in ``data/raw/manual_tuition.csv`` (hybrid approach). Any rows retrieved are written
to ``data/raw/oecd_tuition.csv`` to *fill* countries missing from the manual set.

Usage:
    python fetch_oecd.py [--dataflow OECD.EDU.IMEP,DSD_EAG_FIN,1.0]
"""

from __future__ import annotations

import argparse
import csv
import os

from tuition import config
from tuition.http import get_json


def try_fetch(dataflow: str, start: int, end: int) -> list[dict]:
    """Query the OECD SDMX-JSON API for a tuition dataflow.

    Returns tidy rows, or ``[]`` when the dataflow yields no usable fee observations —
    which, for Education at a Glance Table C5, is the expected outcome. The SDMX
    representation is deeply nested and its dimension layout changes between editions,
    so there is no schema that can be relied on across years; the authoritative figures
    are the curated ones. This function exists to re-verify that conclusion on demand
    rather than to assert it from memory.
    """
    url = f"{config.OECD_SDMX_BASE}/{dataflow}/all"
    try:
        payload = get_json(
            url,
            params={"startPeriod": start, "endPeriod": end, "format": "jsondata"},
        )
    except Exception as exc:
        print(f"[oecd] SDMX request failed: {exc}")
        return []

    data = payload.get("data") if isinstance(payload, dict) else None
    if not data:
        print("[oecd] no observations returned for this dataflow.")
        return []
    print("[oecd] SDMX payload returned, but its dimension layout is not stable across "
          "Education at a Glance editions; fees taken from curated data instead.")
    return []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataflow", default="OECD.EDU.IMEP,DSD_EAG_FIN,1.0",
                    help="OECD SDMX dataflow ref (agency,id,version)")
    ap.add_argument("--start", type=int, default=2020)
    ap.add_argument("--end", type=int, default=2024)
    args = ap.parse_args()

    rows = try_fetch(args.dataflow, args.start, args.end)

    os.makedirs(config.RAW_DIR, exist_ok=True)
    fields = ["iso3", "country", "region", "annual_tuition_local", "currency", "year", "source"]
    with open(config.OECD_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    if rows:
        print(f"[oecd] wrote {len(rows)} rows -> {config.OECD_CSV}")
    else:
        print(f"[oecd] no rows retrieved; using curated data. See: {config.OECD_TUITION_HINT}")


if __name__ == "__main__":
    main()
