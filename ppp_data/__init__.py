"""Purchasing-power-parity (PPP) view of the UK's relative decline.

A companion to the repository's separate real-volume and nominal-dollar GDP charts.
Current PPPs compare GDP at each year's price structure; constant PPPs compare volumes
valued at the 2021 benchmark. The overview uses constant PPPs, whose growth is independently
checked against national-accounts constant-dollar GDP.

GDP is not median household income, and the gap between nominal-dollar and volume growth
is an accounting price/exchange-rate residual, not an identified currency effect.
Figures live in ``outputs/ppp/``.

Run it::

    python -m ppp_data              # fetch -> validate -> combine -> charts
    python -m ppp_data --from-csv   # re-chart offline from data/ppp_long.csv

See ``ppp_data/README.md`` for the methodology and the full list of caveats.
"""

__all__ = [
    "charts", "combine", "decompose", "figure", "maddison", "metrics", "paths", "peers",
    "series", "tuition_ppp", "validate", "worldbank",
]
