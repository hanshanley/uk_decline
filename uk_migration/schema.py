"""Tidy-row schema shared by every ``uk_migration`` source client.

Each source ``fetch()`` returns a list of dicts with these keys:

  * ``iso3``      -> always ``GBR`` (UK-only project)
  * ``country``   -> ``United Kingdom``
  * ``period``    -> calendar year (int)
  * ``metric``    -> series name, e.g. ``immigration``, ``net_migration``, ``visas_granted``
  * ``category``  -> optional breakdown, e.g. ``work`` / ``study`` / ``family`` / ``all``
  * ``value``     -> numeric observation
  * ``unit``      -> unit label, e.g. ``people`` or ``% of population``
  * ``legality``  -> legal character of the migration: :data:`LEGALITY`
  * ``flow_type`` -> nature of the measure: :data:`FLOW_TYPES`
  * ``source``    -> human-readable provenance string

``legality`` and ``flow_type`` are kept separate on purpose: ``legality`` answers "legal vs
irregular", while ``flow_type`` answers "inflow / outflow / net / stock / count". Aggregate
measures that are not split by legal status (net migration, migrant stock) carry
``legality = total``, so filtering on ``legality == 'legal'`` never silently drops them.
"""

from __future__ import annotations

ISO3 = "GBR"
COUNTRY = "United Kingdom"

# Legal character of the migration.
LEGAL = "legal"
IRREGULAR = "irregular"
TOTAL = "total"  # aggregate measures not split by legal status (net, stock)
LEGALITY = (LEGAL, IRREGULAR, TOTAL)

# Nature of the measured quantity.
INFLOW = "inflow"
OUTFLOW = "outflow"
NET = "net"
STOCK = "stock"
COUNT = "count"
FLOW_TYPES = (INFLOW, OUTFLOW, NET, STOCK, COUNT)

FIELDS = (
    "iso3",
    "country",
    "period",
    "metric",
    "category",
    "value",
    "unit",
    "legality",
    "flow_type",
    "source",
)


def row(
    period: int,
    metric: str,
    value: float,
    *,
    unit: str,
    legality: str,
    flow_type: str,
    source: str,
    category: str = "all",
) -> dict:
    """Build one tidy row, validating ``legality``/``flow_type`` and coercing types."""
    if legality not in LEGALITY:
        raise ValueError(f"unknown legality {legality!r}; expected one of {LEGALITY}")
    if flow_type not in FLOW_TYPES:
        raise ValueError(f"unknown flow_type {flow_type!r}; expected one of {FLOW_TYPES}")
    return {
        "iso3": ISO3,
        "country": COUNTRY,
        "period": int(period),
        "metric": metric,
        "category": category,
        "value": float(value),
        "unit": unit,
        "legality": legality,
        "flow_type": flow_type,
        "source": source,
    }
