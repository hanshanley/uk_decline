"""trust_data: measure trust in UK government over time (UK vs EU-27 + US comparators).

Trust is captured from two complementary angles (see :mod:`trust_data.metrics`):
  * survey     -> OECD "trust in national government" (% who trust it)
  * governance -> World Bank Worldwide Governance Indicators (WGI) estimates:
                  Voice & Accountability, Government Effectiveness, Rule of Law,
                  Control of Corruption

Sources (all free, no API key required):
  * World Bank WGI  -> api.worldbank.org (source=3, GOV_WGI_*.EST)
  * OECD SDMX       -> sdmx.oecd.org (DSD_GOV_INT@DF_GOV_TDG, measure TRUST_NG),
                       with a vendored manual seed fallback (:mod:`trust_data.manual`)

Every source module returns tidy long-format rows with the schema in
:data:`trust_data.metrics.ROW_FIELDS`. Survey and governance metrics use different scales,
so charts/summaries present per-metric trends rather than strict cross-metric comparisons.
"""

__all__ = [
    "countries",
    "metrics",
    "worldbank",
    "oecd",
    "manual",
    "combine",
    "charts",
    "summary",
    "report",
    "paths",
]

__version__ = "0.1.0"
