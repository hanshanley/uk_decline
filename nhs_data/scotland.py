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
from collections import defaultdict
from datetime import date
from typing import Iterable, Iterator

from . import _util
from ._http import get_json
from .metrics import make_row

BASE = "https://www.opendata.nhs.scot/api/3/action"
NATION = "Scotland"
NATION_CODE = "SCO"
SOURCE = "Public Health Scotland"
SCOTLAND = "S92000003"

# Stage of Treatment Waiting Times / Ongoing Waits - Long Trend
RTT_ONGOING_RESOURCE = "5816ec92-66bf-4033-ae55-9df45ff19d49"
# Stage of Treatment Waiting Times / Ongoing and Completed Waits - Monthly
RTT_MONTHLY_RESOURCE = "ac63b747-fdcc-410c-ae43-de6fe3c46abf"
# Monthly A&E Activity and Waiting Times / Monthly Accident and Emergency Activity
AE_ACTIVITY_RESOURCE = "37ba17b1-c323-492c-87d5-e986aae9ab59"
# Cancer Waiting Times / Cancer Wait Time - 62 Day Standard
CANCER_62_RESOURCE = "23b3bbf7-7a37-4f86-974b-6360d6748e08"
# Diagnostic Waiting Times / Waiting Times at Scotland Level
DIAGNOSTICS_CURRENT_RESOURCE = "df75544f-4ba1-488d-97c7-30ab6258270d"
# Diagnostic Waiting Times / 2007 - 2019: Waiting Times At Scotland Level
DIAGNOSTICS_ARCHIVE_RESOURCE = "d61e6e61-3fa6-4b14-8312-2c76d17094bb"

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


def _rtt_totals(
    resource_id: str, count_field: str, *, monthly: bool = False,
) -> dict[date, float | None]:
    required = (
        "MonthEnding",
        "HBT",
        "PatientType",
        "Specialty",
        count_field,
    )
    filters = {"HBT": SCOTLAND, "Specialty": "Z9"}
    if monthly:
        required += ("WaitType",)
        filters["WaitType"] = "Ongoing"
    required_types = {"New Outpatient", "Inpatient/Day case"}
    components: dict[date, dict[str, float | None]] = {}
    for row in _datastore_records(
        resource_id,
        filters=filters,
        required_fields=required,
        sort="MonthEnding",
    ):
        patient_type = row.get("PatientType")
        if patient_type not in required_types:
            continue
        if monthly and row.get("WaitType") != "Ongoing":
            continue
        day = _month_end(row["MonthEnding"])
        stage_counts = components.setdefault(day, {})
        if patient_type in stage_counts:
            raise ValueError(f"duplicate Scottish ongoing wait count: {day} {patient_type}")
        stage_counts[patient_type] = _num(row.get(count_field))
    return {
        day: (
            sum(value for value in counts.values() if value is not None)
            if required_types <= counts.keys() and all(v is not None for v in counts.values())
            else None
        )
        for day, counts in components.items()
    }


def _fetch_rtt() -> list[dict]:
    """Sum both stages, preferring the newer monthly resource's revised observations.

    Incomplete months are omitted, including when the monthly resource suppresses
    a component previously present in the older long-trend resource. Stage medians
    cannot recover a pooled median and are not emitted.
    """
    totals = _rtt_totals(RTT_ONGOING_RESOURCE, "NumberWaiting")
    totals.update(_rtt_totals(RTT_MONTHLY_RESOURCE, "Waits", monthly=True))
    rows = [
        _tidy_row(day, "rtt_waiting_list_total", total)
        for day, total in sorted(totals.items())
        if total is not None
    ]
    return rows


def _fetch_ae_4hr() -> list[dict]:
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


def _fetch_cancer_62day() -> list[dict]:
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
        total = _num(row.get("NumberOfEligibleReferrals62DayStandard"))
        met = _num(row.get("NumberOfEligibleReferralsTreatedWithin62Days"))
        if total is None or met is None:
            continue
        period = _quarter_period(row["Quarter"])
        dates[period] = _quarter_end(row["Quarter"])
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
    match = re.match(r"(\d+)(?:-| days and over$)", waiting_time)
    return bool(match and int(match.group(1)) >= 43)


def _fetch_diagnostics_current() -> dict[date, tuple[float, float]]:
    required = (
        "DiagnosticTestDescription",
        "MonthEnding",
        "Country",
        "WaitingTime",
        "NumberOnList",
    )
    totals_by_group: dict[tuple[date, str], float] = {}
    bands_by_group: dict[tuple[date, str], float] = defaultdict(float)
    breaches_by_group: dict[tuple[date, str], float] = defaultdict(float)
    for row in _datastore_records(
        DIAGNOSTICS_CURRENT_RESOURCE,
        filters={
            "Country": SCOTLAND,
            "DiagnosticTestDescription": ["All Imaging", "All Endoscopy"],
        },
        required_fields=required,
        sort="MonthEnding",
    ):
        if not _is_all_diagnostic_type(row):
            continue
        day = _month_end(row["MonthEnding"])
        value = _num(row.get("NumberOnList"))
        if value is None:
            continue
        band = str(row.get("WaitingTime") or "")
        key = (day, str(row["DiagnosticTestDescription"]))
        if band == "Total Number Waiting":
            totals_by_group[key] = value
        elif re.match(r"^\d+(?:-| days and over$)", band):
            bands_by_group[key] += value
            if _is_six_week_breach_band(band):
                breaches_by_group[key] += value
    totals: dict[date, float] = defaultdict(float)
    breaches: dict[date, float] = defaultdict(float)
    # Early quarters include a total row alongside bands; later months contain
    # only the exhaustive disjoint bands. Never count both in the denominator.
    for key, band_total in bands_by_group.items():
        day, _test = key
        totals[day] += totals_by_group.get(key, band_total)
        breaches[day] += breaches_by_group[key]
    return {day: (totals[day], breaches[day]) for day in totals}


def _fetch_diagnostics_archive() -> dict[date, tuple[float, float]]:
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
        total = _num(row.get("NumberOnList"))
        breach = _num(row.get("NumberWaitingOverSixWeeks"))
        if total is None or breach is None:
            continue
        totals[day] += total
        breaches[day] += breach
    return {day: (totals[day], breaches[day]) for day in totals}


def _fetch_diagnostics_6week() -> list[dict]:
    by_day = _fetch_diagnostics_archive()
    by_day.update(_fetch_diagnostics_current())
    return [
        _tidy_row(day, "diagnostics_6week_breach_pct", breach / total * 100)
        for day, (total, breach) in sorted(by_day.items())
        if total
    ]


def fetch(start_year: int | None = None, end_year: int | None = None) -> list[dict]:
    """Fetch tidy Scotland waiting-time rows for the inclusive year range."""
    start, end = _util.year_bounds(start_year, end_year)
    rows: list[dict] = []
    for metric, fetcher in (
        ("rtt", _fetch_rtt),
        ("ae_4hr_pct", _fetch_ae_4hr),
        ("cancer_62day_pct", _fetch_cancer_62day),
        ("diagnostics_6week_breach_pct", _fetch_diagnostics_6week),
    ):
        try:
            rows.extend(fetcher())
        except Exception as exc:  # noqa: BLE001 - keep other metrics available
            _util.warn(NATION_CODE, metric, exc)
    return sorted(
        _util.filter_rows_by_year(rows, start, end),
        key=lambda row: (row["metric"], row["date"]),
    )
