"""Build the historical tuition series (back to the early 1970s), in real 2022 USD.

Every figure is traceable to a real primary source:
  * US   — NCES Digest 2023, Table 330.10 (Public 4-year, in-district tuition & fees),
           taken directly in the table's own **constant 2022-23 dollars** (CPI-adjusted
           by the U.S. Bureau of Labor Statistics). Fetched by ``fetch_nces.py``.
  * UK   — England statutory fee caps (Acts / SIs on legislation.gov.uk), nominal GBP,
           deflated to constant-2022 GBP using **World Bank CPI (FP.CPI.TOTL)** and
           converted to USD using the **World Bank 2022 exchange rate (PA.NUS.FCRF)**.
  * DE   — Germany (representative EU): no general tuition (0), from Eurydice / HE history.

Output: ``data/processed/tuition_history.csv`` with nominal and real-2022-USD columns and
a per-row ``source`` + ``source_url``. Requires network (real World Bank rates); there is
no fabricated fallback for the historical deflators.
"""

from __future__ import annotations

import csv
import os

from tuition import config
from tuition.rates import fetch_series


def _nearest(series: dict[int, float], year: int) -> tuple[int, float] | None:
    if not series:
        return None
    if year in series:
        return year, series[year]
    best = min(series, key=lambda y: abs(y - year))
    return best, series[best]


def real_base_usd(nominal_local: float, cpi_at_year: float, cpi_base: float, fx_base_lcu_per_usd: float) -> float:
    """Deflate nominal local currency to constant base-year USD.

    real_base_local = nominal * (CPI_base / CPI_year);  USD = real_base_local / FX_base.
    """
    real_local = nominal_local * (cpi_base / cpi_at_year)
    return real_local / fx_base_lcu_per_usd


def load_nces() -> list[dict]:
    """US rows already in constant 2022-23 USD (NCES) — no further adjustment."""
    with open(config.NCES_CSV, newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        out.append({
            "country": "United States", "iso3": "USA", "region": config.US,
            "year": int(r["year"]),
            "nominal_local": float(r["tuition_current_usd"]), "currency": "USD",
            "real_2022_usd": float(r["tuition_constant2022_usd"]),
            "source": r["source"], "source_url": r["source_url"],
        })
    return out


def load_manual() -> list[dict]:
    with open(config.HISTORY_MANUAL_CSV, newline="") as fh:
        return list(csv.DictReader(fh))


def deflate_manual(rows: list[dict]) -> list[dict]:
    """Deflate nominal local tuition to constant-2022 USD via World Bank CPI + FX."""
    iso3s = sorted({r["iso3"] for r in rows})
    cpi = fetch_series(config.WB_CPI_INDICATOR, iso3s, 1970, config.REAL_BASE_YEAR)
    fx = fetch_series(config.WB_FX_INDICATOR, iso3s, config.REAL_BASE_YEAR - 3, config.REAL_BASE_YEAR)

    out = []
    for r in rows:
        iso3 = r["iso3"]
        nominal = float(r["annual_tuition_local"])
        real_usd = 0.0
        if nominal != 0:
            cpi_series = cpi.get(iso3, {})
            base = _nearest(cpi_series, config.REAL_BASE_YEAR)
            at_year = _nearest(cpi_series, int(r["year"]))
            fx_base = _nearest(fx.get(iso3, {}), config.REAL_BASE_YEAR)
            if not (base and at_year and fx_base and fx_base[1]):
                raise RuntimeError(f"missing World Bank CPI/FX for {iso3}; cannot deflate {r['country']} {r['year']}")
            real_usd = real_base_usd(nominal, at_year[1], base[1], fx_base[1])
        out.append({
            "country": r["country"], "iso3": iso3, "region": r["region"],
            "year": int(r["year"]),
            "nominal_local": nominal, "currency": r["currency"],
            "real_2022_usd": round(real_usd, 2),
            "source": r["source"], "source_url": r["source_url"],
        })
    return out


FIELDS = ["country", "iso3", "region", "year", "nominal_local", "currency",
          "real_2022_usd", "source", "source_url"]


def main() -> None:
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    rows = load_nces() + deflate_manual(load_manual())
    rows.sort(key=lambda r: (r["region"], r["year"]))
    with open(config.HISTORY_OUT_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in FIELDS})
    span = f"{min(r['year'] for r in rows)}-{max(r['year'] for r in rows)}"
    print(f"[history] wrote {len(rows)} rows ({span}) -> {config.HISTORY_OUT_CSV}")


if __name__ == "__main__":
    main()
