"""Static configuration: country/region tables, WB indicators, 5-year bands, citations.

Age-structure data is pulled live from the free, key-less **World Bank World Development
Indicators** API. The underlying figures are collected by the **UN Population Division**
(World Population Prospects) and redistributed by the World Bank; both organisations are
credited in :data:`CITATIONS` (proper bibliographic form) and in every output's ``source``.
``data/raw/manual_age.csv`` is a verifiable offline snapshot of the same live WB data.
"""

from __future__ import annotations

import os
from typing import NamedTuple

# Reuse the curated geographic-Europe country list from the sibling europe_data package.
from europe_data import countries as _eu_countries

# --- Regions ----------------------------------------------------------------
UK = "UK"
EUR = "EUR"   # European countries (used for the "Europe median/mean" benchmark)
US = "US"


class Country(NamedTuple):
    name: str
    iso3: str      # World Bank country code (== ISO 3166-1 alpha-3)
    region: str    # UK / EUR / US


def _build_countries() -> list[Country]:
    out: list[Country] = []
    for c in _eu_countries.COUNTRIES:
        if c.iso3 == "GBR":
            out.append(Country(c.name, "GBR", UK))
        else:
            out.append(Country(c.name, c.iso3, EUR))
    out.append(Country("United States", "USA", US))
    return out


ALL_COUNTRIES: list[Country] = _build_countries()
BY_ISO3: dict[str, Country] = {c.iso3: c for c in ALL_COUNTRIES}


def iso3_codes() -> list[str]:
    return [c.iso3 for c in ALL_COUNTRIES]


def name_for_iso3(iso3: str) -> str:
    c = BY_ISO3.get(iso3)
    return c.name if c else iso3


def region_for_iso3(iso3: str) -> str:
    c = BY_ISO3.get(iso3)
    return c.region if c else ""


# --- World Bank WDI ---------------------------------------------------------
WORLD_BANK_BASE = "https://api.worldbank.org/v2"

# Broad age-structure indicators (metric id -> (WB indicator, unit)).
BROAD_INDICATORS: dict[str, tuple[str, str]] = {
    "pop_share_0_14_pct": ("SP.POP.0014.TO.ZS", "percent of total population"),
    "pop_share_15_64_pct": ("SP.POP.1564.TO.ZS", "percent of total population"),
    "pop_share_65plus_pct": ("SP.POP.65UP.TO.ZS", "percent of total population"),
    "old_age_dependency_ratio": ("SP.POP.DPND.OL", "per 100 working-age (15-64)"),
    "child_dependency_ratio": ("SP.POP.DPND.YG", "per 100 working-age (15-64)"),
}

# 5-year age bands: WB code suffix -> (label, midpoint age used for the median derivation).
# The open-ended top band 80+ has no true midpoint; 82.5 is a documented convention.
AGE_BANDS: list[tuple[str, str, float]] = [
    ("0004", "0-4", 2.5),
    ("0509", "5-9", 7.5),
    ("1014", "10-14", 12.5),
    ("1519", "15-19", 17.5),
    ("2024", "20-24", 22.5),
    ("2529", "25-29", 27.5),
    ("3034", "30-34", 32.5),
    ("3539", "35-39", 37.5),
    ("4044", "40-44", 42.5),
    ("4549", "45-49", 47.5),
    ("5054", "50-54", 52.5),
    ("5559", "55-59", 57.5),
    ("6064", "60-64", 62.5),
    ("6569", "65-69", 67.5),
    ("7074", "70-74", 72.5),
    ("7579", "75-79", 77.5),
    ("80UP", "80+", 82.5),
]
BAND_WIDTH_YEARS = 5.0
# Ordered band labels (young -> old), for pyramids and the median computation.
BAND_ORDER: list[str] = [label for _, label, _ in AGE_BANDS]

# Sexes for the 5-year-band counts (WB indicator suffix -> label).
SEXES: dict[str, str] = {"MA": "male", "FE": "female"}


# --- Metrics -----------------------------------------------------------------
class Metric(NamedTuple):
    id: str
    label: str
    unit: str
    family: str        # structure | dependency | pyramid | derived
    higher_is_better: bool | None
    description: str


