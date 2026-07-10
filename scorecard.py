#!/usr/bin/env python3
"""Build the unified "UK decline scorecard" — an 8-panel small-multiples image that
pulls one signature series from each analysis (GDP, markets, NHS, tax, tuition, trust,
migration, ageing), UK-highlighted, each annotated with its start->latest change.

All series are read from the committed data/outputs CSVs (no re-fetch). Writes
outputs/uk_decline_scorecard.png.

Usage:  python scorecard.py
"""

from __future__ import annotations

import csv
import pathlib
import re

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.ticker import MaxNLocator

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"

# ── House style ──────────────────────────────────────────────────────────────
# Palette from the shared vizstyle house style; scorecard keeps its own minimal
# rcParams (it hides the left spine for the small-multiples look).
from vizstyle import BG, TEXT, MUTED, GRID, ACCENT, GREEN  # noqa: E402

WORSE, BETTER, NEUTRAL = ACCENT, GREEN, MUTED
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT, "font.family": "serif",
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "xtick.major.size": 0, "ytick.major.size": 0, "text.parse_math": False,
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


def tax_burden():
    r = _rows(DATA / "tax_revenue_to_gdp.csv")
    pts = {int(x["year"]): float(x["value"]) for x in r if x["iso3"] == "GBR" and x["metric"] == "tax_to_gdp_pct" and x.get("value")}
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


def net_migration():
    r = _rows(DATA / "processed" / "uk_migration_long.csv")
    pts = {}
    for x in r:
        if x["metric"] == "net_migration" and x.get("category") == "all" and x["source"].startswith("ONS") and x.get("value"):
            y = _year(x["period"])
            if y:
                pts[y] = float(x["value"])
    ys = sorted(pts)
    return ys, [pts[y] for y in ys]


def rail_delays():
    """Annual mean of London & South East CaSL (% of trains cancelled or significantly late)."""
    r = _rows(DATA / "rail_performance.csv")
    buckets: dict[int, list[float]] = {}
    for x in r:
        if (x["region"] == "London and South East" and x["metric"] == "casl_pct"
                and x.get("value")):
            buckets.setdefault(int(x["year"]), []).append(float(x["value"]))
    ys = sorted(buckets)
    return ys, [sum(buckets[y]) / len(buckets[y]) for y in ys]


def london_gdp_share():
    r = _rows(DATA / "london_gdp.csv")
    pts = {int(x["year"]): float(x["value"]) for x in r
           if x["region"] == "London" and x["metric"] == "share_of_uk_gdp_pct" and x.get("value")}
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


# title, loader, value formatter, good_direction (+1 up-is-good, -1 down-is-good, 0 neutral),
# source, start_override. Every panel is tracked from the same COMMON_START year so the
# scorecard reads as one holistic "UK since 2007" story; tuition is the one exception
# (sparse data — its nearest anchor point is 2006, the pre-£9k-cap baseline).
COMMON_START = 2007

PANELS = [
    ("GDP per capita vs the US", gdp_vs_us, lambda v: f"{v:.0f}%", +1,
     "World Bank WDI (CPI-deflated real US$)", None),
    ("Rail delays, London & SE", rail_delays, lambda v: f"{v:.1f}%", -1,
     "Office of Rail and Road (ORR), Table 3103 (CaSL)", None),
    ("NHS waiting list, England", nhs_england, lambda v: f"{v/1e6:.1f}M", -1,
     "NHS England", None),
    ("Tax burden (% of GDP)", tax_burden, lambda v: f"{v:.0f}%", -1,
     "OECD Revenue Statistics", None),
    ("University tuition (real)", tuition_real, lambda v: f"${v/1e3:.1f}k", -1,
     "Eurydice / NCES / UK fee cap (constant 2022 US$)", 2006),
    ("Trust in national government", trust_govt, lambda v: f"{v:.0f}%", +1,
     "OECD / Gallup World Poll via OWID", None),
    ("UK-listed companies", uk_listed_companies, lambda v: f"{v:,.0f}", +1,
     "WFE via World Bank WDI (to 2022); LSE factsheets (2023+)", None),
    ("London's share of UK GDP", london_gdp_share, lambda v: f"{v:.1f}%", -1,
     "ONS, Regional GDP (current prices)", None),
]


def _panel(ax, title, loader, fmt, good_dir, source, start_override):
    xs, ys = loader()
    start = start_override or COMMON_START
    pts = [(x, y) for x, y in zip(xs, ys) if x >= start]
    if not pts:
        ax.set_axis_off()
        return
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    change = ys[-1] - ys[0]
    worse = (good_dir == +1 and change < 0) or (good_dir == -1 and change > 0)
    color = NEUTRAL if good_dir == 0 else (WORSE if worse else BETTER)

    ax.plot(xs, ys, color=color, linewidth=2.6, solid_capstyle="round")
    ax.fill_between(xs, ys, min(ys), color=color, alpha=0.10)
    ax.plot([xs[-1]], [ys[-1]], "o", color=color, markersize=6,
            markeredgecolor="white", markeredgewidth=1.2, zorder=5)

    # Header: title (top-left), latest value (top-right), start->latest (just above plot).
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left", pad=26, color=TEXT)
    ax.annotate(fmt(ys[-1]), xy=(1, 1), xycoords="axes fraction", xytext=(0, 18),
                textcoords="offset points", fontsize=15, fontweight="bold", color=color,
                ha="right", va="bottom")
    ax.annotate(f"{fmt(ys[0])} in {xs[0]}  to  {fmt(ys[-1])} in {xs[-1]}",
                xy=(0, 1), xycoords="axes fraction", xytext=(0, 3), textcoords="offset points",
                fontsize=8.5, color=MUTED, ha="left", va="bottom")

    # Y-axis: a light left spine with ~3 labelled ticks so values are readable.
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(GRID)
    ax.spines["left"].set_linewidth(0.8)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=3))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt(v)))
    ax.tick_params(axis="y", labelsize=8, colors=MUTED, length=0, pad=2)
    ax.grid(axis="y", linestyle="-", linewidth=0.6, color=GRID, alpha=0.7)
    ax.set_axisbelow(True)

    ax.set_xticks([xs[0], xs[-1]])
    ax.set_xticklabels([str(xs[0]), str(xs[-1])], fontsize=9, color=MUTED)
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
    ax.text(0.0, -0.24, source, transform=ax.transAxes, fontsize=6.8, color=MUTED,
            style="italic", va="top")


def main() -> int:
    fig, axes = plt.subplots(2, 4, figsize=(17, 9))
    for ax, panel in zip(axes.flat, PANELS):
        _panel(ax, *panel)

    fig.suptitle("The UK since 2007",
                 fontsize=23, fontweight="bold", y=0.99)
    fig.text(0.5, 0.935,
             "Eight measures of Britain's slide, each tracked from 2007 \u2014 the eve of the "
             "financial crisis.",
             ha="center", fontsize=11.5, color=MUTED)
    fig.text(0.5, 0.015,
             "All series from official public sources (World Bank, OECD, ONS, NHS, ORR, "
             "Eurydice/NCES, Gallup). Real/monetary figures are inflation-adjusted. See per-analysis READMEs.",
             ha="center", fontsize=8.5, color=MUTED, style="italic")

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
