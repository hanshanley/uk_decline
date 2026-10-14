"""OECD median disposable incomes, converted with household-consumption PPPs."""

from __future__ import annotations

import csv
import io
import math
from typing import Iterable

from . import countries
from ._http import get_text

BASE = "https://sdmx.oecd.org/public/rest/v1/data"
INCOME_FLOW = "OECD.WISE.INE,DSD_WISE_IDD@DF_IDD,1.0"
PPP_FLOW = "OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE4,1.0"
ISO3S = ("GBR", "USA", "DEU", "FRA", "ITA")
METRIC = "median_disposable_income_oecd_ppp"
UNIT = "current household-consumption PPP US$ per equivalised household"
SOURCE = "OECD Income Distribution Database; OECD annual household-consumption PPPs"
COMPARISON_START = 2013


def _records(
    text: str, dimensions: dict[str, str], *, extra_fields: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    required = {*dimensions, *extra_fields, "REF_AREA", "TIME_PERIOD", "OBS_VALUE", "CURRENCY",
                "OBS_STATUS", "UNIT_MULT"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("OECD income/PPP response is missing required CSV columns")
    records = list(reader)
    if not records:
        raise ValueError("OECD income/PPP response contains no observations")
    for row in records:
        if any(row[key] != value for key, value in dimensions.items()):
            raise ValueError(f"Unexpected OECD income/PPP dimensions: {row!r}")
    return records


def _value(row: dict[str, str]) -> float:
    value = float(row["OBS_VALUE"]) * 10 ** int(row["UNIT_MULT"] or 0)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Invalid OECD income/PPP value: {row!r}")
    return value


def build_rows(
    income_csv: str, ppp_csv: str, start: int, end: int, iso3s: Iterable[str] = ISO3S,
) -> list[dict]:
    codes = set(iso3s)
    incomes = _records(income_csv, {
        "FREQ": "A", "MEASURE": "INC_DISP", "STATISTICAL_OPERATION": "MEDIAN",
        "UNIT_MEASURE": "XDC_HH_EQ", "AGE": "_T", "METHODOLOGY": "METH2012",
        "PRICE_BASE": "V", "POVERTY_LINE": "_Z",
    }, extra_fields=("DEFINITION",))
    ppps = _records(ppp_csv, {
        "FREQ": "A", "SECTOR": "S1", "COUNTERPART_SECTOR": "S1",
        "TRANSACTION": "PPP_P31S14", "INSTR_ASSET": "F21", "ACTIVITY": "_Z",
        "EXPENDITURE": "_Z", "UNIT_MEASURE": "XDC_USD",
        "PRICE_BASE": "_Z", "TRANSFORMATION": "N",
        "TABLE_IDENTIFIER": "T001",
    })
    factors = {}
    for row in ppps:
        key = row["REF_AREA"], int(row["TIME_PERIOD"])
        if key in factors or key[0] not in codes:
            raise ValueError(f"Duplicate or unexpected OECD consumption PPP: {key}")
        factors[key] = row

    observations = {}
    current_start = {}
    for row in incomes:
        country, year = row["REF_AREA"], int(row["TIME_PERIOD"])
        definition = row["DEFINITION"]
        key = country, year, definition
        if definition not in {"D_CUR", "D_PREV"} or country not in codes or key in observations:
            raise ValueError(f"Duplicate or unexpected OECD income observation: {key}")
        observations[key] = row
        if definition == "D_CUR":
            current_start[country] = min(year, current_start.get(country, year))

    rows = []
    for (country, year, definition), row in sorted(observations.items()):
        if not start <= year <= end:
            continue
        if definition == "D_PREV" and year >= current_start.get(country, end + 1):
            continue
        factor = factors.get((country, year))
        if factor is None or factor["CURRENCY"] != row["CURRENCY"]:
            raise ValueError(f"Missing or currency-mismatched consumption PPP: {country} {year}")
        income, ppp = _value(row), _value(factor)
        rows.append({
            "iso3": country, "country": countries.name_for_iso3(country), "year": year,
            "metric": METRIC, "value": income / ppp, "unit": UNIT, "source": SOURCE,
            "status": " ".join(dict.fromkeys((row["OBS_STATUS"], factor["OBS_STATUS"]))),
            "income_definition": f"METH2012/{definition}",
            "national_currency_income": income, "consumption_ppp": ppp,
            "currency": row["CURRENCY"],
        })
    # The five-country comparison already has annual coverage throughout this window.
    expected = set(range(max(start, COMPARISON_START), min(end, 2023) + 1))
    for country in codes:
        years = {row["year"] for row in rows if row["iso3"] == country}
        if missing := expected - years:
            raise ValueError(f"OECD median income lost published coverage: {country} {sorted(missing)}")
    return rows


def fetch(start: int, end: int, iso3s: Iterable[str] = ISO3S) -> list[dict]:
    codes = tuple(iso3s)
    query = "+".join(codes)
    params = {"startPeriod": str(start), "endPeriod": str(end), "format": "csvfile"}
    income = get_text(
        f"{BASE}/{INCOME_FLOW}/"
        f"{query}.A.INC_DISP.MEDIAN.XDC_HH_EQ._T.METH2012.D_CUR+D_PREV._Z",
        params=params, timeout=120,
    )
    ppp = get_text(
        f"{BASE}/{PPP_FLOW}/A.{query}.S1.S1.PPP_P31S14.F21._Z._Z.XDC_USD._Z.N.T001",
        params=params, timeout=120,
    )
    return build_rows(income, ppp, start, end, codes)
