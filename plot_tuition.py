"""Generate tuition figures in the shared Substack style.

Reads ``data/processed/tuition_by_country.csv`` (primary per-country rows) and writes:
  1. tuition_region_comparison.png — average & median annual domestic tuition (USD) for
     UK vs EU-27 vs US.
  2. tuition_by_country.png — per-country annual domestic tuition (USD), ranked, colored
     by region, showing the UK as an outlier against the EU-27.

Usage:
    python plot_tuition.py            # nominal USD (default)
    python plot_tuition.py --ppp      # PPP-adjusted USD
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
    "College Pricing 2024 (US, in-state public); UK fee cap. FX/PPP: World Bank."
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


def plot_region_comparison(rows: list[dict], value_key: str, unit: str, out_path: str) -> None:
    agg = aggregate_by_region(rows, value_key)
    regions = [r for r in (config.UK, config.EU, config.US) if r in agg]
    labels = [REGION_LABELS[r] for r in regions]
    means = [agg[r]["mean_annual"] for r in regions]
    medians = [agg[r]["median_annual"] for r in regions]

    fig, ax = plt.subplots(figsize=(10, 6.5))
    x = range(len(regions))
    width = 0.38
    bars_mean = ax.bar([i - width / 2 for i in x], means, width, label="Average",
                       color=theme.BLUE, edgecolor=theme.BG, linewidth=0.6)
    bars_med = ax.bar([i + width / 2 for i in x], medians, width, label="Median",
                      color=theme.GOLD, edgecolor=theme.BG, linewidth=0.6)

    for b in bars_mean:
        ax.annotate(_money(b.get_height()), (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=9, color=theme.TEXT,
                    xytext=(0, 2), textcoords="offset points")
    # Label median bars only where they differ from the mean (single-country regions
    # have mean == median, so a second identical label would just overprint).
    for i, b in enumerate(bars_med):
        if abs((medians[i] or 0) - (means[i] or 0)) > 1:
            ax.annotate(_money(b.get_height()), (b.get_x() + b.get_width() / 2, b.get_height()),
                        ha="center", va="bottom", fontsize=9, color=theme.TEXT,
                        xytext=(0, 2), textcoords="offset points")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel(f"Annual domestic tuition ({unit})")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title("Cost of a bachelor's degree: UK vs EU-27 vs US\nannual domestic tuition (fees only)",
                 fontweight="bold", pad=14)
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    # Legend sits over the empty EU-27 column so it never overlaps the UK/US bars.
    ax.legend(loc="upper center", frameon=False)
    _finalize(fig, out_path, bottom=0.13)


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
    ap.add_argument("--ppp", action="store_true", help="use PPP-adjusted USD instead of nominal")
    args = ap.parse_args()

    theme.apply()
    value_key = "annual_tuition_usd_ppp" if args.ppp else "annual_tuition_usd"
    unit = "USD, PPP-adjusted" if args.ppp else "USD"
    suffix = "_ppp" if args.ppp else ""

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
