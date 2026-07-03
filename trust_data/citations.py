"""Formal citations for every data source, keyed by the ``source`` string on the tidy rows.

Keeping citations here (single source of truth) lets figures show a short citation caption and
the READMEs show the full formal citation, both crediting the organisation that collected the
data. Text is taken verbatim from the publishers' own recommended citations:

  * World Bank WGI  -> govindicators.org "Cite this Dataset"
  * OECD survey     -> Our World in Data grapher metadata (citationLong), which credits the
                       OECD "How's Life? Well-being Database" (Gallup World Poll question) as
                       the original data collector.
"""

from __future__ import annotations

from typing import NamedTuple


class Citation(NamedTuple):
    short: str   # one-line credit for figure captions
    full: str    # full formal citation for READMEs


CITATIONS: dict[str, Citation] = {
    "World Bank WGI": Citation(
        short="World Bank, Worldwide Governance Indicators (Kaufmann & Kraay, 2024)",
        full=(
            "Kaufmann, Daniel & Aart C. Kraay (2024). "
            "\u201cThe Worldwide Governance Indicators: Methodology and 2024 Update.\u201d "
            "Policy Research Working Paper. Washington, DC: World Bank Group. "
            "Dataset: *Worldwide Governance Indicators (WGI)*, 2024 update, World Bank Group, "
            "Washington, DC \u2014 accessed via the World Bank API (DataBank source 3). "
            "https://www.govindicators.org"
        ),
    ),
    "OECD Trust in Government via Our World in Data (grapher: oecd-average-trust-in-governments)": (
        Citation(
            short="OECD, How\u2019s Life? Well-being Database (Gallup World Poll), via Our World in Data",
            full=(
                "OECD (2026), with major processing by Our World in Data. "
                "\u201cOECD average trust in governments\u201d [dataset]. "
                "Original data: OECD, *How\u2019s Life? Well-being Database* \u2014 survey item from "
                "the Gallup World Poll (\u201cIn this country, do you have confidence in national "
                "government, or not?\u201d). "
                "https://ourworldindata.org/grapher/oecd-average-trust-in-governments"
            ),
        )
    ),
}


def short_citation(source: str) -> str:
    c = CITATIONS.get(source)
    return c.short if c else source


def full_citation(source: str) -> str:
    c = CITATIONS.get(source)
    return c.full if c else source
