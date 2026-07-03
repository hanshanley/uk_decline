"""tax: average & median tax burden — UK vs the US vs European countries.

Two complementary lenses (see README / :mod:`tax.config`):

  * **Macro burden**      -> total tax revenue (incl. social contributions) as a
    share of GDP (OECD *Revenue Statistics*, ``tax_to_gdp_pct``).
  * **Individual burden** -> the labour **tax wedge** and **net personal average
    tax rate** on a worker at 67% / 100% / 167% of the average wage, single and
    one-earner-couple-with-2-children (OECD *Taxing Wages*).

Sources are free and key-less (OECD SDMX). Every source module returns tidy
long-format rows with the schema in :mod:`tax.combine` (``LONG_FIELDS``); rows carry
``source`` and definitional caveats live in :mod:`tax.config` so cross-country
comparisons stay honest. ``median`` is answered two ways: the cross-country median of
each metric (UK vs the median European country vs US) in :mod:`tax.stats`, and the
average-wage tax wedge as the standard proxy for the typical/median worker.
"""

__all__ = [
    "config",
    "revenue",
    "taxing_wages",
    "fallback",
    "combine",
    "stats",
    "charts",
]

__version__ = "0.1.0"
