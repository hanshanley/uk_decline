"""Build the normalized per-country tuition dataset.

Loads the authoritative manual tuition figures (and any best-effort fetched OECD /
Eurostat rows that fill *missing* countries), attaches the World Bank FX rate, and writes
``data/processed/tuition_by_country.csv`` with nominal-USD and constant-2022-USD columns.

Usage:
    python build_dataset.py            # fetch live World Bank rates
    python build_dataset.py --offline  # use config fallback rates (no network)
"""

from __future__ import annotations

import argparse
import csv
import os

from tuition import config
from tuition.rates import fetch_rates, save_rates, fetch_series, _fallback_record

OUTPUT_FIELDS = [
    "country", "iso3", "region", "annual_tuition_local", "currency", "year",
    "include_primary", "annual_tuition_usd", "annual_tuition_usd_real2022",
    "fx_lcu_per_usd", "fx_year", "source", "notes",
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


def convert(rows: list[dict], rates: dict[str, dict], us_deflator: dict[int, float] | None = None) -> list[dict]:
    """Convert local tuition to nominal USD (market FX) and constant-2022 USD.

    ``us_deflator`` maps a reference year -> (US CPI_2022 / US CPI_year); the nominal-USD
    figure is multiplied by it to get constant-2022 USD. If empty (e.g. offline), the
    real figure falls back to the nominal USD undeflated.
    """
    us_deflator = us_deflator or {}
    out: list[dict] = []
    for row in rows:
        iso3 = row["iso3"]
        rate = rates.get(iso3)
        local = float(row["annual_tuition_local"])
        cur = row["currency"]
        cfg = config.BY_ISO3.get(iso3)
        if cfg and cur != cfg.currency:
            print(f"[build] WARN {row['country']}: currency {cur} != config {cfg.currency}")

        usd = usd_real = None
        fx = fx_year = None
        if rate:
            fx, fx_year = rate["fx_lcu_per_usd"], rate["fx_year"]
            if fx:
                usd = round(local / fx, 2)
                deflator = us_deflator.get(int(row["year"]), 1.0)
                usd_real = round(usd * deflator, 2)

        out.append({
            "country": row["country"],
            "iso3": iso3,
            "region": row["region"],
            "annual_tuition_local": local,
            "currency": cur,
            "year": row["year"],
            "include_primary": row.get("include_primary", "1"),
            "annual_tuition_usd": usd,
            "annual_tuition_usd_real2022": usd_real,
            "fx_lcu_per_usd": fx if rate else None,
            "fx_year": fx_year,
            "source": row.get("source", ""),
            "notes": row.get("notes", ""),
        })
    return out


def _us_cpi_deflator() -> dict[int, float]:
    """Fetch US CPI and return {year: CPI_2022 / CPI_year} for real-terms deflation."""
    series = fetch_series(config.WB_CPI_INDICATOR, ["USA"], 2010, config.REAL_BASE_YEAR + 3).get("USA", {})
    base = series.get(config.REAL_BASE_YEAR)
    if not base:
        return {}
    return {year: base / cpi for year, cpi in series.items() if cpi}


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
        deflator: dict[int, float] = {}
        print("[build] using offline fallback rates (no CPI deflation)")
    else:
        rates = fetch_rates()
        save_rates(rates)
        deflator = _us_cpi_deflator()
        print(f"[build] fetched World Bank FX for {len(rates)} countries + US CPI deflator")

    converted = convert(rows, rates, deflator)
    with open(config.TUITION_BY_COUNTRY_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows({k: _csv_safe(v) for k, v in row.items()} for row in converted)
    print(f"[build] wrote {len(converted)} rows -> {config.TUITION_BY_COUNTRY_CSV}")


if __name__ == "__main__":
    main()
