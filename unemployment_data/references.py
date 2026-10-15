"""Official monthly EU-27 and US reference rates from Eurostat une_rt_m."""

from __future__ import annotations

import numpy as np
import pandas as pd

from europe_data._http import get_json
from europe_data.eurostat import BASE, _iter_values

from .sources import START

URL = f"{BASE}/une_rt_m"
SOURCE_URL = "https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table?lang=en"
COUNTRIES = {"EU27_2020": "EU", "US": "US"}
METRICS = {"TOTAL": "unemployment_rate", "Y_LT25": "youth_unemployment_rate"}
AGES = {
    ("EU", "unemployment_rate"): "15-74",
    ("EU", "youth_unemployment_rate"): "15-24",
    ("US", "unemployment_rate"): "16+",
    ("US", "youth_unemployment_rate"): "16-24",
}
FIELDS = [
    "date", "country", "age_group", "metric", "value", "unit",
    "seasonal_adjustment", "source", "series_id", "dataset_updated", "source_url", "status",
]


def parse(payload: dict) -> pd.DataFrame:
    if set(payload.get("id", [])) != {"freq", "s_adj", "age", "unit", "sex", "geo", "time"}:
        raise ValueError("Unexpected Eurostat unemployment dimensions")
    records = []
    for coordinate, value, status in _iter_values(payload):
        if value is None:
            continue
        expected = {"freq": "M", "s_adj": "SA", "unit": "PC_ACT", "sex": "T"}
        if any(coordinate[key] != value for key, value in expected.items()) or (
            coordinate["geo"] not in COUNTRIES or coordinate["age"] not in METRICS
        ):
            raise ValueError(f"Unexpected Eurostat unemployment series: {coordinate}")
        country = COUNTRIES[coordinate["geo"]]
        metric = METRICS[coordinate["age"]]
        records.append({
            "date": f"{coordinate['time']}-01", "country": country,
            "age_group": AGES[country, metric], "metric": metric, "value": float(value),
            "unit": "%", "seasonal_adjustment": "Seasonally adjusted",
            "source": "Eurostat une_rt_m",
            "series_id": "une_rt_m." + ".".join(
                coordinate[key] for key in ("freq", "s_adj", "age", "unit", "sex", "geo")
            ),
            "dataset_updated": payload["updated"], "source_url": SOURCE_URL, "status": status,
        })
    return pd.DataFrame(records, columns=FIELDS)


def validate(
    frame: pd.DataFrame, previous: pd.DataFrame | None = None, *,
    require_recent: bool = False, as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    missing = set(FIELDS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing unemployment reference columns: {sorted(missing)}")
    frame = frame[FIELDS].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    if not np.isfinite(frame["value"]).all() or not frame["value"].between(0, 100).all():
        raise ValueError("Unemployment reference rates must be finite percentages between 0 and 100")
    if frame["date"].isna().any() or not frame["date"].dt.is_month_start.all() or (
        frame["date"] < START
    ).any():
        raise ValueError("Unemployment reference dates must be month starts from 2000")
    if frame.duplicated(["country", "metric", "date"]).any():
        raise ValueError("Duplicate unemployment reference observations")
    if set(zip(frame["country"], frame["metric"])) != set(AGES):
        raise ValueError("Expected overall and youth unemployment for both EU and US")
    for column, expected in (
        ("unit", "%"), ("seasonal_adjustment", "Seasonally adjusted"),
        ("source", "Eurostat une_rt_m"), ("source_url", SOURCE_URL),
    ):
        if not frame[column].eq(expected).all():
            raise ValueError(f"Unexpected unemployment reference {column}")
    today = pd.Timestamp.now(tz="UTC").normalize() if as_of is None else pd.Timestamp(as_of)
    today = today.tz_localize("UTC") if today.tzinfo is None else today.tz_convert("UTC")
    updated = pd.to_datetime(frame["dataset_updated"], utc=True, errors="raise")
    if updated.isna().any() or (updated > today + pd.Timedelta(days=1)).any() or (
        frame["date"].dt.tz_localize("UTC") + pd.offsets.MonthEnd(0) > updated
    ).any():
        raise ValueError("Invalid unemployment reference dataset or observation dates")
    if require_recent and ((today - updated).dt.days > 90).any():
        raise ValueError("Eurostat unemployment dataset is more than 90 days old")
    required = set(pd.date_range(START, "2025-12-01", freq="MS"))
    for (country, metric), age in AGES.items():
        part = frame.loc[(frame["country"] == country) & (frame["metric"] == metric)]
        geo = next(code for code, name in COUNTRIES.items() if name == country)
        age_code = next(code for code, name in METRICS.items() if name == metric)
        expected_id = f"une_rt_m.M.SA.{age_code}.PC_ACT.T.{geo}"
        if not part["age_group"].eq(age).all() or not part["series_id"].eq(expected_id).all():
            raise ValueError(f"Wrong unemployment reference definition for {country}/{metric}")
        # No US household survey was collected in October 2025 (federal shutdown).
        baseline = required - {pd.Timestamp("2025-10-01")} if country == "US" else required
        if not baseline.issubset(set(part["date"])):
            raise ValueError(f"Missing required unemployment reference history for {country}/{metric}")
        if require_recent and (today.tz_localize(None) - part["date"].max()).days > 120:
            raise ValueError(f"Latest unemployment reference is more than 120 days old: {country}/{metric}")
    if previous is not None:
        saved = validate(previous, as_of=today)
        keys = ["country", "metric", "date"]
        if not set(saved[keys].itertuples(index=False, name=None)).issubset(
            set(frame[keys].itertuples(index=False, name=None))
        ):
            raise ValueError("Unemployment reference refresh lost previously published observations")
    frame["status"] = frame["status"].fillna("")
    return frame.sort_values(["metric", "country", "date"]).reset_index(drop=True)


def fetch() -> pd.DataFrame:
    payload = get_json(URL, params={
        "lang": "en", "freq": "M", "s_adj": "SA", "sex": "T", "unit": "PC_ACT",
        "geo": list(COUNTRIES), "age": list(METRICS), "sinceTimePeriod": "2000-01",
    }, timeout=90)
    return validate(parse(payload), require_recent=True)
