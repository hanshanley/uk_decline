"""Understated small-multiple chart of sterling's bilateral exchange rates."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from vizstyle import ACCENT, BG, BLUE, MUTED, TEXT, house_style, source_note

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "outputs" / "sterling" / "sterling_exchange_rates.png"

PANELS = {
    "USD": ("US dollar", "$", 2),
    "EUR": ("Euro", "€", 2),
    "JPY": ("Japanese yen", "¥", 0),
    "CHF": ("Swiss franc", "CHF ", 2),
}


def _load(source) -> pd.DataFrame:
    return source.copy() if hasattr(source, "columns") else pd.read_csv(source)


def _format_value(currency: str, value: float) -> str:
    _label, prefix, decimals = PANELS[currency]
    return f"{prefix}{value:,.{decimals}f}"


def make_chart(source, output: Path | str = DEFAULT_OUTPUT) -> Path:
    """Render four uncluttered panels showing how much currency £1 buys."""
    frame = _load(source)
    house_style()

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(13.6, 9.2),
        sharex=True,
        gridspec_kw={"hspace": 0.58, "wspace": 0.18},
    )
    latest_year = int(frame["year"].max())
    latest_status = frame.loc[frame["year"] == latest_year, "period_status"].iloc[0]
    latest_months = int(frame.loc[frame["year"] == latest_year, "months"].iloc[0])
    latest_label = (
        f"{latest_year} YTD ({latest_months} months)"
        if latest_status == "year_to_date"
        else str(latest_year)
    )

    for ax, currency in zip(axes.flat, PANELS):
        sub = frame[frame["currency"] == currency].sort_values("year")
        first = sub.iloc[0]
        latest = sub.iloc[-1]
        change = (latest["value"] / first["value"] - 1) * 100

        ax.plot(
            sub["year"],
            sub["value"],
            color=BLUE,
            linewidth=2.8,
            solid_capstyle="round",
        )
        ax.scatter(
            [latest["year"]],
            [latest["value"]],
            s=36,
            color=ACCENT,
            edgecolor=BG,
            linewidth=0.8,
            zorder=5,
        )
        ax.set_title(
            PANELS[currency][0],
            loc="left",
            fontsize=14,
            fontweight="bold",
            color=TEXT,
            y=1.12,
            pad=0,
        )
        ax.text(
            0,
            1.025,
            (
                f"{_format_value(currency, first['value'])} in 2000  ·  "
                f"{_format_value(currency, latest['value'])} in {latest_label}  ·  "
                f"{change:+.0f}%"
            ),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9.4,
            color=MUTED,
        )
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.margins(x=0.015, y=0.18)
        ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])

    fig.suptitle(
        "How much foreign currency £1 buys",
        x=0.06,
        y=0.975,
        ha="left",
        fontsize=22,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.062,
        0.93,
        "Annual averages of monthly ECB reference rates, 2000 to the latest observation.",
        ha="left",
        fontsize=11.5,
        color=MUTED,
    )
    source_note(
        fig,
        "Source: European Central Bank euro foreign exchange reference rates, "
        f"monthly averages. Cross-rates derived from each currency's rate per euro.\n"
        f"The {latest_year} observation averages January–July and is not a full-year rate.",
        x=0.06,
        y=0.018,
    )
    fig.subplots_adjust(left=0.06, right=0.97, top=0.82, bottom=0.11)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight", pad_inches=0.15, facecolor=BG)
    plt.close(fig)
    return output
