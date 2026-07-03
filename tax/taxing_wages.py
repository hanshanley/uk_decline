"""OECD Taxing Wages client: labour tax wedge & net personal average tax rate.

Dataflow ``DSD_TAX_WAGES_COMP@DF_TW_COMP`` — key order:
``REF_AREA.MEASURE.UNIT_MEASURE.HOUSEHOLD_TYPE.INCOME_PRINCIPAL.INCOME_SPOUSE.FREQ``.
We fetch two indicators (tax wedge, net personal average tax rate) across the household
types and earnings levels in :data:`tax.config.HOUSEHOLDS` / ``EARNINGS`` and tag each
tidy row with the ``household`` + ``earnings`` variant.
"""

from __future__ import annotations

from . import config
from ._http import sdmx_csv
from .combine import make_row

SOURCE = "OECD Taxing Wages (comparative)"

# (metric id, (MEASURE code, UNIT code))
_INDICATORS: list[tuple[str, tuple[str, str]]] = [
    ("tax_wedge_pct", config.TW_TAX_WEDGE),
    ("net_personal_avg_tax_rate_pct", config.TW_NPATR),
]

# Metric ids this source owns (used to scope the offline fallback).
METRICS = tuple(metric for metric, _ in _INDICATORS)


def _fetch_indicator(
    metric: str,
    measure: str,
    unit: str,
    areas: list[str],
    start: int,
    end: int,
) -> list[dict]:
    # Key order: REF_AREA.MEASURE.UNIT_MEASURE.HOUSEHOLD_TYPE.INCOME_PRINCIPAL.
    # INCOME_SPOUSE.FREQ. Pin household types and earnings levels server-side (so the
    # API doesn't ship every combination). The spouse-income position stays wildcarded
    # in the query (its valid codes differ by household) and is filtered per household
    # below via config.HOUSEHOLD_SPOUSE, so each variant maps to exactly one OECD family
    # type — no two rows can share a variant key.
    households = "+".join(config.HOUSEHOLDS)
    earnings = "+".join(config.EARNINGS)
    key = f"{'+'.join(areas)}.{measure}.{unit}.{households}.{earnings}..A"
    raw = sdmx_csv(config.TW_DATAFLOW, key, start, end, base=config.SDMX_BASE)

    out: list[dict] = []
    for r in raw:
        iso3 = r.get("REF_AREA", "")
        household_code = r.get("HOUSEHOLD_TYPE", "")
        earnings_code = r.get("INCOME_PRINCIPAL", "")
        spouse_code = r.get("INCOME_SPOUSE", "")
        value = r.get("OBS_VALUE", "")
        if iso3 not in config.BY_ISO3 or value in (None, ""):
            continue
        if household_code not in config.HOUSEHOLDS or earnings_code not in config.EARNINGS:
            continue
        if spouse_code != config.HOUSEHOLD_SPOUSE.get(household_code):
            continue
        out.append(
            make_row(
                iso3=iso3,
                year=int(r["TIME_PERIOD"]),
                metric=metric,
                value=float(value),
                source=SOURCE,
                household=config.HOUSEHOLDS[household_code],
                earnings=config.EARNINGS[earnings_code],
            )
        )
    return out


def fetch(start: int, end: int, iso3s: list[str] | None = None) -> list[dict]:
    """Fetch tax-wedge & net-personal-average-tax-rate rows for all variants."""
    areas = iso3s if iso3s is not None else config.iso3_codes()
    out: list[dict] = []
    for metric, (measure, unit) in _INDICATORS:
        out.extend(_fetch_indicator(metric, measure, unit, areas, start, end))
    return out
