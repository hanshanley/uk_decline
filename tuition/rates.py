"""Currency conversion rates from the World Bank API (no API key required).

Pulls, per country, the latest available exchange rate ``PA.NUS.FCRF`` (LCU per US$,
period average) for nominal-USD conversion. Real-terms (constant-dollar) deflation uses
CPI ``FP.CPI.TOTL`` via :func:`fetch_series`. (PPP conversion was intentionally dropped —
PPP baskets distort tuition comparisons; we use market FX + CPI-deflated constant dollars.)

Falls back to :data:`tuition.config.FALLBACK_FX` (keyed by currency) when the network is
unavailable, so the pipeline still runs offline.
"""

from __future__ import annotations

import csv
import os
from typing import Iterable, Optional

from . import config
from .http import get_json


def _fallback_record(country: config.Country) -> dict:
    """Build a rate record from the config fallback table (offline path)."""
    fx = 1.0 if country.currency == "USD" else config.FALLBACK_FX.get(country.currency)
    return {"currency": country.currency, "fx_lcu_per_usd": fx, "fx_year": None}


def _fetch_series(indicator: str, iso3s: list[str], start: int, end: int) -> dict[str, dict[int, float]]:
    """Return ``{iso3: {year: value}}`` for every non-null observation in the range."""
    codes = ";".join(iso3s)
    payload = get_json(
        f"{config.WORLD_BANK_BASE}/country/{codes}/indicator/{indicator}",
        params={"format": "json", "per_page": 20000, "date": f"{start}:{end}"},
    )
    out: dict[str, dict[int, float]] = {}
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        return out
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
        out.setdefault(iso3, {})[year] = val
    return out


def fetch_series(indicator: str, iso3s: list[str], start: int, end: int) -> dict[str, dict[int, float]]:
    """Public wrapper: fetch a full ``{iso3: {year: value}}`` World Bank series."""
    return _fetch_series(indicator, iso3s, start, end)


def _fetch_latest(indicator: str, iso3s: list[str], start: int, end: int) -> dict[str, tuple[int, float]]:
    """Return ``{iso3: (year, value)}`` for the most recent non-null observation."""
    series = _fetch_series(indicator, iso3s, start, end)
    return {iso3: (max(years), years[max(years)]) for iso3, years in series.items() if years}


def fetch_rates(
    iso3s: Optional[Iterable[str]] = None,
    start: int = 2015,
    end: int = 2025,
) -> dict[str, dict]:
    """Fetch the latest FX per country, falling back to config tables on failure.

    Returns ``{iso3: {currency, fx_lcu_per_usd, fx_year}}``.
    """
    codes = list(iso3s) if iso3s is not None else config.iso3_codes()
    fx: dict[str, tuple[int, float]] = {}
    try:
        fx = _fetch_latest(config.WB_FX_INDICATOR, codes, start, end)
    except Exception as exc:  # pragma: no cover - network failure path
        print(f"[rates] World Bank fetch failed ({exc}); using fallback tables.")

    out: dict[str, dict] = {}
    for iso3 in codes:
        country = config.BY_ISO3[iso3]
        rec = _fallback_record(country)  # start from fallback, override with fetched
        if iso3 in fx:
            rec["fx_year"], rec["fx_lcu_per_usd"] = fx[iso3]
        if country.currency == "USD":  # USD is the base currency
            rec["fx_lcu_per_usd"] = 1.0
        out[iso3] = rec
    return out


def fetch_rates_for_years(
    requested: dict[str, set[int]],
) -> dict[tuple[str, int], dict]:
    """Fetch source-year FX for ``{iso3: {years}}`` using real World Bank observations.

    Exact years are preferred. If an exact observation is unavailable, the nearest
    published observation in a three-year search window is used and its actual year is
    retained in ``fx_year``. No configured fallback value is used on this live path.
    """
    requested = {
        iso3: {int(year) for year in years}
        for iso3, years in requested.items()
        if iso3 in config.BY_ISO3 and years
    }
    if not requested:
        return {}
    all_years = {year for years in requested.values() for year in years}
    series: dict[str, dict[int, float]] = {}
    try:
        series = _fetch_series(
            config.WB_FX_INDICATOR,
            list(requested),
            min(all_years) - 3,
            max(all_years) + 3,
        )
    except Exception as exc:  # pragma: no cover - network failure path
        print(f"[rates] source-year World Bank FX fetch failed ({exc}).")

    out: dict[tuple[str, int], dict] = {}
    for iso3, years in requested.items():
        country = config.BY_ISO3[iso3]
        available = series.get(iso3, {})
        for year in years:
            rec = {
                "currency": country.currency,
                "fx_lcu_per_usd": None,
                "fx_year": None,
            }
            if country.currency == "USD":
                rec.update({"fx_lcu_per_usd": 1.0, "fx_year": year})
            elif available:
                fx_year = min(available, key=lambda y: (abs(y - year), -y))
                rec.update({
                    "fx_lcu_per_usd": available[fx_year],
                    "fx_year": fx_year,
                })
            out[(iso3, year)] = rec
    return out


def save_rates(
    rates: dict[str | tuple[str, int], dict],
    path: Optional[str] = None,
) -> str:
    path = path or config.RATES_CSV
    fields = ["iso3", "currency", "fx_lcu_per_usd", "fx_year"]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for key, rec in sorted(rates.items()):
            iso3 = key[0] if isinstance(key, tuple) else key
            writer.writerow({"iso3": iso3, **{k: rec.get(k) for k in fields[1:]}})
    return path


if __name__ == "__main__":
    os.makedirs(config.RAW_DIR, exist_ok=True)
    rates = fetch_rates()
    out = save_rates(rates)
    print(f"[rates] wrote {len(rates)} rows -> {out}")
