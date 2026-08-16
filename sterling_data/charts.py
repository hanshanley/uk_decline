"""Single chart of major-currency strength against sterling."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, GOLD, GREEN, MUTED, TEXT, house_style, source_note

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "outputs" / "sterling" / "sterling_currency_strength.png"

SERIES = {
    "USD": ("US dollar", ACCENT),
    "EUR": ("Euro", BLUE),
    "JPY": ("Japanese yen", GOLD),
    "CHF": ("Swiss franc", GREEN),
}


def _load(source) -> pd.DataFrame:
    return source.copy() if hasattr(source, "columns") else pd.read_csv(source)


def currency_strength_change(
    frame: pd.DataFrame, base_year: int = 2000
) -> pd.DataFrame:
    """Return each foreign currency's percentage change against sterling.

    Input values are foreign-currency units bought by £1. Inverting the ratio gives
    the pound value of one foreign-currency unit. Positive values therefore mean
    the foreign currency strengthened against sterling since ``base_year``.
    """
    result = frame.copy()
    bases = (
        result[result["year"] == base_year]
        .set_index("currency")["value"]
        .to_dict()
    )
    missing = set(SERIES) - set(bases)
    if missing:
        raise ValueError(f"missing {base_year} observations for {sorted(missing)}")
    result["change_pct"] = result.apply(
        lambda row: (float(bases[row["currency"]]) / float(row["value"]) - 1) * 100,
        axis=1,
    )
    return result


def make_chart(source, output: Path | str = DEFAULT_OUTPUT) -> Path:
    """Render all currencies as changes in value against the pound."""
    frame = _load(source)
    frame = frame[frame["period_status"] == "full_year"].copy()
    frame = currency_strength_change(frame)
    house_style()

    fig, ax = plt.subplots(figsize=(13.5, 7.6))
    latest_year = int(frame["year"].max())

    for currency, (label, color) in SERIES.items():
        sub = frame[frame["currency"] == currency].sort_values("year")
        last = sub.iloc[-1]
        ax.plot(
            sub["year"],
            sub["change_pct"],
            color=color,
            linewidth=2.8,
            solid_capstyle="round",
        )
        ax.scatter(
            [last["year"]],
            [last["change_pct"]],
            s=36,
            color=color,
            edgecolor=BG,
            linewidth=0.8,
            zorder=5,
        )
        ax.text(
            float(last["year"]) + 0.35,
            float(last["change_pct"]),
            f"{label}  {last['change_pct']:+.0f}%",
            color=color,
            fontsize=10.5,
            fontweight="bold",
            va="center",
            ha="left",
        )

    ax.axhline(0, color=TEXT, linewidth=0.9, alpha=0.5)
    ax.set_xlim(1999.7, latest_year + 3.3)
    ax.set_ylim(-30, 150)
    ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
    ax.set_yticks([-20, 0, 20, 40, 60, 80, 100, 120, 140])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    ax.set_ylabel("Change in value against the pound since 2000")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)

    fig.suptitle(
        "How major currencies have moved against the pound",
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
        "Cumulative change since 2000. Above zero means the foreign currency "
        "has strengthened against sterling.",
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
    fig.subplots_adjust(left=0.075, right=0.88, top=0.84, bottom=0.14)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight", pad_inches=0.15, facecolor=BG)
    plt.close(fig)
    return output
