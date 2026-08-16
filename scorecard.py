#!/usr/bin/env python3
"""Build the unified UK scorecard: eight high-signal economic and social indicators.

All series are read from generated data/output CSVs (no re-fetch). Writes
outputs/uk_decline_scorecard.png.

Usage:  python scorecard.py
"""

from __future__ import annotations

import csv
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
    DATA / "stock_market_size_wide.csv": ".venv/bin/python -m markets_data",
    DATA / "uk_listed_companies_lse.csv": ".venv/bin/python -m markets_data.lse_factsheets",
    DATA / "austerity_spending.csv": ".venv/bin/python -m austerity_data",
    DATA / "food_bank_calendar_year.csv": ".venv/bin/python -m foodbank_data",
    DATA / "crime_csew_long.csv": ".venv/bin/python -m crime_data",
}

# ── House style ──────────────────────────────────────────────────────────────
# Palette from the shared vizstyle house style; scorecard keeps its own minimal
# rcParams (it hides the left spine for the small-multiples look).
from vizstyle import BG, TEXT, MUTED, GRID, ACCENT, GREEN  # noqa: E402

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
    M = "gdp_per_capita_real_usd"
    uk = {int(x["year"]): float(x[M]) for x in r if x["country"] == "United Kingdom" and x.get(M)}
    us = {int(x["year"]): float(x[M]) for x in r if x["country"] == "United States" and x.get(M)}
    ys = sorted(set(uk) & set(us))
    return ys, [100 * uk[y] / us[y] for y in ys]


def nhs_england():
    r = _rows(OUT / "nhs" / "nhs_waiting_times.csv")
    pts = {}
    for x in r:
        if x["nation_code"] == "ENG" and x["metric"] == "rtt_waiting_list_total" and x.get("value"):
            y = _year(x["date"])
            if y:
                pts[y] = float(x["value"])  # keep last (latest month) per year
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def tuition_real():
    r = _rows(DATA / "processed" / "tuition_history.csv")
    pts = {int(x["year"]): float(x["real_2022_usd"]) for x in r if x["country"] == "United Kingdom" and x.get("real_2022_usd")}
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def trust_govt():
    r = _rows(DATA / "trust" / "trust_combined_long.csv")
    pts = {int(x["year"]): float(x["value"]) for x in r if x["iso3"] == "GBR" and x["metric"] == "trust_national_govt_pct" and x.get("value")}
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def uk_listed_companies():
    r = _rows(DATA / "stock_market_size_wide.csv")
    pts = {int(x["year"]): float(x["listed_domestic_companies"]) for x in r
           if x["region"] == "United Kingdom" and x.get("listed_domestic_companies")}
    # The World Bank/WFE "listed domestic companies" series ends at 2022; extend it with the
    # UK-domiciled count (Main Market + AIM) read straight from the LSE factsheets, which joins
    # the WB series to within <1% at the 2022 overlap (WB 1,606 vs LSE 1,619).
    lse_path = DATA / "uk_listed_companies_lse.csv"
    if lse_path.exists() and pts:
        wb_last = max(pts)
        for x in _rows(lse_path):
            if x["metric"] == "lse_companies_uk" and x.get("value"):
                y = int(x["year"])
                if y > wb_last:
                    pts[y] = float(x["value"])
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


def fraud_share():
    r = _rows(DATA / "crime_csew_long.csv")
    excl_name = "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE"
    incl_name = "ALL CSEW HEADLINE CRIME INCLUDING FRAUD AND COMPUTER MISUSE"
    excl = {
        int(x["year"]): float(x["value"])
        for x in r if x["offence_group"] == excl_name and x.get("value")
    }
    incl = {
        int(x["year"]): float(x["value"])
        for x in r if x["offence_group"] == incl_name and x.get("value")
    }
    ys = sorted(set(excl) & set(incl))
    return ys, [100 * (incl[y] - excl[y]) / incl[y] for y in ys]


# title, loader, value formatter, good_direction (+1 up-is-good, -1 down-is-good, 0 neutral),
# source, start year. Baselines vary because the official comparable series do.

PANELS = [
    ("GDP per capita vs the US", gdp_vs_us, lambda v: f"{v:.0f}%", +1,
     "World Bank WDI · real US dollars", 2007),
    ("UK-listed companies", uk_listed_companies, lambda v: f"{v:,.0f}", +1,
     "WFE / World Bank; LSE factsheets", 2007),
    ("NHS waiting list, England", nhs_england, lambda v: f"{v/1e6:.1f}M", -1,
     "NHS England", 2007),
    ("Culture & recreation spending", culture_spending, lambda v: f"£{v:.1f}bn", +1,
     "HM Treasury · real 2025–26 prices", 2007),
    ("University tuition (real)", tuition_real, lambda v: f"${v/1e3:.1f}k", -1,
     "Eurydice / NCES / UK fee cap (constant 2022 US$)", 2006),
    ("Trust in national government", trust_govt, lambda v: f"{v:.0f}%", +1,
     "OECD / Gallup World Poll via OWID", 2007),
    ("Emergency food parcels", food_bank_parcels, lambda v: f"{v/1e6:.1f}M", -1,
     "Trussell · calendar-year UK totals", 2015),
    ("Fraud share of headline crime", fraud_share, lambda v: f"{v:.0f}%", -1,
     "ONS Crime Survey for England & Wales", 2017),
]


def _panel(ax, title, loader, fmt, good_dir, source, start):
    xs, ys = loader()
    pts = [(x, y) for x, y in zip(xs, ys) if x >= start]
    if not pts:
        ax.set_axis_off()
        return
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    change = ys[-1] - ys[0]
    worse = (good_dir == +1 and change < 0) or (good_dir == -1 and change > 0)
    color = NEUTRAL if good_dir == 0 else (WORSE if worse else BETTER)

    ax.plot(xs, ys, color=color, linewidth=2.4, solid_capstyle="round")
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
    for ax, panel in zip(axes.flat, PANELS):
        _panel(ax, *panel)

    fig.suptitle("Britain's pressure points",
                 fontsize=22, fontweight="bold", y=0.99)
    fig.text(0.5, 0.935,
             "Eight high-signal indicators from the latest comparable official series.",
             ha="center", fontsize=11, color=MUTED)
    fig.text(0.5, 0.015,
             "Baselines vary with data availability. Monetary series are inflation-adjusted. "
             "Definitions and caveats are documented in each analysis README.",
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
