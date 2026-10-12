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

import html
import json
import math
import re
import time
from functools import lru_cache
from urllib.parse import urljoin

import pandas as pd
import requests

from . import _http, _util
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
    "june-2026"
)
DIAGNOSTICS_PUBLICATION_PAGE = (
    "https://www.health-ni.gov.uk/publications/"
    "northern-ireland-waiting-time-statistics-diagnostic-waiting-times-"
    "june-2026"
)
EMERGENCY_PUBLICATION_PAGE = (
    "https://www.health-ni.gov.uk/publications/"
    "northern-ireland-waiting-time-statistics-emergency-care-waiting-times-"
    "april-june-2026"
)
CANCER_62DAY_PAGE = (
    "https://www.health-ni.gov.uk/publications/"
    "northern-ireland-waiting-time-statistics-cancer-waiting-times-"
    "april-june-2026"
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
    _util.warn(NATION_CODE, metric, exc)


def _polite_pause(url: str) -> None:
    if "health-ni.gov.uk" not in url.lower():
        return
    global _LAST_HEALTH_NI_REQUEST
    elapsed = time.monotonic() - _LAST_HEALTH_NI_REQUEST
    if elapsed < _HEALTH_NI_DELAY_SECONDS:
        time.sleep(_HEALTH_NI_DELAY_SECONDS - elapsed)
    _LAST_HEALTH_NI_REQUEST = time.monotonic()


@lru_cache(maxsize=None)
def _html(url: str) -> str:
    _http._ensure_allowed_host(url)
    last_resp = None
    for attempt in range(5):
        _polite_pause(url)
        resp = _http.session().get(url, timeout=60)
        _http._ensure_allowed_host(resp.url)
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
        if not resp.text.strip():
            raise ValueError(f"empty publication page: {url}")
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


def _current_publication(metric: str, pinned: str) -> str:
    try:
        slug = {"diagnostics": "diagnostic", "emergency": "emergency-care"}.get(
            metric, metric
        )
        pages = _publication_pages(
            ARTICLE_URLS[metric], f"waiting-time-statistics-{slug}-waiting-times"
        )
        if not pages:
            raise ValueError("no current publication link found")
        # DoH lists the current publication before previous releases.
        return pages[0]
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        _warn(f"{metric} publication discovery; using pinned release", exc)
        return pinned


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


CORE_HSC_TRUSTS = frozenset(
    {"Belfast", "Northern", "South Eastern", "Southern", "Western"}
)


def _complete_quarters(df: pd.DataFrame, trust_col: str = "HSC Trust") -> set:
    """Observation dates where all five HSC trusts have usable data.

    NI migrated trusts to the 'encompass' patient-record system on a rolling
    schedule (South Eastern Nov 2023, Belfast Jun 2024, Northern Nov 2024,
    Southern & Western May 2025). A trust's data is briefly absent right after its
    migration, so that period's NI-wide total is incomplete. We keep only periods
    with all five trusts present, so every emitted figure is a complete,
    source-traceable total — incomplete quarters are dropped, never interpolated.
    """
    tmp = df.dropna(subset=["date"]).copy()
    tmp["_trust"] = tmp[trust_col].astype(str).str.strip()
    present = tmp.groupby("date")["_trust"].apply(set)
    return {q for q, trusts in present.items() if CORE_HSC_TRUSTS <= trusts}


def _fetch_outpatient_waiting_list() -> list[dict]:
    url, _page = _find_attachment_on_pages(
        (_current_publication("outpatient", OUTPATIENT_PUBLICATION_PAGE),),
        include=("outpatients",),
        exclude=("icats",),
    )
    frames = []
    for sheet_name, df in _workbook(url).items():
        if not {"Quarter Ending", "HSC Trust", "Total Waiting"}.issubset(df.columns):
            continue
        frame = df[["Quarter Ending", "HSC Trust", "Total Waiting"]].copy()
        frame["sheet"] = sheet_name
        frames.append(frame)
    if not frames:
        raise RuntimeError("outpatient workbook has no Total Waiting sheets")

    df = pd.concat(frames, ignore_index=True)
    df["date"] = _dates(df["Quarter Ending"])
    df["value"] = _number_series(df["Total Waiting"])
    df = df.dropna(subset=["date", "value"])
    complete = _complete_quarters(df, "HSC Trust")
    grouped = (
        df[df["date"].isin(complete)]
        .groupby("date", as_index=False)["value"]
        .sum()
        .sort_values("date")
    )
    return [
        _make_metric_row(row.date, "rtt_waiting_list_total", row.value)
        for row in grouped.itertuples(index=False)
        if row.value > 0
    ]


def _emergency_frame(document: str) -> pd.DataFrame:
    """Read the underlying count table in DoH's interactive HTML publication."""
    required = {
        "Date", "Trust", "Dept", "Type", "Under4hrs", "Between4to12hrs",
        "Over12hrs", "TotalAttendances", "PercentUnder4hrs",
    }
    frames = []
    for attrs, body in re.findall(
        r"<script\b([^>]*)>(.*?)</script>", document, re.IGNORECASE | re.DOTALL
    ):
        if not re.search(r"type=[\"']application/json[\"']", attrs, re.IGNORECASE):
            continue
        payload = json.loads(body)
        if not isinstance(payload, dict) or not isinstance(payload.get("x"), dict):
            continue
        widget = payload["x"]
        options = widget.get("options")
        if not isinstance(options, dict):
            continue
        definitions = options.get("columnDefs")
        if not isinstance(definitions, list):
            continue
        named = [
            spec for spec in definitions
            if isinstance(spec, dict) and isinstance(spec.get("name"), str)
            and "targets" in spec
        ]
        positions = {
            spec["name"]: spec["targets"] for spec in named
        }
        if not required <= positions.keys():
            continue
        data = widget.get("data")
        if len(positions) != len(named) or not isinstance(data, list) or any(
            not isinstance(positions[name], int)
            or not 0 <= positions[name] < len(data)
            or not isinstance(data[positions[name]], list)
            for name in required
        ):
            raise ValueError("invalid emergency-care count-table columns")
        if len({positions[name] for name in required}) != len(required):
            raise ValueError("duplicate emergency-care count-table positions")
        columns = {name: data[positions[name]] for name in sorted(required)}
        if len({len(values) for values in columns.values()}) != 1:
            raise ValueError("unequal emergency-care count-table column lengths")
        frames.append(pd.DataFrame(columns))
    if len(frames) != 1:
        raise ValueError("expected one emergency-care count table in publication")
    return frames[0]


def _fetch_emergency_4hr() -> list[dict]:
    page = _current_publication("emergency", EMERGENCY_PUBLICATION_PAGE)
    urls = list(dict.fromkeys(
        urljoin(page, href)
        for href, _label in LINK_RE.findall(_html(page))
        if "ni-emergency-care-waiting-times-data-" in href and ".html" in href
    ))
    if len(urls) != 1:
        raise ValueError("no unique interactive emergency-care data publication")
    df = _emergency_frame(_http.get_bytes(urls[0]).decode("utf-8"))
    df["date"] = _dates(df["Date"]) + pd.offsets.MonthEnd(0)
    if df["date"].isna().any():
        raise ValueError("invalid emergency-care observation date")
    if not set(df["Trust"]) <= CORE_HSC_TRUSTS:
        raise ValueError("unrecognised emergency-care trust")
    if not df["Dept"].map(lambda name: isinstance(name, str) and bool(name.strip())).all():
        raise ValueError("missing emergency-care department identifier")
    if not set(df["Type"]) <= {"Type 1", "Type 2", "Type 3"}:
        raise ValueError("unrecognised emergency-department type")
    if df.duplicated(["date", "Trust", "Dept", "Type"]).any():
        raise ValueError("duplicate emergency-care month/department observations")
    count_cols = ["Under4hrs", "Between4to12hrs", "Over12hrs", "TotalAttendances"]
    df[count_cols] = df[count_cols].apply(_number_series)
    missing_dates = set(df.loc[df[count_cols].isna().any(axis=1), "date"])
    df = df.dropna(subset=count_cols)
    if any(
        (~df[col].map(math.isfinite) | (df[col] < 0) | (df[col] % 1 != 0)).any()
        for col in count_cols
    ):
        raise ValueError("invalid emergency-care counts")
    df["classified_waits"] = df[count_cols[:3]].sum(axis=1)
    if (df["classified_waits"] > df["TotalAttendances"]).any():
        raise ValueError("emergency-care time bands exceed attendances")
    positive = df["classified_waits"] > 0
    published = _number_series(df.loc[positive, "PercentUnder4hrs"])
    calculated = df.loc[positive, "Under4hrs"] / df.loc[positive, "classified_waits"] * 100
    if published.isna().any() or ((calculated - published).abs() > 0.051).any():
        raise ValueError("emergency-care rates disagree with published percentages")
    complete = _complete_quarters(df, "Trust") - missing_dates
    omitted = (set(df["date"]) - complete) | missing_dates
    if omitted:
        _warn("ae_4hr_pct", ValueError(
            f"omitting {len(omitted)} months with incomplete department/trust data"
        ))
    df = df[df["date"].isin(complete) & df["Trust"].isin(CORE_HSC_TRUSTS)]
    grouped = (
        df.groupby("date", as_index=False)[["Under4hrs", "classified_waits"]]
        .sum()
        .sort_values("date")
    )
    grouped = grouped[grouped["classified_waits"] > 0]
    if grouped.empty:
        raise ValueError("no complete emergency-care months parsed")
    grouped["value"] = grouped["Under4hrs"] / grouped["classified_waits"] * 100
    return [
        _make_metric_row(row.date, "ae_4hr_pct", row.value)
        for row in grouped.itertuples(index=False)
    ]


def _fetch_cancer_62day() -> list[dict]:
    page = _current_publication("cancer", CANCER_62DAY_PAGE)
    url, _page = _find_attachment_on_pages(
        (page,), include=("cwt",), exclude=("icd10",),
    )
    required = {
        "Treatment Month",
        "HSC Trust",
        "Patients Treated Within 62 Days",
        "Total Patients Treated",
    }
    frames = [df for df in _workbook(url).values() if required.issubset(df.columns)]
    if len(frames) != 1:
        raise RuntimeError("expected one 62-day cancer table by HSC Trust")
    df = frames[0].copy()
    df["HSC Trust"] = df["HSC Trust"].astype(str).str.strip()
    df = df[df["HSC Trust"].isin(CORE_HSC_TRUSTS)].copy()

    df["date"] = _dates(df["Treatment Month"]) + pd.offsets.MonthEnd(0)
    df["within"] = _number_series(df["Patients Treated Within 62 Days"])
    df["total"] = _number_series(df["Total Patients Treated"])
    if df.dropna(subset=["date"]).duplicated(["date", "HSC Trust"]).any():
        raise ValueError("duplicate cancer month/trust observations")
    all_dates = set(df["date"].dropna())
    df = df.dropna(subset=["date", "within", "total"])
    if (
        ~df["within"].map(math.isfinite)
        | ~df["total"].map(math.isfinite)
        | (df["within"] < 0)
        | (df["total"] < df["within"])
    ).any():
        raise ValueError("invalid cancer numerator/denominator")
    complete = _complete_quarters(df)
    if all_dates - complete:
        _warn("cancer_62day_pct", ValueError(
            f"omitting {len(all_dates - complete)} months without all five trusts"
        ))
    grouped = (
        df[df["date"].isin(complete)]
        .groupby("date", as_index=False)[["within", "total"]]
        .sum()
        .sort_values("date")
    )
    grouped = grouped[grouped["total"] > 0]
    grouped["value"] = grouped["within"] / grouped["total"] * 100
    if grouped.empty:
        raise ValueError("no complete cancer months parsed")
    return [
        _make_metric_row(row.date, "cancer_62day_pct", row.value)
        for row in grouped.itertuples(index=False)
    ]


def _fetch_diagnostics_6week_breach() -> list[dict]:
    url, _page = _find_attachment_on_pages(
        (_current_publication("diagnostics", DIAGNOSTICS_PUBLICATION_PAGE),),
        include=("diagnostic-waiting-times",),
        exclude=("reporting-turnaround",),
    )
    frames = []
    for sheet_name, df in _workbook(url).items():
        if not {"Quarter Ending", "HSC Trust", "0 - 6 weeks", "Total"}.issubset(
            df.columns
        ):
            continue
        frame = df[["Quarter Ending", "HSC Trust", "0 - 6 weeks", "Total"]].copy()
        frame["sheet"] = sheet_name
        frames.append(frame)
    if not frames:
        raise RuntimeError("diagnostic workbook has no waiting-time sheets")

    df = pd.concat(frames, ignore_index=True)
    df["date"] = _dates(df["Quarter Ending"])
    df["within_6w"] = _number_series(df["0 - 6 weeks"])
    df["total"] = _number_series(df["Total"])
    df = df.dropna(subset=["date", "within_6w", "total"])
    complete = _complete_quarters(df, "HSC Trust")
    grouped = (
        df[df["date"].isin(complete)]
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


def fetch(start_year: int | None = None, end_year: int | None = None) -> list[dict]:
    """Fetch Northern Ireland waiting-time rows filtered by calendar year."""
    start, end = _util.year_bounds(start_year, end_year)
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
        _util.filter_rows_by_year(rows, start, end),
        key=lambda row: (row["date"], row["metric"]),
    )
