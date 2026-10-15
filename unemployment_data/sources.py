"""Download and validate comparable UK Labour Force Survey unemployment rates."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
import re

import numpy as np
import pandas as pd

from europe_data._http import get_text

START = pd.Timestamp("2000-01-01")
SOURCE = "Office for National Statistics, Labour Force Survey"
SERIES = {
    "unemployment_rate": (
        "MGSX", "16+", "Unemployment rate (aged 16 and over, seasonally adjusted): %",
    ),
    "youth_unemployment_rate": (
        "MGWY", "16-24", "LFS: Unemployment rate: UK: All: Aged 16-24: %: SA",
    ),
}
FIELDS = [
    "date", "period_start", "period_end", "country", "age_group", "metric",
    "value", "unit", "seasonal_adjustment", "source", "series_id", "release_date",
]


def parse_series(text: str, metric: str) -> pd.DataFrame:
    """Keep rolling three-month observations, not annual or quarterly aggregates."""
    series_id, age_group, title = SERIES[metric]
    rows = list(csv.reader(StringIO(text)))
    metadata = {}
    metadata_keys = {"Title", "CDID", "Source dataset ID", "Unit", "Release date"}
    for row in rows:
        if row and row[0] in metadata_keys:
            if len(row) != 2 or row[0] in metadata:
                raise ValueError(f"Malformed or duplicate ONS metadata: {row}")
            metadata[row[0]] = row[1].strip()
    expected = {
        "Title": title, "CDID": series_id, "Source dataset ID": "LMS", "Unit": "%",
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"Unexpected ONS {series_id} {key}: {metadata.get(key)!r}")
    release = datetime.strptime(metadata["Release date"], "%d-%m-%Y").date()
    records = []
    for row in rows:
        if not row or not re.fullmatch(r"\d{4} [A-Z]{3}", row[0]):
            continue
        if len(row) != 2:
            raise ValueError(f"Malformed ONS {series_id} observation: {row}")
        date = pd.Timestamp(datetime.strptime(row[0], "%Y %b"))
        if not row[1].strip():
            continue
        records.append({
            "date": date,
            "period_start": date - pd.DateOffset(months=1),
            "period_end": (date.to_period("M") + 1).end_time.normalize(),
            "country": "UK", "age_group": age_group, "metric": metric,
            "value": float(row[1]), "unit": "%",
            "seasonal_adjustment": "Seasonally adjusted", "source": SOURCE,
            "series_id": series_id, "release_date": release,
        })
    frame = pd.DataFrame(records, columns=FIELDS)
    if frame.empty or frame.duplicated("date").any():
        raise ValueError(f"Missing or duplicate ONS {series_id} monthly observations")
    return frame.loc[frame["date"] >= START].reset_index(drop=True)


def validate(
    frame: pd.DataFrame,
    previous: pd.DataFrame | None = None,
    *,
    require_recent: bool = False,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    missing = set(FIELDS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing unemployment columns: {sorted(missing)}")
    frame = frame[FIELDS].copy()
    for column in ("date", "period_start", "period_end", "release_date"):
        frame[column] = pd.to_datetime(frame[column], errors="raise")
        if frame[column].isna().any() or (
            frame[column] != frame[column].dt.normalize()
        ).any():
            raise ValueError(f"Invalid unemployment {column}")
    frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    if not np.isfinite(frame["value"]).all() or not frame["value"].between(0, 100).all():
        raise ValueError("Unemployment rates must be finite percentages between 0 and 100")
    if frame.duplicated(["metric", "date"]).any():
        raise ValueError("Duplicate unemployment metric/date observations")
    if set(frame["metric"]) != set(SERIES):
        raise ValueError("Expected both overall and youth unemployment rates")
    for column, expected in (
        ("country", "UK"), ("unit", "%"), ("source", SOURCE),
        ("seasonal_adjustment", "Seasonally adjusted"),
    ):
        if not frame[column].eq(expected).all():
            raise ValueError(f"Unexpected unemployment {column}")
    if not frame["date"].dt.is_month_start.all() or (frame["date"] < START).any():
        raise ValueError("Unemployment dates must be centre-month starts from 2000")
    periods = frame["date"].dt.to_period("M")
    if not frame["period_start"].eq((periods - 1).dt.to_timestamp()).all() or not (
        frame["period_end"].eq((periods + 1).dt.end_time.dt.normalize()).all()
    ):
        raise ValueError("Unemployment reference periods must span three centred months")
    today = (
        pd.Timestamp(datetime.now(timezone.utc).date())
        if as_of is None else pd.Timestamp(as_of).normalize()
    )
    if (frame["period_end"] > frame["release_date"]).any() or (
        frame["release_date"] > today
    ).any():
        raise ValueError("Unemployment reference or release dates are inconsistent")
    if frame["release_date"].nunique() != 1:
        raise ValueError("Overall and youth unemployment must use the same ONS release")
    if require_recent and (today - frame["release_date"].iloc[0]).days > 90:
        raise ValueError("ONS unemployment release is more than 90 days old")
    required = set(pd.date_range(START, "2025-12-01", freq="MS"))
    latest = set()
    for metric, (series_id, age_group, _) in SERIES.items():
        part = frame.loc[frame["metric"] == metric]
        if not part["series_id"].eq(series_id).all() or not part["age_group"].eq(age_group).all():
            raise ValueError(f"Wrong series or age group for {metric}")
        if not required.issubset(set(part["date"])):
            raise ValueError(f"Missing required 2000-2025 monthly coverage for {metric}")
        latest.add(part["date"].max())
    if len(latest) != 1:
        raise ValueError("Overall and youth unemployment have different latest periods")
    if previous is not None:
        saved = validate(previous, as_of=today)
        old_keys = set(zip(saved["metric"], saved["date"]))
        new_keys = set(zip(frame["metric"], frame["date"]))
        if not old_keys.issubset(new_keys):
            raise ValueError("Unemployment refresh lost previously published observations")
    return frame.sort_values(["metric", "date"]).reset_index(drop=True)


def fetch() -> pd.DataFrame:
    frames = []
    for metric, (series_id, _, _) in SERIES.items():
        uri = (
            "/employmentandlabourmarket/peoplenotinwork/unemployment/"
            f"timeseries/{series_id.lower()}/lms"
        )
        text = get_text(
            "https://www.ons.gov.uk/generator",
            params={"format": "csv", "uri": uri}, timeout=90,
        )
        frames.append(parse_series(text, metric))
    return validate(pd.concat(frames, ignore_index=True), require_recent=True)
