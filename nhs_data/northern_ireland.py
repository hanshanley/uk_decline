"""Northern Ireland NHS waiting-time statistics from Department of Health files.

The Department of Health (NI) publishes quarterly spreadsheets rather than an
API.  For the headline ``rtt_waiting_list_total`` this module uses the total
number of patients waiting for a first consultant-led outpatient appointment:
NI publishes outpatient and inpatient/day-case waits separately, so the
outpatient total is the most stable elective-waiting-list headline available
for the canonical UK-wide metric.

Diagnostic waits use the spreadsheet's ``> 6`` week bands (computed as Total
minus ``0 - 6 weeks``) for ``diagnostics_6week_breach_pct``.
"""

from __future__ import annotations

import datetime as dt
import html
import io
import re
import sys
import time
from functools import lru_cache
from urllib.parse import urljoin

import pandas as pd

from . import _http
from .metrics import make_row

NATION = "Northern Ireland"
NATION_CODE = "NIR"
SOURCE = "Department of Health (NI)"

ARTICLE_URLS = {
    "outpatient": "https://www.health-ni.gov.uk/articles/outpatient-waiting-times",
    "diagnostics": "https://www.health-ni.gov.uk/articles/diagnostic-waiting-times",
    "emergency": "https://www.health-ni.gov.uk/articles/emergency-care-waiting-times",
    "cancer": "https://www.health-ni.gov.uk/articles/cancer-waiting-times",
}

OUTPATIENT_PUBLICATION_PAGE = (
    "https://www.health-ni.gov.uk/publications/"
    "northern-ireland-waiting-time-statistics-outpatient-waiting-times-"
    "march-2026"
)
DIAGNOSTICS_PUBLICATION_PAGE = (
    "https://www.health-ni.gov.uk/publications/"
    "northern-ireland-waiting-time-statistics-diagnostic-waiting-times-"
    "march-2026"
)
EMERGENCY_OPEN_DATA_URL = (
    "https://admin.opendatani.gov.uk/en/dataset/emergency-care-waiting-times"
)
CANCER_62DAY_PAGE = (
    "https://www.health-ni.gov.uk/publications/"
    "northern-ireland-waiting-time-statistics-cancer-waiting-times-"
    "january-march-2025"
)

