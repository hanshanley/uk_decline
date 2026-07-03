"""Formal data citations for every source used in nhs_data.

Single source of truth for proper attribution: the organisation that *collected /
published* each dataset, the dataset title, and where it was accessed. Rendered
into the generated summary (:mod:`nhs_data.summary`) and mirrored in the README so
every showcased artifact credits the collecting body, not just a short label.
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple


class Citation(NamedTuple):
    publisher: str  # the organisation that collected / published the data
    title: str  # dataset / statistical series title
    via: str  # access platform + URL


# Ordered list of citations. ``accessed`` is stamped at render time.
CITATIONS: list[Citation] = [
    Citation(
        "NHS England",
        "Consultant-led Referral to Treatment (RTT) Waiting Times; "
        "A&E Attendances and Emergency Admissions; Cancer Waiting Times; and "
        "Monthly Diagnostic Waiting Times and Activity (DM01)",
        "NHS England statistical work areas, https://www.england.nhs.uk/statistics/statistical-work-areas/",
    ),
    Citation(
        "Public Health Scotland",
        "NHS Scotland waiting times: Stage of Treatment (ongoing waits); "
        "Accident & Emergency activity and waiting times; Cancer waiting times; "
        "and Diagnostic waiting times",
        "Scottish Health and Social Care Open Data platform, https://www.opendata.nhs.scot/",
    ),
    Citation(
        "Welsh Government (StatsWales)",
        "NHS activity and performance: Referral to treatment times; Accident and "
        "emergency 4-hour performance; Suspected cancer pathway; and Diagnostic and "
        "therapy services waiting times",
        "StatsWales open data API, https://statswales.gov.wales/",
    ),
    Citation(
        "Department of Health (Northern Ireland), Information & Analysis Directorate",
        "Northern Ireland Waiting Time Statistics: Outpatient, Diagnostic and Cancer "
        "Waiting Times; and Emergency Care Waiting Times",
        "https://www.health-ni.gov.uk/ and OpenDataNI, https://www.opendatani.gov.uk/",
    ),
    Citation(
        "Office for National Statistics (ONS); National Records of Scotland (NRS); "
        "Northern Ireland Statistics and Research Agency (NISRA)",
        "Mid-year population estimates (dataset NM_2002_1), used only for the "
        "derived per-1,000 population-adjusted series",
        "Nomis (operated by Durham University on behalf of ONS), https://www.nomisweb.co.uk/",
    ),
]

# Contains public sector information licensed under the Open Government Licence v3.0.
LICENCE_NOTE = (
    "Contains public sector information licensed under the Open Government "
    "Licence v3.0."
)


def render_markdown(accessed: date | None = None) -> str:
    """Return a markdown block of formal citations, stamped with an access date."""
    accessed = accessed or date.today()
    lines = ["## Data sources & citations\n"]
    lines.append(
        "Every value is collected and published by the official statistical body "
        "for each nation; nothing is modelled or synthesised. Cite as:\n"
    )
    for c in CITATIONS:
        lines.append(
            f"- **{c.publisher}** \u2014 *{c.title}.* {c.via} "
            f"(accessed {accessed:%Y-%m-%d})."
        )
    lines.append(f"\n{LICENCE_NOTE}")
    return "\n".join(lines) + "\n"
