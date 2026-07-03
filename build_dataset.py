"""Build the normalized per-country tuition dataset.

Loads the authoritative manual tuition figures (and any best-effort fetched OECD /
Eurostat rows that fill *missing* countries), attaches World Bank FX + PPP rates, and
writes ``data/processed/tuition_by_country.csv`` with USD and PPP-USD tuition columns.

Usage:
    python build_dataset.py            # fetch live World Bank rates
    python build_dataset.py --offline  # use config fallback rates (no network)
"""

from __future__ import annotations

import argparse
import csv
import os

from tuition import config
from tuition.rates import fetch_rates, save_rates, _fallback_record

OUTPUT_FIELDS = [
    "country", "iso3", "region", "annual_tuition_local", "currency", "year",
    "include_primary", "annual_tuition_usd", "annual_tuition_usd_ppp",
    "fx_lcu_per_usd", "fx_year", "ppp_lcu_per_intl", "ppp_year", "source", "notes",
]


def load_manual() -> list[dict]:
    with open(config.MANUAL_CSV, newline="") as fh:
        return list(csv.DictReader(fh))


def load_fetched_fills(existing_iso3: set[str]) -> list[dict]:
    """Load OECD/Eurostat rows only for countries missing from the manual set."""
    fills: list[dict] = []
    for path, src in ((config.OECD_CSV, "OECD"), (config.EUROSTAT_CSV, "Eurostat")):
        if not os.path.exists(path):
            continue
        before = len(fills)
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("iso3") and row["iso3"] not in existing_iso3:
                    fills.append(row)
                    existing_iso3.add(row["iso3"])
        added = len(fills) - before
        if added:
            print(f"[build] filled {added} missing countries from {src}")
    return fills


def _csv_safe(value):
    """Neutralize CSV formula injection in untrusted string cells (spreadsheet safety)."""
    if isinstance(value, str) and value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def convert(rows: list[dict], rates: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        iso3 = row["iso3"]
        rate = rates.get(iso3)
        local = float(row["annual_tuition_local"])
        cur = row["currency"]
        cfg = config.BY_ISO3.get(iso3)
        if cfg and cur != cfg.currency:
            print(f"[build] WARN {row['country']}: currency {cur} != config {cfg.currency}")

        usd = usd_ppp = None
        fx = ppp = None
        fx_year = ppp_year = None
        if rate:
            fx, ppp = rate["fx_lcu_per_usd"], rate["ppp_lcu_per_intl"]
            fx_year, ppp_year = rate["fx_year"], rate["ppp_year"]
            if fx:
                usd = round(local / fx, 2)
            if ppp:
                usd_ppp = round(local / ppp, 2)

        out.append({
            "country": row["country"],
            "iso3": iso3,
            "region": row["region"],
            "annual_tuition_local": local,
            "currency": cur,
            "year": row["year"],
            "include_primary": row.get("include_primary", "1"),
            "annual_tuition_usd": usd,
            "annual_tuition_usd_ppp": usd_ppp,
            "fx_lcu_per_usd": fx if rate else None,
            "fx_year": fx_year,
            "ppp_lcu_per_intl": ppp if rate else None,
            "ppp_year": ppp_year,
            "source": row.get("source", ""),
            "notes": row.get("notes", ""),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true", help="use config fallback rates")
    args = ap.parse_args()

    os.makedirs(config.RAW_DIR, exist_ok=True)
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)

    rows = load_manual()
    seen = {r["iso3"] for r in rows}
    rows += load_fetched_fills(seen)

    if args.offline:
        rates = {c.iso3: _fallback_record(c) for c in config.ALL_COUNTRIES}
        print("[build] using offline fallback rates")
    else:
        rates = fetch_rates()
        save_rates(rates)
        print(f"[build] fetched World Bank rates for {len(rates)} countries")

    converted = convert(rows, rates)
    with open(config.TUITION_BY_COUNTRY_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows({k: _csv_safe(v) for k, v in row.items()} for row in converted)
    print(f"[build] wrote {len(converted)} rows -> {config.TUITION_BY_COUNTRY_CSV}")


if __name__ == "__main__":
    main()
