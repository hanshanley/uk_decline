"""Published household and industrial retail energy prices with explicit scopes."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import math
import re

import pandas as pd

from europe_data._http import get_bytes, get_json, get_text
from uk_migration._govuk import govuk_attachment

PAGE = "/government/statistical-data-sets/international-domestic-energy-prices"
INDUSTRIAL_PAGE = "/government/statistical-data-sets/international-non-domestic-energy-prices"
COUNTRIES = {"GBR": "United Kingdom", "USA": "United States", "DEU": "Germany", "FRA": "France"}
EU_COLUMNS = {"UK": "GBR", "Germany": "DEU", "France": "FRA"}
TABLES = {"electricity": "5.6", "gas": "5.10"}
BANDS = {"electricity": "2,500-4,999 kWh/year", "gas": "5,557-55,556 kWh/year"}
EIA_BASE = "https://www.eia.gov/totalenergy/data/browser/csv.php?tbl="
EIA = {
    "electricity": (EIA_BASE + "T09.08", "ESRCUUS", "Cents per Kilowatthour,  Including Taxes",
                    "Average Price of Electricity to Ultimate Customers, Residential"),
    "gas": (EIA_BASE + "T09.10", "NGRCUUS", "Dollars per Thousand Cubic Feet",
            "Natural Gas Price, Delivered to Consumers, Residential"),
}
INDUSTRIAL_TABLES = {"electricity": "5.4"}
INDUSTRIAL_BANDS = {"electricity": "2,000-19,999 MWh/year"}
INDUSTRIAL_EIA = {
    "electricity": (EIA_BASE + "T09.08", "ESICUUS", "Cents per Kilowatthour,  Including Taxes",
                    "Average Price of Electricity to Ultimate Customers, Industrial"),
}
EU_TAX = {
    False: "All taxes and levies included",
    True: "Including taxes, excluding VAT and other recoverable taxes and levies",
}
US_SCOPE = {False: "All residential customers", True: "All industrial customers"}
US_TAX = {False: "EIA published residential basis", True: "EIA published industrial basis"}
HEAT_URL = EIA_BASE + "TA4"
HEAT_SERIES = "NGTXKUS"
FX_URL = "https://api.worldbank.org/v2/country/GBR/indicator/PA.NUS.FCRF"
BTU_PER_KWH = 3412.0  # EIA Appendix A6 conventional conversion.
UNIT = "pence/kWh"
FIELDS = [
    "iso3", "country", "fuel", "year", "value", "unit", "source_value", "source_unit",
    "conversion_factor", "consumer_scope", "tax_basis", "status", "source_table",
    "source_url", "source_vintage", "vintage_kind", "gbp_per_usd", "btu_per_cubic_foot",
    "fx_source_url", "heat_source_url", "retrieved_utc",
]
OPTIONAL = {"gbp_per_usd", "btu_per_cubic_foot", "fx_source_url", "heat_source_url", "status"}


def _definitions(industrial: bool):
    return (INDUSTRIAL_TABLES, INDUSTRIAL_BANDS, INDUSTRIAL_EIA) if industrial else (TABLES, BANDS, EIA)


def _number(value) -> tuple[float, str]:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([pr]?)\s*", str(value))
    if not match or float(match.group(1)) <= 0:
        raise ValueError(f"Invalid energy price or year: {value}")
    return float(match.group(1)), match.group(2)


def parse_workbook(content: bytes, fuel: str, url: str, *, industrial: bool = False) -> pd.DataFrame:
    tables, bands, _ = _definitions(industrial)
    if fuel not in tables:
        raise ValueError(f"Unsupported energy price profile: {fuel}, industrial={industrial}")
    with pd.ExcelFile(io.BytesIO(content)) as workbook:
        cover = workbook.parse("Cover sheet", header=None)
        sheet = workbook.parse("Annual incl tax", header=None)
    dates = [
        re.fullmatch(r"Publication date:\s*(\d{2}/\d{2}/\d{4})", str(value).strip())
        for value in cover.iloc[:, 0]
    ]
    dates = [match.group(1) for match in dates if match]
    text = "\n".join(sheet.iloc[:15, 0].astype(str))
    expected_title = (
        "Annual non-domestic electricity prices in the EU including taxes "
        "(excluding VAT and other recoverable taxes and levies)"
        if industrial else f"Annual domestic {fuel} prices in the EU including all taxes and levies"
    )
    band = "2,000 - 19,999" if industrial else "2,500 - 4,999" if fuel == "electricity" else "5,557 - 55,556"
    if (
        len(dates) != 1
        or sheet.iloc[0, 0] != expected_title
        or "In pence per kWh." not in text
        or "Annual average is presented as the unweighted average of semesters one and two" not in text
        or band not in text
    ):
        raise ValueError(f"{fuel}: unexpected international energy price definition")
    headers = sheet.index[sheet.iloc[:, 0].eq("Customer size")]
    if len(headers) != 1:
        raise ValueError(f"{fuel}: missing or ambiguous international price header")
    header = int(headers[0])
    if sheet.iloc[header, 1] != "Year":
        raise ValueError(f"{fuel}: expected annual, not semester, observations")
    columns = {}
    for label, code in EU_COLUMNS.items():
        matches = [i for i, value in sheet.iloc[header].items() if value == label]
        if len(matches) != 1:
            raise ValueError(f"{fuel}: missing or ambiguous country: {label}")
        columns[code] = matches[0]
    rows = []
    for _, row in sheet.loc[sheet.iloc[:, 0].eq("Medium")].iterrows():
        year, year_status = _number(row.iloc[1])
        if year % 1:
            raise ValueError("Energy prices require integer calendar years")
        for code, column in columns.items():
            price, status = _number(row[column])
            rows.append(dict(
                iso3=code, country=COUNTRIES[code], fuel=fuel, year=int(year),
                value=price, unit=UNIT, source_value=price, source_unit=UNIT,
                conversion_factor=1., consumer_scope=bands[fuel],
                tax_basis=EU_TAX[industrial], status=status or year_status,
                source_table=f"QEP {tables[fuel]}, Annual incl tax", source_url=url,
                source_vintage=pd.to_datetime(dates[0], format="%d/%m/%Y").strftime("%Y-%m-%d"),
                vintage_kind="Workbook publication date",
            ))
    return pd.DataFrame(rows)


def parse_eia(
    text: str, series: str, unit: str, description: str, *, start: int = 2008, end: int | None = None,
) -> dict[int, float]:
    frame = pd.read_csv(io.StringIO(text), dtype=str)
    if not {"MSN", "YYYYMM", "Value", "Description", "Unit"}.issubset(frame.columns):
        raise ValueError("EIA energy response has missing fields")
    frame = frame.loc[frame["MSN"].eq(series)]
    if frame.empty or not frame["Unit"].eq(unit).all() or not frame["Description"].eq(description).all():
        raise ValueError(f"Unexpected EIA energy series: {series}")
    if not frame["YYYYMM"].str.fullmatch(r"\d{4}(?:0[1-9]|1[0-3])").all():
        raise ValueError(f"Unexpected EIA period: {series}")
    annual = frame.loc[frame["YYYYMM"].str.endswith("13")]
    years = annual["YYYYMM"].str[:4].astype(int)
    annual = annual.loc[years.between(start, end or datetime.now(timezone.utc).year - 1)]
    if annual["YYYYMM"].duplicated().any():
        raise ValueError(f"Duplicate EIA annual energy observation: {series}")
    # EIA's month 13 is the published annual rate, not a mean of monthly unit prices.
    return {int(row.YYYYMM[:4]): _number(row.Value)[0] for row in annual.itertuples()}


def parse_fx(payload: list) -> dict[int, float]:
    if (
        not isinstance(payload, list) or len(payload) != 2
        or payload[0].get("pages") != 1 or payload[0].get("sourceid") != "2"
        or not isinstance(payload[1], list) or len(payload[1]) != payload[0].get("total")
    ):
        raise ValueError("Unexpected or incomplete World Bank annual exchange-rate response")
    rates = {}
    for row in payload[1]:
        if (
            row.get("countryiso3code") != "GBR" or row.get("indicator", {}).get("id") != "PA.NUS.FCRF"
            or not re.fullmatch(r"\d{4}", row.get("date", ""))
            or row["value"] is None
        ):
            raise ValueError("Missing, duplicate or incompatible sterling-dollar exchange rate")
        year, value = int(row["date"]), float(row["value"])
        if year in rates or not math.isfinite(value) or value <= 0:
            raise ValueError("Invalid sterling-dollar exchange rate")
        rates[year] = value
    return rates


def add_us(
    european: pd.DataFrame, prices: dict[str, dict[int, float]],
    heat: dict[int, float], fx: dict[int, float], *, release: str, industrial: bool = False,
) -> pd.DataFrame:
    _, _, eia = _definitions(industrial)
    rows = european.to_dict("records")
    for fuel, part in european.groupby("fuel"):
        for year in sorted(set(part["year"])):
            if year not in prices[fuel] or year not in fx or (fuel == "gas" and year not in heat):
                raise ValueError(f"Missing US energy conversion input: {fuel} {year}")
            factor = fx[year] if fuel == "electricity" else (
                100 * fx[year] / (heat[year] * 1000 / BTU_PER_KWH)
            )
            rows.append(dict(
                iso3="USA", country=COUNTRIES["USA"], fuel=fuel, year=year,
                value=prices[fuel][year] * factor, unit=UNIT,
                source_value=prices[fuel][year], source_unit=eia[fuel][2],
                conversion_factor=factor, consumer_scope=US_SCOPE[industrial],
                tax_basis=US_TAX[industrial], status="",
                source_table=eia[fuel][1], source_url=eia[fuel][0], source_vintage=release,
                vintage_kind="Retrieved source snapshot",
                gbp_per_usd=fx[year], btu_per_cubic_foot=heat[year] if fuel == "gas" else None,
                fx_source_url=FX_URL, heat_source_url=HEAT_URL if fuel == "gas" else "",
            ))
    frame = pd.DataFrame(rows).reindex(columns=FIELDS)
    frame["retrieved_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return frame


def validate(frame: pd.DataFrame, *, previous=None, as_of=None, industrial: bool = False) -> pd.DataFrame:
    tables, bands, eia = _definitions(industrial)
    if not set(FIELDS).issubset(frame.columns):
        raise ValueError("Missing international energy fields")
    frame = frame[FIELDS].copy()
    for column in ("status", "fx_source_url", "heat_source_url"):
        frame[column] = frame[column].fillna("")
    if frame[list(set(FIELDS) - OPTIONAL)].isna().any().any() or frame.duplicated(["iso3", "fuel", "year"]).any():
        raise ValueError("Missing or duplicate energy prices")
    for column in ("year", "value", "source_value", "conversion_factor"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not frame[column].map(lambda value: math.isfinite(value) and value > 0).all():
            raise ValueError(f"Invalid energy price or conversion: {column}")
    today = pd.Timestamp(as_of or datetime.now(timezone.utc)).normalize().tz_localize(None)
    releases = pd.to_datetime(frame["source_vintage"], errors="raise")
    if (
        not frame["year"].mod(1).eq(0).all()
        or not frame["year"].between(2008, today.year - 1).all()
        or releases.isna().any() or releases.gt(today).any()
        or frame["year"].ge(releases.dt.year).any()
        or not frame["unit"].eq(UNIT).all() or not frame["status"].isin(["", "p", "r"]).all()
        or pd.to_datetime(frame["retrieved_utc"], errors="raise", utc=True).isna().any()
        or set(zip(frame["iso3"], frame["fuel"])) != {(code, fuel) for code in COUNTRIES for fuel in tables}
    ):
        raise ValueError("Invalid energy definitions, dates or coverage")
    latest = int(frame["year"].max())
    for (code, fuel), part in frame.groupby(["iso3", "fuel"]):
        if (
            set(part["year"]) != set(range(2008, max(2025, latest) + 1))
            or not part["country"].eq(COUNTRIES[code]).all()
        ):
            raise ValueError(f"Missing required energy price history: {code} {fuel}")
    for row in frame.to_dict("records"):
        if row["iso3"] == "USA":
            fx = float(row["gbp_per_usd"])
            if not math.isfinite(fx) or fx <= 0 or row["fx_source_url"] != FX_URL:
                raise ValueError("Invalid US energy exchange-rate input")
            factor = fx
            if row["fuel"] == "gas":
                heat = float(row["btu_per_cubic_foot"])
                if not math.isfinite(heat) or heat <= 0 or row["heat_source_url"] != HEAT_URL:
                    raise ValueError("Invalid US gas heat-content input")
                factor = 100 * fx / (heat * 1000 / BTU_PER_KWH)
            if (
                row["source_unit"] != eia[row["fuel"]][2]
                or row["source_table"] != eia[row["fuel"]][1]
                or row["source_url"] != eia[row["fuel"]][0]
                or row["consumer_scope"] != US_SCOPE[industrial]
                or row["tax_basis"] != US_TAX[industrial]
                or row["vintage_kind"] != "Retrieved source snapshot"
            ):
                raise ValueError("US energy price does not use the selected sector series")
        else:
            factor = 1.
            if (
                row["source_unit"] != UNIT or row["consumer_scope"] != bands[row["fuel"]]
                or row["tax_basis"] != EU_TAX[industrial]
                or row["source_table"] != f"QEP {tables[row['fuel']]}, Annual incl tax"
                or not row["source_url"].startswith("https://assets.publishing.service.gov.uk/")
                or row["vintage_kind"] != "Workbook publication date"
            ):
                raise ValueError("European energy price does not match the selected tax and consumer profile")
        if (
            not math.isclose(row["conversion_factor"], factor, rel_tol=1e-12)
            or not math.isclose(row["value"], row["source_value"] * factor, rel_tol=1e-12)
        ):
            raise ValueError("Energy price does not match its recorded physical/currency conversion")
    if previous is not None and not set(zip(previous["iso3"], previous["fuel"], previous["year"])).issubset(
        set(zip(frame["iso3"], frame["fuel"], frame["year"])),
    ):
        raise ValueError("Energy prices lost previously published observations")
    return frame.sort_values(["fuel", "iso3", "year"]).reset_index(drop=True)


def fetch(*, previous=None, industrial: bool = False) -> pd.DataFrame:
    tables, _, eia = _definitions(industrial)
    frames = []
    for fuel, table in tables.items():
        url, _ = govuk_attachment(
            "table_" + table.replace(".", "") + "1", INDUSTRIAL_PAGE if industrial else PAGE,
        )
        frames.append(parse_workbook(get_bytes(url, timeout=120), fuel, url, industrial=industrial))
    european = pd.concat(frames, ignore_index=True)
    start, end = int(european["year"].min()), int(european["year"].max())
    prices = {
        fuel: parse_eia(get_text(url, timeout=120), code, unit, description, start=start, end=end)
        for fuel, (url, code, unit, description) in eia.items()
    }
    heat = (
        parse_eia(get_text(HEAT_URL, timeout=120), HEAT_SERIES, "Btu per Cubic Foot",
                  "Natural Gas Consumption, End-Use Sectors Heat Content", start=start, end=end)
        if "gas" in tables else {}
    )
    fx = parse_fx(get_json(FX_URL, params={"format": "json", "date": f"{start}:{end}", "per_page": 100}, timeout=120))
    # MER CSVs do not carry a release date; retain the retrieval date rather than inventing one.
    release = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    frame = validate(
        add_us(european, prices, heat, fx, release=release, industrial=industrial),
        previous=previous, industrial=industrial,
    )
    today = datetime.now(timezone.utc)
    if end < today.year - (1 if today.month >= 7 else 2):
        raise ValueError("International energy prices are stale")
    return frame
