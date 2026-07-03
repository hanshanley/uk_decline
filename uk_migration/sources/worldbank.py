"""World Bank WDI client: UK migrant stock and net-migration backdrop.

Provides the long historical context that the flow-based UK sources lack:
  * ``SM.POP.TOTL``    -> international migrant stock (people)
  * ``SM.POP.TOTL.ZS`` -> international migrant stock (% of population)
  * ``SM.POP.NETM``    -> net migration (people; modelled annual estimate)

No API key required. Only the UK (``GBR``) is fetched.
"""

from __future__ import annotations

from datetime import datetime

from .. import schema
from .._http import get_json

BASE = "https://api.worldbank.org/v2"
SOURCE = "World Bank WDI"

# indicator -> (metric, category, unit, legality, flow_type)
INDICATORS: dict[str, tuple[str, str, str, str, str]] = {
    "SM.POP.TOTL": ("migrant_stock", "all", "people", schema.TOTAL, schema.STOCK),
    "SM.POP.TOTL.ZS": ("migrant_stock_pct", "all", "% of population", schema.TOTAL, schema.STOCK),
    "SM.POP.NETM": ("net_migration_wb", "all", "people", schema.TOTAL, schema.NET),
    # UK total population — real denominator for population-normalising the flow series.
    "SP.POP.TOTL": ("uk_population", "all", "people", schema.TOTAL, schema.STOCK),
}


def _fetch_indicator(indicator: str, start: int, end: int) -> list[dict]:
    metric, category, unit, legality, flow_type = INDICATORS[indicator]
    out: list[dict] = []
    page = 1
    while True:
        payload = get_json(
            f"{BASE}/country/GBR/indicator/{indicator}",
            params={
                "format": "json",
                "per_page": 1000,
                "date": f"{start}:{end}",
                "page": page,
            },
        )
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            return out
        meta, data = payload[0], payload[1]
        for record in data:
            value = record.get("value")
            if value is None:
                continue
            out.append(
                schema.row(
                    period=int(record["date"]),
                    metric=metric,
                    value=float(value),
                    unit=unit,
                    legality=legality,
                    flow_type=flow_type,
                    source=SOURCE,
                    category=category,
                )
            )
        if page >= int(meta.get("pages", 1)):
            return out
        page += 1


def fetch(start: int = 1960, end: int | None = None) -> list[dict]:
    """Fetch UK migrant-stock and net-migration backdrop rows (tidy schema)."""
    if end is None:
        end = datetime.now().year
    out: list[dict] = []
    for indicator in INDICATORS:
        out.extend(_fetch_indicator(indicator, start, end))
    return out
