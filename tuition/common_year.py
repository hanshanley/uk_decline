"""Build a genuinely common-academic-year England/EU/US fee comparison."""

from __future__ import annotations

import argparse
import csv
import io
import math
from pathlib import Path
import re
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
import pandas as pd

from tuition import build_dataset, config, dataset, rates
from tuition.http import session

PAGE = "https://eurydice.eacea.ec.europa.eu/data-and-visuals/national-student-fees"
SHEET = "Fees_sub-topic 5"
MEASURE = "Most common annual fee; home, full-time, first-cycle students"
FIELDS = [*build_dataset.OUTPUT_FIELDS, "academic_year", "source_url", "source_measure"]
EU_CODES = {
    country.iso3: "BE-NL" if country.iso3 == "BEL" else "EL" if country.iso3 == "GRC" else country.iso2
    for country in config.EU27
}


def latest_workbook(html: str) -> tuple[int, str]:
    candidates = set()
    for link in BeautifulSoup(html, "html.parser").select("a[href]"):
        url = urljoin(PAGE, link["href"])
        if urlsplit(url).hostname != "eurydice.eacea.ec.europa.eu":
            continue
        match = re.search(r"Open data_(20\d{2})[-_](20\d{2})(?:_\d+)?\.xlsx$", unquote(urlsplit(url).path))
        if match and int(match[2]) == int(match[1]) + 1:
            candidates.add((int(match[1]), url))
    if not candidates:
        raise ValueError("Eurydice has no dated common-year fee workbook")
    year = max(year for year, _ in candidates)
    urls = {url for source_year, url in candidates if source_year == year}
    if len(urls) != 1:
        raise ValueError("Eurydice common-year fee workbook is ambiguous")
    return year, urls.pop()


def parse_eurydice(book: dict[str, pd.DataFrame], year: int, source_url: str) -> list[dict]:
    table = book[SHEET]
    reference = f"Reference academic year: {year}/{year + 1}"
    if reference not in table.iloc[:, 0].values:
        raise ValueError("Eurydice fee reference academic year changed")
    exchange = book["Eurostat data"]
    exchange_headers = [
        (row, column) for row in range(len(exchange)) for column in range(len(exchange.columns))
        if exchange.iat[row, column] == "Euro/ECU exchange rates"
    ]
    if len(exchange_headers) != 1:
        raise ValueError("Eurydice publisher exchange-rate metadata is missing or ambiguous")
    row, column = exchange_headers[0]
    if row + 1 >= len(exchange) or exchange.iat[row + 1, column] != year:
        raise ValueError("Eurydice publisher exchange-rate year does not match the fee year")
    headers = table.index[table.iloc[:, 0].eq("Annual fee amount (in euro)")].tolist()
    if len(headers) != 1:
        raise ValueError("Eurydice euro fee block is missing or ambiguous")
    header = headers[0]
    columns = list(table.iloc[header])
    if any(columns.count(code) != 1 for code in EU_CODES.values()):
        raise ValueError("Eurydice common-year country columns are missing or duplicated")
    body = table.iloc[header + 1:]
    selected = body[
        body.iloc[:, 0].eq("Most common") & body.iloc[:, 1].eq("First cycle")
        & body.iloc[:, 2].eq("Home students") & body.iloc[:, 3].eq("Full-time")
    ]
    if len(selected) != 1:
        raise ValueError("Eurydice most-common home/full-time/first-cycle fee row changed")
    row = selected.iloc[0]
    records = []
    for country in config.EU27:
        code = EU_CODES[country.iso3]
        raw = row.iloc[columns.index(code)]
        missing = pd.isna(raw) or str(raw).strip() in (":", "N/A")
        value = None if missing else float(raw)
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError(f"Invalid Eurydice common-year fee: {country.name}")
        records.append(dict(
            country=country.name, iso3=country.iso3, region=config.EU,
            annual_tuition_local=value, currency="EUR", year=year, include_primary="1",
            source=f"Eurydice {year}/{year + 1}, {SHEET}, most common (in euro)",
            source_url=source_url, source_measure=MEASURE,
            notes=(
                "Belgium is represented by the Flemish Community. "
                if country.iso3 == "BEL" else ""
            ) + (
                "Fee amount not reported; not treated as zero." if missing else
                "Publisher euro amounts; fees may include registration/administration charges."
            ),
        ))
    return records


def national_rows(history: list[dict], year: int) -> list[dict]:
    records = []
    for code, region in (("GBR", config.UK), ("USA", config.US)):
        matches = [row for row in history if row["iso3"] == code and int(row["year"]) == year]
        if len(matches) != 1:
            raise ValueError(f"No unique same-year national fee observation: {code} {year}")
        row = matches[0]
        records.append(dict(
            country=config.BY_ISO3[code].name, iso3=code, region=region,
            annual_tuition_local=float(row["nominal_local"]), currency=row["currency"],
            year=year, include_primary="1", source=row["source"], source_url=row["source_url"],
            source_measure=(
                "England statutory full-time home undergraduate fee cap" if code == "GBR" else
                "US public four-year average published in-state tuition and fees"
            ),
            notes="Matched academic start year; not a UK-wide average or a net price after aid.",
        ))
    return records


