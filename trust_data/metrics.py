"""Canonical trust metrics, the tidy-row schema, and comparability caveats.

We measure "trust in government" from two complementary angles that are **not** on a common
scale, so each row carries its ``metric`` + ``source`` and the caveats below keep downstream
charts / summaries honest:

  * survey     -> OECD "trust in national government" (share of people who trust it, %)
  * governance -> World Bank Worldwide Governance Indicators (WGI) estimates (~ -2.5..+2.5)

Higher is "more trust / better governance" for every metric defined here.
"""

from __future__ import annotations

from typing import Any, NamedTuple

# Tidy long-format row schema returned by every source module.
ROW_FIELDS: tuple[str, ...] = (
    "iso3",     # World Bank / OECD country code, e.g. "GBR"
    "country",  # display name, e.g. "United Kingdom"
    "year",     # int
    "metric",   # canonical metric id (see METRICS)
    "value",    # float
    "unit",     # unit label
    "source",   # source attribution string
)


class Metric(NamedTuple):
    id: str
    label: str
    unit: str
    family: str  # survey | governance
    higher_is_better: bool
    description: str


METRICS: dict[str, Metric] = {
    "trust_national_govt_pct": Metric(
        "trust_national_govt_pct",
        "Trust in national government",
        "percent",
        "survey",
        higher_is_better=True,
        description=(
            "Share of people who report they trust the national government "
            "(OECD, based on the Gallup World Poll question on confidence in "
            "national government)."
        ),
    ),
    "wgi_voice_accountability": Metric(
        "wgi_voice_accountability",
        "WGI: Voice & Accountability",
        "estimate (-2.5..2.5)",
        "governance",
        higher_is_better=True,
        description=(
            "Perceptions of the extent to which citizens can participate in "
            "selecting their government, plus freedom of expression, association "
            "and a free media (World Bank WGI, governance estimate)."
        ),
    ),
    "wgi_government_effectiveness": Metric(
        "wgi_government_effectiveness",
        "WGI: Government Effectiveness",
        "estimate (-2.5..2.5)",
        "governance",
        higher_is_better=True,
        description=(
            "Perceptions of the quality of public and civil services, policy "
            "formulation/implementation, and the credibility of the government's "
            "commitment to such policies (World Bank WGI)."
        ),
    ),
    "wgi_rule_of_law": Metric(
        "wgi_rule_of_law",
        "WGI: Rule of Law",
        "estimate (-2.5..2.5)",
        "governance",
        higher_is_better=True,
        description=(
            "Perceptions of confidence in and adherence to the rules of society "
            "- contract enforcement, property rights, the police and the courts "
            "(World Bank WGI)."
        ),
    ),
    "wgi_control_of_corruption": Metric(
        "wgi_control_of_corruption",
        "WGI: Control of Corruption",
        "estimate (-2.5..2.5)",
        "governance",
        higher_is_better=True,
        description=(
            "Perceptions of the extent to which public power is exercised for "
            "private gain, including petty and grand corruption and state capture "
            "(World Bank WGI)."
        ),
    ),
}

# Comparability caveats surfaced in the summary so cross-metric reads stay honest.
CAVEATS: dict[str, str] = {
    "trust_national_govt_pct": (
        "Survey measure with sparse, roughly-annual coverage; question wording and "
        "sample differ from national polls (e.g. British Social Attitudes), so treat "
        "the level as indicative and focus on the trend."
    ),
    "wgi_voice_accountability": (
        "WGI is a perceptions-based composite index (aggregated from many sources) on "
        "an approximate -2.5..+2.5 scale; it proxies governance quality, not direct "
        "public trust, and is not comparable to the survey percentage."
    ),
    "wgi_government_effectiveness": (
        "Composite perceptions index; compare trends over time rather than exact levels."
    ),
    "wgi_rule_of_law": (
        "Composite perceptions index; compare trends over time rather than exact levels."
    ),
    "wgi_control_of_corruption": (
        "Composite perceptions index; compare trends over time rather than exact levels."
    ),
}

# Convenience groupings.
SURVEY_METRICS: tuple[str, ...] = tuple(
    m for m, meta in METRICS.items() if meta.family == "survey"
)
GOVERNANCE_METRICS: tuple[str, ...] = tuple(
    m for m, meta in METRICS.items() if meta.family == "governance"
)


def make_row(
    iso3: str,
    country: str,
    year: int,
    metric: str,
    value: float,
    source: str,
) -> dict[str, Any]:
    """Build a validated tidy row, deriving the unit from the metric id."""
    if metric not in METRICS:
        raise KeyError(f"unknown metric id: {metric!r}")
    return {
        "iso3": iso3,
        "country": country,
        "year": int(year),
        "metric": metric,
        "value": float(value),
        "unit": METRICS[metric].unit,
        "source": source,
    }
