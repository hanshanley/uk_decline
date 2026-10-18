"""Explicit distribution-neutral extensions of observed OECD median incomes."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
import math
from pathlib import Path
import re

import pandas as pd

from . import countries, oecd_income
from ._http import get_json, get_text

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "data/oecd_income_estimates.csv"
OBSERVED = ROOT / "data/oecd_median_income_ppp.csv"
THROUGH_YEAR = 2025
METRIC = "modelled_median_disposable_income_ppp"
METHOD = "distribution-neutral household-income/person growth; relative consumption-deflator PPP"
FLOW = "OECD.ECO.MAD,DSD_EO@DF_EO"
METADATA = "https://sdmx.oecd.org/public/rest/v1/dataflow/OECD.ECO.MAD/DSD_EO@DF_EO/latest"
BASE = "https://sdmx.oecd.org/public/rest/v1/data"
COUNTRIES = {code: countries.name_for_iso3(code) for code in oecd_income.ISO3S}
CURRENCIES = {"GBR": "GBP", "USA": "USD", "DEU": "EUR", "FRA": "EUR", "ITA": "EUR", "POL": "PLN"}
# These are the country conventions used by the OECD's real household-income series.
INCOME_MEASURES = {code: "YDH_G" if code in {"GBR", "FRA"} else "YDH" for code in COUNTRIES}
FIELDS = [
    "iso3", "country", "year", "metric", "value", "unrounded_value", "unit", "status",
    "base_year", "base_value", "income_measure", "income_base", "income_target",
    "population_base", "population_target", "price_base", "price_target",
    "us_price_base", "us_price_target", "method", "source_vintage", "source_url", "retrieved_utc",
]


def anchors(observed: pd.DataFrame, through: int) -> dict[str, pd.Series]:
    required = {"iso3", "country", "year", "metric", "value", "unit"}
    if not required.issubset(observed.columns):
        raise ValueError("Income estimates require the saved observed OECD source table")
    observed = observed.copy()
    observed["year"] = pd.to_numeric(observed["year"], errors="raise")
    observed["value"] = pd.to_numeric(observed["value"], errors="raise")
    if (
        set(observed["iso3"]) != set(COUNTRIES)
        or observed.duplicated(["iso3", "year"]).any()
        or not observed["metric"].eq(oecd_income.METRIC).all()
        or not observed["unit"].eq(oecd_income.UNIT).all()
        or not observed["value"].map(lambda value: math.isfinite(value) and value > 0).all()
        or not observed["year"].mod(1).eq(0).all()
    ):
        raise ValueError("Invalid observed income anchors")
    result = {}
    for code, country in COUNTRIES.items():
        part = observed[(observed["iso3"] == code) & (observed["year"] <= through)].sort_values("year")
        if part.empty or not part["country"].eq(country).all():
            raise ValueError(f"Missing or incompatible observed income anchor: {code}")
        anchor = part.iloc[-1]
        if through - int(anchor["year"]) > 2:
            raise ValueError(f"Income model is limited to a two-year tail: {code}")
        result[code] = anchor
    return result


def parse_macro(text: str, flow: str) -> dict[tuple[str, int, str], float]:
    reader = csv.DictReader(io.StringIO(text))
    fields = {
        "DATAFLOW", "REF_AREA", "MEASURE", "FREQ", "TIME_PERIOD", "OBS_VALUE",
        "UNIT_MEASURE", "UNIT_MULT", "PRICE_BASE", "BASE_PER", "CURRENCY",
    }
    if not fields.issubset(reader.fieldnames or []):
        raise ValueError("OECD income-model inputs have missing columns")
    agency, dataset, version = flow.split(",")
    identifier = f"{agency}:{dataset}({version})"
    data, periods = {}, {}
    for row in reader:
        if None in row or any(row[field] is None for field in fields):
            raise ValueError("Malformed OECD income-model input")
        code, measure = row["REF_AREA"], row["MEASURE"]
        if (
            row["DATAFLOW"] != identifier or code not in COUNTRIES or row["FREQ"] != "A"
            or measure not in {"YDH", "YDH_G", "POP", "PCP"}
            or not re.fullmatch(r"\d{4}", row["TIME_PERIOD"])
        ):
            raise ValueError("Unexpected OECD income-model definition")
        if measure not in {INCOME_MEASURES[code], "POP", "PCP"}:
            continue
        unit = "PS" if measure == "POP" else "GR" if measure == "PCP" else "XDC"
        if row["UNIT_MEASURE"] != unit:
            raise ValueError(f"Wrong OECD income-model unit: {code} {measure}")
        if measure in {"YDH", "YDH_G"} and (
            row["PRICE_BASE"] != "V"
            or row["CURRENCY"] not in (CURRENCIES[code], "")
        ):
            raise ValueError(f"Wrong household-income currency/price basis: {code}")
        if measure == "PCP":
            if row["PRICE_BASE"] != "D" or not re.fullmatch(r"\d{4}", row["BASE_PER"]):
                raise ValueError(f"Wrong consumption-deflator basis: {code}")
            if code in periods and periods[code] != row["BASE_PER"]:
                raise ValueError(f"Consumption-deflator reference year changed within country: {code}")
            periods[code] = row["BASE_PER"]
        key = code, int(row["TIME_PERIOD"]), measure
        if key in data:
            raise ValueError(f"Duplicate OECD income-model input: {key}")
        value = float(row["OBS_VALUE"]) * 10 ** int(row["UNIT_MULT"])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid OECD income-model input: {key}")
        data[key] = value
    return data


def build(
    observed: pd.DataFrame, macro: dict[tuple[str, int, str], float], *, through: int, vintage: str,
    source_url: str, retrieved: str,
) -> pd.DataFrame:
    rows = []
    for code, anchor in anchors(observed, through).items():
        first = int(anchor["year"])
        measure = INCOME_MEASURES[code]
        for year in range(first + 1, through + 1):
            def get(area, period, item):
                key = area, period, item
                if key not in macro:
                    raise ValueError(f"Missing income-model input: {key}")
                return macro[key]

            row = dict(
                iso3=code, country=COUNTRIES[code], year=year, metric=METRIC,
                unit=oecd_income.UNIT, status="MODELLED", base_year=first,
                base_value=float(anchor["value"]), income_measure=measure,
                income_base=get(code, first, measure), income_target=get(code, year, measure),
                population_base=get(code, first, "POP"), population_target=get(code, year, "POP"),
                price_base=get(code, first, "PCP"), price_target=get(code, year, "PCP"),
                us_price_base=get("USA", first, "PCP"), us_price_target=get("USA", year, "PCP"),
                method=METHOD, source_vintage=vintage, source_url=source_url, retrieved_utc=retrieved,
            )
            income_growth = (row["income_target"] / row["population_target"]) / (
                row["income_base"] / row["population_base"]
            )
            ppp_growth = (row["price_target"] / row["price_base"]) / (
                row["us_price_target"] / row["us_price_base"]
            )
            row["unrounded_value"] = row["base_value"] * income_growth / ppp_growth
            row["value"] = round(row["unrounded_value"], -2)
            rows.append(row)
    return pd.DataFrame(rows, columns=FIELDS)


def validate(frame: pd.DataFrame, observed: pd.DataFrame, through: int = THROUGH_YEAR) -> pd.DataFrame:
    if not set(FIELDS).issubset(frame.columns):
        raise ValueError("Saved income estimates have missing fields")
    frame = frame[FIELDS].copy()
    expected = {
        (code, year)
        for code, anchor in anchors(observed, through).items()
        for year in range(int(anchor["year"]) + 1, through + 1)
    }
    if not expected and frame.empty:
        return frame
    if frame.isna().any().any() or frame.duplicated(["iso3", "year"]).any():
        raise ValueError("Missing or duplicate model estimates")
    numeric = [
        "year", "value", "unrounded_value", "base_year", "base_value", "income_base",
        "income_target", "population_base", "population_target", "price_base", "price_target",
        "us_price_base", "us_price_target",
    ]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not frame[column].map(lambda value: math.isfinite(value) and value > 0).all():
            raise ValueError(f"Invalid income-model value: {column}")
    if (
        not frame["year"].mod(1).eq(0).all()
        or set(zip(frame["iso3"], frame["year"])) != expected
        or not frame["metric"].eq(METRIC).all() or not frame["status"].eq("MODELLED").all()
        or not frame["unit"].eq(oecd_income.UNIT).all() or not frame["method"].eq(METHOD).all()
        or frame["source_vintage"].nunique() != 1
        or not frame["source_vintage"].str.fullmatch(r"OECD Economic Outlook(?: No)? \d+").all()
        or not frame["source_url"].str.startswith(f"{BASE}/{FLOW},").all()
        or pd.to_datetime(frame["retrieved_utc"], errors="raise", utc=True).isna().any()
    ):
        raise ValueError("Invalid income-model identity, coverage or provenance")
    base = anchors(observed, through)
    for row in frame.to_dict("records"):
        anchor = base[row["iso3"]]
        if (
            row["country"] != COUNTRIES[row["iso3"]]
            or row["income_measure"] != INCOME_MEASURES[row["iso3"]]
            or row["base_year"] != int(anchor["year"])
            or not math.isclose(row["base_value"], float(anchor["value"]), rel_tol=1e-12)
        ):
            raise ValueError("Income-model calibration no longer matches observed data")
        income_growth = (row["income_target"] / row["population_target"]) / (
            row["income_base"] / row["population_base"]
        )
        ppp_growth = (row["price_target"] / row["price_base"]) / (
            row["us_price_target"] / row["us_price_base"]
        )
        value = row["base_value"] * income_growth / ppp_growth
        if (
            not math.isclose(row["unrounded_value"], value, rel_tol=1e-12)
            or row["value"] != round(value, -2)
        ):
            raise ValueError("Income estimate does not match its recorded model inputs")
    return frame.sort_values(["iso3", "year"]).reset_index(drop=True)


def fetch(observed: pd.DataFrame, through: int = THROUGH_YEAR) -> pd.DataFrame:
    base = anchors(observed, through)
    if all(int(row["year"]) >= through for row in base.values()):
        return pd.DataFrame(columns=FIELDS)
    release = get_json(METADATA, params={"references": "none"}, timeout=120)["data"]["dataflows"]
    if (
        len(release) != 1 or release[0].get("agencyID") != "OECD.ECO.MAD"
        or release[0].get("id") != "DSD_EO@DF_EO"
        or not re.fullmatch(r"\d+\.\d+", release[0].get("version", ""))
        or not re.fullmatch(r"Economic Outlook(?: No)? \d+", release[0].get("name", ""))
    ):
        raise ValueError("Unexpected OECD Economic Outlook metadata")
    flow = FLOW + "," + release[0]["version"]
    first = min(int(row["year"]) for row in base.values())
    url = f"{BASE}/{flow}/" + "+".join(COUNTRIES) + ".YDH+YDH_G+POP+PCP.A"
    params = {"format": "csvfile", "startPeriod": str(first), "endPeriod": str(through)}
    text = get_text(url, params=params, timeout=120)
    source_url = url + f"?format=csvfile&startPeriod={first}&endPeriod={through}"
    frame = build(
        observed, parse_macro(text, flow), through=through,
        vintage="OECD " + release[0]["name"], source_url=source_url,
        retrieved=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return validate(frame, observed, through)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed", type=Path, default=OBSERVED)
    parser.add_argument("--csv", type=Path, default=SAVED)
    parser.add_argument("--from-csv", type=Path)
    args = parser.parse_args(argv)
    observed = pd.read_csv(args.observed)
    frame = validate(pd.read_csv(args.from_csv), observed) if args.from_csv else fetch(observed)
    if not args.from_csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False)
    print(f"[income_estimates] {len(frame)} explicitly modelled values through {THROUGH_YEAR}; "
          "not observed OECD medians")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
