"""crime_data: crime in the UK over time, framed honestly (UK vs US + EU comparators).

Two complementary, free, key-less sources (see the source modules):
  * ONS Crime Survey for England & Wales (CSEW) -> the long-run headline-crime trend
    (incidents, 1,000s), year ending 1981 -> present. The authoritative UK trend measure.
  * World Bank -> intentional homicide rate per 100,000 (UNODC-sourced), for an
    apples-to-apples comparison of the UK against the US and EU-27 peers.

The story is deliberately nuanced: total CSEW crime has fallen sharply since its mid-1990s
peak, but once newer harms (fraud & computer misuse) are counted the picture is far less
rosy, and UK homicide sits above several European peers. Every value is fetched live or
parsed verbatim from the source; nothing is hand-entered.
"""

__all__ = ["countries", "csew", "homicide", "charts"]

__version__ = "0.1.0"
