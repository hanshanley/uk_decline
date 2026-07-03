"""Eurostat client: median & mean equivalised net disposable income in PPS.

Dataset ``ilc_di03`` ("Mean and median income by age and sex"). We pull the totals
(``sex=T``, ``age=TOTAL``) in Purchasing Power Standard (``unit=PPS``) for both the
median (``MED_EI``) and mean (``MEAN_EI``).

The dissemination API returns JSON-stat: a flat ``value`` map keyed by a row-major
linear index over the ordered ``id`` dimensions, which we decode back to coordinates.

Note: the UK left EU-SILC after Brexit, so UK rows generally stop around 2018.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from . import countries
from ._http import get_json

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
DATASET = "ilc_di03"

# statinfo code -> metric name
STATINFO: dict[str, str] = {
    "MED_EI": "median_disposable_income",
    "MEAN_EI": "mean_disposable_income",
}

SOURCE = "Eurostat ilc_di03"
UNIT = "PPS"  # Purchasing Power Standard


def _iter_values(payload: dict) -> Iterator[tuple[dict, float]]:
    """Yield (coord_codes, value) for every observation in a JSON-stat payload."""
    dim_ids: list[str] = payload["id"]
    sizes: list[int] = payload["size"]
    # For each dimension, an ordered list of category codes (by index).
    ordered: list[list[str]] = []
    for dim in dim_ids:
        index = payload["dimension"][dim]["category"]["index"]
        codes = [None] * len(index)
        for code, i in index.items():
            codes[i] = code
        ordered.append(codes)
    # Row-major strides (last dimension varies fastest).
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    for key, value in payload.get("value", {}).items():
        idx = int(key)
        coord: dict[str, str] = {}
        for d, dim in enumerate(dim_ids):
            pos = (idx // strides[d]) % sizes[d]
            coord[dim] = ordered[d][pos]
        yield coord, value


def fetch(
    start: int,
    end: int,
    geos: Iterable[str] | None = None,
    statinfos: Iterable[str] | None = None,
) -> list[dict]:
    """Fetch Eurostat median/mean disposable income (PPS) rows.

    Returns tidy dict rows: iso3, country, year, metric, value, unit, source.
    """
    geo_list = list(geos) if geos is not None else countries.eurostat_geos()
    stat_list = list(statinfos) if statinfos is not None else list(STATINFO)

    params: list[tuple[str, str]] = [
        ("format", "JSON"),
        ("unit", UNIT),
        ("sex", "T"),
        ("age", "TOTAL"),
        ("sinceTimePeriod", str(start)),
        ("untilTimePeriod", str(end)),
    ]
    params += [("statinfo", s) for s in stat_list]
    params += [("geo", g) for g in geo_list]

    payload = get_json(f"{BASE}/{DATASET}", params=params)
    if "value" not in payload:  # e.g. an error envelope
        return []

    out: list[dict] = []
    for coord, value in _iter_values(payload):
        geo = coord.get("geo", "")
        metric = STATINFO.get(coord.get("statinfo", ""))
        if metric is None or value is None:
            continue
        out.append(
            {
                "iso3": countries.iso3_for_eurostat(geo),
                "country": countries.name_for_eurostat(geo),
                "year": int(coord["time"]),
                "metric": metric,
                "value": float(value),
                "unit": UNIT,
                "source": SOURCE,
            }
        )
    return out
