"""Fetch and reshape HM Treasury's long-run public-spending tables.

The analysis uses the annual Public Spending Statistics (PSS) Chapter 4 workbook:

* Table 4.1: public sector current expenditure, net investment and Total Managed
  Expenditure (TME), including real-terms and percentage-of-GDP series.
* Table 4.3: real public expenditure on services by function.

All values are official outturns. The latest July release is resolved from GOV.UK
rather than inferred or manually entered.
"""

from __future__ import annotations

import io
import re
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests

COLLECTION_URL = "https://www.gov.uk/government/collections/national-statistics-release"
PINNED_RELEASE_URL = (
    "https://www.gov.uk/government/statistics/"
    "public-spending-statistics-release-july-2026"
)
SOURCE = "HM Treasury, Public Spending Statistics, July 2026, Tables 4.1 and 4.3"
HISTORICAL_WORKBOOK_URL = (
    "https://assets.publishing.service.gov.uk/media/"
    "5a7c5e0eed915d6969f4461a/pesa_2012_tables_chapter4.xlsx"
)
HISTORICAL_SOURCE = (
    "HM Treasury, Public Expenditure Statistical Analyses 2012, Table 4.3"
)
_USER_AGENT = "uk_decline/0.1 (UK public spending research)"
_FY_RE = re.compile(r"^\d{4}-\d{2}$")
_ALLOWED_HOSTS = {"www.gov.uk", "assets.publishing.service.gov.uk"}

AGGREGATE_COLUMNS = {
    "public_sector_current_expenditure_real": (3, "GBP billion, real"),
    "public_sector_net_investment_real": (9, "GBP billion, real"),
    "public_sector_net_investment_pct_gdp": (10, "percent of GDP"),
    "total_managed_expenditure_real": (13, "GBP billion, real"),
    "total_managed_expenditure_pct_gdp": (14, "percent of GDP"),
}

FUNCTIONS = {
    "General public services": "general_public_services",
    "Defence": "defence",
    "Public order and safety": "public_order_safety",
    "Economic affairs": "economic_affairs",
    "Environment protection": "environment_protection",
    "Housing and community amenities": "housing_community",
    "Health": "health",
    "Recreation, culture and religion": "recreation_culture",
    "Education": "education",
    "Social protection": "social_protection",
}

ROW_FIELDS = [
    "financial_year",
    "year",
    "metric",
    "category",
    "value",
    "unit",
    "source",
]


def _ensure_allowed_host(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


def _get(url: str, timeout: int = 60) -> requests.Response:
    """Fetch a GOV.UK resource while validating every redirect target."""
    for _ in range(5):
        _ensure_allowed_host(url)
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
        )
        if response.is_redirect or response.is_permanent_redirect:
            url = urljoin(url, response.headers["Location"])
            continue
        response.raise_for_status()
        return response
    raise RuntimeError(f"too many redirects fetching {url!r}")


def _release_links(html: str) -> list[tuple[int, str]]:
    pattern = (
        r'href="([^"]*/government/statistics/'
        r'public-spending-statistics-release-july-(\d{4})[^"]*)"'
    )
    found: list[tuple[int, str]] = []
    for href, year in re.findall(pattern, html, flags=re.I):
        found.append((int(year), urljoin("https://www.gov.uk", href)))
    return found


def resolve_release_url(
    collection_url: str = COLLECTION_URL, timeout: int = 60
) -> str:
    """Return the newest annual July PSS release listed on GOV.UK."""
    try:
        links = _release_links(_get(collection_url, timeout).text)
        if links:
            return max(links)[1]
    except Exception as exc:  # pragma: no cover - network fallback
        print(f"[austerity_data] could not resolve latest release ({exc}); using pinned.")
    return PINNED_RELEASE_URL


def _chapter4_links(html: str) -> list[str]:
    hrefs = re.findall(r'href="([^"]+\.xlsx(?:\?[^"]*)?)"', html, flags=re.I)
    return [
        urljoin("https://www.gov.uk", href)
        for href in hrefs
        if re.search(r"chapter[_-]?4", href, flags=re.I)
    ]


def resolve_workbook_url(
    release_url: str | None = None, timeout: int = 60
) -> str:
    """Return the Chapter 4 workbook URL from the latest PSS release page."""
    release_url = release_url or resolve_release_url(timeout=timeout)
    links = _chapter4_links(_get(release_url, timeout).text)
    if not links:
        raise RuntimeError(f"no Chapter 4 workbook found at {release_url}")
    return links[0]


