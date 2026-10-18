"""Regions compared in the stock-market pipeline and their World Bank codes.

The comparison is anchored on the **UK vs US**; a handful of reference regions
(World, EU, Japan, China) are included so the two can be read against the global
picture. Codes are World Bank 3-letter region/aggregate codes.
"""

from __future__ import annotations

from typing import NamedTuple
from vizstyle import country_color


class Region(NamedTuple):
    name: str
    code: str  # World Bank code, used in tidy rows / charts
    core: bool  # True for the UK/US focus pair


REGIONS: list[Region] = [
    Region("United Kingdom", "GBR", True),
    Region("United States", "USA", True),
    Region("World", "WLD", False),
    Region("European Union", "EUU", False),
    Region("Japan", "JPN", False),
    Region("China", "CHN", False),
]

BY_CODE: dict[str, Region] = {r.code: r for r in REGIONS}

COLOURS: dict[str, str] = {region.code: country_color(region.code) for region in REGIONS}


def codes(core_only: bool = False) -> list[str]:
    return [r.code for r in REGIONS if (r.core or not core_only)]


def name_for_code(code: str) -> str:
    r = BY_CODE.get(code)
    return r.name if r else code
