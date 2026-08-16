"""Single comparative chart of trade as a share of GDP."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GOLD, GREEN, MUTED, TEXT, house_style, source_note

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "outputs" / "trade" / "trade_share_gdp.png"

STYLE = {
    "GBR": ("United Kingdom", ACCENT, 3.2, 5),
    "DEU": ("Germany", GREEN, 2.0, 3),
    "FRA": ("France", BLUE, 2.0, 3),
    "JPN": ("Japan", GOLD, 2.0, 3),
    "USA": ("United States", MUTED, 1.8, 2),
}


def _load(source) -> pd.DataFrame:
    return source.copy() if hasattr(source, "columns") else pd.read_csv(source)


def make_chart(source, output: Path | str = DEFAULT_OUTPUT) -> Path:
    """Render UK trade openness against major economies."""
    frame = _load(source)
    house_style()

    fig, ax = plt.subplots(figsize=(13.5, 7.6))
    latest_year = int(frame["year"].max())

    for code, (label, color, width, zorder) in STYLE.items():
        sub = frame[frame["country_code"] == code].sort_values("year")
        if sub.empty:
            continue
        last = sub.iloc[-1]
        ax.plot(
            sub["year"],
            sub["value"],
            color=color,
            linewidth=width,
            alpha=1 if code == "GBR" else 0.9,
            solid_capstyle="round",
            zorder=zorder,
        )
        ax.scatter(
            [last["year"]],
            [last["value"]],
            s=36 if code == "GBR" else 25,
            color=color,
            edgecolor=BG,
            linewidth=0.8,
            zorder=zorder + 1,
        )
        ax.text(
            float(last["year"]) + 0.35,
            float(last["value"]),
            f"{label}  {last['value']:.0f}% ({int(last['year'])})",
            color=color,
            fontsize=10.2,
            fontweight="bold" if code == "GBR" else "normal",
            va="center",
            ha="left",
        )

    ax.set_xlim(1999.7, latest_year + 4.6)
    ax.set_ylim(15, 100)
    ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    ax.set_ylabel("Exports plus imports of goods and services (% of GDP)")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)

    fig.suptitle(
        "Trade as a share of the economy",
        x=0.065,
        y=0.965,
        ha="left",
        fontsize=22,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.067,
        0.91,
        "Exports plus imports of goods and services as a percentage of GDP.",
        ha="left",
        fontsize=11.5,
        color=MUTED,
    )
    source_note(
        fig,
        "Source: World Bank, World Development Indicators, Trade (% of GDP), "
        "NE.TRD.GNFS.ZS. Latest available year varies by country.",
        x=0.065,
        y=0.025,
    )
    fig.subplots_adjust(left=0.075, right=0.84, top=0.84, bottom=0.13)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight", pad_inches=0.15, facecolor=BG)
    plt.close(fig)
    return output

