"""Source clients for UK immigration figures.

Each module exposes ``fetch()`` returning tidy rows (see :mod:`uk_migration.schema`).
"""

__all__ = ["worldbank", "ons_ltim", "ons_ips_history", "visas", "asylum", "irregular"]
