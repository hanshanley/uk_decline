"""Plot the historical tuition series (real, constant 2022 USD), 1963/71 -> 2022.

Reads ``data/processed/tuition_history.csv`` (built by build_history.py) and writes to
``outputs/`` in the shared Substack style. Every value is inflation-adjusted (constant
2022 USD) and traceable to a primary source (see the source note on the figure).

Usage:
    python plot_history.py
"""

from __future__ import annotations

import csv
import os

import matplotlib.pyplot as plt

from tuition import config, theme

# region key -> (label, colour, matplotlib draw style)
SERIES = {
    config.US: ("US — public 4-year, in-state (NCES)", theme.GOLD, "line"),
    config.UK: ("UK — England fee cap (statutory)", theme.ACCENT, "step"),
    config.EU: ("Germany — public (representative EU)", theme.BLUE, "step"),
}
SOURCE_NOTE = (
    "Real 2022 USD (inflation-adjusted). Sources: US — NCES Digest 2023 Table 330.10 "
    "(constant 2022-23 $, BLS CPI); UK — England statutory fee caps (legislation.gov.uk), "
    "deflated via World Bank CPI + 2022 FX; Germany — Eurydice / HE fee history."
)


def load_history() -> dict[str, list[tuple[int, float]]]:
    by_region: dict[str, list[tuple[int, float]]] = {}
    with open(config.HISTORY_OUT_CSV, newline="") as fh:
        for r in csv.DictReader(fh):
            by_region.setdefault(r["region"], []).append((int(r["year"]), float(r["real_2022_usd"])))
    for region in by_region:
        by_region[region].sort()
    return by_region


def plot(out_path: str) -> None:
    theme.apply()
    data = load_history()

    fig, ax = plt.subplots(figsize=(12, 7))
    for region, (label, color, style) in SERIES.items():
        pts = data.get(region)
        if not pts:
            continue
        xs = [y for y, _ in pts]
        ys = [v for _, v in pts]
        if style == "step":
            ax.step(xs, ys, where="post", color=color, linewidth=2.4, label=label)
            ax.plot(xs, ys, "o", color=color, markersize=5, markeredgecolor=theme.BG, markeredgewidth=0.8)
        else:
            ax.plot(xs, ys, color=color, linewidth=2.4, marker="o", markersize=4,
                    markeredgecolor=theme.BG, markeredgewidth=0.8, label=label)

    ax.set_ylabel("Annual domestic tuition (constant 2022 USD)")
    ax.set_xlabel("Year")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title(
        "The rise of UK tuition, 1971\u20132022 (real 2022 dollars)\n"
        "From free to more expensive than US public college",
        fontweight="bold", pad=14,
    )
    ax.grid(axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.margins(x=0.02)
    ax.legend(loc="upper left", frameon=False)

    theme.source_note(fig, SOURCE_NOTE)
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.12)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def main() -> None:
    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)
    plot(os.path.join(config.OUTPUTS_DIR, "tuition_history_real_usd.png"))


if __name__ == "__main__":
    main()
