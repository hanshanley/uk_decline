"""Regions compared in the stock-market pipeline and their World Bank codes.

The comparison is anchored on the **UK vs US**; a handful of reference regions
(World, EU, Japan, China) are included so the two can be read against the global
picture. Codes are World Bank 3-letter region/aggregate codes.
"""

from __future__ import annotations

from typing import NamedTuple


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

# Stable colour per region so charts stay consistent across runs. Earthy
# "Substack" palette shared with pre1870_reapportionment_package: the UK focus
# line takes the warm accent, the US the deep blue, the rest muted earth tones.
COLOURS: dict[str, str] = {
    "GBR": "#C85A3D",  # UK -- warm accent (focus line)
    "USA": "#3D6F8C",  # US -- deep blue
    "WLD": "#8C7B6B",  # World -- muted brown-grey
    "EUU": "#4A7C59",  # EU -- green
    "JPN": "#C2993E",  # Japan -- gold
    "CHN": "#7B2D26",  # China -- deep red
}


def codes(core_only: bool = False) -> list[str]:
    return [r.code for r in REGIONS if (r.core or not core_only)]


def name_for_code(code: str) -> str:
    r = BY_CODE.get(code)
    return r.name if r else code
