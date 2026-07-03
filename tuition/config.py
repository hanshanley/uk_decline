"""Static configuration: country tables, regions, sources, paths, fallback rates.

The authoritative tuition figures live in ``data/raw/manual_tuition.csv`` (each row
carries its own ``source`` + ``year``). Currency conversion (nominal FX and PPP) is
pulled live from the World Bank API by :mod:`tuition.rates`; the ``FALLBACK_*`` tables
below are only used when the network is unavailable (e.g. offline unit tests).
"""

from __future__ import annotations

import os
from typing import NamedTuple

# --- Regions ----------------------------------------------------------------
UK = "UK"
EU = "EU"
US = "US"

# A four-year degree = annual tuition x this factor. UK/most EU bachelor's are
# nominally 3 years, so this is a normalized comparison (documented in README).
DEGREE_YEARS = 4


class Country(NamedTuple):
    name: str
    iso3: str          # World Bank / ISO 3166-1 alpha-3
    iso2: str          # ISO 3166-1 alpha-2
    currency: str      # ISO 4217
    region: str        # UK / EU / US


# EU-27 member states (domestic / in-country tuition applies). Croatia adopted the
# euro in 2023; Bulgaria still uses the lev (BGN) as of 2024.
EU27: list[Country] = [
    Country("Austria", "AUT", "AT", "EUR", EU),
    Country("Belgium", "BEL", "BE", "EUR", EU),
    Country("Bulgaria", "BGR", "BG", "BGN", EU),
    Country("Croatia", "HRV", "HR", "EUR", EU),
    Country("Cyprus", "CYP", "CY", "EUR", EU),
    Country("Czechia", "CZE", "CZ", "CZK", EU),
    Country("Denmark", "DNK", "DK", "DKK", EU),
    Country("Estonia", "EST", "EE", "EUR", EU),
    Country("Finland", "FIN", "FI", "EUR", EU),
    Country("France", "FRA", "FR", "EUR", EU),
    Country("Germany", "DEU", "DE", "EUR", EU),
    Country("Greece", "GRC", "GR", "EUR", EU),
    Country("Hungary", "HUN", "HU", "HUF", EU),
    Country("Ireland", "IRL", "IE", "EUR", EU),
    Country("Italy", "ITA", "IT", "EUR", EU),
    Country("Latvia", "LVA", "LV", "EUR", EU),
    Country("Lithuania", "LTU", "LT", "EUR", EU),
    Country("Luxembourg", "LUX", "LU", "EUR", EU),
    Country("Malta", "MLT", "MT", "EUR", EU),
    Country("Netherlands", "NLD", "NL", "EUR", EU),
    Country("Poland", "POL", "PL", "PLN", EU),
    Country("Portugal", "PRT", "PT", "EUR", EU),
    Country("Romania", "ROU", "RO", "RON", EU),
    Country("Slovakia", "SVK", "SK", "EUR", EU),
    Country("Slovenia", "SVN", "SI", "EUR", EU),
    Country("Spain", "ESP", "ES", "EUR", EU),
    Country("Sweden", "SWE", "SE", "SEK", EU),
]

UK_COUNTRY = Country("United Kingdom", "GBR", "GB", "GBP", UK)
US_COUNTRY = Country("United States", "USA", "US", "USD", US)

ALL_COUNTRIES: list[Country] = [*EU27, UK_COUNTRY, US_COUNTRY]
BY_ISO3: dict[str, Country] = {c.iso3: c for c in ALL_COUNTRIES}

# Display labels for the three comparison regions (shared by analyze + plotting).
REGION_LABELS: dict[str, str] = {UK: "UK", EU: "EU-27", US: "US"}


def is_primary(row: dict) -> bool:
    """True if a tuition row is a headline per-country figure.

    Treats an explicit ``"1"`` or a blank/absent ``include_primary`` as primary, and
    ``"0"`` (reference rows: US private nonprofit, UK Scotland) as excluded.
    """
    return str(row.get("include_primary", "1")).strip() in ("1", "")


def iso3_codes() -> list[str]:
    return [c.iso3 for c in ALL_COUNTRIES]


# --- Data sources -----------------------------------------------------------
# OECD "Education at a Glance" average annual tuition fees (Table C5): mostly
# published as Excel/PDF, with a best-effort SDMX attempt in fetch_oecd.py.
OECD_SDMX_BASE = "https://sdmx.oecd.org/public/rest/data"
OECD_TUITION_HINT = (
    "https://www.oecd.org/en/data/indicators/tuition-fees.html "
    "(Education at a Glance, Table C5.1 — annual tuition fees, bachelor's)"
)
# Eurostat/Eurydice "National Student Fee and Support Systems in European Higher
# Education" — the annual EU-27 first-cycle fee reference.
EURYDICE_HINT = (
    "https://eurydice.eacea.ec.europa.eu/publications/"
    "national-student-fee-and-support-systems-european-higher-education-202425"
)
WORLD_BANK_BASE = "https://api.worldbank.org/v2"
WB_FX_INDICATOR = "PA.NUS.FCRF"   # official exchange rate, LCU per US$ (period avg)
WB_PPP_INDICATOR = "PA.NUS.PPP"   # PPP conversion factor, GDP, LCU per international $
WB_CPI_INDICATOR = "FP.CPI.TOTL"  # consumer price index (for real-terms deflation)

# --- Paths ------------------------------------------------------------------
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PKG_DIR)
DATA_DIR = os.path.join(ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")  # generated figures

MANUAL_CSV = os.path.join(RAW_DIR, "manual_tuition.csv")
HISTORY_MANUAL_CSV = os.path.join(RAW_DIR, "tuition_history_manual.csv")
NCES_CSV = os.path.join(RAW_DIR, "nces_tuition_public4yr.csv")
OECD_CSV = os.path.join(RAW_DIR, "oecd_tuition.csv")
EUROSTAT_CSV = os.path.join(RAW_DIR, "eurostat_tuition.csv")
RATES_CSV = os.path.join(RAW_DIR, "wb_rates.csv")

TUITION_BY_COUNTRY_CSV = os.path.join(PROCESSED_DIR, "tuition_by_country.csv")
SUMMARY_CSV = os.path.join(PROCESSED_DIR, "summary.csv")
HISTORY_OUT_CSV = os.path.join(PROCESSED_DIR, "tuition_history.csv")

# Real-terms base year (matches the NCES constant-dollar column: constant 2022-23 $).
REAL_BASE_YEAR = 2022

# --- Fallback conversion rates (offline only) -------------------------------
# LCU per US$ (nominal, ~2024 annual averages). Used only if World Bank fetch fails.
FALLBACK_FX: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.924,
    "GBP": 0.782,
    "BGN": 1.808,
    "CZK": 23.20,
    "DKK": 6.90,
    "HUF": 365.0,
    "PLN": 3.98,
    "RON": 4.60,
    "SEK": 10.60,
}
# LCU per international $ (PPP, ~2023 World Bank PA.NUS.PPP). Offline fallback only.
FALLBACK_PPP: dict[str, float] = {
    "USD": 1.00,
    "EUR": 0.72,
    "GBP": 0.70,
    "BGN": 0.70,
    "CZK": 13.0,
    "DKK": 6.60,
    "HUF": 155.0,
    "PLN": 1.80,
    "RON": 1.75,
    "SEK": 8.80,
}
