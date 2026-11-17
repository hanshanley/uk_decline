"""Fresh, per-refresh official bulk transport, shared by source subprocesses."""

from contextlib import contextmanager
import csv
from datetime import date
import io
import math
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile
from zlib import error as ZlibError

import requests

from ._http import get_bytes

ENV = "UK_DECLINE_WORLDBANK_BULK_DIR"
ARCHIVES = {
    2: ("WDI_CSV.zip", "WDICSV.csv"),
    3: ("WGI_CSV.zip", "WGICSV.csv"),
}
BASE = "https://databankfiles.worldbank.org/public/ddpext_download/"
FIELDS = ("Country Name", "Country Code", "Indicator Name", "Indicator Code")


def required_indicators():
    from age_data.config import BROAD_INDICATORS
    from europe_data.worldbank import INDICATORS as GDP
    from markets_data.markets import BY_INDICATOR, CPI_INDICATOR
    from trade_data.worldbank import INDICATOR as TRADE
    from trust_data.worldbank import INDICATORS as WGI
    from investment_data.sources import MILITARY_INDICATOR

    return {
        2: set(GDP) | set(BY_INDICATOR) | {CPI_INDICATOR, TRADE, MILITARY_INDICATOR}
           | {indicator for indicator, _ in BROAD_INDICATORS.values()},
        3: set(WGI),
    }


def prepare(directory: Path, source: int, indicators: set[str]) -> None:
    filename, member = ARCHIVES[source]
    content = get_bytes(BASE + filename, timeout=(15, 180), headers={"Cache-Control": "no-cache"})
    with TemporaryDirectory(dir=directory, prefix=f"source-{source}-") as staging:
        staged = Path(staging)
        with ZipFile(io.BytesIO(content)) as archive, archive.open(member) as binary:
            reader = csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig"))
            fields = reader.fieldnames or []
            if not set(FIELDS).issubset(fields) or len(fields) != len(set(fields)):
                raise ValueError(f"World Bank bulk source {source} has invalid columns")
            years = [field for field in fields if re.fullmatch(r"\d{4}", field)]
            if not years or max(map(int, years)) < date.today().year - 1:
                raise ValueError(f"World Bank bulk source {source} is missing recent years")
            found = set()
            handles = {}
            try:
                for row in reader:
                    indicator = row.get("Indicator Code")
                    if indicator not in indicators:
                        continue
                    if indicator not in handles:
                        handle = (staged / f"{indicator}.csv").open("w", newline="")
                        writer = csv.DictWriter(handle, fieldnames=[*FIELDS, *years])
                        writer.writeheader()
                        handles[indicator] = (handle, writer)
                    handles[indicator][1].writerow({field: row[field] for field in [*FIELDS, *years]})
                    found.add(indicator)
            finally:
                for handle, _ in handles.values():
                    handle.close()
            if found != indicators:
                raise ValueError(f"World Bank bulk source {source} lacks indicators: {sorted(indicators - found)}")
        staged.rename(directory / str(source))
    print(f"[worldbank] prepared fresh source {source}: {len(found)} indicators from {filename}", flush=True)


@contextmanager
def fresh_bulk(sources=(2, 3)):
    previous = os.environ.get(ENV)
    with TemporaryDirectory(prefix="uk-decline-worldbank-") as directory:
        try:
            required = required_indicators()
            for source in sources:
                try:
                    prepare(Path(directory), source, required[source])
                except (requests.RequestException, ValueError, BadZipFile, KeyError, EOFError, ZlibError) as error:
                    print(f"[worldbank] bulk source {source} unavailable: {error}; trying live API", flush=True)
            os.environ[ENV] = directory
            yield
        finally:
            if previous is None:
                os.environ.pop(ENV, None)
            else:
                os.environ[ENV] = previous


def observations(indicator: str, codes: list[str], start: int, end: int, source: int | None):
    directory = os.environ.get(ENV)
    source = 2 if source is None else source
    if not directory or source not in ARCHIVES or not re.fullmatch(r"[A-Z0-9_.]+", indicator):
        return None
    path = Path(directory) / str(source) / f"{indicator}.csv"
    if not path.exists():
        return None
    rows = []
    seen = set()
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        years = [field for field in fields if field.isdigit() and start <= int(field) <= end]
        latest = min(end, date.today().year - 1)
        expected = set(range(max(start, 1960), latest + 1)) if source == 2 else {
            year for year in {1996, 1998, 2000, *range(2002, latest + 1)}
            if start <= year <= latest
        }
        if (not set(FIELDS).issubset(fields) or len(fields) != len(set(fields))
                or not expected.issubset(map(int, years))):
            raise ValueError(f"World Bank bulk {indicator} has incomplete year columns")
        for row in reader:
            code = row["Country Code"]
            if code not in codes:
                continue
            if code in seen or row["Indicator Code"] != indicator:
                raise ValueError(f"World Bank bulk {indicator} has duplicate or mismatched profiles")
            seen.add(code)
            for year in years:
                raw = row[year]
                if raw is None:
                    raise ValueError(f"World Bank bulk {indicator} has a truncated row")
                value = None if raw == "" else float(raw)
                if value is not None and not math.isfinite(value):
                    raise ValueError(f"World Bank bulk {indicator} contains a nonfinite value")
                rows.append({
                    "countryiso3code": code, "country": {"value": row["Country Name"]},
                    "indicator": {"id": indicator, "value": row["Indicator Name"]},
                    "date": year, "value": value,
                })
    if seen != set(codes):
        raise ValueError(f"World Bank bulk {indicator} lacks countries: {sorted(set(codes) - seen)}")
    return rows