def download_workbook(
    url: str | None = None,
    historical_url: str = HISTORICAL_WORKBOOK_URL,
    timeout: int = 120,
) -> dict:
    """Download current PSS tables plus the historical functional-spending table."""
    url = url or resolve_workbook_url(timeout=timeout)
    response = _get(url, timeout)
    workbook = pd.read_excel(
        io.BytesIO(response.content),
        sheet_name=["4_1", "4_3"],
        header=None,
    )
    historical = _get(historical_url, timeout)
    workbook["historical_4_3"] = pd.read_excel(
        io.BytesIO(historical.content),
        sheet_name="TABLE 4.3",
        header=None,
    )
    return workbook


def fiscal_start(financial_year: str) -> int:
    """Return the starting calendar year from a label such as ``2010-11``."""
    if not _FY_RE.match(str(financial_year)):
        raise ValueError(f"invalid financial year: {financial_year!r}")
    return int(str(financial_year)[:4])


def _number(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if pd.notna(parsed) else None


def _row(
    financial_year: str,
    metric: str,
    category: str,
    value,
    unit: str,
    source: str = SOURCE,
) -> dict:
    return {
        "financial_year": financial_year,
        "year": fiscal_start(financial_year),
        "metric": metric,
        "category": category,
        "value": float(value),
        "unit": unit,
        "source": source,
    }


def parse_aggregates(sheet: pd.DataFrame) -> list[dict]:
    """Parse Table 4.1 into tidy aggregate spending and investment rows."""
    rows: list[dict] = []
    for i in range(sheet.shape[0]):
        financial_year = str(sheet.iloc[i, 1]).strip()
        if not _FY_RE.match(financial_year):
            continue
        for metric, (column, unit) in AGGREGATE_COLUMNS.items():
            value = _number(sheet.iloc[i, column])
            if value is not None:
                rows.append(_row(financial_year, metric, "United Kingdom", value, unit))
    if not rows:
        raise ValueError("Table 4.1 contained no fiscal-year rows")
    return rows


def _function_name(label: str) -> str | None:
    clean = re.sub(r"^\d+\.\s*", "", label).strip()
    clean = re.sub(r"\(\d+\)", "", clean).strip()
    return FUNCTIONS.get(clean)


def parse_functions(sheet: pd.DataFrame) -> list[dict]:
    """Parse high-level functional rows from real-terms Table 4.3."""
    year_columns: list[tuple[int, str]] = []
    for column in range(1, sheet.shape[1]):
        label = str(sheet.iloc[4, column]).strip()
        if _FY_RE.match(label):
            year_columns.append((column, label))
    if not year_columns:
        raise ValueError("Table 4.3 contained no fiscal-year columns")

    rows: list[dict] = []
    for i in range(5, sheet.shape[0]):
        label = str(sheet.iloc[i, 0]).strip()
        category = _function_name(label)
        if category is None:
            continue
        for column, financial_year in year_columns:
            value = _number(sheet.iloc[i, column])
            if value is not None:
                rows.append(
                    _row(
                        financial_year,
                        "functional_spending_real",
                        category,
                        value,
                        "GBP billion, real",
                    )
                )
    if not rows:
        raise ValueError("Table 4.3 contained no recognised functional spending rows")
    return rows


def parse_historical_functions(sheet: pd.DataFrame) -> list[dict]:
    """Parse PESA 2012 Table 4.3, which extends the function series to 1988-89.

    These rows retain their original 2011-12 price basis. Charts convert each
    vintage to an index relative to its own 2010-11 observation, avoiding a
    synthetic cash-level splice.
    """
    year_columns: list[tuple[int, str]] = []
    for column in range(2, sheet.shape[1]):
        label = str(sheet.iloc[4, column]).strip()
        if _FY_RE.match(label):
            year_columns.append((column, label))
    if not year_columns:
        raise ValueError("historical Table 4.3 contained no fiscal-year columns")

    rows: list[dict] = []
    for i in range(6, sheet.shape[0]):
        label = str(sheet.iloc[i, 1]).strip()
        category = _function_name(label)
        if category is None:
            continue
        for column, financial_year in year_columns:
            value = _number(sheet.iloc[i, column])
            if value is not None:
                rows.append(
                    _row(
                        financial_year,
                        "functional_spending_historical_real",
                        category,
                        value,
                        "GBP billion, real (2011-12 prices)",
                        HISTORICAL_SOURCE,
                    )
                )
    if not rows:
        raise ValueError("historical Table 4.3 contained no recognised function rows")
    return rows


def build_rows(workbook: dict | None = None) -> list[dict]:
    """Return a sorted tidy dataset from the official PSS workbook."""
    workbook = workbook or download_workbook()
    rows = parse_aggregates(workbook["4_1"]) + parse_functions(workbook["4_3"])
    if "historical_4_3" in workbook:
        rows += parse_historical_functions(workbook["historical_4_3"])
    rows.sort(key=lambda row: (row["metric"], row["category"], row["year"]))
    return rows
