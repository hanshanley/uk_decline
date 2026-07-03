"""Public Health Scotland CKAN client for NHS waiting-time metrics.

Public Health Scotland publishes open data through a CKAN datastore API at
``www.opendata.nhs.scot``.  This module reads the datastore schemas before using
known resource ids, filters to Scotland-wide rows, and emits the shared tidy-row
schema used by :mod:`nhs_data.combine`.
"""

from __future__ import annotations

import calendar
import json
import re
import sys
from collections import defaultdict
from datetime import date
from typing import Iterable, Iterator

from ._http import get_json
from .metrics import make_row

BASE = "https://www.opendata.nhs.scot/api/3/action"
NATION = "Scotland"
NATION_CODE = "SCO"
SOURCE = "Public Health Scotland"
SCOTLAND = "S92000003"

# Stage of Treatment Waiting Times / Ongoing Waits - Long Trend
RTT_ONGOING_RESOURCE = "5816ec92-66bf-4033-ae55-9df45ff19d49"
# Monthly A&E Activity and Waiting Times / Monthly Accident and Emergency Activity
AE_ACTIVITY_RESOURCE = "37ba17b1-c323-492c-87d5-e986aae9ab59"
# Cancer Waiting Times / Cancer Wait Time - 62 Day Standard
CANCER_62_RESOURCE = "23b3bbf7-7a37-4f86-974b-6360d6748e08"
# Diagnostic Waiting Times / Waiting Times at Scotland Level
DIAGNOSTICS_CURRENT_RESOURCE = "df75544f-4ba1-488d-97c7-30ab6258270d"
# Diagnostic Waiting Times / 2007 - 2019: Waiting Times At Scotland Level
DIAGNOSTICS_ARCHIVE_RESOURCE = "d61e6e61-3fa6-4b14-8312-2c76d17094bb"

def _warn(metric: str, exc: Exception) -> None:
    print(f"[nhs_data] WARNING: SCO {metric} failed: {exc}", file=sys.stderr)


def _year_bounds(start_year: int | None, end_year: int | None) -> tuple[int, int]:
    end = end_year if end_year is not None else date.today().year
    start = start_year if start_year is not None else end - 9
    if start > end:
        raise ValueError("start_year must be <= end_year")
    return start, end


def _in_year_range(day: date, start_year: int, end_year: int) -> bool:
    return start_year <= day.year <= end_year


def _month_end(value: int | str) -> date:
    text = str(value)
    year = int(text[:4])
    month = int(text[4:6])
    if len(text) >= 8:
        day = int(text[6:8])
    else:
        day = calendar.monthrange(year, month)[1]
    return date(year, month, day)


def _quarter_end(value: str) -> date:
    match = re.fullmatch(r"(\d{4})Q([1-4])", value)
    if not match:
        raise ValueError(f"unsupported quarter label: {value!r}")
    year = int(match.group(1))
    quarter = int(match.group(2))
    month = quarter * 3
    return date(year, month, calendar.monthrange(year, month)[1])


def _month_period(day: date) -> str:
    return f"{day:%Y-%m}"


def _quarter_period(label: str) -> str:
    return f"{label[:4]}-Q{label[-1]}"


