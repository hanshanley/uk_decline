#!/usr/bin/env python3
"""Build the unified UK scorecard: eight high-signal economic and social indicators.

All series are read from generated data/output CSVs (no re-fetch). Writes
outputs/uk_decline_scorecard.png.

Usage:  python scorecard.py
"""

from __future__ import annotations

import csv
from datetime import date
import pathlib
import re
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.ticker import MaxNLocator

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"

REQUIRED_INPUTS = {
    DATA / "europe_combined_wide.csv": ".venv/bin/python -m europe_data.fetch_data",
    OUT / "nhs" / "nhs_waiting_times.csv": ".venv/bin/python -m nhs_data",
    DATA / "processed" / "tuition_history.csv": ".venv/bin/python -m tuition.build_history",
    DATA / "trust" / "trust_combined_long.csv": ".venv/bin/python -m trust_data.fetch_trust",
    DATA / "uk_listed_companies_lse.csv": ".venv/bin/python -m markets_data.lse_factsheets",
    DATA / "austerity_spending.csv": ".venv/bin/python -m austerity_data",
    DATA / "food_bank_calendar_year.csv": ".venv/bin/python -m foodbank_data",
    DATA / "crime_csew_long.csv": ".venv/bin/python -m crime_data",
}

# ── House style ──────────────────────────────────────────────────────────────
# Palette from the shared vizstyle house style; scorecard keeps its own minimal
# rcParams (it hides the left spine for the small-multiples look).
from vizstyle import BG, TEXT, MUTED, GRID, ACCENT, GREEN  # noqa: E402
from nhs_data import metrics as nhs_metrics  # noqa: E402

WORSE, BETTER, NEUTRAL = ACCENT, GREEN, MUTED
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT, "font.family": "sans-serif",
    "font.sans-serif": ["Avenir Next", "Avenir", "Helvetica Neue", "Arial", "DejaVu Sans"],
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "xtick.major.size": 0, "ytick.major.size": 0, "text.parse_math": False,
    "grid.alpha": 0.35,
})
STROKE = [pe.withStroke(linewidth=3, foreground="white")]


