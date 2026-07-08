"""Fetch and reshape ONS regional GDP into a tidy London-concentration table.

Source: **Office for National Statistics (ONS)**, *Regional economic activity by gross
domestic product, UK* — dataset "Regional gross domestic product: all ITL regions".
We use two current-price tables from the workbook:

  - **Table 5** — GDP at current market prices (£ million), by region.
  - **Table 7** — GDP per head at current market prices (£), by region.

From these we derive, for **London** (ITL1, ONS code ``TLI``) against the **UK** total:

  - ``share_of_uk_gdp_pct``      — London GDP / UK GDP x 100 (the concentration measure).
  - ``gdp_per_head_index_uk100`` — London GDP/head / UK GDP/head x 100 (UK = 100).

Both are **same-year ratios**: numerator and denominator share the same (current) price
base, so no inflation adjustment applies — deflation cancels top and bottom. The raw £
levels are also emitted for transparency.

Data vintage: the ONS annual ITL release currently ends at **2023** (regional annual GDP
lags ~18 months; there is no 2024 edition yet, and the timelier quarterly product excludes
Scotland/NI and is index-only, so it cannot extend these UK-wide, £-level metrics).
"""

from __future__ import annotations

import io
import re
from urllib.parse import urlsplit

import pandas as pd
import requests

ONS_HOST = "www.ons.gov.uk"
DATASET_PAGE = (
    "https://www.ons.gov.uk/economy/grossdomesticproductgdp/datasets/"
    "regionalgrossdomesticproductallnutslevelregions"
)
# Pinned latest edition (used if the dataset page can't be scraped). The resolver below
# prefers the newest edition actually listed on the page.
PINNED_XLSX = (
    "https://www.ons.gov.uk/file?uri=/economy/grossdomesticproductgdp/datasets/"
    "regionalgrossdomesticproductallnutslevelregions/1998to2023/"
    "regionalgrossdomesticproductgdpbyallinternationalterritoriallevelitlregions.xlsx"
)
SOURCE = ("Office for National Statistics (ONS), Regional economic activity by gross "
          "domestic product, UK: Regional GDP, all ITL regions (current market prices)")

LONDON_CODE = "TLI"   # London ITL1 (ONS geography code)
UK_CODE = "UK"
_SHEET_GDP = "Table 5"        # GDP at current market prices, £ million
_SHEET_GDP_PER_HEAD = "Table 7"  # GDP per head at current market prices, £
_HEADER_ROW = 1               # row holding year labels; data starts at row 2
_CODE_COL, _NAME_COL = 1, 2   # "ITL code", "Region name"
_FIRST_YEAR_COL = 3
_USER_AGENT = "uk_decline/0.1 (London GDP concentration research)"


def _ensure_ons_host(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not (host == ONS_HOST or host.endswith(".ons.gov.uk")):
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


def resolve_xlsx_url(page_url: str = DATASET_PAGE, timeout: int = 60) -> str:
    """Return the newest ``.xlsx`` edition linked on the ONS dataset page.

    Falls back to :data:`PINNED_XLSX` if the page can't be scraped. Editions are named
    ``.../1998toYYYY/...`` so we pick the highest end year.
    """
    _ensure_ons_host(page_url)
    try:
        resp = requests.get(page_url, timeout=timeout, headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
        hrefs = re.findall(r'href="(/file\?uri=[^"]+\.xlsx)"', resp.text, flags=re.I)
        best, best_year = None, -1
        for href in hrefs:
            m = re.search(r"/1998to(\d{4})/", href)
            year = int(m.group(1)) if m else 0
            if year > best_year:
                best, best_year = href, year
        if best:
            return f"https://{ONS_HOST}{best}"
    except Exception as exc:  # pragma: no cover - network/parse failure path
        print(f"[london_data] could not resolve latest xlsx ({exc}); using pinned URL.")
    return PINNED_XLSX


def download_workbook(url: str | None = None, timeout: int = 120) -> dict:
    """Download the ONS regional-GDP workbook -> ``{sheet_name: DataFrame}``."""
    url = url or resolve_xlsx_url()
    _ensure_ons_host(url)
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": _USER_AGENT})
    _ensure_ons_host(resp.url)
    resp.raise_for_status()
    return pd.read_excel(io.BytesIO(resp.content), sheet_name=None, header=None)


def _row_by_code(sheet: pd.DataFrame, code: str) -> tuple[list[int], list[float]]:
    """Return (years, values) for the region whose ITL code == ``code``."""
    years = [int(float(v)) for v in sheet.iloc[_HEADER_ROW, _FIRST_YEAR_COL:].tolist()
             if str(v) != "nan"]
    for i in range(_HEADER_ROW + 1, sheet.shape[0]):
        if str(sheet.iloc[i, _CODE_COL]).strip() == code:
            vals = [float(v) for v in sheet.iloc[i, _FIRST_YEAR_COL:_FIRST_YEAR_COL + len(years)]]
            return years, vals
    raise KeyError(f"ITL code {code!r} not found in sheet")


def build_rows(workbook: dict | None = None) -> list[dict]:
    """Return tidy rows for London vs UK: GDP levels, share, per-head, per-head index."""
    if workbook is None:
        workbook = download_workbook()
    gdp = workbook[_SHEET_GDP]
    per_head = workbook[_SHEET_GDP_PER_HEAD]

    yrs_uk, uk_gdp = _row_by_code(gdp, UK_CODE)
    yrs_ldn, ldn_gdp = _row_by_code(gdp, LONDON_CODE)
    yrs_uk_ph, uk_ph = _row_by_code(per_head, UK_CODE)
    yrs_ldn_ph, ldn_ph = _row_by_code(per_head, LONDON_CODE)
    if not (yrs_uk == yrs_ldn == yrs_uk_ph == yrs_ldn_ph):
        raise ValueError("year columns differ between London/UK or GDP/per-head tables")

    uk = dict(zip(yrs_uk, uk_gdp))
    ldn = dict(zip(yrs_ldn, ldn_gdp))
    uk_h = dict(zip(yrs_uk_ph, uk_ph))
    ldn_h = dict(zip(yrs_ldn_ph, ldn_ph))

    rows: list[dict] = []

    def add(region, year, metric, value, unit):
        rows.append({"region": region, "year": year, "metric": metric,
                     "value": round(value, 4), "unit": unit, "source": SOURCE})

    for y in yrs_uk:
        add("United Kingdom", y, "gdp_current_gbp_m", uk[y], "GBP million")
        add("London", y, "gdp_current_gbp_m", ldn[y], "GBP million")
        add("London", y, "share_of_uk_gdp_pct", 100.0 * ldn[y] / uk[y], "percent")
        add("United Kingdom", y, "gdp_per_head_gbp", uk_h[y], "GBP per head")
        add("London", y, "gdp_per_head_gbp", ldn_h[y], "GBP per head")
        add("London", y, "gdp_per_head_index_uk100", 100.0 * ldn_h[y] / uk_h[y], "index, UK=100")

    rows.sort(key=lambda r: (r["metric"], r["region"], r["year"]))
    return rows