def _num(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _check_fields(fields: list[dict], required: Iterable[str]) -> None:
    found = {field.get("id") for field in fields}
    missing = [field for field in required if field not in found]
    if missing:
        raise KeyError(f"missing datastore fields: {', '.join(missing)}")


def _datastore_records(
    resource_id: str,
    *,
    filters: dict[str, object] | None = None,
    required_fields: Iterable[str] = (),
    sort: str | None = None,
    limit: int = 5000,
) -> Iterator[dict]:
    offset = 0
    checked_fields = False
    while True:
        params: dict[str, object] = {
            "resource_id": resource_id,
            "limit": limit,
            "offset": offset,
        }
        if filters:
            params["filters"] = json.dumps(filters)
        if sort:
            params["sort"] = sort
        payload = get_json(f"{BASE}/datastore_search", params=params)
        if not payload.get("success"):
            raise RuntimeError(f"CKAN datastore_search failed for {resource_id}")
        result = payload["result"]
        if not checked_fields:
            _check_fields(result.get("fields", []), required_fields)
            checked_fields = True
        records = result.get("records", [])
        yield from records
        offset += len(records)
        if not records or offset >= int(result.get("total", offset)):
            return


def _tidy_row(day: date, metric: str, value: float) -> dict:
    return make_row(
        NATION,
        NATION_CODE,
        _month_period(day),
        day.isoformat(),
        metric,
        value,
        SOURCE,
    )


def _fetch_rtt_total(start_year: int, end_year: int) -> list[dict]:
    required = (
        "MonthEnding",
        "HBT",
        "PatientType",
        "Specialty",
        "NumberWaiting",
    )
    totals: dict[date, float] = defaultdict(float)
    for row in _datastore_records(
        RTT_ONGOING_RESOURCE,
        filters={"HBT": SCOTLAND, "Specialty": "Z9"},
        required_fields=required,
        sort="MonthEnding",
    ):
        day = _month_end(row["MonthEnding"])
        if not _in_year_range(day, start_year, end_year):
            continue
        value = _num(row.get("NumberWaiting"))
        if value is not None:
            totals[day] += value
    return [
        _tidy_row(day, "rtt_waiting_list_total", totals[day])
        for day in sorted(totals)
    ]


def _fetch_rtt_median(start_year: int, end_year: int) -> list[dict]:
    required = (
        "MonthEnding",
        "HBT",
        "PatientType",
        "Specialty",
        "NumberWaiting",
        "Median",
    )
    weighted_days: dict[date, float] = defaultdict(float)
    weights: dict[date, float] = defaultdict(float)
    for row in _datastore_records(
        RTT_ONGOING_RESOURCE,
        filters={"HBT": SCOTLAND, "Specialty": "Z9"},
        required_fields=required,
        sort="MonthEnding",
    ):
        day = _month_end(row["MonthEnding"])
        if not _in_year_range(day, start_year, end_year):
            continue
        number_waiting = _num(row.get("NumberWaiting"))
        median_days = _num(row.get("Median"))
        if number_waiting is None or median_days is None or number_waiting <= 0:
            continue
        weighted_days[day] += median_days * number_waiting
        weights[day] += number_waiting
    return [
        _tidy_row(day, "rtt_median_wait_weeks", weighted_days[day] / weights[day] / 7)
        for day in sorted(weighted_days)
        if weights[day]
    ]


def _fetch_ae_4hr(start_year: int, end_year: int) -> list[dict]:
    required = (
        "Month",
        "Country",
        "AttendanceCategory",
        "NumberOfAttendancesAll",
        "NumberWithin4HoursAll",
    )
    totals: dict[date, float] = defaultdict(float)
    within: dict[date, float] = defaultdict(float)
    for row in _datastore_records(
        AE_ACTIVITY_RESOURCE,
        filters={"Country": SCOTLAND, "AttendanceCategory": "All"},
        required_fields=required,
        sort="Month",
    ):
        day = _month_end(row["Month"])
        if not _in_year_range(day, start_year, end_year):
            continue
        total = _num(row.get("NumberOfAttendancesAll"))
        met = _num(row.get("NumberWithin4HoursAll"))
        if total is None or met is None:
            continue
        totals[day] += total
        within[day] += met
    return [
        _tidy_row(day, "ae_4hr_pct", within[day] / totals[day] * 100)
        for day in sorted(totals)
        if totals[day]
    ]


def _fetch_cancer_62day(start_year: int, end_year: int) -> list[dict]:
    required = (
        "Quarter",
        "HB",
        "HBT",
        "CancerType",
        "NumberOfEligibleReferrals62DayStandard",
        "NumberOfEligibleReferralsTreatedWithin62Days",
    )
    eligible: dict[str, float] = defaultdict(float)
    treated: dict[str, float] = defaultdict(float)
    dates: dict[str, date] = {}
    for row in _datastore_records(
        CANCER_62_RESOURCE,
        filters={"HB": SCOTLAND, "CancerType": "All Cancer Types"},
        required_fields=required,
        sort="Quarter",
    ):
        day = _quarter_end(row["Quarter"])
        if not _in_year_range(day, start_year, end_year):
            continue
        total = _num(row.get("NumberOfEligibleReferrals62DayStandard"))
        met = _num(row.get("NumberOfEligibleReferralsTreatedWithin62Days"))
        if total is None or met is None:
            continue
        period = _quarter_period(row["Quarter"])
        dates[period] = day
        eligible[period] += total
        treated[period] += met
    return [
        make_row(
            NATION,
            NATION_CODE,
            period,
            dates[period].isoformat(),
            "cancer_62day_pct",
            treated[period] / eligible[period] * 100,
            SOURCE,
        )
        for period in sorted(eligible)
        if eligible[period]
    ]


def _is_all_diagnostic_type(row: dict) -> bool:
    description = str(row.get("DiagnosticTestDescription") or "")
    return description.startswith("All ")


def _is_six_week_breach_band(waiting_time: str) -> bool:
    if waiting_time == "365 days and over":
        return True
    match = re.match(r"(\d+)-", waiting_time)
    return bool(match and int(match.group(1)) >= 43)


def _fetch_diagnostics_current(
    start_year: int, end_year: int
) -> dict[date, tuple[float, float]]:
    required = (
        "DiagnosticTestDescription",
        "MonthEnding",
        "Country",
        "WaitingTime",
        "NumberOnList",
    )
    totals: dict[date, float] = defaultdict(float)
    breaches: dict[date, float] = defaultdict(float)
    for row in _datastore_records(
        DIAGNOSTICS_CURRENT_RESOURCE,
        filters={"Country": SCOTLAND},
        required_fields=required,
        sort="MonthEnding",
    ):
        if not _is_all_diagnostic_type(row):
            continue
        day = _month_end(row["MonthEnding"])
        if not _in_year_range(day, start_year, end_year):
            continue
        value = _num(row.get("NumberOnList"))
        if value is None:
            continue
        totals[day] += value
        if _is_six_week_breach_band(str(row.get("WaitingTime") or "")):
            breaches[day] += value
    return {day: (totals[day], breaches[day]) for day in totals}


def _fetch_diagnostics_archive(
    start_year: int, end_year: int
) -> dict[date, tuple[float, float]]:
    required = (
        "MonthEnding",
        "Country",
        "DiagnosticTestDescription",
        "NumberOnList",
        "NumberWaitingOverSixWeeks",
    )
    totals: dict[date, float] = defaultdict(float)
    breaches: dict[date, float] = defaultdict(float)
    for row in _datastore_records(
        DIAGNOSTICS_ARCHIVE_RESOURCE,
        filters={"Country": SCOTLAND},
        required_fields=required,
        sort="MonthEnding",
    ):
        if not _is_all_diagnostic_type(row):
            continue
        day = _month_end(row["MonthEnding"])
        if not _in_year_range(day, start_year, end_year):
            continue
        total = _num(row.get("NumberOnList"))
        breach = _num(row.get("NumberWaitingOverSixWeeks"))
        if total is None or breach is None:
            continue
        totals[day] += total
        breaches[day] += breach
    return {day: (totals[day], breaches[day]) for day in totals}


def _fetch_diagnostics_6week(start_year: int, end_year: int) -> list[dict]:
    by_day = _fetch_diagnostics_archive(start_year, end_year)
    by_day.update(_fetch_diagnostics_current(start_year, end_year))
    return [
        _tidy_row(day, "diagnostics_6week_breach_pct", breach / total * 100)
        for day, (total, breach) in sorted(by_day.items())
        if total
    ]


def fetch(start_year: int | None = None, end_year: int | None = None) -> list[dict]:
    """Fetch tidy Scotland waiting-time rows for the inclusive year range."""
    start, end = _year_bounds(start_year, end_year)
    rows: list[dict] = []
    for metric, fetcher in (
        ("rtt_waiting_list_total", _fetch_rtt_total),
        ("rtt_median_wait_weeks", _fetch_rtt_median),
        ("ae_4hr_pct", _fetch_ae_4hr),
        ("cancer_62day_pct", _fetch_cancer_62day),
        ("diagnostics_6week_breach_pct", _fetch_diagnostics_6week),
    ):
        try:
            rows.extend(fetcher(start, end))
        except Exception as exc:  # noqa: BLE001 - keep other metrics available
            _warn(metric, exc)
    return sorted(rows, key=lambda row: (row["metric"], row["date"]))
