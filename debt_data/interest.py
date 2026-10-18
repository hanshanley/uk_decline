"""Central/federal government interest payments relative to its own spending."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import io
import math
import re

from bs4 import BeautifulSoup
import pandas as pd
import requests

from europe_data._http import get_json, get_text
from investment_data.sources import flags

BASE = "https://sdmx.oecd.org/public/rest/v1/data"
FLOW = "OECD.SDD.NAD,DSD_NASEC10@DF_TABLE12"
METADATA_URL = "https://sdmx.oecd.org/public/rest/v1/dataflow/OECD.SDD.NAD/DSD_NASEC10@DF_TABLE12/latest"
COUNTRIES = {
    "GBR": "United Kingdom", "USA": "United States", "DEU": "Germany",
    "FRA": "France", "ITA": "Italy",
}
CURRENCIES = {"GBR": "GBP", "USA": "USD", "DEU": "EUR", "FRA": "EUR", "ITA": "EUR"}
DIMENSIONS = dict(
    FREQ="A", REF_AREA="+".join(code for code in COUNTRIES if code != "USA"),
    SECTOR="S1311", COUNTERPART_SECTOR="_Z", ACCOUNTING_ENTRY="D",
    TRANSACTION="D41+OTE", INSTR_ASSET="_Z", EXPENDITURE="_Z",
    UNIT_MEASURE="XDC", VALUATION="S", PRICE_BASE="V", TRANSFORMATION="N",
    TABLE_IDENTIFIER="T0200",
)
OECD_VINTAGE = "OECD National Accounts, central government S1311"
US_SERIES = {
    "interest": ("A091RC1A027NBEA", "Monetary interest paid: Government: Federal"),
    "expenditure": ("W019RC1A027NBEA", "Federal government total expenditures"),
}
FRED_BASE = "https://fred.stlouisfed.org/data/"
UNIT = "percent of central/federal government expenditure"
FIELDS = [
    "iso3", "country", "year", "value", "unit", "interest", "expenditure", "currency",
    "status", "interest_series_id", "expenditure_series_id",
    "interest_source_url", "expenditure_source_url", "retrieved_utc", "source_vintage",
]
BASELINE_END = {code: 2025 for code in COUNTRIES}


def _scaled(value: str, multiplier: int) -> float:
    if not -24 <= multiplier <= 24:
        raise ValueError("Invalid central-interest unit multiplier")
    try:
        result = float(Decimal(value).scaleb(multiplier))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid central-interest number: {value!r}") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Invalid central-interest value: {value!r}")
    return result


def _row(code: str, year: int, numerator: float, denominator: float, retrieved: str) -> dict:
    if denominator <= 0:
        raise ValueError(f"Non-positive central-government spending: {code} {year}")
    return dict(
        iso3=code, country=COUNTRIES[code], year=year,
        value=100 * numerator / denominator, unit=UNIT,
        interest=numerator, expenditure=denominator, currency=CURRENCIES[code],
        status="", retrieved_utc=retrieved,
    )


def parse(text: str, *, end: int, retrieved: str, source_url: str, flow: str) -> pd.DataFrame:
    reader = csv.DictReader(io.StringIO(text))
    required = {
        "DATAFLOW", *DIMENSIONS, "TIME_PERIOD", "OBS_VALUE", "UNIT_MULT",
        "CURRENCY", "CONSOLIDATION", "OBS_STATUS",
    }
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("OECD central-interest data has missing columns")
    agency, dataset, version = flow.split(",")
    identifier = f"{agency}:{dataset}({version})"
    seen, observations = set(), {}
    for row in reader:
        if None in row or any(row[field] is None for field in required):
            raise ValueError("Malformed OECD central-interest observation")
        if (
            row["DATAFLOW"] != identifier
            or any(row[dim] not in expected.split("+") for dim, expected in DIMENSIONS.items())
            or row["CONSOLIDATION"] != ("C" if row["TRANSACTION"] == "D41" else "P")
            or row["CURRENCY"] != CURRENCIES.get(row["REF_AREA"])
        ):
            raise ValueError("Unexpected OECD central-government interest/expenditure definition")
        if not re.fullmatch(r"\d{4}", row["TIME_PERIOD"]):
            raise ValueError("Invalid OECD central-interest year")
        code, year, transaction = row["REF_AREA"], int(row["TIME_PERIOD"]), row["TRANSACTION"]
        key = code, year, transaction
        if key in seen or not 2000 <= year <= end:
            raise ValueError(f"Duplicate or out-of-range OECD central-interest observation: {key}")
        seen.add(key)
        status = flags(*(row.get(field, "") for field in (
            "OBS_STATUS", "OBS_STATUS_2", "OBS_STATUS_3", "OBS_STATUS2",
        )))
        if not row["OBS_VALUE"] or "F" in status:
            continue
        value = _scaled(row["OBS_VALUE"], int(row["UNIT_MULT"]))
        series_id = flow + "/" + ".".join(row[dim] for dim in DIMENSIONS)
        observations[key] = value, status, series_id
    rows = []
    for code, year in sorted({(code, year) for code, year, _ in observations}):
        if (code, year, "D41") not in observations or (code, year, "OTE") not in observations:
            raise ValueError(f"Unmatched central-government interest and total expenditure: {code} {year}")
        numerator, numerator_status, numerator_id = observations[code, year, "D41"]
        denominator, denominator_status, denominator_id = observations[code, year, "OTE"]
        record = _row(code, year, numerator, denominator, retrieved)
        record.update(
            status=flags(numerator_status, denominator_status),
            interest_series_id=numerator_id, expenditure_series_id=denominator_id,
            interest_source_url=source_url, expenditure_source_url=source_url,
            source_vintage=OECD_VINTAGE,
        )
        rows.append(record)
    return pd.DataFrame(rows, columns=FIELDS)


def parse_federal(text: str, component: str, *, end: int) -> tuple[dict[int, float], str]:
    code, title = US_SERIES[component]
    soup = BeautifulSoup(text, "html.parser")
    metadata = {}
    for table in soup.select("table:not(#data-table-observations)"):
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            if len(cells) == 2:
                metadata[cells[0]] = cells[1]
    expected = {
        "Series ID": code, "Title": title, "Source": "U.S. Bureau of Economic Analysis",
        "Release": "Gross Domestic Product", "Frequency": "Annual",
        "Units": "Billions of Dollars", "Seasonal Adjustment": "Not Seasonally Adjusted",
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Unexpected BEA federal {component} series metadata")
    updated = metadata.get("Last Updated", "")[:10]
    datetime.strptime(updated, "%Y-%m-%d")
    table = soup.find("table", id="data-table-observations")
    if table is None:
        raise ValueError(f"Missing BEA federal {component} observations")
    records = [
        [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        for row in table.find_all("tr")
    ]
    if not records or records[0] != ["DATE", "VALUE"]:
        raise ValueError(f"Unexpected BEA federal {component} observation columns")
    observations, seen = {}, set()
    for record in records[1:]:
        if len(record) != 2 or not re.fullmatch(r"\d{4}-01-01", record[0]):
            raise ValueError(f"Malformed annual BEA federal {component} observation")
        year = int(record[0][:4])
        if year in seen:
            raise ValueError(f"Duplicate BEA federal {component} year: {year}")
        seen.add(year)
        if not 2000 <= year <= end or record[1] in ("", "."):
            continue
        observations[year] = _scaled(record[1], 9)
    return observations, updated


def validate(frame: pd.DataFrame, previous: pd.DataFrame | None = None) -> pd.DataFrame:
    if missing := set(FIELDS) - set(frame.columns):
        raise ValueError(f"Central-interest data has missing fields: {sorted(missing)}")
    frame = frame[FIELDS].copy()
    frame["status"] = frame["status"].fillna("").map(flags)
    if frame.empty or frame.isna().any().any():
        raise ValueError("Central-interest data has missing observations or provenance")
    if pd.to_datetime(frame["retrieved_utc"], errors="raise", utc=True).isna().any():
        raise ValueError("Central-interest data has missing retrieval timestamps")
    for column in ("year", "value", "interest", "expenditure"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not frame[column].map(math.isfinite).all():
            raise ValueError("Central-interest data has non-finite values")
    if (
        frame["year"].mod(1).ne(0).any() or frame["year"].lt(2000).any()
        or frame["year"].ge(datetime.now(timezone.utc).year).any()
        or frame.duplicated(["iso3", "year"]).any() or not frame["unit"].eq(UNIT).all()
        or (frame["interest"] < 0).any() or (frame["expenditure"] <= 0).any()
        or not frame["value"].between(0, 100).all()
        or frame["status"].str.split(";").map(lambda codes: "F" in codes).any()
    ):
        raise ValueError("Invalid central-interest years, values, units or forecast observations")
    if set(frame["iso3"]) != set(COUNTRIES):
        raise ValueError("Central-interest data is missing required countries")
    frame["year"] = frame["year"].astype(int)
    for code, country in COUNTRIES.items():
        part = frame[frame["iso3"] == code]
        if not part["country"].eq(country).all() or not part["currency"].eq(CURRENCIES[code]).all():
            raise ValueError(f"Incompatible central-interest country or currency: {code}")
        if code == "USA":
            for component, (series, _) in US_SERIES.items():
                if (
                    not part[f"{component}_series_id"].eq(series).all()
                    or not part[f"{component}_source_url"].eq(FRED_BASE + series).all()
                ):
                    raise ValueError("US interest and expenditure must both use federal-only series")
            if (
                part["source_vintage"].nunique() != 1
                or not part["source_vintage"].str.fullmatch(
                    r"BEA NIPA \(FRED updated \d{4}-\d{2}-\d{2}\)"
                ).all()
            ):
                raise ValueError("US federal components mix source vintages")
        else:
            for transaction, column in (("D41", "interest_series_id"), ("OTE", "expenditure_series_id")):
                dimensions = dict(DIMENSIONS, REF_AREA=code, TRANSACTION=transaction)
                pattern = re.escape(FLOW) + r",\d+\.\d+/" + re.escape(".".join(dimensions.values()))
                if not part[column].str.fullmatch(pattern).all():
                    raise ValueError(f"Only central government S1311 is allowed: {code} {transaction}")
            if (
                not part["source_vintage"].eq(OECD_VINTAGE).all()
                or any(not part[column].str.startswith(f"{BASE}/{FLOW},").all()
                       for column in ("interest_source_url", "expenditure_source_url"))
            ):
                raise ValueError(f"Invalid central-interest source provenance: {code}")
        if not set(range(2000, BASELINE_END[code] + 1)).issubset(set(part["year"])):
            raise ValueError(f"Central-interest data lost published annual coverage: {code}")
    european = frame[frame["iso3"] != "USA"]
    versions = european["interest_series_id"].str.split("/").str[0]
    if versions.nunique() != 1 or not versions.eq(
        european["expenditure_series_id"].str.split("/").str[0]
    ).all():
        raise ValueError("Central-interest data mixes OECD versions between components or years")
    expected = 100 * frame["interest"] / frame["expenditure"]
    if not all(math.isclose(actual, target, rel_tol=1e-10, abs_tol=1e-10)
               for actual, target in zip(frame["value"], expected)):
        raise ValueError("Central-interest percentage does not match its source numerator/denominator")
    if previous is not None:
        current = pd.MultiIndex.from_frame(frame[["iso3", "year"]])
        old = pd.MultiIndex.from_frame(previous[["iso3", "year"]])
        if not old.isin(current).all():
            raise ValueError("Central-interest refresh lost previously published observations")
    return frame.sort_values(["iso3", "year"]).reset_index(drop=True)


def fetch() -> pd.DataFrame:
    end = datetime.now(timezone.utc).year - 1
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    metadata = get_json(METADATA_URL, params={"references": "none"}, timeout=120)
    releases = metadata.get("data", {}).get("dataflows", [])
    if len(releases) != 1:
        raise ValueError("OECD central-government metadata does not identify one current dataflow")
    release = releases[0]
    if (
        release.get("agencyID") != "OECD.SDD.NAD"
        or release.get("id") != "DSD_NASEC10@DF_TABLE12"
        or not re.fullmatch(r"\d+\.\d+", release.get("version", ""))
    ):
        raise ValueError("Unexpected OECD central-government metadata")
    flow = FLOW + "," + release["version"]
    url = f"{BASE}/{flow}/" + ".".join(DIMENSIONS.values())
    params = {"format": "csvfile", "startPeriod": "2000", "endPeriod": str(end)}
    frame = parse(
        get_text(url, params=params, timeout=120), end=end, retrieved=retrieved,
        source_url=url + f"?format=csvfile&startPeriod=2000&endPeriod={end}", flow=flow,
    )
    components, updates = {}, set()
    for component, (code, _) in US_SERIES.items():
        components[component], updated = parse_federal(
            get_text(FRED_BASE + code, timeout=90, headers={
                "Accept": "text/html", "User-Agent": requests.utils.default_user_agent(),
            }),
            component, end=end,
        )
        updates.add(updated)
    if len(updates) != 1:
        raise ValueError("BEA federal interest and expenditure use different release dates")
    rows = []
    for year in sorted(set.union(*(set(part) for part in components.values()))):
        if any(year not in part for part in components.values()):
            raise ValueError(f"Unmatched BEA federal interest and total expenditure: {year}")
        row = _row("USA", year, components["interest"][year], components["expenditure"][year], retrieved)
        row.update(
            interest_series_id=US_SERIES["interest"][0],
            expenditure_series_id=US_SERIES["expenditure"][0],
            interest_source_url=FRED_BASE + US_SERIES["interest"][0],
            expenditure_source_url=FRED_BASE + US_SERIES["expenditure"][0],
            source_vintage=f"BEA NIPA (FRED updated {next(iter(updates))})",
        )
        rows.append(row)
    return validate(pd.concat([frame, pd.DataFrame(rows, columns=FIELDS)], ignore_index=True))
