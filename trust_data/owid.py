"""Live OWID/OECD trust-in-government CSV client.

The grapher series is OECD's How's Life? trust measure based on the Gallup World Poll.
Values are downloaded on every production run; no local value snapshot is substituted.
"""

from __future__ import annotations

import csv
import io
from typing import Iterable

from . import citations, countries, metrics
from ._http import get_text

URL = (
    "https://ourworldindata.org/grapher/oecd-average-trust-in-governments.csv"
    "?csvType=full&useColumnShortNames=true"
)
SOURCE = next(source for source in citations.CITATIONS if "Our World in Data" in source)


def parse(text: str, start: int, end: int, iso3s: Iterable[str] | None = None) -> list[dict]:
    """Parse the live OWID grapher CSV into canonical trust rows."""
    keep = set(iso3s) if iso3s is not None else set(countries.iso3_codes())
    out: list[dict] = []
    for raw in csv.DictReader(io.StringIO(text)):
        iso3 = (raw.get("Code") or raw.get("code") or "").strip()
        year_text = (raw.get("Year") or raw.get("year") or "").strip()
        value_text = (raw.get("trust_in_government") or "").strip()
        if iso3 not in keep or not year_text or not value_text:
            continue
        year = int(year_text)
        if start <= year <= end:
            out.append(
                metrics.make_row(
                    iso3=iso3,
                    country=countries.name_for_iso3(iso3),
                    year=year,
                    metric="trust_national_govt_pct",
                    value=float(value_text),
                    source=SOURCE,
                )
            )
    return out


def fetch(start: int, end: int, iso3s: Iterable[str] | None = None) -> list[dict]:
    """Download and parse the current public OWID/OECD trust series."""
    return parse(get_text(URL), start, end, iso3s)
