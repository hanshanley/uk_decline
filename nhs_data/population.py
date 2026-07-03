"""ONS mid-year population estimates (via the Nomis API) for per-capita views.

Nomis (``nomisweb.co.uk``) is the ONS's official data service. Dataset
``NM_2002_1`` ("Population estimates - local authority based by single year of
age") provides mid-year population estimates; we read the all-ages, both-sexes
total for each of the four UK nations.

These are **real published estimates** — ONS for England & Wales, National Records
of Scotland (NRS) for Scotland, and NISRA for Northern Ireland — surfaced together
through Nomis. Nothing here is synthesised or interpolated: years without a
published estimate simply have no entry, and callers must skip them rather than
extrapolate.
"""

from __future__ import annotations

from ._http import get_json

NOMIS_DATASET = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.json"
SOURCE = "ONS/NRS/NISRA mid-year population estimates (via Nomis, NM_2002_1)"

# GSS country code -> nation code used in tidy rows.
GEOGRAPHY: dict[str, str] = {
    "E92000001": "ENG",
    "S92000003": "SCO",
    "W92000004": "WAL",
    "N92000002": "NIR",
}


def fetch(
    start_year: int | None = None, end_year: int | None = None
) -> dict[tuple[str, int], float]:
    """Return ``{(nation_code, year): population}`` of real ONS mid-year estimates.

    Only years actually published by ONS are returned; a missing year is absent
    from the mapping (never filled in or projected).
    """
    params = {
        "geography": ",".join(GEOGRAPHY),
        "date": "latestMINUS20-latest",
        "gender": "0",  # persons (both sexes)
        "c_age": "200",  # all ages
        "measures": "20100",  # value
        "select": "geography_code,time_name,obs_value",
    }
    payload = get_json(NOMIS_DATASET, params=params)
    out: dict[tuple[str, int], float] = {}
    for obs in payload.get("obs", []):
        code = (obs.get("geography") or {}).get("geogcode")
        nation = GEOGRAPHY.get(code)
        value = (obs.get("obs_value") or {}).get("value")
        try:
            year = int((obs.get("time") or {}).get("value"))
        except (TypeError, ValueError):
            continue
        if nation is None or value is None:
            continue
        if start_year is not None and year < start_year:
            continue
        if end_year is not None and year > end_year:
            continue
        out[(nation, year)] = float(value)
    return out
