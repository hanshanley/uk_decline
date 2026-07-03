"""StatsWales client for Welsh NHS waiting-time statistics.

StatsWales now serves these datasets through the public
``https://api.stats.gov.wales/v1`` JSON API.  The view endpoint is paginated;
all rows are read through :func:`nhs_data._http.get_json`.
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import datetime
from typing import Iterable, Iterator
from urllib.parse import urljoin

from . import _util, metrics, nations
from ._http import get_json

BASE = "https://api.stats.gov.wales/v1"
PAGE_SIZE = 10_000

NATION = nations.BY_CODE["WAL"].name
NATION_CODE = "WAL"
SOURCE = nations.BY_CODE["WAL"].source_name

DATASETS = {
    "rtt_performance": "acd9529c-979a-48ef-a773-870b3ebe4391",
    "ae_performance": "3ce1cc28-0625-4674-89d6-9cf3a56f2d9c",
    "cancer_current": "394da9f2-b879-4994-94de-577d8f863247",
    "cancer_historic_urgent": "6fe55e52-ff8f-4d49-b577-797065e661c9",
    "diagnostics_current": "3c2720e6-95ae-4eeb-9e88-ed74bb40c6b9",
    "diagnostics_grouped": "46750781-de32-4f20-9903-895bfa37f9b5",
}

RTT_FILTERS = (
    ("Local health board provider", "All Wales LHB (Provider)"),
    ("Specialty", "All Treatment Functions"),
)

CANCER_CURRENT_DESC = (
    "The percentage of patients starting their first definitive treatment in "
    "the month within 62 days of first being suspected of cancer (no suspensions)"
)
CANCER_HISTORIC_DESC = (
    "Percentage of patients starting treatment via the urgent suspected cancer "
    "route within 62 days"
)


def _filter(column: str, *values: str) -> dict[str, object]:
    return {"columnName": column, "values": list(values)}


def _view_rows(
    dataset_id: str, filters: Iterable[tuple[str, str] | dict[str, object]] = ()
) -> Iterator[dict[str, object]]:
    """Yield every row from a StatsWales dataset view, following pagination."""
    filter_payload: list[dict[str, object]] = []
    for item in filters:
        if isinstance(item, dict):
            filter_payload.append(item)
        else:
            column, value = item
            filter_payload.append(_filter(column, value))

    url: str | None = f"{BASE}/{dataset_id}/view"
    params: dict[str, object] | None = {
        "lang": "en",
        "page_size": PAGE_SIZE,
        "page_number": 1,
    }
    if filter_payload:
        params["filter"] = json.dumps(filter_payload)

    while url:
        payload = get_json(url, params=params)

        if isinstance(payload, dict) and "value" in payload:
            yield from payload.get("value") or []
            next_url = payload.get("odata.nextLink")
            url = urljoin(BASE, next_url) if next_url else None
            params = None
            continue

        headers = [h["name"] for h in payload.get("headers", [])]
        for row in payload.get("data", []):
            if isinstance(row, dict):
                yield row
            else:
                yield dict(zip(headers, row))

        page = int(payload.get("current_page") or (params or {}).get("page_number", 1))
        total_pages = int(payload.get("total_pages") or page)
        if page >= total_pages:
            return
        params = dict(params or {})
        params["page_number"] = page + 1


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {":", "..", "n/a", "N/A", "-"}:
        return None
    return float(text)


def _period_end(label: object) -> tuple[str, str]:
    text = str(label).strip()
    for fmt in ("%b-%Y", "%b-%y", "%B %Y"):
        try:
            dt = datetime.strptime(text, fmt)
            last_day = calendar.monthrange(dt.year, dt.month)[1]
            period = f"{dt.year:04d}-{dt.month:02d}"
            return period, f"{period}-{last_day:02d}"
        except ValueError:
            pass
    raise ValueError(f"unsupported StatsWales date label: {text!r}")


def _row(period_label: object, metric: str, value: float) -> dict:
    period, period_date = _period_end(period_label)
    return metrics.make_row(NATION, NATION_CODE, period, period_date, metric, value, SOURCE)


def _fetch_rtt() -> Iterator[dict]:
    """Yield both RTT metrics from a single pass over the shared RTT view."""
    median_desc = "Median waiting time (decimal weeks)"
    for row in _view_rows(DATASETS["rtt_performance"], RTT_FILTERS):
        desc = row.get("Data description")
        if desc == "Total pathways waiting":
            metric = "rtt_waiting_list_total"
        elif desc == median_desc:
            metric = "rtt_median_wait_weeks"
        else:
            continue
        value = _number(row.get("Data values"))
        if value is not None:
            yield _row(row["Date"], metric, value)


def _fetch_ae_4hr_pct() -> Iterator[dict]:
    filters = (
        ("Hospital", "Wales"),
        ("Hospital Type", "All Emergency Care Facilities"),
        ("Target", "4 hour target"),
        (
            "Data description",
            "Percentage of patients who spend less than the target time in an emergency department",
        ),
    )
    for row in _view_rows(DATASETS["ae_performance"], filters):
        value = _number(row.get("Data values"))
        if value is not None:
            yield _row(row["Date"], "ae_4hr_pct", value)


def _fetch_cancer_62day_pct() -> Iterator[dict]:
    seen: set[str] = set()
    current_filters = (
        ("Local health board", "Wales"),
        ("Tumour site", "All sites"),
        ("Sex", "Total"),
        ("Age group", "Total"),
        ("Data description", CANCER_CURRENT_DESC),
    )
    for row in _view_rows(DATASETS["cancer_current"], current_filters):
        value = _number(row.get("Data values"))
        if value is None:
            continue
        out = _row(row["Date"], "cancer_62day_pct", value)
        seen.add(out["period"])
        yield out

    historic_filters = (
        ("local health board", "Wales"),
        ("tumour site", "Total"),
        ("Data description", CANCER_HISTORIC_DESC),
    )
    for row in _view_rows(DATASETS["cancer_historic_urgent"], historic_filters):
        value = _number(row.get("Data values"))
        if value is None:
            continue
        out = _row(row["Date"], "cancer_62day_pct", value)
        if out["period"] not in seen:
            yield out


def _is_exact_diagnostics_6week_breach(label: object) -> bool:
    text = str(label).strip()
    lower = text.lower()
    if lower in {"total waiting", "up to 8 weeks", "over 8 weeks"}:
        return False
    if lower == "forty weeks and over":
        return True
    match = re.match(r"over\s+(\d+)\s+weeks?", lower)
    return bool(match and int(match.group(1)) >= 6)


def _diagnostics_pct_from_rows(
    rows: Iterable[dict], weeks_column: str, *, grouped_over8: bool = False
) -> Iterator[dict]:
    totals: dict[str, float] = {}
    breaches: dict[str, float] = {}
    dates: dict[str, str] = {}

    for row in rows:
        value = _number(row.get("Data values"))
        if value is None:
            continue
        period, period_date = _period_end(row["Date"])
        dates[period] = period_date
        weeks = row.get(weeks_column)
        if weeks == "Total Waiting":
            totals[period] = value
        elif (
            (grouped_over8 and weeks == "Over 8 Weeks")
            or _is_exact_diagnostics_6week_breach(weeks)
        ):
            breaches[period] = breaches.get(period, 0.0) + value

    for period, total in totals.items():
        if total <= 0:
            continue
        breach = breaches.get(period)
        if breach is None:
            continue
        yield metrics.make_row(
            NATION,
            NATION_CODE,
            period,
            dates[period],
            "diagnostics_6week_breach_pct",
            breach / total * 100.0,
            SOURCE,
        )


def _fetch_diagnostics_6week_breach_pct() -> Iterator[dict]:
    filters = (
        ("Service", "Diagnostics"),
        ("Local health board or site", "All Welsh Hospitals"),
        ("Age group", "Total"),
    )
    exact_rows = list(
        _diagnostics_pct_from_rows(
            _view_rows(DATASETS["diagnostics_current"], filters),
            "Weeks waiting",
        )
    )
    exact_periods = {row["period"] for row in exact_rows}
    yield from exact_rows

    grouped_rows = _diagnostics_pct_from_rows(
        _view_rows(DATASETS["diagnostics_grouped"], filters),
        "Grouped weeks waiting",
        grouped_over8=True,
    )
    for row in grouped_rows:
        if row["period"] not in exact_periods:
            yield row


FETCHERS = (
    ("rtt", _fetch_rtt),
    ("ae_4hr_pct", _fetch_ae_4hr_pct),
    ("cancer_62day_pct", _fetch_cancer_62day_pct),
    ("diagnostics_6week_breach_pct", _fetch_diagnostics_6week_breach_pct),
)


def fetch(start_year: int | None = None, end_year: int | None = None) -> list[dict]:
    """Fetch tidy all-Wales waiting-time rows for an inclusive year range."""
    start, end = _util.year_bounds(start_year, end_year)
    out: list[dict] = []
    for metric, fetcher in FETCHERS:
        try:
            out.extend(fetcher())
        except Exception as exc:
            _util.warn(NATION_CODE, metric, exc)
    out = _util.filter_rows_by_year(out, start, end)
    return sorted(out, key=lambda row: (row["date"], row["metric"]))
