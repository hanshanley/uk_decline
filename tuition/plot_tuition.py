"""Generate tuition figures in the shared Substack style.

Reads ``data/processed/tuition_by_country.csv`` (primary per-country rows) and writes:
  1. tuition_region_comparison.png — average & median annual domestic tuition (USD) for
     UK vs EU-27 vs US.
  2. tuition_by_country.png — per-country annual domestic tuition (USD), ranked, colored
     by region, showing the UK as an outlier against the EU-27.

Usage:
    python plot_tuition.py            # nominal USD (default)
    python plot_tuition.py --real     # constant 2022 USD (CPI-adjusted)
"""

from __future__ import annotations

import argparse
import os

import matplotlib.pyplot as plt

from tuition import config, theme
from tuition.dataset import load_primary
from tuition.stats import aggregate_by_region

REGION_LABELS = config.REGION_LABELS
REGION_COLOR = {config.UK: theme.ACCENT, config.EU: theme.BLUE, config.US: theme.GOLD}
SOURCE_NOTE = (
    "Sources: Eurydice National Student Fee 2023/24 (EU-27); College Board Trends in "
    "College Pricing 2024 (US, in-state public); UK fee cap. FX & CPI: World Bank."
)


def _money(v: float) -> str:
    return f"${v:,.0f}"


def _finalize(fig, out_path: str, bottom: float) -> None:
    """Common figure tail: source note, layout, and high-DPI save (shared style)."""
    theme.source_note(fig, SOURCE_NOTE)
    plt.tight_layout()
    plt.subplots_adjust(bottom=bottom)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


DEGREE_YEARS = {config.UK: 3, config.US: 4, config.EU: 3}  # typical bachelor's length by region


def plot_region_comparison(rows: list[dict], value_key: str, unit: str, out_path: str) -> None:
    agg = aggregate_by_region(rows, value_key)
    # Typical (median) annual fee per region; UK and US are ~single values so mean≈median,
    # and the EU median (~free) is the honest "typical" student experience.
    order = [r for r in (config.EU, config.US, config.UK) if r in agg]  # low -> high (barh)
    labels = [REGION_LABELS[r] for r in order]
    vals = [agg[r]["median_annual"] for r in order]
    means = [agg[r]["mean_annual"] for r in order]
    colors = [(theme.ACCENT if r == config.UK else theme.TEXT if r == config.US else theme.GREEN)
              for r in order]

    fig, ax = plt.subplots(figsize=(11, 5.4))
    ypos = list(range(len(order)))
    ax.barh(ypos, vals, height=0.62, color=colors, zorder=3)

    for i, r in enumerate(order):
        v = vals[i]
        if v and v > 0:
            yrs = DEGREE_YEARS.get(r, 3)
            ax.annotate(f"{_money(v)}/yr", (v, i), ha="left", va="center", fontsize=12,
                        fontweight="bold", color=colors[i], xytext=(6, 0),
                        textcoords="offset points")
            ax.annotate(f"\u2248 {_money(v*yrs)} over a typical {yrs}-year degree", (v, i),
                        ha="left", va="center", fontsize=8.5, color=theme.MUTED, xytext=(6, -14),
                        textcoords="offset points")
        else:
            ax.annotate(f"most EU countries: free  (EU-27 average {_money(means[i])}/yr)",
                        (0, i), ha="left", va="center", fontsize=10, color=theme.GREEN,
                        fontweight="bold", xytext=(6, 0), textcoords="offset points")

    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=12)
    ax.set_xlabel(f"Annual tuition & fees ({unit})")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_xlim(0, max(vals) * 1.4)
    ax.set_title("The UK now charges US-level university tuition \u2014 while the rest of the EU is free\n"
                 "public universities, domestic / in-state students",
                 fontweight="bold", pad=14)
    ax.grid(axis="x", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    _finalize(fig, out_path, bottom=0.16)


def plot_by_country(rows: list[dict], value_key: str, unit: str, out_path: str) -> None:
    data = [(r["country"], r[value_key], r["region"]) for r in rows if r[value_key] is not None]
    data.sort(key=lambda t: t[1])  # ascending -> highest at top of horizontal bars

    fig, ax = plt.subplots(figsize=(11, 9))
    y = range(len(data))
    colors = [REGION_COLOR[region] for _, _, region in data]
    ax.barh(list(y), [v for _, v, _ in data], color=colors, edgecolor=theme.BG, linewidth=0.5)

    ax.set_yticks(list(y))
    ax.set_yticklabels([name for name, _, _ in data], fontsize=9)
    ax.set_xlabel(f"Annual domestic tuition ({unit})")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title("Annual domestic bachelor's tuition by country\nUK stands out against the EU-27",
                 fontweight="bold", pad=14)
    ax.grid(axis="x", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.margins(y=0.01)

    for i, (_, v, _region) in enumerate(data):
        if v > 0:
            ax.annotate(_money(v), (v, i), ha="left", va="center", fontsize=8,
                        color=theme.TEXT, xytext=(3, 0), textcoords="offset points")

    handles = [plt.Rectangle((0, 0), 1, 1, color=REGION_COLOR[r]) for r in (config.UK, config.EU, config.US)]
    ax.legend(handles, [REGION_LABELS[r] for r in (config.UK, config.EU, config.US)],
              loc="lower right", frameon=False)
    _finalize(fig, out_path, bottom=0.08)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--real", action="store_true",
                    help="use constant 2022 USD (CPI-adjusted) instead of nominal market-FX USD")
    args = ap.parse_args()

    theme.apply()
    value_key = "annual_tuition_usd_real2022" if args.real else "annual_tuition_usd"
    unit = "constant 2022 USD" if args.real else "USD"
    suffix = "_real" if args.real else ""

    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)
    rows = load_primary([value_key])

    plot_region_comparison(
        rows, value_key, unit,
        os.path.join(config.OUTPUTS_DIR, f"tuition_region_comparison{suffix}.png"),
    )
    plot_by_country(
        rows, value_key, unit,
        os.path.join(config.OUTPUTS_DIR, f"tuition_by_country{suffix}.png"),
    )


if __name__ == "__main__":
    main()
