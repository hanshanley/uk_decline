"""Comparable general-government interest payments as a share of expenditure."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import io
import math
import re

import pandas as pd

from europe_data._http import get_json, get_text
from investment_data.sources import flags

BASE = "https://sdmx.oecd.org/public/rest/v1/data"
FLOW = "OECD.ECO.MAD,DSD_EO@DF_EO"
METADATA_URL = "https://sdmx.oecd.org/public/rest/v1/dataflow/OECD.ECO.MAD/DSD_EO@DF_EO/latest"
COUNTRIES = {
    "GBR": "United Kingdom", "USA": "United States", "DEU": "Germany",
    "FRA": "France", "ITA": "Italy",
}
CURRENCIES = {"GBR": "GBP", "USA": "USD", "DEU": "EUR", "FRA": "EUR", "ITA": "EUR"}
DIMENSIONS = dict(REF_AREA="+".join(COUNTRIES), MEASURE="GGINTP+YPGT", FREQ="A")
UNIT = "percent of total government expenditure"
FIELDS = [
    "iso3", "country", "year", "value", "unit", "interest", "expenditure", "currency",
    "status", "interest_series_id", "expenditure_series_id", "source_url", "retrieved_utc",
    "source_vintage",
]
BASELINE_END = {code: 2025 for code in COUNTRIES}


def parse(
    text: str, *, end: int, retrieved: str, source_url: str, flow: str, vintage: str,
) -> pd.DataFrame:
    reader = csv.DictReader(io.StringIO(text))
    required = {
        "DATAFLOW", *DIMENSIONS, "TIME_PERIOD", "OBS_VALUE", "UNIT_MULT",
        "CURRENCY", "UNIT_MEASURE", "PRICE_BASE", "ADJUSTMENT", "OBS_STATUS",
    }
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("OECD interest-budget data has missing columns")
    agency, dataset, version = flow.split(",")
    identifier = f"{agency}:{dataset}({version})"
    seen, observations = set(), {}
    for row in reader:
        if None in row or any(row[field] is None for field in required):
            raise ValueError("Malformed OECD interest-budget observation")
        # OECD omits the US currency attribute; XDC and US geography still identify dollars.
        if (
            row["DATAFLOW"] != identifier
            or any(row[dim] not in expected.split("+") for dim, expected in DIMENSIONS.items())
            or row["UNIT_MEASURE"] != "XDC" or row["PRICE_BASE"] != "V"
            or row["ADJUSTMENT"] not in ("", "N")
            or row["CURRENCY"] not in (
                ("USD", "") if row["REF_AREA"] == "USA" else (CURRENCIES.get(row["REF_AREA"]),)
            )
        ):
            raise ValueError("Unexpected OECD government interest/expenditure definition")
        if not re.fullmatch(r"\d{4}", row["TIME_PERIOD"]):
            raise ValueError("Invalid OECD interest-budget year")
        code, year, transaction = row["REF_AREA"], int(row["TIME_PERIOD"]), row["MEASURE"]
        key = code, year, transaction
        if key in seen or not 2000 <= year <= end:
            raise ValueError(f"Duplicate or out-of-range OECD interest-budget observation: {key}")
        seen.add(key)
        status = flags(*(row.get(field, "") for field in (
            "OBS_STATUS", "OBS_STATUS_2", "OBS_STATUS_3", "OBS_STATUS2",
        )))
        if not row["OBS_VALUE"] or "F" in status:
            continue
        multiplier = int(row["UNIT_MULT"])
        if not -24 <= multiplier <= 24:
            raise ValueError("Invalid OECD interest-budget unit multiplier")
        try:
            value = float(Decimal(row["OBS_VALUE"]).scaleb(multiplier))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid OECD interest/expenditure number: {key}") from exc
        if not math.isfinite(value) or value < 0 or (transaction == "YPGT" and value == 0):
            raise ValueError(f"Invalid OECD interest/expenditure value: {key}")
        series_id = flow + "/" + ".".join(row[dim] for dim in DIMENSIONS)
        observations[key] = value, status, series_id
    rows = []
    for code, year in sorted({(code, year) for code, year, _ in observations}):
        if (code, year, "GGINTP") not in observations or (code, year, "YPGT") not in observations:
            raise ValueError(f"Unmatched OECD interest and total expenditure: {code} {year}")
        numerator, numerator_status, numerator_id = observations[code, year, "GGINTP"]
        denominator, denominator_status, denominator_id = observations[code, year, "YPGT"]
        rows.append(dict(
            iso3=code, country=COUNTRIES[code], year=year,
            value=100 * numerator / denominator, unit=UNIT,
            interest=numerator, expenditure=denominator, currency=CURRENCIES[code],
            status=flags(numerator_status, denominator_status),
            interest_series_id=numerator_id, expenditure_series_id=denominator_id,
            source_url=source_url, retrieved_utc=retrieved, source_vintage=vintage,
        ))
    return pd.DataFrame(rows, columns=FIELDS)


def validate(frame: pd.DataFrame, previous: pd.DataFrame | None = None) -> pd.DataFrame:
    if missing := set(FIELDS) - set(frame.columns):
        raise ValueError(f"Interest-budget data has missing fields: {sorted(missing)}")
    frame = frame[FIELDS].copy()
    frame["status"] = frame["status"].fillna("").map(flags)
    if frame.empty or frame.isna().any().any():
        raise ValueError("Interest-budget data has missing observations or provenance")
    if (
        not frame["source_url"].str.startswith(f"{BASE}/{FLOW},").all()
        or not pd.to_datetime(frame["retrieved_utc"], errors="raise", utc=True).notna().all()
        or frame["source_vintage"].nunique() != 1
        or not frame["source_vintage"].str.fullmatch(r"OECD Economic Outlook(?: No)? \d+").all()
    ):
        raise ValueError("Interest-budget data has invalid source provenance")
    for column in ("year", "value", "interest", "expenditure"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not frame[column].map(math.isfinite).all():
            raise ValueError("Interest-budget data has non-finite values")
    if (
        frame["year"].mod(1).ne(0).any()
        or frame["year"].lt(2000).any()
        or frame["year"].ge(datetime.now(timezone.utc).year).any()
        or frame.duplicated(["iso3", "year"]).any()
        or not frame["unit"].eq(UNIT).all()
        or (frame["interest"] < 0).any() or (frame["expenditure"] <= 0).any()
        or not frame["value"].between(0, 100).all()
        or frame["status"].str.split(";").map(lambda codes: "F" in codes).any()
    ):
        raise ValueError("Invalid interest-budget years, values, units or forecast observations")
    if set(frame["iso3"]) != set(COUNTRIES):
        raise ValueError("Interest-budget data is missing required countries")
    frame["year"] = frame["year"].astype(int)
    for code, country in COUNTRIES.items():
        part = frame[frame["iso3"] == code]
        if not part["country"].eq(country).all() or not part["currency"].eq(CURRENCIES[code]).all():
            raise ValueError(f"Incompatible interest-budget country or currency: {code}")
        for measure, column in (("GGINTP", "interest_series_id"), ("YPGT", "expenditure_series_id")):
            pattern = re.escape(FLOW) + rf",\d+\.\d+/{code}\.{measure}\.A"
            if not part[column].str.fullmatch(pattern).all():
                raise ValueError(f"Incompatible interest-budget series: {code} {measure}")
        if not set(range(2000, BASELINE_END[code] + 1)).issubset(set(part["year"])):
            raise ValueError(f"Interest-budget data lost published annual coverage: {code}")
    versions = frame["interest_series_id"].str.split("/").str[0]
    if versions.nunique() != 1 or not versions.eq(
        frame["expenditure_series_id"].str.split("/").str[0]
    ).all():
        raise ValueError("Interest-budget data mixes OECD editions between components or years")
    expected = 100 * frame["interest"] / frame["expenditure"]
    if not all(math.isclose(actual, target, rel_tol=1e-10, abs_tol=1e-10)
               for actual, target in zip(frame["value"], expected)):
        raise ValueError("Interest-budget percentage does not match its source numerator/denominator")
    if previous is not None:
        current = pd.MultiIndex.from_frame(frame[["iso3", "year"]])
        old = pd.MultiIndex.from_frame(previous[["iso3", "year"]])
        if not old.isin(current).all():
            raise ValueError("Interest-budget refresh lost previously published observations")
    return frame.sort_values(["iso3", "year"]).reset_index(drop=True)


def fetch() -> pd.DataFrame:
    end = datetime.now(timezone.utc).year - 1
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    metadata = get_json(METADATA_URL, params={"references": "none"}, timeout=120)
    releases = metadata.get("data", {}).get("dataflows", [])
    if len(releases) != 1:
        raise ValueError("OECD Economic Outlook metadata does not identify one current edition")
    release = releases[0]
    if (
        release.get("agencyID") != "OECD.ECO.MAD"
        or release.get("id") != "DSD_EO@DF_EO"
        or not re.fullmatch(r"\d+\.\d+", release.get("version", ""))
        or not re.fullmatch(r"Economic Outlook(?: No)? \d+", release.get("name", ""))
    ):
        raise ValueError("Unexpected OECD Economic Outlook edition metadata")
    flow, vintage = FLOW + "," + release["version"], "OECD " + release["name"]
    url = f"{BASE}/{flow}/" + ".".join(DIMENSIONS.values())
    params = {"format": "csvfile", "startPeriod": "2000", "endPeriod": str(end)}
    text = get_text(url, params=params, timeout=120)
    source_url = url + f"?format=csvfile&startPeriod=2000&endPeriod={end}"
    return validate(parse(
        text, end=end, retrieved=retrieved, source_url=source_url, flow=flow, vintage=vintage,
    ))
