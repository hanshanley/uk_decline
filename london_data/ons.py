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
RELEASE_SEARCH_URL = "https://api.beta.ons.gov.uk/v1/search"

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


def _edition_links(html: str) -> list[tuple[int, str]]:
    """Return ``[(end_year, href), ...]`` for dated regional-GDP workbook links."""
    links: list[tuple[int, str]] = []
    hrefs = re.findall(r'href="(/file\?uri=[^"]+\.xlsx)"', html, flags=re.I)
    for href in hrefs:
        m = re.search(r"/1998to(\d{4})/", href)
        if m is not None:
            links.append((int(m.group(1)), href))
    return links


def latest_published_year(page_url: str = DATASET_PAGE, timeout: int = 60) -> int:
    """Return the latest end-year currently published on the ONS dataset page."""
    _ensure_ons_host(page_url)
    resp = _get(page_url, timeout=timeout)
    links = _edition_links(resp.text)
    if not links:
        raise RuntimeError("ONS regional-GDP page contains no dated workbook editions")
    return max(year for year, _href in links)


def next_release(target_year: int, timeout: int = 60) -> dict | None:
    """Return the ONS release-calendar entry for ``1998 to target_year``, if scheduled.

    This queries the official ONS search API rather than hard-coding a date. Returned keys
    are ``title``, ``release_date`` and ``uri``.
    """
    params = {
        "q": f"Regional economic activity by gross domestic product UK 1998 to {target_year}",
        "content_type": "release",
        "limit": 20,
    }
    resp = requests.get(RELEASE_SEARCH_URL, params=params, timeout=timeout,
                        headers={"User-Agent": _USER_AGENT})
    resp.raise_for_status()
    needle = f"1998 to {target_year}"
    for item in resp.json().get("items", []):
        title = str(item.get("title", ""))
        if needle in title:
            return {
                "title": title,
                "release_date": item.get("release_date"),
                "uri": item.get("uri"),
            }
    return None


def availability_status(target_year: int = 2024, timeout: int = 60) -> dict:
    """Return official publication status for a requested regional-GDP end-year."""
    latest = latest_published_year(timeout=timeout)
    return {
        "latest_published_year": latest,
        "target_year": target_year,
        "available": latest >= target_year,
        "next_release": None if latest >= target_year else next_release(target_year, timeout),
    }


def resolve_xlsx_url(page_url: str = DATASET_PAGE, timeout: int = 60) -> str:
    """Return the newest ``.xlsx`` edition linked on the ONS dataset page.

    Falls back to :data:`PINNED_XLSX` if the page can't be scraped or has no dated edition.
    Editions are named ``.../1998toYYYY/...`` so we pick the highest end year; hrefs that
    don't carry an edition year are ignored (they can't win over the pinned fallback).
    """
    _ensure_ons_host(page_url)
    try:
        resp = _get(page_url, timeout=timeout)
        links = _edition_links(resp.text)
        if links:
            _year, best = max(links)
            return f"https://{ONS_HOST}{best}"
    except Exception as exc:  # pragma: no cover - network/parse failure path
        print(f"[london_data] could not resolve latest xlsx ({exc}); using pinned URL.")
    return PINNED_XLSX


def _get(url: str, timeout: int) -> requests.Response:
    """GET with redirects disabled, validating the ONS host at every hop (anti-SSRF).

    Following redirects automatically would fetch the redirect target *before* the host
    could be re-checked, so we resolve hops manually and reject any non-ONS ``Location``.
    """
    for _ in range(5):
        _ensure_ons_host(url)
        resp = requests.get(url, timeout=timeout, allow_redirects=False,
                            headers={"User-Agent": _USER_AGENT})
        if resp.is_redirect or resp.is_permanent_redirect:
            url = requests.compat.urljoin(url, resp.headers["Location"])
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"too many redirects fetching {url!r}")


def download_workbook(url: str | None = None, timeout: int = 120) -> dict:
    """Download the ONS regional-GDP workbook -> ``{sheet_name: DataFrame}``.

    Only the two sheets we use (GDP and GDP-per-head) are parsed.
    """
    url = url or resolve_xlsx_url()
    resp = _get(url, timeout=timeout)
    return pd.read_excel(io.BytesIO(resp.content), header=None,
                         sheet_name=[_SHEET_GDP, _SHEET_GDP_PER_HEAD])


def _to_float(value) -> float | None:
    """Parse an ONS cell to float, tolerating footnote/suppression markers ([r], :, -)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_by_code(sheet: pd.DataFrame, code: str) -> tuple[list[int], list[float]]:
    """Return (years, values) for the region whose ITL code == ``code``.

    Years and their values are anchored to the *same* column indices (the columns whose
    header cell is a numeric year), so a blank/merged header cell can't misalign them.
    """
    header = sheet.iloc[_HEADER_ROW]
    year_cols = [j for j in range(_FIRST_YEAR_COL, sheet.shape[1])
                 if _to_float(header.iloc[j]) is not None]
    years = [int(_to_float(header.iloc[j])) for j in year_cols]
    for i in range(_HEADER_ROW + 1, sheet.shape[0]):
        if str(sheet.iloc[i, _CODE_COL]).strip() == code:
            vals = [_to_float(sheet.iloc[i, j]) for j in year_cols]
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
    uk_per_head = dict(zip(yrs_uk_ph, uk_ph))
    ldn_per_head = dict(zip(yrs_ldn_ph, ldn_ph))

    rows: list[dict] = []

    def add(region, year, metric, value, unit):
        if value is None:
            return  # skip a year where an ONS cell was blank/suppressed
        rows.append({"region": region, "year": year, "metric": metric,
                     "value": round(value, 4), "unit": unit, "source": SOURCE})

    def ratio(num, den):
        return 100.0 * num / den if (num is not None and den) else None

    for y in yrs_uk:
        add("United Kingdom", y, "gdp_current_gbp_m", uk[y], "GBP million")
        add("London", y, "gdp_current_gbp_m", ldn[y], "GBP million")
        add("London", y, "share_of_uk_gdp_pct", ratio(ldn[y], uk[y]), "percent")
        add("United Kingdom", y, "gdp_per_head_gbp", uk_per_head[y], "GBP per head")
        add("London", y, "gdp_per_head_gbp", ldn_per_head[y], "GBP per head")
        add("London", y, "gdp_per_head_index_uk100",
            ratio(ldn_per_head[y], uk_per_head[y]), "index, UK=100")

    rows.sort(key=lambda r: (r["metric"], r["region"], r["year"]))
    return rows
