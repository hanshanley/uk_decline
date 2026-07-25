"""Purchasing-power-parity (PPP) view of the UK's relative decline.

A **parallel** set of figures to the repository's headline, market-exchange-rate charts.
The headline analyses (``europe_data``, ``markets_data``, ``tuition``) deliberately use
**real constant US$ at market exchange rates**, because that is what UK output actually
buys on world markets. This package asks the complementary question — **what does UK
output buy at home?** — by converting at purchasing power parity instead.

Neither view is "the truth". They answer different questions, and the gap between them is
itself informative: it is precisely the sterling exchange-rate / relative-price-level
effect, which this package isolates and charts explicitly.

Nothing here modifies the headline analyses. Every figure is additive and lives in
``outputs/ppp/``.

Run it::

    python -m ppp_data                 # fetch -> validate -> combine -> charts
    python -m ppp_data --from-csv data/ppp_long.csv   # re-chart without re-fetching

See ``ppp_data/README.md`` for the methodology and the full list of caveats.
"""

__all__ = ["charts", "combine", "decompose", "metrics", "paths", "peers", "validate", "worldbank"]
