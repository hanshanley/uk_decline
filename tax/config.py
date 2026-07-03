"""Static configuration: country/region tables, OECD SDMX dataflows, metric defs, paths.

Tax figures are pulled live from the free, key-less **OECD SDMX** API by
:mod:`tax.revenue` and :mod:`tax.taxing_wages`. ``data/raw/manual_tax.csv`` provides a
small curated fallback (each row cites its own ``source`` + ``year``) so the pipeline
still yields output when the network is unavailable — mirroring ``tuition``.
"""

from __future__ import annotations

import os
from typing import NamedTuple

# --- Regions ----------------------------------------------------------------
UK = "UK"
EUR = "EUR"   # European countries (used for the "Europe median" benchmark)
US = "US"


class Country(NamedTuple):
    name: str
    iso3: str      # OECD SDMX REF_AREA (== ISO 3166-1 alpha-3)
    region: str    # UK / EUR / US


# European OECD members (covered by both Revenue Statistics *and* Taxing Wages).
# Transcontinental Turkey is excluded to match europe_data's geographic-Europe scope.
EUROPE: list[Country] = [
    Country("Austria", "AUT", EUR),
    Country("Belgium", "BEL", EUR),
    Country("Czechia", "CZE", EUR),
    Country("Denmark", "DNK", EUR),
    Country("Estonia", "EST", EUR),
    Country("Finland", "FIN", EUR),
    Country("France", "FRA", EUR),
    Country("Germany", "DEU", EUR),
    Country("Greece", "GRC", EUR),
    Country("Hungary", "HUN", EUR),
    Country("Iceland", "ISL", EUR),
    Country("Ireland", "IRL", EUR),
    Country("Italy", "ITA", EUR),
    Country("Latvia", "LVA", EUR),
    Country("Lithuania", "LTU", EUR),
    Country("Luxembourg", "LUX", EUR),
    Country("Netherlands", "NLD", EUR),
    Country("Norway", "NOR", EUR),
    Country("Poland", "POL", EUR),
    Country("Portugal", "PRT", EUR),
    Country("Slovak Republic", "SVK", EUR),
    Country("Slovenia", "SVN", EUR),
    Country("Spain", "ESP", EUR),
    Country("Sweden", "SWE", EUR),
    Country("Switzerland", "CHE", EUR),
]

UK_COUNTRY = Country("United Kingdom", "GBR", UK)
US_COUNTRY = Country("United States", "USA", US)

ALL_COUNTRIES: list[Country] = [*EUROPE, UK_COUNTRY, US_COUNTRY]
BY_ISO3: dict[str, Country] = {c.iso3: c for c in ALL_COUNTRIES}


def iso3_codes() -> list[str]:
    return [c.iso3 for c in ALL_COUNTRIES]


def name_for_iso3(iso3: str) -> str:
    c = BY_ISO3.get(iso3)
    return c.name if c else iso3


def region_for_iso3(iso3: str) -> str:
    c = BY_ISO3.get(iso3)
    return c.region if c else ""


# --- OECD SDMX dataflows -----------------------------------------------------
SDMX_BASE = "https://sdmx.oecd.org/public/rest/data"

# Revenue Statistics in OECD member countries — comparative tax revenues.
# Key order: REF_AREA.MEASURE.SECTOR.STANDARD_REVENUE.CTRY_SPECIFIC_REVENUE.UNIT_MEASURE.FREQ
# Headline tax-to-GDP = total tax revenue (net), general government, % of GDP.
REV_DATAFLOW = "OECD.CTP.TPS,DSD_REV_COMP_OECD@DF_RSOECD,2.0"
REV_SECTOR = "S13"          # General government (total)
REV_STANDARD = "_T"         # Total tax revenue
REV_UNIT = "PT_B1GQ"        # Percentage of GDP

# Labour taxation — OECD comparative country indicators (Taxing Wages).
# Key order: REF_AREA.MEASURE.UNIT_MEASURE.HOUSEHOLD_TYPE.INCOME_PRINCIPAL.INCOME_SPOUSE.FREQ
TW_DATAFLOW = "OECD.CTP.TPS,DSD_TAX_WAGES_COMP@DF_TW_COMP,2.1"

# (MEASURE code, UNIT_MEASURE code) for the two individual-burden indicators.
TW_TAX_WEDGE = ("AV_TW", "PT_COS_LB")        # tax wedge, % of labour costs
TW_NPATR = ("NPATR", "PT_WG_EARN_G")         # net personal average tax rate, % gross wage

# Household types and earnings levels we collect (OECD codes -> short labels).
HOUSEHOLDS: dict[str, str] = {
    "S_C0": "single_nokids",
    "C_C2": "couple2kids",
}
EARNINGS: dict[str, str] = {
    "AW67": "67aw",
    "AW100": "100aw",
    "AW167": "167aw",
}


# --- Metrics -----------------------------------------------------------------
class Metric(NamedTuple):
    id: str
    label: str
    unit: str
    family: str        # macro | individual
    higher_is_better: bool
    description: str


METRICS: dict[str, Metric] = {
    "tax_to_gdp_pct": Metric(
        "tax_to_gdp_pct",
        "Total tax revenue (% of GDP)",
        "percent",
        "macro",
        higher_is_better=False,
        description=(
            "Total tax revenue including social security contributions, general "
            "government, as a share of GDP (OECD Revenue Statistics, net basis)."
        ),
    ),
    "tax_wedge_pct": Metric(
        "tax_wedge_pct",
        "Labour tax wedge (% of labour costs)",
        "percent",
        "individual",
        higher_is_better=False,
        description=(
            "Income tax plus employee and employer social security contributions "
            "less cash benefits, as a share of total labour cost (OECD Taxing Wages)."
        ),
    ),
    "net_personal_avg_tax_rate_pct": Metric(
        "net_personal_avg_tax_rate_pct",
        "Net personal average tax rate (% of gross wage)",
        "percent",
        "individual",
        higher_is_better=False,
        description=(
            "Income tax plus employee social security contributions less cash "
            "benefits, as a share of gross wage earnings — what the worker feels "
            "in take-home terms (OECD Taxing Wages)."
        ),
    ),
}

# Comparability caveats surfaced in the manifest / summary so comparisons stay honest.
CAVEATS: dict[str, str] = {
    "tax_to_gdp_pct": (
        "Macro ratio: total tax take / GDP. It reflects the whole tax system "
        "(income, payroll, VAT, corporate, property) — not any one worker's burden."
    ),
    "tax_wedge_pct": (
        "Modelled for a stylised worker at a share of the country's average wage; "
        "the average-wage single person is the standard proxy for the typical worker. "
        "True per-country median-earner wedges are not uniformly published."
    ),
    "net_personal_avg_tax_rate_pct": (
        "Excludes employer social contributions (unlike the tax wedge) and VAT/"
        "consumption taxes; it is the direct income-tax + employee-SSC take on wages."
    ),
}


def variant_key(metric: str, household: str, earnings: str) -> str:
    """Build a stable wide-table column key for a metric variant.

    Macro metrics (no household/earnings dimension) return the bare metric id;
    individual metrics return e.g. ``tax_wedge_pct__single_nokids__100aw``.
    """
    if not household and not earnings:
        return metric
    return f"{metric}__{household}__{earnings}"


# --- Paths ------------------------------------------------------------------
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PKG_DIR)
DATA_DIR = os.path.join(ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")

MANUAL_CSV = os.path.join(RAW_DIR, "manual_tax.csv")
