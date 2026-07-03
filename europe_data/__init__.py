"""europe_data: fetch European per-capita GDP (PPP) and median disposable income (PPP/PPS).

Data sources (all free, no API key required):
  * World Bank WDI  -> GDP per capita, PPP (nominal + constant int'l $)
  * Eurostat ilc_di03 -> median & mean equivalised disposable income (PPS)
  * World Bank PIP  -> median income (2017 PPP $/day), fills UK post-2018 gap
"""

__all__ = ["countries", "worldbank", "eurostat", "pip", "combine"]

__version__ = "0.1.0"