def _rows(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def _year(s):
    m = re.search(r"(\d{4})", str(s))
    return int(m.group(1)) if m else None


# ── One loader per panel -> (xs, ys) sorted by x ─────────────────────────────
def gdp_vs_us():
    r = _rows(DATA / "europe_combined_wide.csv")
    M = "gdp_per_capita_ppp_constant"
    uk = {int(x["year"]): float(x[M]) for x in r if x["country"] == "United Kingdom" and x.get(M)}
    us = {int(x["year"]): float(x[M]) for x in r if x["country"] == "United States" and x.get(M)}
    ys = sorted(set(uk) & set(us))
    return ys, [100 * uk[y] / us[y] for y in ys]


def _nhs_observations():
    r = _rows(OUT / "nhs" / "nhs_waiting_times.csv")
    pts = {}
    for x in sorted(r, key=lambda x: x["date"]):
        if x["nation_code"] == "ENG" and x["metric"] == "rtt_waiting_list_total" and x.get("value"):
            y = _year(x["date"])
            if y:
                pts[y] = x  # keep last (latest month) per year
    return pts


def nhs_england():
    pts = _nhs_observations()
    ys = sorted(pts)
    return ys, [float(pts[y]["value"]) for y in ys]


def tuition_nominal():
    r = _rows(DATA / "processed" / "tuition_history.csv")
    pts = {int(x["year"]): float(x["nominal_local"]) for x in r
           if x["country"] == "United Kingdom" and x["currency"] == "GBP"
           and x.get("nominal_local") not in (None, "") and int(x["year"]) <= date.today().year}
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def trust_govt():
    r = _rows(DATA / "trust" / "trust_combined_long.csv")
    pts = {int(x["year"]): float(x["value"]) for x in r if x["iso3"] == "GBR" and x["metric"] == "trust_national_govt_pct" and x.get("value")}
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def uk_listed_companies():
    r = _rows(DATA / "uk_listed_companies_lse.csv")
    pts = {int(x["year"]): float(x["value"])
           for x in sorted(r, key=lambda x: x["date"])
           if x["region"] == "United Kingdom" and x["metric"] == "lse_companies_uk"
           and x.get("value")}
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def culture_spending():
    """Real recreation, culture and religion spending in 2025-26 GBP billions."""
    r = _rows(DATA / "austerity_spending.csv")
    pts = {
        int(x["year"]): float(x["value"])
        for x in r
        if x["metric"] == "functional_spending_real"
        and x["category"] == "recreation_culture"
        and x.get("value")
    }
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def food_bank_parcels():
    r = _rows(DATA / "food_bank_calendar_year.csv")
    pts = {int(x["year"]): float(x["total"]) for x in r if x.get("total")}
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def _crime_observations():
    r = _rows(DATA / "crime_csew_long.csv")
    name = "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE"
    pts = {
        int(x["year"]): x
        for x in sorted(r, key=lambda x: x["date"])
        if x["offence_group"] == name and x.get("value")
    }
    return pts


def crime_incidents():
    """CSEW incidents excluding fraud and computer misuse, converted from thousands."""
    pts = _crime_observations()
    ys = sorted(pts)
    return ys, [float(pts[y]["value"]) * 1_000 for y in ys]


# title, loader, value formatter, good_direction (+1 up-is-good, -1 down-is-good, 0 neutral),
# source, start year. Baselines vary because the official comparable series do.

PANELS = [
    ("Real GDP per head vs US", gdp_vs_us, lambda v: f"{v:.0f}%", +1,
     "World Bank WDI · volume ratio, 2021 PPP benchmark", 2007),
    ("UK companies on the LSE", uk_listed_companies, lambda v: f"{v:,.0f}", +1,
     "LSE · UK-classified companies, Main Market + AIM\n"
     "Includes investment companies; not the WDI definition", 2018),
    ("NHS waiting list, England", nhs_england, lambda v: f"{v/1e6:.1f}M", -1,
     "NHS England · treatment entries, not unique patients\n"
     "Scope breaks: 2013, 2024; endpoints not like-for-like",
     2007,
     tuple(int(date[:4]) for date, _ in nhs_metrics.series_breaks(
         "rtt_waiting_list_total", "ENG"))),
    ("Recreation, culture & religion", culture_spending, lambda v: f"£{v:.1f}bn", +1,
     "HM Treasury · financial years, inflation-adjusted", 2007),
    ("England tuition cap", tuition_nominal, lambda v: f"£{v:,.0f}", -1,
     "England statutory maximum · academic years, nominal GBP\n"
     "Not inflation-adjusted; not average UK tuition", 2006),
    ("Trust in national government", trust_govt, lambda v: f"{v:.0f}%", +1,
     "OECD / Gallup via OWID · 2–3-year pooled averages\n"
     "Years label the end of each survey period", 2007, (), 3),
    ("Emergency food parcels", food_bank_parcels, lambda v: f"{v/1e6:.1f}M", -1,
     "Trussell network · calendar-year parcels, not people\n"
     "Mixed 3-/7-day parcels from 2020", 2015),
    ("Crime incidents, England & Wales", crime_incidents, lambda v: f"{v/1e6:.1f}M", -1,
     "ONS CSEW · excludes fraud & computer misuse", 2007),
]


def _panel(ax, title, loader, fmt, good_dir, source, start, break_years=(),
           max_gap_years=1):
    xs, ys = loader()
    pts = [(x, y) for x, y in zip(xs, ys) if x >= start]
    if not pts:
        raise ValueError(f"{title}: no observations from {start} onward")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    breaks = [year for year in break_years if xs[0] < year <= xs[-1]]
    change = ys[-1] - ys[0]
    worse = (good_dir == +1 and change < 0) or (good_dir == -1 and change > 0)
    color = NEUTRAL if good_dir == 0 or breaks else (WORSE if worse else BETTER)

    boundaries = [0] + [
        i for i in range(1, len(xs))
        if xs[i] > xs[i - 1] + max_gap_years
        or any(xs[i - 1] < year <= xs[i] for year in breaks)
    ] + [len(xs)]
    for first, last in zip(boundaries, boundaries[1:]):
        ax.plot(xs[first:last], ys[first:last], color=color, linewidth=2.4,
                solid_capstyle="round", marker="o" if last - first == 1 else None,
                markersize=3)
    ax.plot([xs[-1]], [ys[-1]], "o", color=color, markersize=6,
            markeredgecolor="white", markeredgewidth=1.5, zorder=5)

    # Header: title (top-left), latest value (top-right), start->latest (just above plot).
    ax.set_title(title, fontsize=11.5, fontweight="bold", loc="left", pad=25, color=TEXT)
    ax.annotate(fmt(ys[-1]), xy=(1, 1), xycoords="axes fraction", xytext=(0, 18),
                textcoords="offset points", fontsize=14, fontweight="bold", color=color,
                ha="right", va="bottom")
    ax.annotate(f"{fmt(ys[0])} in {xs[0]}  to  {fmt(ys[-1])} in {xs[-1]}",
                xy=(0, 1), xycoords="axes fraction", xytext=(0, 3), textcoords="offset points",
                fontsize=8, color=MUTED, ha="left", va="bottom")

    # Y-axis: a light left spine with ~3 labelled ticks so values are readable.
    ax.yaxis.set_major_locator(MaxNLocator(nbins=3))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt(v)))
    ax.tick_params(axis="y", labelsize=7.5, colors=MUTED, length=0, pad=2)
    ax.grid(axis="y", linestyle="-", linewidth=0.55, color=GRID, alpha=0.55)
    ax.set_axisbelow(True)

    ax.set_xticks([xs[0], xs[-1]])
    ax.set_xticklabels([str(xs[0]), str(xs[-1])], fontsize=8.5, color=MUTED)
    # Give each panel at least a minimum span relative to its own magnitude, so a
    # genuinely small move (e.g. tax burden 33->34%, median age 39->41) is not
    # magnified to fill the panel and overstate the change.
    dr = max(ys) - min(ys)
    span = max(dr * 1.30, 0.22 * max(abs(min(ys)), abs(max(ys))), 1.0)
    extra = (span - dr) / 2.0
    lo, hi = min(ys) - extra, max(ys) + extra
    if min(ys) >= 0 and lo < 0:  # keep naturally non-negative series off a negative axis
        hi -= lo
        lo = 0.0
    ax.set_ylim(lo, hi)
    ax.margins(x=0.04)
    ax.text(0.0, -0.23, source, transform=ax.transAxes, fontsize=6.6, color=MUTED,
            va="top")


