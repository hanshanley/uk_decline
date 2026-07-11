"""OECD SDMX client for survey trust in government (best-effort, key-less).

Trust data lives in the OECD "Trust and Drivers of Government" dataflow
``OECD.GOV.GIP,DSD_GOV_INT@DF_GOV_TDG_2025`` (measure ``TRUST_NG`` = trust in the national
government, expressed as a percentage). We request SDMX-JSON v2 with ``dimensionAtObservation
=AllDimensions`` and decode the observation keys generically from the returned structure, so
we do not hard-code the internal codelist ordering.

The OECD Data API rate-limits aggressively and occasionally returns backend "mapping store"
errors; on any failure this module returns ``[]`` so the caller can fall back to the vendored
manual seed (see :mod:`trust_data.manual`) - the same hybrid pattern used elsewhere in this
repo for OECD data.
"""

from __future__ import annotations

from typing import Iterable

import requests

from . import countries, metrics
from ._http import get_json

BASE = "https://sdmx.oecd.org/public/rest/data"
AGENCY = "OECD.GOV.GIP"

# Trust and Drivers of Government dataflow, with an older-edition fallback.
DATAFLOWS: tuple[str, ...] = (
    "DSD_GOV_INT@DF_GOV_TDG_2025",
    "DSD_GOV_TDG_SPS_GPC@DF_GOV_TDG_2023",
)

# OECD MEASURE code -> canonical trust metric id.
MEASURES: dict[str, str] = {
    "TRUST_NG": "trust_national_govt_pct",
}

SOURCE = "OECD (Trust in national government)"
TRUST_SCALE = "HMH"  # high or moderately high trust

_ACCEPT = {"Accept": "application/vnd.sdmx.data+json;version=2"}


def _index_dimensions(structure: dict) -> tuple[dict[str, int], dict[str, list]]:
    """Return (dim_id -> position, dim_id -> [value dicts]) for observation dimensions."""
    obs_dims = structure["dimensions"]["observation"]
    idx = {d["id"]: i for i, d in enumerate(obs_dims)}
    values = {d["id"]: d["values"] for d in obs_dims}
    return idx, values


def _decode(payload: dict) -> list[dict]:
    data = payload.get("data") or {}
    structures = data.get("structures") or []
    datasets = data.get("dataSets") or []
    if not structures or not datasets:
        return []
    idx, values = _index_dimensions(structures[0])
    for req in ("REF_AREA", "MEASURE", "TIME_PERIOD"):
        if req not in idx:
            return []
    observations = datasets[0].get("observations") or {}

    out: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for key, obs in observations.items():
        parts = key.split(":")
        measure_code = values["MEASURE"][int(parts[idx["MEASURE"]])]["id"]
        metric = MEASURES.get(measure_code)
        if metric is None:
            continue
        iso3 = values["REF_AREA"][int(parts[idx["REF_AREA"]])]["id"]
        if iso3 not in countries.BY_ISO3:
            continue
        if "SCALE" in idx:
            scale = values["SCALE"][int(parts[idx["SCALE"]])]["id"]
            if scale != TRUST_SCALE:
                continue
        year = values["TIME_PERIOD"][int(parts[idx["TIME_PERIOD"]])]["id"]
        value = obs[0]
        if value is None:
            continue
        row_key = (iso3, int(str(year)[:4]), metric)
        if row_key in seen:
            raise ValueError(f"duplicate OECD trust observation for {row_key}")
        seen.add(row_key)
        out.append(
            metrics.make_row(
                iso3=iso3,
                country=countries.name_for_iso3(iso3),
                year=row_key[1],
                metric=metric,
                value=float(value),
                source=SOURCE,
            )
        )
    return out


def _fetch_dataflow(dataflow: str, iso3s: list[str], start: int) -> list[dict]:
    # Key: FREQ.REF_AREA.MEASURE.<remaining dims empty>. REF_AREA and MEASURE are the only
    # positions we pin; trailing dots are padded generously (extra dots are ignored).
    ref = "+".join(iso3s)
    measures = "+".join(MEASURES)
    key = f".{ref}.{measures}......"
    url = f"{BASE}/{AGENCY},{dataflow}/{key}"
    payload = get_json(
        url,
        params={"startPeriod": start, "dimensionAtObservation": "AllDimensions"},
        headers=_ACCEPT,
    )
    return _decode(payload)


def fetch(
    start: int,
    end: int,
    iso3s: Iterable[str] | None = None,
) -> list[dict]:
    """Best-effort fetch of OECD survey trust rows; returns ``[]`` on any failure.

    ``end`` is accepted for signature symmetry with the other sources but the OECD API is
    queried from ``start`` onward and filtered downstream.
    """
    iso3_list = list(iso3s) if iso3s is not None else countries.iso3_codes()
    for dataflow in DATAFLOWS:
        try:
            rows = _fetch_dataflow(dataflow, iso3_list, start)
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"[oecd] {dataflow} failed: {exc}")
            continue
        if rows:
            return [r for r in rows if start <= r["year"] <= end]
        print(f"[oecd] {dataflow} returned no trust rows.")
    print("[oecd] no OECD trust rows retrieved; caller should use the manual seed.")
    return []
