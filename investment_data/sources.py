"""Official spending/GDP series, with auditable same-year currency denominators."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import math
import re

import numpy as np
import pandas as pd

from europe_data._http import get_json, get_text
from europe_data.eurostat import BASE as EUROSTAT, _iter_values

BASE = "https://sdmx.oecd.org/public/rest/v1/data"
START = 2000
TRANSPORT = "inland_transport_investment_pct_gdp"
CAPITAL = "public_fixed_investment_pct_gdp"
BUDGET = "government_rd_budget_pct_gdp"
RESEARCH = "total_rd_expenditure_pct_gdp"
MILITARY = "military_expenditure_pct_gdp"
UNIT = "percent of GDP"
COUNTRIES = {
    "GBR": "United Kingdom", "USA": "United States", "POL": "Poland",
    "EU27_2020": "EU-27", "EUU": "European Union",
}
CURRENCIES = {"GBR": "GBP", "USA": "USD", "POL": "PLN", "EU27_2020": "EUR"}
AREA = "GBR+USA+POL+EU27_2020"
NATIONAL_AREA = "GBR+USA+POL"
FLOWS = {
    "capital": (
        "OECD.SDD.NAD,DSD_NASEC10@DF_TABLE12,1.1",
        dict(FREQ="A", REF_AREA=AREA, SECTOR="S13", COUNTERPART_SECTOR="_Z",
             ACCOUNTING_ENTRY="D", TRANSACTION="P51G", INSTR_ASSET="_Z",
             EXPENDITURE="_Z", UNIT_MEASURE="XDC", VALUATION="S", PRICE_BASE="V",
             TRANSFORMATION="N", TABLE_IDENTIFIER="T0200"),
    ),
    "gdp": (
        "OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE1_EXPENDITURE,2.0",
        dict(FREQ="A", REF_AREA=AREA, SECTOR="S1", COUNTERPART_SECTOR="S1",
             TRANSACTION="B1GQ", INSTR_ASSET="_Z", ACTIVITY="_Z", EXPENDITURE="_Z",
             UNIT_MEASURE="XDC", PRICE_BASE="V", TRANSFORMATION="N",
             TABLE_IDENTIFIER="T0102"),
    ),
    "budget": (
        "OECD.STI.STP,DSD_RDS_GOV@DF_GBARD_NABS07,1.0",
        dict(REF_AREA=NATIONAL_AREA, FREQ="A", MEASURE="C", SEO="_T", FUNDMODE="_T",
             TRANSCOORD="_Z", UNIT_MEASURE="XDC", PRICE_BASE="V"),
    ),
    "research": (
        "OECD.STI.STP,DSD_MSTI@DF_MSTI,1.3",
        dict(REF_AREA=AREA, FREQ="A", MEASURE="G", UNIT_MEASURE="PT_B1GQ",
             PRICE_BASE="_Z", TRANSFORMATION="_Z"),
    ),
}
EU_BUDGET_URL = f"{EUROSTAT}/gba_nabsfin07"
MILITARY_INDICATOR = "MS.MIL.XPND.GD.ZS"
MILITARY_URL = (
    "https://api.worldbank.org/v2/country/GBR;USA;POL;EUU/indicator/"
    + MILITARY_INDICATOR
)
FIELDS = [
    "metric", "iso3", "country", "year", "value", "unit", "status", "source",
    "series_id", "source_url", "numerator", "gdp", "currency", "gdp_series_id",
    "gdp_source_url", "retrieved_utc",
]
# Initial published coverage, not a requirement to fill genuine missing observations.
BASELINES = {
    CAPITAL: {code: (2000, 2024 if code == "USA" else 2025, ()) for code in CURRENCIES},
    BUDGET: {
        "GBR": (2000, 2023, ()), "USA": (2000, 2025, ()),
        "POL": (2000, 2024, (2002, 2003)), "EU27_2020": (2004, 2025, ()),
    },
    RESEARCH: {code: (2000, 2023 if code == "GBR" else 2024, ()) for code in CURRENCIES},
    MILITARY: {code: (2000, 2025, ()) for code in ("GBR", "USA", "POL", "EUU")},
}
STATUS_CODES = set("ABDEFGIKWOMPSLHQJNUV")


def flags(*values: str) -> str:
    codes = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"Unknown spending observation status: {value}")
        if not value:
            continue
        parts = value.upper().split(";")
        if any(len(part) != 1 or part not in STATUS_CODES for part in parts):
            raise ValueError(f"Unknown spending observation status: {value}")
        codes.update(parts)
    return ";".join(sorted(codes - {"A"}))


def parse_oecd(text: str, name: str, end: int) -> dict[tuple[str, int], dict]:
    flow, dimensions = FLOWS[name]
    reader = csv.DictReader(io.StringIO(text))
    required = {*dimensions, "DATAFLOW", "TIME_PERIOD", "OBS_VALUE", "UNIT_MULT", "OBS_STATUS"}
    if dimensions["UNIT_MEASURE"] == "XDC":
        required.add("CURRENCY")
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f"Missing OECD {name} columns")
    agency, dataset, version = flow.split(",")
    identifier = f"{agency}:{dataset}({version})"
    records = {}
    seen = set()
    for row in reader:
        if row["DATAFLOW"] != identifier or any(
            row[dim] not in expected.split("+") for dim, expected in dimensions.items()
        ):
            raise ValueError(f"Unexpected OECD {name} definition: {row}")
        if not re.fullmatch(r"\d{4}", row["TIME_PERIOD"]):
            raise ValueError(f"Invalid OECD {name} year")
        code, year = row["REF_AREA"], int(row["TIME_PERIOD"])
        key = code, year
        if key in seen or not START <= year <= end:
            raise ValueError(f"Duplicate or out-of-range OECD {name} observation: {key}")
        seen.add(key)
        status = flags(*(row.get(col, "") for col in (
            "OBS_STATUS", "OBS_STATUS_2", "OBS_STATUS_3", "OBS_STATUS2",
        )))
        if not row["OBS_VALUE"] or "F" in status:
            continue
        value = float(row["OBS_VALUE"]) * 10 ** int(row["UNIT_MULT"])
        if not math.isfinite(value) or value < 0 or (name == "gdp" and value == 0):
            raise ValueError(f"Invalid OECD {name} value: {key}")
        currency = row.get("CURRENCY", "")
        if dimensions["UNIT_MEASURE"] == "XDC" and currency != CURRENCIES[code]:
            raise ValueError(f"Unexpected OECD {name} currency: {key} {currency}")
        series_id = flow + "/" + ".".join(row[dim] for dim in dimensions)
        records[key] = dict(
            value=value, status=status, currency=currency,
            source="OECD " + dataset, series_id=series_id,
            source_url=f"{BASE}/{series_id}?format=csvfile",
        )
    if not records:
        raise ValueError(f"OECD {name} returned no usable observations")
    return records


def _record(metric: str, code: str, year: int, raw: dict, retrieved: str) -> dict:
    return {
        "metric": metric, "iso3": code, "country": COUNTRIES[code], "year": year,
        "value": raw["value"], "unit": UNIT, "status": raw["status"],
        "source": raw["source"], "series_id": raw["series_id"],
        "source_url": raw["source_url"], "numerator": None, "gdp": None,
        "currency": "", "gdp_series_id": "", "gdp_source_url": "",
        "retrieved_utc": retrieved,
    }


def ratio_rows(
    metric: str, numerators: dict, denominators: dict, retrieved: str,
) -> list[dict]:
    rows = []
    for (code, year), numerator in numerators.items():
        denominator = denominators.get((code, year))
        if denominator is None or denominator["currency"] != numerator["currency"]:
            raise ValueError(f"Missing or currency-mismatched GDP for {metric}: {code} {year}")
        if denominator["value"] <= 0:
            raise ValueError(f"Non-positive GDP for {code} {year}")
        row = _record(metric, code, year, numerator, retrieved)
        row.update(
            value=100 * numerator["value"] / denominator["value"],
            numerator=numerator["value"], gdp=denominator["value"],
            currency=numerator["currency"], gdp_series_id=denominator["series_id"],
            gdp_source_url=denominator["source_url"],
            status=flags(numerator["status"], denominator["status"]),
            source=numerator["source"] + "; OECD nominal GDP",
        )
        rows.append(row)
    return rows


def parse_eu_budget(payload: dict, retrieved: str, end: int) -> list[dict]:
    expected = dict(freq="A", nabs07="TOTAL", unit="PC_GDP", geo="EU27_2020")
    if set(payload.get("id", [])) != {*expected, "time"}:
        raise ValueError("Unexpected Eurostat research-budget dimensions")
    rows = []
    for coord, value, status in _iter_values(payload):
        if any(coord[dim] != val for dim, val in expected.items()):
            raise ValueError(f"Unexpected Eurostat research-budget definition: {coord}")
        year = int(coord["time"])
        if not START <= year <= end:
            raise ValueError("Out-of-range Eurostat research-budget year")
        if value is None:
            continue
        source_status = flags(*status.upper().replace(" ", ""))
        if "F" in source_status:
            continue
        rows.append(_record(BUDGET, "EU27_2020", year, dict(
            value=float(value), status=source_status, source="Eurostat gba_nabsfin07",
            series_id="gba_nabsfin07.A.TOTAL.PC_GDP.EU27_2020",
            source_url=EU_BUDGET_URL + "?freq=A&nabs07=TOTAL&unit=PC_GDP&geo=EU27_2020",
        ), retrieved))
    return rows


def parse_military(payload: list, retrieved: str, end: int) -> list[dict]:
    if (
        not isinstance(payload, list) or len(payload) != 2
        or payload[0].get("pages") != 1 or payload[0].get("sourceid") != "2"
        or not isinstance(payload[1], list) or payload[0].get("total") != len(payload[1])
    ):
        raise ValueError("Incomplete World Bank military-expenditure response")
    rows = []
    for item in payload[1]:
        code, year = item["countryiso3code"], int(item["date"])
        if (
            item["indicator"]["id"] != MILITARY_INDICATOR
            or code not in BASELINES[MILITARY] or not START <= year <= end
        ):
            raise ValueError("Unexpected World Bank military-expenditure definition")
        if item["value"] is None:
            continue
        status = flags(item["obs_status"])
        if "F" in status:
            continue
        rows.append(_record(MILITARY, code, year, dict(
            value=float(item["value"]), status=status,
            source="SIPRI via World Bank WDI",
            series_id=f"WDI.{MILITARY_INDICATOR}.{code}",
            source_url=f"https://api.worldbank.org/v2/country/{code}/indicator/{MILITARY_INDICATOR}",
        ), retrieved))
    return rows


def validate(frame: pd.DataFrame, previous: pd.DataFrame | None = None) -> pd.DataFrame:
    if missing := set(FIELDS) - set(frame.columns):
        raise ValueError(f"Missing investment/funding columns: {sorted(missing)}")
    frame = frame[FIELDS].copy()
    text_fields = set(FIELDS) - {"year", "value", "numerator", "gdp"}
    for column in text_fields:
        frame[column] = frame[column].fillna("")
    for column in ("year", "value", "numerator", "gdp"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if (
        not np.isfinite(frame[["year", "value"]]).all().all()
        or not frame["year"].eq(frame["year"].round()).all()
        or not frame["year"].between(START, datetime.now(timezone.utc).year - 1).all()
        or not frame["value"].between(0, 100).all()
        or not frame["unit"].eq(UNIT).all()
        or frame.duplicated(["metric", "iso3", "year"]).any()
    ):
        raise ValueError("Invalid, duplicate or out-of-range investment/funding observations")
    frame["year"] = frame["year"].astype(int)
    allowed = {(metric, code) for metric, codes in BASELINES.items() for code in codes}
    actual = set(zip(frame["metric"], frame["iso3"]))
    if actual != allowed:
        raise ValueError("Missing or unexpected investment/funding country series")
    for row in frame.itertuples():
        if row.country != COUNTRIES[row.iso3] or flags(row.status) != row.status or "F" in row.status:
            raise ValueError("Invalid investment/funding country or status")
        if any(not getattr(row, field) for field in ("source", "series_id", "source_url", "retrieved_utc")):
            raise ValueError("Missing investment/funding provenance")
        computed = row.metric == CAPITAL or (row.metric == BUDGET and row.iso3 != "EU27_2020")
        if computed:
            if (
                not np.isfinite([row.numerator, row.gdp]).all() or row.numerator < 0 or row.gdp <= 0
                or row.currency != CURRENCIES[row.iso3] or not row.gdp_series_id or not row.gdp_source_url
                or not math.isclose(row.value, 100 * row.numerator / row.gdp, rel_tol=1e-10, abs_tol=1e-10)
            ):
                raise ValueError("Invalid same-currency spending/GDP conversion")
        elif pd.notna(row.numerator) or pd.notna(row.gdp) or row.currency or row.gdp_series_id:
            raise ValueError("Direct source percentages must not acquire a fabricated GDP denominator")
    retrieved = pd.to_datetime(frame["retrieved_utc"], utc=True, errors="raise")
    if retrieved.isna().any() or (retrieved > pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)).any():
        raise ValueError("Invalid funding source retrieval dates")
    for metric, countries in BASELINES.items():
        for code, (first, last, missing) in countries.items():
            expected = set(range(first, last + 1)) - set(missing)
            years = set(frame.loc[(frame["metric"] == metric) & (frame["iso3"] == code), "year"])
            if not expected <= years:
                raise ValueError(f"Lost investment/funding baseline coverage: {metric}/{code}")
    if previous is not None:
        saved = validate(previous)
        keys = ["metric", "iso3", "year"]
        if not set(saved[keys].itertuples(index=False, name=None)) <= set(
            frame[keys].itertuples(index=False, name=None)
        ):
            raise ValueError("Investment/funding refresh lost previously published observations")
    return frame.sort_values(["metric", "iso3", "year"]).reset_index(drop=True)


def fetch() -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    end, retrieved = now.year - 1, now.isoformat(timespec="seconds")
    data = {}
    for name, (flow, dimensions) in FLOWS.items():
        text = get_text(
            f"{BASE}/{flow}/" + ".".join(dimensions.values()),
            params={"startPeriod": str(START), "endPeriod": str(end), "format": "csvfile"},
            headers={"Accept": "text/csv"}, timeout=120,
        )
        data[name] = parse_oecd(text, name, end)
    rows = [
        _record(RESEARCH, code, year, raw, retrieved)
        for (code, year), raw in data["research"].items()
    ]
    rows += ratio_rows(CAPITAL, data["capital"], data["gdp"], retrieved)
    rows += ratio_rows(BUDGET, data["budget"], data["gdp"], retrieved)
    eu = get_json(EU_BUDGET_URL, params=dict(
        lang="en", freq="A", nabs07="TOTAL", unit="PC_GDP", geo="EU27_2020",
        sinceTimePeriod=str(START), untilTimePeriod=str(end),
    ), timeout=120)
    rows += parse_eu_budget(eu, retrieved, end)
    military = get_json(MILITARY_URL, params={
        "format": "json", "date": f"{START}:{end}", "per_page": 1000,
    }, timeout=120)
    rows += parse_military(military, retrieved, end)
    return validate(pd.DataFrame(rows, columns=FIELDS))
