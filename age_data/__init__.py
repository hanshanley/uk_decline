"""age_data: how the UK's age distribution has changed over time — vs the US & Europe.

The population-ageing story, in three views (see :mod:`age_data.config`):

  * **Broad age structure** -> share of the population aged 0-14 / 15-64 / 65+, and the
    old-age & child dependency ratios (World Bank WDI).
  * **Population pyramids**  -> share of the population in each 5-year age band, by sex,
    for the UK over time (World Bank WDI 5-year age-sex bands).
  * **Median age**          -> transparently *derived* from the published 5-year band
    counts (documented interpolation), clearly labelled as a derivation.

Data is collected by the **United Nations Population Division** (World Population
Prospects) and redistributed via the **World Bank** World Development Indicators; the
full bibliographic citations live in :data:`age_data.config.CITATIONS`. Every source
module returns tidy long-format rows with the schema in :mod:`age_data.combine`, and
every row carries a ``source`` so figures/tables stay honestly attributed.
"""

__all__ = [
    "config",
    "worldbank",
    "pyramids",
    "median_age",
    "fallback",
    "combine",
    "stats",
    "charts",
]

__version__ = "0.1.0"
