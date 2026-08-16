"""Single indexed chart comparing sterling against major currencies."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GOLD, GREEN, MUTED, TEXT, house_style, source_note

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "outputs" / "sterling" / "sterling_exchange_rates_indexed.png"

SERIES = {
    "USD": ("US dollar", ACCENT),
    "EUR": ("Euro", BLUE),
    "JPY": ("Japanese yen", GOLD),
    "CHF": ("Swiss franc", GREEN),
}


def _load(source) -> pd.DataFrame:
    return source.copy() if hasattr(source, "columns") else pd.read_csv(source)


def index_to_year(frame: pd.DataFrame, base_year: int = 2000) -> pd.DataFrame:
    """Index each currency's exchange rate to ``base_year = 100``."""
    indexed = frame.copy()
    bases = (
        indexed[indexed["year"] == base_year]
        .set_index("currency")["value"]
        .to_dict()
    )
    missing = set(SERIES) - set(bases)
    if missing:
        raise ValueError(f"missing {base_year} observations for {sorted(missing)}")
    indexed["index"] = indexed.apply(
        lambda row: float(row["value"]) / float(bases[row["currency"]]) * 100,
        axis=1,
    )
    return indexed


def make_chart(source, output: Path | str = DEFAULT_OUTPUT) -> Path:
    """Render all currencies on one comparable 2000=100 scale."""
    frame = _load(source)
    frame = frame[frame["period_status"] == "full_year"].copy()
    frame = index_to_year(frame)
    house_style()

    fig, ax = plt.subplots(figsize=(13.5, 7.6))
    latest_year = int(frame["year"].max())

    for currency, (label, color) in SERIES.items():
        sub = frame[frame["currency"] == currency].sort_values("year")
        last = sub.iloc[-1]
        ax.plot(
            sub["year"],
            sub["index"],
            color=color,
            linewidth=2.8,
            solid_capstyle="round",
        )
        ax.scatter(
            [last["year"]],
            [last["index"]],
            s=36,
            color=color,
            edgecolor=BG,
            linewidth=0.8,
            zorder=5,
        )
        ax.text(
            float(last["year"]) + 0.35,
            float(last["index"]),
            f"{label}  {last['index']:.0f}",
            color=color,
            fontsize=10.5,
            fontweight="bold",
            va="center",
            ha="left",
        )

    ax.axhline(100, color=TEXT, linewidth=0.9, alpha=0.45)
    ax.text(2000.1, 102.5, "2000 = 100", color=MUTED, fontsize=9.5)
    ax.set_xlim(1999.7, latest_year + 3.1)
    ax.set_ylim(35, 145)
    ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
    ax.set_yticks([40, 60, 80, 100, 120, 140])
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f"))
    ax.set_ylabel("Foreign currency bought by £1 (index, 2000 = 100)")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)

    fig.suptitle(
        "The pound against major currencies",
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
        "Foreign currency bought by £1, indexed to 2000. Higher means a stronger pound.",
        ha="left",
        fontsize=11.5,
        color=MUTED,
    )
    source_note(
        fig,
        "Source: European Central Bank euro foreign exchange reference rates, "
        "monthly averages; pound cross-rates derived from each currency's euro rate.\n"
        f"Only complete calendar years are shown; the latest is {latest_year}.",
        x=0.065,
        y=0.02,
    )
    fig.subplots_adjust(left=0.075, right=0.89, top=0.84, bottom=0.14)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight", pad_inches=0.15, facecolor=BG)
    plt.close(fig)
    return output
