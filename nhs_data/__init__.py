"""nhs_data: fetch NHS waiting-time statistics for the four UK nations over time.

Metric families (see :mod:`nhs_data.metrics`):
  * Elective / RTT   -> total on the waiting list + median wait
  * A&E              -> 4-hour performance (share seen within 4 hours)
  * Cancer           -> 62-day standard performance
  * Diagnostics      -> waiting for a diagnostic test (6-week standard)

Sources (health is devolved, so each nation publishes separately):
  * Scotland          -> Public Health Scotland open data API (opendata.nhs.scot)
  * Wales             -> StatsWales OData API (statswales.gov.wales)
  * England           -> NHS England CSV/Excel statistical work areas
  * Northern Ireland  -> Department of Health NI quarterly spreadsheets
  * Population         -> ONS/NRS/NISRA mid-year estimates via Nomis (per-capita view)

Every source module returns tidy long-format rows with the schema described in
:mod:`nhs_data.metrics` (``ROW_FIELDS``). Metric definitions differ by nation, so
rows carry ``metric`` + ``source`` and charts show per-nation trends rather than
strict apples-to-apples comparisons.
"""

__all__ = [
    "nations",
    "metrics",
    "population",
    "sources",
    "scotland",
    "wales",
    "england",
    "northern_ireland",
    "combine",
    "charts",
    "summary",
]

__version__ = "0.1.0"
