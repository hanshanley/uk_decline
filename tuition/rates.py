"""Currency conversion rates from the World Bank API (no API key required).

Pulls, per country, the latest available:
  * ``PA.NUS.FCRF`` — official exchange rate, LCU per US$ (period average)  -> nominal USD
  * ``PA.NUS.PPP``  — PPP conversion factor, GDP, LCU per international $    -> PPP USD

Falls back to :data:`tuition.config.FALLBACK_FX` / ``FALLBACK_PPP`` (keyed by currency)
when the network is unavailable, so the pipeline still runs offline.
"""

from __future__ import annotations

import csv
import os
from typing import Iterable, Optional

from . import config
from .http import get_json


def _fallback_record(country: config.Country) -> dict:
    """Build a rate record from the config fallback tables (offline path)."""
    if country.currency == "USD":  # USD is the base currency
        fx = ppp = 1.0
    else:
        fx = config.FALLBACK_FX.get(country.currency)
        ppp = config.FALLBACK_PPP.get(country.currency)
    return {
        "currency": country.currency,
        "fx_lcu_per_usd": fx,
        "fx_year": None,
        "ppp_lcu_per_intl": ppp,
        "ppp_year": None,
    }


def _fetch_latest(indicator: str, iso3s: list[str], start: int, end: int) -> dict[str, tuple[int, float]]:
    """Return ``{iso3: (year, value)}`` for the most recent non-null observation."""
    codes = ";".join(iso3s)
    payload = get_json(
        f"{config.WORLD_BANK_BASE}/country/{codes}/indicator/{indicator}",
        params={"format": "json", "per_page": 20000, "date": f"{start}:{end}"},
    )
    latest: dict[str, tuple[int, float]] = {}
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        return latest
    for row in payload[1]:
        value = row.get("value")
        iso3 = row.get("countryiso3code")
        if value is None or not iso3:
            continue
        try:
            year = int(row["date"])
            val = float(value)
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed upstream rows rather than crashing the run
        prev = latest.get(iso3)
        if prev is None or year > prev[0]:
            latest[iso3] = (year, val)
    return latest


def fetch_rates(
    iso3s: Optional[Iterable[str]] = None,
    start: int = 2015,
    end: int = 2025,
) -> dict[str, dict]:
    """Fetch FX + PPP per country, falling back to config tables on failure.

    Returns ``{iso3: {currency, fx_lcu_per_usd, fx_year, ppp_lcu_per_intl, ppp_year}}``.
    """
    codes = list(iso3s) if iso3s is not None else config.iso3_codes()
    fx: dict[str, tuple[int, float]] = {}
    ppp: dict[str, tuple[int, float]] = {}
    try:
        fx = _fetch_latest(config.WB_FX_INDICATOR, codes, start, end)
        ppp = _fetch_latest(config.WB_PPP_INDICATOR, codes, start, end)
    except Exception as exc:  # pragma: no cover - network failure path
        print(f"[rates] World Bank fetch failed ({exc}); using fallback tables.")

    out: dict[str, dict] = {}
    for iso3 in codes:
        country = config.BY_ISO3[iso3]
        rec = _fallback_record(country)  # start from fallback, override with fetched
        if iso3 in fx:
            rec["fx_year"], rec["fx_lcu_per_usd"] = fx[iso3]
        if iso3 in ppp:
            rec["ppp_year"], rec["ppp_lcu_per_intl"] = ppp[iso3]
        # USD is the base currency: exchange/PPP to itself is 1.0.
        if country.currency == "USD":
            rec["fx_lcu_per_usd"], rec["ppp_lcu_per_intl"] = 1.0, 1.0
        out[iso3] = rec
    return out


def save_rates(rates: dict[str, dict], path: Optional[str] = None) -> str:
    path = path or config.RATES_CSV
    fields = ["iso3", "currency", "fx_lcu_per_usd", "fx_year", "ppp_lcu_per_intl", "ppp_year"]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for iso3, rec in sorted(rates.items()):
            writer.writerow({"iso3": iso3, **{k: rec.get(k) for k in fields[1:]}})
    return path


if __name__ == "__main__":
    os.makedirs(config.RAW_DIR, exist_ok=True)
    rates = fetch_rates()
    out = save_rates(rates)
    print(f"[rates] wrote {len(rates)} rows -> {out}")
