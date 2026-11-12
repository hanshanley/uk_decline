"""World Bank client: 5-year age-band population by sex, as shares (for pyramids).

Fetches the ``SP.POP.{band}.MA`` / ``SP.POP.{band}.FE`` count indicators (00-04 … 80+),
then converts each (band, sex) count to a share of that country-year's total population
(the sum over all bands and both sexes, so the shares are internally consistent and sum
to ~100%). Underlying data is the UN Population Division's World Population Prospects,
redistributed by World Bank database 16 (see :data:`age_data.config.CITATIONS`).
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from typing import Iterable, Iterator

import requests

from europe_data._http import get_bytes
from europe_data._worldbank import observations

from . import config
from ._http import get_json
from .combine import make_row

SOURCE = config.SOURCE_WB
METRIC = "pop_band_share_pct"
METRICS = (METRIC,)
COUNTRY_BATCH_SIZE = 10
POPULATION_SOURCE = 16
BULK_URL = "https://databankfiles.worldbank.org/public/ddpext_download/HNP_Stats_CSV.zip"


def _batches(items: list[str], size: int = COUNTRY_BATCH_SIZE) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _fetch_api_counts(
    iso3s: list[str], start: int, end: int
) -> dict[tuple[str, int, str, str], float]:
    """Return ``{(iso3, year, band_label, sex_label): count}`` for every 5-year band."""
    counts: dict[tuple[str, int, str, str], float] = {}
    batch_size = len(iso3s) if start == end else COUNTRY_BATCH_SIZE
    for batch in _batches(iso3s, batch_size):
        for band_code, band_label, _mid in config.AGE_BANDS:
            for sex_code, sex_label in config.SEXES.items():
                indicator = f"SP.POP.{band_code}.{sex_code}"
                for row in observations(
                    indicator, batch, start, end, source=POPULATION_SOURCE, download=get_json,
                ):
                    value = row.get("value")
                    iso3 = row.get("countryiso3code") or ""
                    if value is None or iso3 not in config.BY_ISO3:
                        continue
                    counts[(iso3, int(row["date"]), band_label, sex_label)] = float(value)
    return counts


def _bulk_counts(iso3s: list[str], start: int, end: int) -> dict:
    indicators = {
        f"SP.POP.{code}.{sex}": (band, label)
        for code, band, _mid in config.AGE_BANDS
        for sex, label in config.SEXES.items()
    }
    countries = set(iso3s)
    years = range(start, end + 1)
    required = {"Country Code", "Indicator Code", *(str(year) for year in years)}
    counts = {}
    with zipfile.ZipFile(io.BytesIO(get_bytes(BULK_URL, timeout=180))) as archive:
        try:
            data = archive.open("HNP_StatsCSV.csv")
        except KeyError as error:
            raise ValueError("World Bank HNP bulk archive has no population data table") from error
        with data, io.TextIOWrapper(data, encoding="utf-8-sig", newline="") as text:
            rows = csv.DictReader(text)
            if not required.issubset(rows.fieldnames or []):
                raise ValueError("World Bank HNP bulk table is missing requested columns/years")
            for row in rows:
                iso3, indicator = row["Country Code"], row["Indicator Code"]
                if iso3 not in countries or indicator not in indicators:
                    continue
                band, sex = indicators[indicator]
                for year in years:
                    raw = row[str(year)]
                    if raw in (None, "", ".."):
                        continue
                    value = float(raw)
                    key = (iso3, year, band, sex)
                    if not math.isfinite(value) or value < 0 or key in counts:
                        raise ValueError(f"Invalid or duplicate World Bank HNP count: {key}")
                    counts[key] = value
    expected = {
        (iso3, year, band, sex)
        for iso3 in countries for year in years for band, sex in indicators.values()
    }
    if expected - counts.keys():
        raise ValueError("World Bank HNP bulk table is missing requested age-sex observations")
    return counts


def _fetch_counts(
    iso3s: list[str], start: int, end: int
) -> dict[tuple[str, int, str, str], float]:
    if start > end:
        raise ValueError("World Bank start year must not exceed end year")
    if not iso3s:
        return {}
    try:
        return _bulk_counts(iso3s, start, end)
    except (requests.RequestException, ValueError, zipfile.BadZipFile) as error:
        print(
            f"[worldbank] HNP bulk transport unavailable ({error}); "
            "retrying the same database through the API",
            flush=True,
        )
        return _fetch_api_counts(iso3s, start, end)


def _totals(counts: dict[tuple[str, int, str, str], float]) -> dict[tuple[str, int], float]:
    totals: dict[tuple[str, int], float] = {}
    for (iso3, year, _band, _sex), n in counts.items():
        totals[(iso3, year)] = totals.get((iso3, year), 0.0) + n
    return totals


def counts_by_band(
    iso3s: Iterable[str], start: int, end: int
) -> dict[tuple[str, int, str, str], float]:
    """Public helper: raw 5-year band counts (used by the median-age derivation)."""
    codes = list(iso3s)
    return _fetch_counts(codes, start, end)


def rows_from_counts(counts: dict[tuple[str, int, str, str], float]) -> list[dict]:
    """Convert raw band counts to tidy ``pop_band_share_pct`` rows (share of total pop)."""
    expected = {
        (band_label, sex_label)
        for _band_code, band_label, _mid in config.AGE_BANDS
        for sex_label in config.SEXES.values()
    }
    observed: dict[tuple[str, int], set[tuple[str, str]]] = {}
    for iso3, year, band, sex in counts:
        observed.setdefault((iso3, year), set()).add((band, sex))
    complete = {key for key, profile in observed.items() if profile == expected}
    totals: dict[tuple[str, int], float] = {}
    for (iso3, year, _band, _sex), n in counts.items():
        key = (iso3, year)
        if key in complete:
            totals[key] = totals.get(key, 0.0) + n
    out: list[dict] = []
    for (iso3, year, band, sex), n in counts.items():
        if (iso3, year) not in complete:
            continue
        total = totals.get((iso3, year), 0.0)
        if total <= 0:
            continue
        out.append(
            make_row(
                iso3=iso3,
                year=year,
                metric=METRIC,
                value=100.0 * n / total,
                source=SOURCE,
                age_band=band,
                sex=sex,
            )
        )
    return out


def fetch(start: int, end: int, iso3s: Iterable[str] | None = None) -> list[dict]:
    """Fetch 5-year age-band population shares by sex for the given years/countries."""
    codes = list(iso3s) if iso3s is not None else config.iso3_codes()
    return rows_from_counts(_fetch_counts(codes, start, end))