ATTACHMENT_RE = re.compile(
    r"href=[\"']([^\"']+\.(?:xlsx|xls|ods|csv)(?:\?[^\"']*)?)[\"']",
    re.IGNORECASE,
)
LINK_RE = re.compile(
    r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_LAST_HEALTH_NI_REQUEST = 0.0
_HEALTH_NI_DELAY_SECONDS = 10.0


def _warn(metric: str, exc: Exception) -> None:
    print(f"warning: Northern Ireland {metric} failed: {exc}", file=sys.stderr)


def _polite_pause(url: str) -> None:
    if "health-ni.gov.uk" not in url.lower():
        return
    global _LAST_HEALTH_NI_REQUEST
    elapsed = time.monotonic() - _LAST_HEALTH_NI_REQUEST
    if elapsed < _HEALTH_NI_DELAY_SECONDS:
        time.sleep(_HEALTH_NI_DELAY_SECONDS - elapsed)
    _LAST_HEALTH_NI_REQUEST = time.monotonic()


def _default_years(
    start_year: int | None, end_year: int | None
) -> tuple[int, int]:
    end = end_year if end_year is not None else dt.date.today().year
    start = start_year if start_year is not None else end - 9
    return start, end


@lru_cache(maxsize=None)
def _html(url: str) -> str:
    last_resp = None
    for attempt in range(5):
        _polite_pause(url)
        resp = _http.session().get(url, timeout=60)
        last_resp = resp
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            delay = (
                int(retry_after)
                if retry_after and retry_after.isdigit() and int(retry_after) > 0
                else 5 * 2**attempt
            )
            time.sleep(min(delay, 60))
            continue
        resp.raise_for_status()
        return html.unescape(resp.text)
    if last_resp is not None:
        last_resp.raise_for_status()
    raise RuntimeError(f"failed to fetch {url}")


def _publication_pages(article_url: str, slug_fragment: str) -> list[str]:
    pages: list[str] = []
    for match in LINK_RE.finditer(_html(article_url)):
        href = urljoin(article_url, match.group(1))
        if "/publications/" not in href or slug_fragment not in href:
            continue
        if href not in pages:
            pages.append(href)
    return pages


def _attachment_urls(page_url: str) -> list[str]:
    urls: list[str] = []
    for match in ATTACHMENT_RE.finditer(_html(page_url)):
        url = urljoin(page_url, match.group(1))
        if url not in urls:
            urls.append(url)
    return urls


def _find_attachment(
    article_url: str,
    slug_fragment: str,
    include: tuple[str, ...],
    exclude: tuple[str, ...] = (),
    fallback_pages: tuple[str, ...] = (),
) -> tuple[str, str]:
    pages = _publication_pages(article_url, slug_fragment) + list(fallback_pages)
    if not pages:
        pages = [article_url, *fallback_pages]

    for page in pages:
        for url in _attachment_urls(page):
            lower = url.lower()
            if all(term in lower for term in include) and not any(
                term in lower for term in exclude
            ):
                return url, page

    raise RuntimeError(f"no matching attachment found for {slug_fragment}")


def _find_attachment_on_pages(
    pages: tuple[str, ...],
    include: tuple[str, ...],
    exclude: tuple[str, ...] = (),
) -> tuple[str, str]:
    for page in pages:
        for url in _attachment_urls(page):
            lower = url.lower()
            if all(term in lower for term in include) and not any(
                term in lower for term in exclude
            ):
                return url, page
    raise RuntimeError("no matching attachment found")


def _number_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _dates(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except TypeError:
        return pd.to_datetime(series, errors="coerce")


def _month_dates(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip()
    dates = pd.to_datetime(values, errors="coerce", format="%B %Y")
    if dates.isna().any():
        dates = dates.fillna(pd.to_datetime(values, errors="coerce"))
    return dates + pd.offsets.MonthEnd(0)


def _month_code_dates(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip()
    dates = pd.to_datetime(values, errors="coerce", format="%b-%y")
    return dates + pd.offsets.MonthEnd(0)


def _period_month(date: pd.Timestamp) -> str:
    return f"{date.year:04d}-{date.month:02d}"


def _period_quarter(date: pd.Timestamp) -> str:
    quarter = (date.month - 1) // 3 + 1
    return f"{date.year:04d}-Q{quarter}"


def _make_metric_row(date: pd.Timestamp, metric: str, value: float) -> dict:
    period = (
        _period_month(date)
        if metric in {"ae_4hr_pct", "cancer_62day_pct"}
        else _period_quarter(date)
    )
    return make_row(
        NATION,
        NATION_CODE,
        period,
        date.date().isoformat(),
        metric,
        value,
        SOURCE,
    )


@lru_cache(maxsize=None)
def _workbook(url: str) -> dict[str, pd.DataFrame]:
    _polite_pause(url)
    data = _http.get_excel(url, sheet_name=None)
    if not isinstance(data, dict):
        raise RuntimeError(f"expected workbook with sheets: {url}")
    return data


def _fetch_outpatient_waiting_list() -> list[dict]:
    url, _page = _find_attachment_on_pages(
        (OUTPATIENT_PUBLICATION_PAGE,),
        include=("outpatients",),
        exclude=("icats",),
    )
    frames = []
    for sheet_name, df in _workbook(url).items():
        if "Quarter Ending" not in df.columns or "Total Waiting" not in df.columns:
            continue
        frame = df[["Quarter Ending", "Total Waiting"]].copy()
        frame["sheet"] = sheet_name
        frames.append(frame)
    if not frames:
        raise RuntimeError("outpatient workbook has no Total Waiting sheets")

    df = pd.concat(frames, ignore_index=True)
    df["date"] = _dates(df["Quarter Ending"])
    df["value"] = _number_series(df["Total Waiting"])
    grouped = (
        df.dropna(subset=["date", "value"])
        .groupby("date", as_index=False)["value"]
        .sum()
        .sort_values("date")
    )
    return [
        _make_metric_row(row.date, "rtt_waiting_list_total", row.value)
        for row in grouped.itertuples(index=False)
        if row.value > 0
    ]


def _fetch_emergency_4hr() -> list[dict]:
    url = next(
        (
            candidate
            for candidate in _attachment_urls(EMERGENCY_OPEN_DATA_URL)
            if "ecwt" in candidate.lower() and candidate.lower().endswith(".csv")
        ),
        None,
    )
    if url is None:
        raise RuntimeError("no emergency care CSV attachment found")
    _polite_pause(url)
    csv_bytes = _http.get_bytes(url)
    df = pd.read_csv(io.BytesIO(csv_bytes))
    required = {"MthAndYrCode", "FourAndUnder_sum", "Total_sum"}
    if not required.issubset(df.columns):
        raise RuntimeError("emergency CSV missing expected columns")

    df["date"] = _month_code_dates(df["MthAndYrCode"])
    df["within_4hr"] = _number_series(df["FourAndUnder_sum"])
    df["total"] = _number_series(df["Total_sum"])
    grouped = (
        df.dropna(subset=["date", "within_4hr", "total"])
        .groupby("date", as_index=False)[["within_4hr", "total"]]
        .sum()
        .sort_values("date")
    )
    grouped = grouped[grouped["total"] > 0]
    grouped["value"] = grouped["within_4hr"] / grouped["total"] * 100
    return [
        _make_metric_row(row.date, "ae_4hr_pct", row.value)
        for row in grouped.itertuples(index=False)
    ]


def _fetch_cancer_62day() -> list[dict]:
    sheet = "62 Day Wait by HSC Trust"
    workbook = None
    for page in (CANCER_62DAY_PAGE,):
        for url in _attachment_urls(page):
            lower = url.lower()
            if "cwt" not in lower or "icd10" in lower:
                continue
            candidate = _workbook(url)
            if sheet in candidate:
                workbook = candidate
                break
        if workbook is not None:
            break
    if workbook is None:
        raise RuntimeError(f"no cancer workbook with {sheet!r}")
    if sheet not in workbook:
        raise RuntimeError(f"cancer workbook missing {sheet!r}")
    df = workbook[sheet]
    required = {
        "Treatment Month",
        "Patients Treated Within 62 Days",
        "Total Patients Treated",
    }
    if not required.issubset(df.columns):
        raise RuntimeError("cancer workbook missing expected columns")

    df["date"] = _month_dates(df["Treatment Month"])
    df["within"] = _number_series(df["Patients Treated Within 62 Days"])
    df["total"] = _number_series(df["Total Patients Treated"])
    grouped = (
        df.dropna(subset=["date", "within", "total"])
        .groupby("date", as_index=False)[["within", "total"]]
        .sum()
        .sort_values("date")
    )
    grouped = grouped[grouped["total"] > 0]
    grouped["value"] = grouped["within"] / grouped["total"] * 100
    return [
        _make_metric_row(row.date, "cancer_62day_pct", row.value)
        for row in grouped.itertuples(index=False)
    ]


def _fetch_diagnostics_6week_breach() -> list[dict]:
    url, _page = _find_attachment_on_pages(
        (DIAGNOSTICS_PUBLICATION_PAGE,),
        include=("diagnostic-waiting-times",),
        exclude=("reporting-turnaround",),
    )
    frames = []
    for sheet_name, df in _workbook(url).items():
        if not {"Quarter Ending", "0 - 6 weeks", "Total"}.issubset(df.columns):
            continue
        frame = df[["Quarter Ending", "0 - 6 weeks", "Total"]].copy()
        frame["sheet"] = sheet_name
        frames.append(frame)
    if not frames:
        raise RuntimeError("diagnostic workbook has no waiting-time sheets")

    df = pd.concat(frames, ignore_index=True)
    df["date"] = _dates(df["Quarter Ending"])
    df["within_6w"] = _number_series(df["0 - 6 weeks"])
    df["total"] = _number_series(df["Total"])
    grouped = (
        df.dropna(subset=["date", "within_6w", "total"])
        .groupby("date", as_index=False)[["within_6w", "total"]]
        .sum()
        .sort_values("date")
    )
    grouped = grouped[grouped["total"] > 0]
    grouped["value"] = (
        (grouped["total"] - grouped["within_6w"]) / grouped["total"] * 100
    )
    return [
        _make_metric_row(row.date, "diagnostics_6week_breach_pct", row.value)
        for row in grouped.itertuples(index=False)
    ]


def _filter_years(rows: list[dict], start_year: int, end_year: int) -> list[dict]:
    out = []
    for row in rows:
        year = int(row["date"][:4])
        if start_year <= year <= end_year:
            out.append(row)
    return out


def fetch(start_year: int | None = None, end_year: int | None = None) -> list[dict]:
    """Fetch Northern Ireland waiting-time rows filtered by calendar year."""
    start, end = _default_years(start_year, end_year)
    rows: list[dict] = []
    fetchers = (
        ("rtt_waiting_list_total", _fetch_outpatient_waiting_list),
        ("ae_4hr_pct", _fetch_emergency_4hr),
        ("cancer_62day_pct", _fetch_cancer_62day),
        ("diagnostics_6week_breach_pct", _fetch_diagnostics_6week_breach),
    )
    for metric, fetcher in fetchers:
        try:
            rows.extend(fetcher())
        except Exception as exc:  # pragma: no cover - live source resilience
            _warn(metric, exc)

    return sorted(
        _filter_years(rows, start, end),
        key=lambda row: (row["date"], row["metric"]),
    )
