"""tuition: median & average cost of a (four-year) bachelor's degree — UK vs EU vs US.

Scope (see README):
  * Cost  = tuition / fees only (no living costs).
  * Cohort = domestic / in-country (EU) students at public institutions.
  * Regions = UK (own category), EU-27, US.

Figures are collected as *annual* tuition in national currency, normalized to USD
(nominal, market FX) and constant 2022 USD, then aggregated per region (median & average). A
four-year total is reported as annual x DEGREE_YEARS.
"""

__all__ = ["config", "http", "stats"]
__version__ = "0.1.0"