def main() -> int:
    missing = [(path, command) for path, command in REQUIRED_INPUTS.items() if not path.exists()]
    if missing:
        print("scorecard inputs are missing; generate them before plotting:", file=sys.stderr)
        for path, command in missing:
            try:
                display_path = path.relative_to(ROOT)
            except ValueError:
                display_path = path
            print(f"  {display_path}\n    {command}", file=sys.stderr)
        return 2

    fig, axes = plt.subplots(2, 4, figsize=(17, 9))
    try:
        for ax, panel in zip(axes.flat, PANELS):
            _panel(ax, *panel)
    except ValueError as error:
        plt.close(fig)
        print(f"scorecard input error: {error}", file=sys.stderr)
        return 2

    fig.suptitle("UK since 2007",
                 fontsize=22, fontweight="bold", y=0.99)
    fig.text(0.5, 0.935,
             "Eight source-backed indicators of economic and social change; "
             "baselines reflect data availability.",
             ha="center", fontsize=11, color=MUTED)
    fig.text(0.5, 0.015,
             "Baselines vary. GDP and spending are inflation-adjusted; tuition is nominal GBP. "
             "Lines break at missing observations or definition changes; see each analysis README.",
             ha="center", fontsize=8, color=MUTED)

    fig.tight_layout(rect=[0.01, 0.03, 0.99, 0.92])
    fig.subplots_adjust(hspace=0.55, wspace=0.28)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "uk_decline_scorecard.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
