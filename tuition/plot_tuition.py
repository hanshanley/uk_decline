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
import textwrap

import matplotlib.pyplot as plt

from tuition import config, theme
from tuition.dataset import load_primary
from tuition.stats import aggregate_by_region

REGION_LABELS = {**config.REGION_LABELS, config.UK: "England (fee cap)"}
REGION_COLOR = {config.UK: theme.ACCENT, config.EU: theme.BLUE, config.US: theme.GOLD}
SOURCE_NOTE = (
    "Sources: EU country compilation, Eurydice 2023/24 plus national fee sources "
    "(France, Ireland, Luxembourg, Netherlands 2026/27; Portugal 2025/26; Spain 2024/25); College Board Trends in "
    "College Pricing 2025 Table CP-1 (US 2025/26, in-state public); UK 2026/27 fee cap. "
    "Source years differ. FX may use a nearby published year (recorded in the CSV); "
    "Real values use same-year BLS CPI-U (2025: 11 months). Missing real values are omitted. "
    "EU fees mix caps, contributions and conditional free places, not national student averages."
)


def _money(v: float) -> str:
    return f"${v:,.0f}"


def _finalize(fig, out_path: str, bottom: float, missing_note: str = "") -> None:
    """Common figure tail: source note, layout, and high-DPI save (shared style)."""
    note = textwrap.fill(SOURCE_NOTE + missing_note, width=155)
    theme.source_note(fig, note)
    plt.tight_layout()
    plt.subplots_adjust(bottom=max(bottom, (10 * len(note.splitlines()) + 42)
                                   / (72 * fig.get_figheight())))
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


DEGREE_YEARS = {config.UK: 3, config.US: 4, config.EU: 3}  # typical bachelor's length by region


def _missing_note(rows: list[dict], value_key: str) -> str:
    missing = [
        f"{r['country']} ({r['year']})"
        for r in rows if r.get(value_key) is None
    ]
    return f" Not plotted: {', '.join(missing)} — conversion data unavailable." if missing else ""


def plot_region_comparison(rows: list[dict], value_key: str, unit: str, out_path: str) -> None:
    agg = aggregate_by_region(rows, value_key)
    # EU statistics weight countries equally, not students.
    order = [r for r in (config.EU, config.US, config.UK) if r in agg]  # low -> high (barh)
    region_year = {}
    for region in order:
        years = [
            int(row["year"])
            for row in rows
            if row["region"] == region and row.get("year") not in (None, "")
            and row.get(value_key) is not None
        ]
        region_year[region] = (
            str(min(years)) if min(years) == max(years)
            else f"{min(years)}–{max(years)}"
        ) if years else None
    labels = []
    for region in order:
        label = REGION_LABELS[region]
        if region == config.EU and agg[region]["n"] < len(config.EU27):
            label = f"EU sample ({agg[region]['n']}/{len(config.EU27)} countries)"
        if region_year[region] is not None:
            label += f" ({region_year[region]})"
        labels.append(label)
    vals = [agg[r]["median_annual"] for r in order]
    means = [agg[r]["mean_annual"] for r in order]
    colors = [REGION_COLOR[r] for r in order]

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
            ax.annotate(f"Median listed fee: $0  (country mean {_money(means[i])}/yr)",
                        (0, i), ha="left", va="center", fontsize=10, color=theme.GREEN,
                        fontweight="bold", xytext=(6, 0), textcoords="offset points")

    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=12)
    ax.set_xlabel(f"Annual tuition & fees ({unit})")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_xlim(0, max([*vals, *means, 1.0]) * 1.4)
    ax.set_title("Domestic tuition comparison — source years differ\n"
                 "public universities, domestic / in-state students",
                 fontweight="bold", pad=14)
    ax.grid(axis="x", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    _finalize(fig, out_path, bottom=0.16, missing_note=_missing_note(rows, value_key))


def plot_by_country(rows: list[dict], value_key: str, unit: str, out_path: str) -> None:
    data = [
        (REGION_LABELS[config.UK] if r["region"] == config.UK else r["country"],
         r[value_key], r["region"])
        for r in rows if r[value_key] is not None
    ]
    data.sort(key=lambda t: t[1])  # ascending -> highest at top of horizontal bars

    fig, ax = plt.subplots(figsize=(11, 9))
    y = range(len(data))
    colors = [REGION_COLOR[region] for _, _, region in data]
    ax.barh(list(y), [v for _, v, _ in data], color=colors, edgecolor=theme.BG, linewidth=0.5)

    ax.set_yticks(list(y))
    ax.set_yticklabels([name for name, _, _ in data], fontsize=9)
    ax.set_xlabel(f"Annual domestic tuition ({unit})")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    periods = {}
    for row in rows:
        if row[value_key] is not None:
            periods.setdefault(REGION_LABELS[row["region"]], set()).add(int(row["year"]))
    def academic(year):
        return f"{year}/{(year + 1) % 100:02d}"
    subtitle = " · ".join(
        f"{label}: {academic(min(years))}"
        + (f"–{academic(max(years))}" if min(years) != max(years) else "")
        for label, years in sorted(periods.items())
    )
    ax.set_title("Annual domestic bachelor's tuition — dated source comparison\n"
                 + subtitle,
                 fontweight="bold", pad=14)
    ax.grid(axis="x", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.margins(y=0.01)

    for i, (_, v, _region) in enumerate(data):
        if v > 0:
            ax.annotate(_money(v), (v, i), ha="left", va="center", fontsize=8,
                        color=theme.TEXT, xytext=(3, 0), textcoords="offset points")
        else:
            ax.plot(0, i, "o", color=theme.GREEN, markersize=4.5, zorder=4)
            ax.annotate("$0", (0, i), ha="left", va="center", fontsize=8,
                        color=theme.GREEN, fontweight="bold",
                        xytext=(7, 0), textcoords="offset points")

    handles = [plt.Rectangle((0, 0), 1, 1, color=REGION_COLOR[r]) for r in (config.UK, config.EU, config.US)]
    ax.legend(handles, [REGION_LABELS[r] for r in (config.UK, config.EU, config.US)],
              loc="lower right", frameon=False)
    _finalize(fig, out_path, bottom=0.08, missing_note=_missing_note(rows, value_key))


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
