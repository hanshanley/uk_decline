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
import datetime as dt
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


def expand_uk_fee_schedule(rows: list[dict]) -> list[dict]:
    """Expand sparse England fee-cap changes into annual nominal observations.

    The primary-source file records policy change points, not every year. Carrying the
    legally fixed nominal cap forward is valid; the annual FX and CPI conversion still
    happens separately in :func:`deflate_manual`.
    """
    uk_changes = sorted(
        (row for row in rows if row["iso3"] == "GBR"),
        key=lambda row: int(row["year"]),
    )
    other = [row for row in rows if row["iso3"] != "GBR"]
    first_fee_year = next(
        (int(row["year"]) for row in uk_changes if float(row["annual_tuition_local"]) > 0),
        None,
    )
    if first_fee_year is None:
        return rows
    end_year = max(int(row["year"]) for row in uk_changes)
    expanded = []
    for year in range(first_fee_year, end_year + 1):
        applicable = [row for row in uk_changes if int(row["year"]) <= year]
        row = dict(applicable[-1])
        row["year"] = str(year)
        expanded.append(row)
    return other + expanded


def deflate_manual(rows: list[dict]) -> list[dict]:
    """Convert nominal local tuition to constant-2022 USD, on the SAME basis as the US NCES
    series: convert at the year's market exchange rate, then deflate by **US** CPI.

    (Earlier versions deflated by each country's own CPI and used a frozen base-year exchange
    rate; that made the UK/EU rows non-comparable with the US-CPI-based NCES figures and
    ignored subsequent moves in the exchange rate. We now match the US basis.)
    """
    # Zero-fee countries need no currency conversion. Excluding them also avoids asking
    # the World Bank for obsolete historical currencies (for example Germany before the
    # euro), which can make an otherwise valid multi-country FX request fail.
    iso3s = sorted({
        r["iso3"]
        for r in rows
        if float(r["annual_tuition_local"]) != 0
    })
    max_year = max(int(r["year"]) for r in rows)
    top = max(config.REAL_BASE_YEAR, max_year)
    fetch_end = min(top, dt.date.today().year - 1)
    # US CPI is the single deflator (base = 2022); market FX per country per year.
    # World Bank rejects ranges ending in a not-yet-complete calendar year. Published
    # future fee caps remain in the output with a blank real value until same-year inputs
    # exist; they are not converted with a carried-forward FX/CPI observation.
    us_cpi = fetch_series(config.WB_CPI_INDICATOR, ["USA"], 1970, fetch_end).get("USA", {})
    fx = fetch_series(config.WB_FX_INDICATOR, iso3s, 1970, fetch_end)

    us_base = _nearest(us_cpi, config.REAL_BASE_YEAR)
    if not us_base:
        raise RuntimeError("missing World Bank US CPI; cannot deflate to real 2022 USD")

    out = []
    for r in rows:
        iso3 = r["iso3"]
        year = int(r["year"])
        nominal = float(r["annual_tuition_local"])
        real_usd: float | None = 0.0
        if nominal != 0:
            # A real value labelled as year Y must use year-Y conversion inputs. Do not
            # silently carry the latest FX/CPI into a published future fee-cap year.
            if year not in us_cpi or year not in fx.get(iso3, {}):
                print(
                    f"[history] leaving real value blank for {r['country']} {year}: "
                    "no same-year World Bank US CPI/FX observation"
                )
                real_usd = None
            else:
                us_at = (year, us_cpi[year])
                fx_at = (year, fx[iso3][year])
                if not fx_at[1]:
                    raise RuntimeError(
                        f"invalid zero World Bank FX for {iso3} {year}"
                    )
                real_usd = real_base_usd(nominal, fx_at[1], us_at[1], us_base[1])
        out.append({
            "country": r["country"], "iso3": iso3, "region": r["region"],
            "year": year,
            "nominal_local": nominal, "currency": r["currency"],
            "real_2022_usd": round(real_usd, 2) if real_usd is not None else None,
            "source": r["source"], "source_url": r["source_url"],
        })
    return out


FIELDS = ["country", "iso3", "region", "year", "nominal_local", "currency",
          "real_2022_usd", "source", "source_url"]


def main() -> None:
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    rows = load_nces() + deflate_manual(expand_uk_fee_schedule(load_manual()))
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