METRICS: dict[str, Metric] = {
    "pop_share_0_14_pct": Metric(
        "pop_share_0_14_pct", "Population aged 0-14 (% of total)", "percent",
        "structure", None,
        "Share of the total population aged 0-14 (World Bank WDI).",
    ),
    "pop_share_15_64_pct": Metric(
        "pop_share_15_64_pct", "Population aged 15-64 (% of total)", "percent",
        "structure", None,
        "Share of the total population of working age, 15-64 (World Bank WDI).",
    ),
    "pop_share_65plus_pct": Metric(
        "pop_share_65plus_pct", "Population aged 65+ (% of total)", "percent",
        "structure", None,
        "Share of the total population aged 65 and above (World Bank WDI).",
    ),
    "old_age_dependency_ratio": Metric(
        "old_age_dependency_ratio", "Old-age dependency ratio", "ratio",
        "dependency", None,
        "People aged 65+ per 100 people of working age (15-64) (World Bank WDI).",
    ),
    "child_dependency_ratio": Metric(
        "child_dependency_ratio", "Child dependency ratio", "ratio",
        "dependency", None,
        "People aged 0-14 per 100 people of working age (15-64) (World Bank WDI).",
    ),
    "pop_band_share_pct": Metric(
        "pop_band_share_pct", "Population share by 5-year age band", "percent",
        "pyramid", None,
        "Share of the total population in a 5-year age band, by sex (World Bank WDI).",
    ),
    "median_age_years": Metric(
        "median_age_years", "Median age (derived)", "years",
        "derived", None,
        "Median age DERIVED from the published 5-year age-band counts by linear "
        "interpolation within the median band; not a directly-published figure.",
    ),
}

CAVEATS: dict[str, str] = {
    "pop_share_0_14_pct": "Shares of 0-14 / 15-64 / 65+ sum to ~100% (rounding aside).",
    "pop_share_65plus_pct": "The headline population-ageing indicator.",
    "old_age_dependency_ratio": (
        "Ratio of 65+ to the 15-64 working-age population, x100; a fiscal-pressure proxy."
    ),
    "pop_band_share_pct": (
        "5-year-band shares by sex; the open-ended top band is 80+ (no upper bound)."
    ),
    "median_age_years": (
        "DERIVED, not published: linear interpolation of the cumulative population "
        "distribution within the band containing the 50th percentile. The open-ended "
        "80+ band is treated as 80-85 for interpolation; reproducible from the WB counts."
    ),
}


# --- Citations (proper bibliographic form; the organisations that collected the data) ---
# Access date recorded for the live pulls performed while building this section.
ACCESS_DATE = "2026-07-03"

CITATIONS: dict[str, str] = {
    "un_wpp": (
        "United Nations, Department of Economic and Social Affairs, Population Division "
        "(2024). World Population Prospects 2024. New York: United Nations. "
        "https://population.un.org/wpp/ (data collector / original source)."
    ),
    "world_bank_wdi": (
        "World Bank (2025). World Development Indicators. Washington, DC: The World Bank. "
        "https://databank.worldbank.org/source/world-development-indicators. Retrieved "
        f"{ACCESS_DATE} via the World Bank API ({WORLD_BANK_BASE}), indicators SP.POP.* "
        "(age structure, dependency ratios and 5-year age-sex population). Age/sex bands "
        "are World Bank staff estimates using the UN Population Division's World "
        "Population Prospects."
    ),
}

# Short attribution stamped on every output row's ``source`` field.
SOURCE_WB = "World Bank WDI (UN World Population Prospects)"
SOURCE_WB_DERIVED = "World Bank WDI (derived: median from 5-year age bands)"

# One-line proper citation for figure source-notes.
FIGURE_SOURCE_NOTE = (
    "Data: UN DESA Population Division, World Population Prospects 2024, via the World "
    f"Bank World Development Indicators (SP.POP.*). Accessed {ACCESS_DATE}."
)


def variant_key(metric: str, age_band: str, sex: str) -> str:
    """Stable wide-table column key for a metric variant.

    Non-pyramid metrics (no band/sex) return the bare metric id; pyramid rows return
    e.g. ``pop_band_share_pct__40-44__female``.
    """
    if not age_band and not sex:
        return metric
    return f"{metric}__{age_band}__{sex}"


# --- Paths ------------------------------------------------------------------
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PKG_DIR)
DATA_DIR = os.path.join(ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")

MANUAL_CSV = os.path.join(RAW_DIR, "manual_age.csv")
