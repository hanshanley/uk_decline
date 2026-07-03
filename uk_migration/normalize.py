"""Population-normalised (per-capita) views of the migration flow series.

Immigration figures are **headcounts**, not monetary values, so CPI inflation adjustment
does not apply to them. The meaningful "real-terms" comparison across decades is to express
each flow relative to the size of the UK population (which grew from ~55.7M in 1970 to ~69M
today). This module divides each flow by the UK total population for the same year and
reports the result per 1,000 people.

Both inputs are real, fetched series:
  * numerator   -> the flow (ONS LTIM / Home Office / World Bank), already in the table
  * denominator -> World Bank ``SP.POP.TOTL`` (UK total population), metric ``uk_population``

Derived rows are labelled with a ``Derived:`` source string so they are never mistaken for
primary data, and are only emitted for years where a real population value exists.
"""

from __future__ import annotations

from . import schema

POP_METRIC = "uk_population"

# (metric, category) flow series to normalise by population.
NORMALISE: tuple[tuple[str, str], ...] = (
    ("immigration", "all"),
    ("emigration", "all"),
    ("net_migration", "all"),
    ("net_migration_wb", "all"),
    ("asylum_applications", "main_applicant"),
    ("irregular_arrivals", "all"),
    ("visas_granted", "work"),
    ("visas_granted", "study"),
    ("visas_granted", "family"),
    ("visas_granted", "visitor"),
    ("visas_granted", "other"),
)


def per_capita(rows: list[dict]) -> list[dict]:
    """Return derived per-1,000-population rows for the configured flow series.

    ``rows`` must already contain the ``uk_population`` series (from World Bank). For every
    configured ``(metric, category)`` and every year with a population value, emit one row
    ``value = flow / population * 1000`` with a transparent ``Derived:`` source.
    """
    population: dict[int, float] = {
        r["period"]: r["value"] for r in rows if r["metric"] == POP_METRIC
    }
    wanted = set(NORMALISE)
    out: list[dict] = []
    for r in rows:
        key = (r["metric"], r["category"])
        if key not in wanted:
            continue
        pop = population.get(r["period"])
        if not pop:
            continue
        out.append(
            schema.row(
                period=r["period"],
                metric=f"{r['metric']}_per_1000_pop",
                value=r["value"] / pop * 1000.0,
                unit="per 1,000 population",
                legality=r["legality"],
                flow_type=r["flow_type"],
                source=f"Derived: {r['source']} \u00f7 World Bank SP.POP.TOTL",
                category=r["category"],
            )
        )
    return out
