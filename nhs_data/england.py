"""NHS England bulk-file client for monthly waiting-time statistics.

NHS England publishes these series as CSV/Excel downloads from statistical work
area pages rather than as a REST API, so this module discovers current file
links from landing pages and parses the published extracts.
"""

from __future__ import annotations

import calendar
import csv
import io
import re
import sys
import zipfile
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin

import pandas as pd

from ._http import get_bytes, get_csv, get_excel
from .metrics import make_row

NATION = "England"
NATION_CODE = "ENG"
SOURCE = "NHS England"

LANDING_URLS = {
    "rtt": "https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/",
    "ae": "https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/",
    "cancer": "https://www.england.nhs.uk/statistics/statistical-work-areas/cancer-waiting-times/",
    "diagnostics": (
        "https://www.england.nhs.uk/statistics/statistical-work-areas/"
        "diagnostics-waiting-times-and-activity/monthly-diagnostics-waiting-times-and-activity/"
    ),
}

CANDIDATE_URLS = {
    "rtt_pages": [
        "https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/rtt-data-2025-26/",
        "https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/rtt-data-2024-25/",
        "https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/rtt-data-2023-24/",
    ],
    "ae_pages": [
        "https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/ae-attendances-and-emergency-admissions-2025-26/",
        "https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/ae-attendances-and-emergency-admissions-2024-25/",
    ],
    "cancer_timeseries": [
        "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/06/CWT-CRS-National-Time-Series-Oct-2009-Apr-2026-with-Revisions.xlsx",
    ],
    "diagnostics_pages": [
        "https://www.england.nhs.uk/statistics/statistical-work-areas/diagnostics-waiting-times-and-activity/monthly-diagnostics-waiting-times-and-activity/monthly-diagnostics-data-2025-26/",
        "https://www.england.nhs.uk/statistics/statistical-work-areas/diagnostics-waiting-times-and-activity/monthly-diagnostics-waiting-times-and-activity/monthly-diagnostics-data-2024-25/",
    ],
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = " ".join(" ".join(self._text).split())
            self.links.append((text, self._href))
            self._href = None
            self._text = []


def _warn(metric: str, exc: Exception) -> None:
    print(f"warning: NHS England {metric} failed: {exc}", file=sys.stderr)


def _links(page_url: str) -> list[tuple[str, str]]:
    parser = _LinkParser()
    parser.feed(get_bytes(page_url).decode("utf-8", "replace"))
    return [(text, urljoin(page_url, href)) for text, href in parser.links if href]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _financial_year(text: str) -> tuple[int, int] | None:
    match = re.search(r"((?:19|20)\d{2})[-_–](\d{2})", text)
    if not match:
        return None
    start = int(match.group(1))
    end = (start // 100) * 100 + int(match.group(2))
    if end < start:
        end += 100
    return start, end


def _fy_overlaps(text: str, start_year: int, end_year: int) -> bool:
    fy = _financial_year(text)
    if not fy:
        return True
    return fy[0] <= end_year and fy[1] >= start_year


def _discover_pages(
    landing_url: str,
    url_token: str,
    candidate_urls: list[str],
    start_year: int,
    end_year: int,
) -> list[str]:
    pages = list(candidate_urls)
    for text, href in _links(landing_url):
        if url_token in href and _fy_overlaps(f"{text} {href}", start_year, end_year):
            pages.append(href)
    return _dedupe(pages)


def _parse_year(raw: str) -> int:
    year = int(raw)
    if year < 100:
        return 2000 + year if year < 80 else 1900 + year
    return year


def _month_from_text(text: str) -> tuple[int, int] | None:
    decoded = unquote(text).lower().replace("_", "-")
    month_re = "|".join(sorted(MONTHS, key=len, reverse=True))
    match = re.search(rf"\b({month_re})[a-z]*[\s.-]*(20\d{{2}}|\d{{2}})\b", decoded)
    if match:
        return _parse_year(match.group(2)), MONTHS[match.group(1)[:3]]
    match = re.search(r"\b(20\d{2})(0[1-9]|1[0-2])(?:[0-3]\d)?\b", decoded)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _period_and_date(year: int, month: int) -> tuple[str, str]:
    end = _month_end(year, month)
    return f"{year:04d}-{month:02d}", end.isoformat()


def _in_range(year: int, month: int, start_year: int, end_year: int) -> bool:
    row_year = _month_end(year, month).year
    return start_year <= row_year <= end_year


def _select_month_links(
    page_urls: list[str],
    predicate,
    start_year: int,
    end_year: int,
) -> list[tuple[int, int, str]]:
    by_month: dict[tuple[int, int], tuple[int, str]] = {}
    for page_url in page_urls:
        for text, href in _links(page_url):
            label = f"{text} {href}"
            month = _month_from_text(href) or _month_from_text(label)
            if not month or not _in_range(*month, start_year, end_year):
                continue
            if not predicate(text, href):
                continue
            priority = int("revised" in label.lower()) + int("final" in label.lower())
            if month not in by_month or priority >= by_month[month][0]:
                by_month[month] = (priority, href)
    return [(year, month, url) for (year, month), (_, url) in sorted(by_month.items())]


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    ).fillna(0.0)


def _percent(value: float) -> float:
    return value * 100.0 if abs(value) <= 1.5 else value


def _csv_text_from_zip(url: str) -> str:
    archive = zipfile.ZipFile(io.BytesIO(get_bytes(url)))
    name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
    raw = archive.read(name)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin1")


def _header_index(lines: list[str], markers: tuple[str, ...]) -> int:
    lowered = tuple(marker.lower() for marker in markers)
    for idx, line in enumerate(lines[:60]):
        low = line.lower()
        if all(marker in low for marker in lowered):
            return idx
    raise ValueError(f"could not find CSV header containing {markers!r}")


def _header_columns(lines: list[str], header_idx: int) -> list[str]:
    return [col.strip() for col in next(csv.reader([lines[header_idx]]))]


def _read_csv_lines(
    lines: list[str],
    header_idx: int,
    usecols: list[str] | None = None,
) -> pd.DataFrame:
    body = "\n".join(lines[header_idx:])
    try:
        return pd.read_csv(io.StringIO(body), usecols=usecols, low_memory=False)
    except Exception:
        return pd.read_csv(
            io.StringIO(body),
            usecols=usecols,
            engine="python",
            on_bad_lines="skip",
        )


def _rtt_week_lower(col: str) -> int | None:
    match = re.search(r"gt\s+(\d+)(?:\s+to\s+\d+)?\s+weeks?", col, re.I)
    return int(match.group(1)) if match else None


def _weighted_median_wait(counts: pd.Series) -> float | None:
    counts_by_week: dict[int, float] = {}
    for col, count in counts.items():
        lower = _rtt_week_lower(str(col))
        if lower is not None:
            counts_by_week[lower] = counts_by_week.get(lower, 0.0) + float(count)
    total = sum(counts_by_week.values())
    if total <= 0:
        return None
    midpoint = total / 2.0
    cumulative = 0.0
    for lower in sorted(counts_by_week):
        cumulative += counts_by_week[lower]
        if cumulative >= midpoint:
            return lower + 0.5
    return None


def _rtt_rows_from_zip(url: str, year: int, month: int) -> list[dict]:
    text = _csv_text_from_zip(url)
    lines = text.splitlines()
    header_idx = _header_index(lines, ("RTT Part", "Treatment Function"))
    columns = _header_columns(lines, header_idx)
    part_col = next(c for c in columns if c.lower() in {"rtt part type", "rtt part name"})
    function_col = next(c for c in columns if c.lower() == "treatment function name")
    total_col = next(c for c in columns if c.lower() == "total all")
    week_cols = [c for c in columns if _rtt_week_lower(c) is not None]
    df = _read_csv_lines(lines, header_idx, [part_col, function_col, total_col, *week_cols])
    mask = (
        df[part_col].astype(str).str.strip().str.upper().eq("PART_2")
        & df[function_col].astype(str).str.strip().str.lower().eq("total")
    )
    subset = df.loc[mask]
    if subset.empty:
        raise ValueError("no England/all-specialties incomplete-pathways rows found")
    total_waiting = float(_to_numeric(subset[total_col]).sum())
    week_counts = subset[week_cols].apply(_to_numeric).sum()
    median = _weighted_median_wait(week_counts)
    period, row_date = _period_and_date(year, month)
    rows = [
        make_row(NATION, NATION_CODE, period, row_date, "rtt_waiting_list_total", total_waiting, SOURCE)
    ]
    if median is not None:
        rows.append(
            make_row(NATION, NATION_CODE, period, row_date, "rtt_median_wait_weeks", median, SOURCE)
        )
    return rows


def _fetch_rtt(start_year: int, end_year: int) -> list[dict]:
    pages = _discover_pages(
        LANDING_URLS["rtt"],
        "rtt-data-",
        CANDIDATE_URLS["rtt_pages"],
        start_year,
        end_year,
    )
    links = _select_month_links(
        pages,
        lambda text, href: ".zip" in href.lower() and "full" in f"{text} {href}".lower(),
        start_year,
        end_year,
    )
    rows: list[dict] = []
    for year, month, url in links:
        try:
            rows.extend(_rtt_rows_from_zip(url, year, month))
        except Exception as exc:
            _warn("RTT monthly extract", exc)
    if not rows:
        raise ValueError("no RTT rows parsed")
    return rows


def _fetch_ae(start_year: int, end_year: int) -> list[dict]:
    pages = _discover_pages(
        LANDING_URLS["ae"],
        "ae-attendances-and-emergency-admissions",
        CANDIDATE_URLS["ae_pages"],
        start_year,
        end_year,
    )
    links = _select_month_links(
        pages,
        lambda text, href: ".csv" in href.lower()
        and "ecds" not in f"{text} {href}".lower()
        and "quarter" not in f"{text} {href}".lower(),
        start_year,
        end_year,
    )
    rows: list[dict] = []
    for year, month, url in links:
        try:
            df = get_csv(url)
            total_mask = pd.Series(False, index=df.index)
            for col in ("Period", "Org Code", "Org name"):
                if col in df:
                    total_mask |= df[col].astype(str).str.strip().str.upper().eq("TOTAL")
            subset = df.loc[total_mask] if total_mask.any() else df
            numeric = subset.select_dtypes(include="number")
            if numeric.empty:
                numeric = subset.apply(_to_numeric)
            attendance_cols = [
                c
                for c in subset.columns
                if "attendances" in c.lower()
                and "over 4" not in c.lower()
                and "admission" not in c.lower()
            ]
            over_cols = [c for c in subset.columns if "over 4" in c.lower()]
            attendances = float(numeric[attendance_cols].sum().sum())
            over_four = float(numeric[over_cols].sum().sum())
            if attendances <= 0:
                continue
            period, row_date = _period_and_date(year, month)
            rows.append(
                make_row(
                    NATION,
                    NATION_CODE,
                    period,
                    row_date,
                    "ae_4hr_pct",
                    (attendances - over_four) / attendances * 100.0,
                    SOURCE,
                )
            )
        except Exception as exc:
            _warn("A&E monthly CSV", exc)
    if not rows:
        raise ValueError("no A&E rows parsed")
    return rows


def _cancer_workbooks() -> list[str]:
    urls = list(CANDIDATE_URLS["cancer_timeseries"])
    for text, href in _links(LANDING_URLS["cancer"]):
        label = f"{text} {href}".lower()
        if href.lower().endswith(".xlsx") and "national-time-series" in label:
            urls.append(href)
    return _dedupe(urls)


def _parse_cancer_workbook(url: str, start_year: int, end_year: int) -> list[dict]:
    sheet = get_excel(url, sheet_name="Monthly Performance", header=None)
    title_cell: tuple[int, int] | None = None
    for row in range(min(10, sheet.shape[0])):
        for col in range(sheet.shape[1]):
            value = str(sheet.iat[row, col]).lower()
            if "62" in value and "first definitive treatment" in value:
                title_cell = (row, col)
                break
        if title_cell:
            break
    if title_cell is None:
        raise ValueError("62-day monthly performance block not found")

    _, title_col = title_cell
    date_col = perf_col = header_row = None
    for row in range(title_cell[0] + 1, min(title_cell[0] + 8, sheet.shape[0])):
        for candidate_date_col in (title_col - 1, title_col):
            if candidate_date_col < 0:
                continue
            if str(sheet.iat[row, candidate_date_col]).strip().lower() == "monthly":
                for col in range(candidate_date_col + 1, min(candidate_date_col + 6, sheet.shape[1])):
                    if "performance" in str(sheet.iat[row, col]).lower():
                        date_col, perf_col, header_row = candidate_date_col, col, row
                        break
            if date_col is not None:
                break
        if date_col is not None:
            break
    if date_col is None or perf_col is None or header_row is None:
        raise ValueError("62-day monthly performance columns not found")

    rows: list[dict] = []
    for _, row in sheet.iloc[header_row + 1 :, [date_col, perf_col]].iterrows():
        dt = pd.to_datetime(row.iloc[0], errors="coerce")
        value = pd.to_numeric(row.iloc[1], errors="coerce")
        if pd.isna(dt) or pd.isna(value):
            continue
        year, month = int(dt.year), int(dt.month)
        if not _in_range(year, month, start_year, end_year):
            continue
        period, row_date = _period_and_date(year, month)
        rows.append(
            make_row(
                NATION,
                NATION_CODE,
                period,
                row_date,
                "cancer_62day_pct",
                _percent(float(value)),
                SOURCE,
            )
        )
    return rows


def _fetch_cancer(start_year: int, end_year: int) -> list[dict]:
    last_error: Exception | None = None
    for url in _cancer_workbooks():
        try:
            rows = _parse_cancer_workbook(url, start_year, end_year)
            if rows:
                return rows
        except Exception as exc:
            last_error = exc
    raise ValueError("no cancer 62-day rows parsed") from last_error


def _diagnostic_week_lower(col: str) -> int | None:
    if "total wl" in col.lower():
        return None
    match = re.search(r"\b(\d+)\s*(?:<|\+|plus)", col.lower())
    return int(match.group(1)) if match else None


def _diagnostics_rows_from_zip(url: str, year: int, month: int) -> list[dict]:
    text = _csv_text_from_zip(url)
    lines = text.splitlines()
    header_idx = _header_index(lines, ("Diagnostic Tests",))
    columns = _header_columns(lines, header_idx)
    test_col = next(c for c in columns if c.lower() == "diagnostic tests")
    total_col = next(c for c in columns if c.lower().startswith("total wl"))
    breach_cols = [
        c
        for c in columns
        if (lower := _diagnostic_week_lower(c)) is not None and lower >= 6
    ]
    df = _read_csv_lines(lines, header_idx, [test_col, total_col, *breach_cols])
    subset = df.loc[df[test_col].astype(str).str.strip().str.upper().eq("TOTAL")]
    if subset.empty:
        subset = df
    total_waiting = float(_to_numeric(subset[total_col]).sum())
    breaches = float(subset[breach_cols].apply(_to_numeric).sum().sum())
    if total_waiting <= 0:
        return []
    period, row_date = _period_and_date(year, month)
    return [
        make_row(
            NATION,
            NATION_CODE,
            period,
            row_date,
            "diagnostics_6week_breach_pct",
            breaches / total_waiting * 100.0,
            SOURCE,
        )
    ]


def _fetch_diagnostics(start_year: int, end_year: int) -> list[dict]:
    pages = _discover_pages(
        LANDING_URLS["diagnostics"],
        "monthly-diagnostics-data-",
        CANDIDATE_URLS["diagnostics_pages"],
        start_year,
        end_year,
    )
    links = _select_month_links(
        pages,
        lambda text, href: ".zip" in href.lower() and "dm01" in f"{text} {href}".lower(),
        start_year,
        end_year,
    )
    rows: list[dict] = []
    for year, month, url in links:
        try:
            rows.extend(_diagnostics_rows_from_zip(url, year, month))
        except Exception as exc:
            _warn("diagnostics monthly extract", exc)
    if not rows:
        raise ValueError("no diagnostics rows parsed")
    return rows


def fetch(start_year: int | None = None, end_year: int | None = None) -> list[dict]:
    """Fetch tidy NHS England monthly waiting-time rows.

    Rows are filtered by the inclusive calendar year of each month-end ``date``.
    When a bound is omitted, the default is approximately the latest 10 years.
    """
    current_year = date.today().year
    if end_year is None:
        end_year = current_year
    if start_year is None:
        start_year = end_year - 9

    out: list[dict] = []
    for metric, loader in (
        ("rtt_waiting_list_total/rtt_median_wait_weeks", _fetch_rtt),
        ("ae_4hr_pct", _fetch_ae),
        ("cancer_62day_pct", _fetch_cancer),
        ("diagnostics_6week_breach_pct", _fetch_diagnostics),
    ):
        try:
            out.extend(loader(start_year, end_year))
        except Exception as exc:
            _warn(metric, exc)

    out = [
        row
        for row in out
        if start_year <= datetime.fromisoformat(row["date"]).date().year <= end_year
    ]
    return sorted(out, key=lambda row: (row["date"], row["metric"]))