def build(rows: list[dict], fx: dict, deflators: dict[int, float]) -> list[dict]:
    years = {int(row["year"]) for row in rows}
    if len(years) != 1:
        raise ValueError("Common-year tuition inputs mix academic years")
    year = years.pop()
    if year not in deflators:
        raise ValueError("Common-year tuition requires same-year published CPI")
    currency_rates = {"USD": dict(currency="USD", fx_lcu_per_usd=1., fx_year=year)}
    for code, currency in (("DEU", "EUR"), ("GBR", "GBP")):
        record = fx.get((code, year))
        if (
            record is None or record["fx_year"] != year or record["currency"] != currency
            or not math.isfinite(record["fx_lcu_per_usd"]) or record["fx_lcu_per_usd"] <= 0
        ):
            raise ValueError(f"Common-year tuition requires exact {year} {currency}/USD exchange rates")
        currency_rates[currency] = record
    conversion_rates = {
        (row["iso3"], year): currency_rates[row["currency"]] for row in rows
    }
    available = [row for row in rows if row["annual_tuition_local"] is not None]
    converted = {
        row["iso3"]: row for row in build_dataset.convert(available, conversion_rates, deflators)
    }
    output = []
    for row in rows:
        result = converted.get(row["iso3"])
        if result is None:
            result = {
                **row, "annual_tuition_usd": None, "annual_tuition_usd_real2022": None,
                "fx_lcu_per_usd": currency_rates[row["currency"]]["fx_lcu_per_usd"],
                "fx_year": year,
            }
        result.update(
            academic_year=f"{year}/{(year + 1) % 100:02d}",
            source_url=row["source_url"], source_measure=row["source_measure"],
        )
        output.append(result)
    validate(output)
    return output


def validate(rows: list[dict], previous: list[dict] | None = None) -> None:
    if not rows or any(set(FIELDS) - set(row) for row in rows):
        raise ValueError("Common-year tuition data is empty or missing fields")
    years = {int(row["year"]) for row in rows}
    if len(years) != 1:
        raise ValueError("Common-year tuition data mixes academic years")
    year = years.pop()
    codes = [row["iso3"] for row in rows]
    if len(codes) != len(set(codes)) or set(codes) != set(config.iso3_codes()):
        raise ValueError("Common-year tuition data must account for all 27 EU countries, England and the US")
    available_eu = 0
    for row in rows:
        country = config.BY_ISO3[row["iso3"]]
        if (
            row["region"] != country.region or row["country"] != country.name
            or row["currency"] != ("EUR" if country.region == config.EU else country.currency)
            or int(row["fx_year"]) != year
            or row["academic_year"] != f"{year}/{(year + 1) % 100:02d}"
            or not row["source"] or not row["source_url"] or not row["source_measure"]
        ):
            raise ValueError(f"Common-year tuition metadata does not match: {country.name}")
        missing = row["annual_tuition_local"] in (None, "")
        amounts = (row["annual_tuition_usd"], row["annual_tuition_usd_real2022"])
        if missing:
            if country.region != config.EU or any(value not in (None, "") for value in amounts):
                raise ValueError("Missing tuition amounts must stay missing, never zero-filled")
            continue
        fx, local = float(row["fx_lcu_per_usd"]), float(row["annual_tuition_local"])
        if (
            not math.isfinite(fx) or fx <= 0 or not math.isfinite(local) or local < 0
            or any(value in (None, "") or not math.isfinite(float(value)) or float(value) < 0 for value in amounts)
            or abs(float(row["annual_tuition_usd"]) - round(local / fx, 2)) > .001
        ):
            raise ValueError(f"Common-year tuition has invalid conversion values: {country.name}")
        if country.region == config.EU:
            available_eu += 1
    if available_eu < 20:
        raise ValueError("Eurydice returned fewer than 20 reported common-year EU fees; refusing a partial comparison")
    if previous:
        previous_years = {int(row["year"]) for row in previous}
        if len(previous_years) != 1 or max(previous_years) > year:
            raise ValueError("Common-year tuition refresh would regress its published academic year")
        if year in previous_years:
            available_before = {row["iso3"] for row in previous if row["annual_tuition_local"] not in (None, "")}
            available_now = {row["iso3"] for row in rows if row["annual_tuition_local"] not in (None, "")}
            if not available_before.issubset(available_now):
                raise ValueError("Common-year tuition refresh lost previously reported fee amounts")


def load() -> list[dict]:
    rows = dataset.load_primary(
        ["annual_tuition_local", "annual_tuition_usd", "annual_tuition_usd_real2022"],
        config.COMMON_YEAR_CSV,
    )
    validate(rows)
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Read a saved primary Eurydice workbook")
    parser.add_argument("--year", type=int, help="Reference academic start year for --input")
    args = parser.parse_args(argv)
    client = session()
    page = client.get(PAGE, timeout=90)
    page.raise_for_status()
    year, url = latest_workbook(page.text)
    if args.input:
        if args.year != year:
            raise ValueError("Saved Eurydice workbook year must match the latest published reference year")
        content = args.input.read_bytes()
    else:
        response = client.get(url, timeout=120)
        response.raise_for_status()
        content = response.content
    book = pd.read_excel(io.BytesIO(content), sheet_name=[SHEET, "Eurostat data"], header=None)
    rows = parse_eurydice(book, year, url)
    with open(config.HISTORY_OUT_CSV, newline="") as handle:
        rows += national_rows(list(csv.DictReader(handle)), year)
    converted = build(
        rows, rates.fetch_rates_for_years({"DEU": {year}, "GBR": {year}}),
        build_dataset._us_cpi_deflator({year}),
    )
    if Path(config.COMMON_YEAR_CSV).exists():
        with open(config.COMMON_YEAR_CSV, newline="") as handle:
            validate(converted, list(csv.DictReader(handle)))
    with open(config.COMMON_YEAR_CSV, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(converted)
    print(f"[tuition] saved matched {year}/{(year + 1) % 100:02d} fees -> {config.COMMON_YEAR_CSV}")


if __name__ == "__main__":
    main()
