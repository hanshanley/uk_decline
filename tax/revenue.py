"""OECD Revenue Statistics client: total tax revenue as a share of GDP (macro burden).

Dataflow ``DSD_REV_COMP_OECD@DF_RSOECD`` — key order:
``REF_AREA.MEASURE.SECTOR.STANDARD_REVENUE.CTRY_SPECIFIC_REVENUE.UNIT_MEASURE.FREQ``.
We pin general government (``S13``), total tax revenue (``_T``) and percentage-of-GDP
(``PT_B1GQ``) so exactly one observation per country-year comes back.
"""

from __future__ import annotations

from . import config
from ._http import sdmx_csv
from .combine import make_row

SOURCE = "OECD Revenue Statistics (comparative, % of GDP)"
METRIC = "tax_to_gdp_pct"
METRICS = (METRIC,)   # metric ids this source owns (used to scope the offline fallback)


def fetch(start: int, end: int, iso3s: list[str] | None = None) -> list[dict]:
    """Fetch total-tax-revenue-as-%-of-GDP rows for the given years and countries."""
    areas = iso3s if iso3s is not None else config.iso3_codes()
    key = (
        f"{'+'.join(areas)}.TAX_REV.{config.REV_SECTOR}.{config.REV_STANDARD}"
        f"._T.{config.REV_UNIT}.A"
    )
    raw = sdmx_csv(config.REV_DATAFLOW, key, start, end, base=config.SDMX_BASE)

    out: list[dict] = []
    for r in raw:
        iso3 = r.get("REF_AREA", "")
        value = r.get("OBS_VALUE", "")
        if iso3 not in config.BY_ISO3 or value in (None, ""):
            continue
        out.append(
            make_row(
                iso3=iso3,
                year=int(r["TIME_PERIOD"]),
                metric=METRIC,
                value=float(value),
                source=SOURCE,
            )
        )
    return out
