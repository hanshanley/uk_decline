"""uk_migration: fetch UK immigration figures over time (legal and irregular).

Data sources (all free, no API key required):
  * ONS Long-Term International Migration -> annual immigration / emigration / net
  * World Bank WDI                        -> migrant stock & net-migration backdrop (GBR)
  * Home Office (via gov.uk content API)  -> entry-clearance visas by category, asylum
  * Home Office irregular-migration data  -> irregular arrivals by route (incl. small boats)

Every source client exposes ``fetch()`` returning tidy dict rows with a common schema
(see :mod:`uk_migration.schema`). ``combine`` merges them into one long CSV and ``charts``
renders summary time-series PNGs.
"""

__all__ = ["schema", "sources", "normalize", "combine", "charts", "run"]

__version__ = "0.1.0"
