"""Canonical NHS waiting-time metrics, the tidy-row schema, and comparability caveats.

This module is the harmonisation contract that every nation source module targets.
Because health is devolved, the *definition* of each metric differs between the four
nations (different clock rules, scope, and reporting cadence). We therefore give each
metric a canonical id + unit, but keep ``source`` on every row and document the
caveats here so downstream charts/summaries can be honest about comparability.
"""

from __future__ import annotations

from typing import Any, NamedTuple

# Tidy long-format row schema returned by every source module.
ROW_FIELDS: tuple[str, ...] = (
    "nation",       # full name, e.g. "England"
    "nation_code",  # ENG / SCO / WAL / NIR
    "period",       # human label, e.g. "2024-03" (monthly) or "2024-Q1" (quarterly)
    "date",         # ISO date for the period (period end or representative day)
    "metric",       # canonical metric id (see METRICS)
    "value",        # float
    "unit",         # unit label
    "source",       # source attribution string
)


class Metric(NamedTuple):
    id: str
    label: str
    unit: str
    family: str  # rtt | ae | cancer | diagnostics
    higher_is_better: bool
    description: str


METRICS: dict[str, Metric] = {
    "rtt_waiting_list_total": Metric(
        "rtt_waiting_list_total",
        "Elective waiting list (pathways / ongoing waits)",
        "pathways / waits",
        "rtt",
        higher_is_better=False,
        description=(
            "Recorded elective pathways / ongoing waits, not unique people. "
            "Scotland sums outpatient and inpatient/day-case waits; NI covers "
            "first outpatient appointments only, not a complete RTT pathway."
        ),
    ),
    "rtt_waiting_list_per_1000": Metric(
        "rtt_waiting_list_per_1000",
        "Elective pathways / waits per 1,000 residents",
        "waits per 1,000 residents",
        "rtt",
        higher_is_better=False,
        description=(
            "Recorded elective pathways / ongoing waits per 1,000 residents, "
            "using published mid-year population estimates. This is not the "
            "number or proportion of unique residents waiting."
        ),
    ),
    "rtt_median_wait_weeks": Metric(
        "rtt_median_wait_weeks",
        "RTT median wait",
        "weeks",
        "rtt",
        higher_is_better=False,
        description="Median waiting time of patients still waiting to start treatment.",
    ),
    "ae_4hr_pct": Metric(
        "ae_4hr_pct",
        "A&E admitted, transferred or discharged within 4 hours",
        "percent",
        "ae",
        higher_is_better=True,
        description=(
            "Share of A&E attendances admitted, transferred or discharged within "
            "4 hours (target 95%)."
        ),
    ),
    "cancer_62day_pct": Metric(
        "cancer_62day_pct",
        "Cancer treated within 62 days",
        "percent",
        "cancer",
        higher_is_better=True,
        description=(
            "Share of patients starting first cancer treatment within 62 days of "
            "an urgent referral (standard 85%)."
        ),
    ),
    "diagnostics_6week_breach_pct": Metric(
        "diagnostics_6week_breach_pct",
        "Diagnostics: six-week threshold",
        "percent",
        "diagnostics",
        higher_is_better=False,
        description=(
            "Share of patients on the diagnostic-test waiting list who have been "
            "waiting 6 weeks or more (breach of the 6-week standard)."
        ),
    ),
    "diagnostics_8week_breach_pct": Metric(
        "diagnostics_8week_breach_pct",
        "Wales diagnostics: waiting over 8 weeks",
        "percent",
        "diagnostics",
        higher_is_better=False,
        description="Share of Welsh diagnostic pathways waiting over 8 weeks.",
    ),
}

# Per-nation, per-metric definitional caveats. Keep short; surfaced in the README
# and the trend summary so comparisons stay honest.
CAVEATS: dict[str, str] = {
    "rtt_waiting_list_total": (
        "England/Wales report RTT 'incomplete pathways'; Scotland reports 'ongoing "
        "waits' by stage of treatment; NI reports outpatient/inpatient/day-case "
        "waits separately (only outpatient waits are used here). These count waits, "
        "not unique people, and are not directly comparable across nations. NI's "
        "encompass rollout from November 2023 introduces a break: the Department "
        "says encompass and legacy figures are not directly comparable."
    ),
    "rtt_waiting_list_per_1000": (
        "Derived: RTT waiting list \u00f7 real ONS mid-year population estimate "
        "\u00d7 1,000. Population comes from ONS/NRS/NISRA via Nomis; only years "
        "with a published estimate are shown (no projection/extrapolation). "
        "Not the proportion of residents waiting: people can have multiple waits. "
        "Inherits the per-nation RTT definitional differences."
    ),
    "rtt_median_wait_weeks": (
        "England is estimated from weekly count bands (midpoint of the median "
        "band); Wales reports its median. Scotland's stage medians cannot be "
        "combined into a pooled median and are not included."
    ),
    "ae_4hr_pct": (
        "A&E 4-hour scope differs (all types vs major/Type-1 only) and reporting "
        "cadence varies (weekly/monthly) between nations."
    ),
    "cancer_62day_pct": (
        "62-day cancer pathway definitions and standards were revised at different "
        "times per nation; watch for series breaks."
    ),
    "diagnostics_6week_breach_pct": (
        "Diagnostic test lists (DM01 in England) cover different test sets per "
        "nation. NI's current target is 9 weeks, not the 6-week threshold shown "
        "here; its encompass rollout from November 2023 breaks comparability "
        "with legacy figures. Welsh six-week values use detailed bands available from August "
        "2024 only; the historical over-eight-week series is a separate metric, "
        "not a substitute or a continuation of this series."
    ),
    "diagnostics_8week_breach_pct": (
        "Wales's diagnostic target is 8 weeks. This series must not be compared "
        "as if it used the six-week threshold of the other nations."
    ),
}


def make_row(
    nation: str,
    nation_code: str,
    period: str,
    date: str,
    metric: str,
    value: float,
    source: str,
) -> dict[str, Any]:
    """Build a validated tidy row, deriving the unit from the metric id."""
    if metric not in METRICS:
        raise KeyError(f"unknown metric id: {metric!r}")
    return {
        "nation": nation,
        "nation_code": nation_code,
        "period": period,
        "date": date,
        "metric": metric,
        "value": float(value),
        "unit": METRICS[metric].unit,
        "source": source,
    }
