"""World Bank WDI client: 5-year age-band population by sex, as shares (for pyramids).

Fetches the ``SP.POP.{band}.MA`` / ``SP.POP.{band}.FE`` count indicators (00-04 … 80+),
then converts each (band, sex) count to a share of that country-year's total population
(the sum over all bands and both sexes, so the shares are internally consistent and sum
to ~100%). Underlying data is the UN Population Division's World Population Prospects,
redistributed by the World Bank (see :data:`age_data.config.CITATIONS`).
"""

from __future__ import annotations

from typing import Iterable

from . import config
from ._http import get_json
from .combine import make_row

SOURCE = config.SOURCE_WB
METRIC = "pop_band_share_pct"
METRICS = (METRIC,)


def _fetch_counts(
    iso3s: list[str], start: int, end: int
) -> dict[tuple[str, int, str, str], float]:
    """Return ``{(iso3, year, band_label, sex_label): count}`` for every 5-year band."""
    codes = ";".join(iso3s)
    counts: dict[tuple[str, int, str, str], float] = {}
    for band_code, band_label, _mid in config.AGE_BANDS:
        for sex_code, sex_label in config.SEXES.items():
            indicator = f"SP.POP.{band_code}.{sex_code}"
            page = 1
            while True:
                payload = get_json(
                    f"{config.WORLD_BANK_BASE}/country/{codes}/indicator/{indicator}",
                    params={
                        "format": "json",
                        "per_page": 1000,
                        "date": f"{start}:{end}",
                        "page": page,
                    },
                )
                if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
                    break
                meta, rows = payload[0], payload[1]
                for row in rows:
                    value = row.get("value")
                    iso3 = row.get("countryiso3code") or ""
                    if value is None or iso3 not in config.BY_ISO3:
                        continue
                    counts[(iso3, int(row["date"]), band_label, sex_label)] = float(value)
                if page >= int(meta.get("pages", 1)):
                    break
                page += 1
    return counts


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
    totals = _totals(counts)
    out: list[dict] = []
    for (iso3, year, band, sex), n in counts.items():
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
