"""Build the historical tuition series (back to the early 1970s), in real 2022 USD.

Every figure is traceable to a real primary source:
  * US   — NCES Digest 2023, Table 330.10 (Public 4-year, in-district tuition & fees),
           taken directly in the table's own **constant 2022-23 dollars** (CPI-adjusted
           by the U.S. Bureau of Labor Statistics). Fetched by ``fetch_nces.py``.
  * UK   — England statutory fee caps (Acts / SIs on legislation.gov.uk), nominal GBP,
           converted to USD at the **year's market exchange rate** (World Bank PA.NUS.FCRF)
           and deflated to constant-2022 USD by **US CPI (FP.CPI.TOTL)** — the same basis as
           the NCES US series, so UK and US are directly comparable.
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


def real_base_usd(nominal_local: float, fx_year_lcu_per_usd: float,
                  us_cpi_year: float, us_cpi_base: float) -> float:
    """Convert nominal local-currency tuition to constant base-year (2022) USD.

    Consistent with the US NCES series (real US$ deflated by US CPI) and the project's
    house methodology: convert at that **year's market exchange rate**, then deflate by
    **US CPI** to the base year.

        nominal_usd = nominal_local / FX_year(LCU per US$)
        real_base_usd = nominal_usd * (US_CPI_base / US_CPI_year)
    """
    nominal_usd = nominal_local / fx_year_lcu_per_usd
    return nominal_usd * (us_cpi_base / us_cpi_year)


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
    """Convert nominal local tuition to constant-2022 USD, on the SAME basis as the US NCES
    series: convert at the year's market exchange rate, then deflate by **US** CPI.

    (Earlier versions deflated by each country's own CPI and used a frozen base-year exchange
    rate; that made the UK/EU rows non-comparable with the US-CPI-based NCES figures and
    ignored subsequent moves in the exchange rate. We now match the US basis.)
    """
    iso3s = sorted({r["iso3"] for r in rows})
    max_year = max(int(r["year"]) for r in rows)
    top = max(config.REAL_BASE_YEAR, max_year)
    # US CPI is the single deflator (base = 2022); market FX per country per year.
    us_cpi = fetch_series(config.WB_CPI_INDICATOR, ["USA"], 1970, top).get("USA", {})
    fx = fetch_series(config.WB_FX_INDICATOR, iso3s, 1970, top)

    us_base = _nearest(us_cpi, config.REAL_BASE_YEAR)
    if not us_base:
        raise RuntimeError("missing World Bank US CPI; cannot deflate to real 2022 USD")

    out = []
    for r in rows:
        iso3 = r["iso3"]
        nominal = float(r["annual_tuition_local"])
        real_usd = 0.0
        if nominal != 0:
            us_at = _nearest(us_cpi, int(r["year"]))
            fx_at = _nearest(fx.get(iso3, {}), int(r["year"]))
            if not (us_at and fx_at and fx_at[1]):
                raise RuntimeError(f"missing World Bank US CPI/FX for {iso3}; cannot deflate {r['country']} {r['year']}")
            real_usd = real_base_usd(nominal, fx_at[1], us_at[1], us_base[1])
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
