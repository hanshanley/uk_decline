"""Separate debt-stock, monthly peer and daily UK borrowing-rate charts."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from ppp_data.figure import labelled_ends
from vizstyle import ACCENT, BG, BLUE, GOLD, GREEN, MUTED, TEXT, house_style
from . import sources

COLORS = {
    "United Kingdom": ACCENT, "United States": TEXT, "Germany": BLUE,
    "France": GOLD, "Italy": GREEN,
}


def make_charts(
    frame: pd.DataFrame, output: Path, *, daily: pd.DataFrame | None = None,
) -> list[Path]:
    frame = sources.validate(frame)
    if daily is not None:
        daily = sources.validate_daily(daily)
    house_style()
    output.mkdir(parents=True, exist_ok=True)
    written = []
    for metric, filename, title, subtitle, ylabel, source in (
        (
            sources.DEBT_METRIC, "uk_public_debt_pct_gdp.png", "UK public-sector net debt",
            "Excluding public-sector banks; monthly debt stock relative to GDP",
            "Public-sector net debt (% of GDP)",
            "Source: Office for National Statistics, Public sector finances, HF6X. "
            "Monthly snapshots, not annual averages. Net debt subtracts liquid financial assets; "
            "includes the Bank of England, but excludes public-sector banks. "
            "Not general-government gross debt; no forecasts added.",
        ),
        (
            sources.YIELD_METRIC, "government_borrowing_costs.png",
            "Long-term government borrowing rates",
            "10-year government-bond yields; monthly averages, not the interest bill on existing debt",
            "Nominal 10-year government-bond yield (% per year)",
            "Source: Organisation for Economic Co-operation and Development, Main Economic Indicators, "
            "via Federal Reserve Bank of St. Louis. National 10-year benchmark bond yields, monthly averages. "
            "Different currencies and inflation expectations: gaps are not pure credit-risk premiums. "
            "Market yields are not average rates paid on the outstanding debt stock.",
        ),
    ):
        data = frame[frame["metric"] == metric]
        latest = data["date"].max()
        fig, ax = plt.subplots(figsize=(13.5, 7.5))
        ends = []
        for country, color in COLORS.items():
            sub = data[data["country"] == country].sort_values("date")
            if sub.empty:
                continue
            monthly = sub.set_index("date")["value"]
            monthly = monthly.reindex(pd.date_range(monthly.index.min(), monthly.index.max(), freq="MS"))
            ax.plot(monthly.index, monthly.values, color=color,
                    linewidth=2.8 if country == "United Kingdom" else 1.6)
            last = sub.iloc[-1]
            ax.scatter([last["date"]], [last["value"]], color=color, s=25, zorder=3)
            precision = 1 if metric == sources.DEBT_METRIC else 2
            ends.append((
                float(last["value"]),
                f"{country} {last['value']:.{precision}f}%\n  {last['date']:%b %Y}", color,
            ))
        labelled_ends(
            ax, ends, min_gap=1.0 if metric == sources.DEBT_METRIC else 0.65,
            x=mdates.date2num(latest + pd.DateOffset(months=3)), fontsize=9.5,
        )
        ax.set_xlim(pd.Timestamp(sources.START), latest + pd.DateOffset(months=3))
        if metric == sources.DEBT_METRIC:
            ax.set_ylim(0, data["value"].max() * 1.12)
        else:
            ax.set_ylim(min(-0.5, data["value"].min() - 0.5), data["value"].max() + 0.7)
            ax.axhline(0, linewidth=0.7, color=MUTED)
        ax.set_xticks([
            pd.Timestamp(year=year, month=1, day=1)
            for year in range(2000, latest.year + 1, 5)
        ])
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
        ax.set_xlabel("Year")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", linewidth=0.5)
        ax.set_axisbelow(True)
        fig.suptitle(title, x=0.08, y=0.97, ha="left", fontsize=22, fontweight="bold")
        fig.text(0.08, 0.91, subtitle, fontsize=11, color=MUTED)
        fig.text(0.08, 0.02, textwrap.fill(source, width=155), va="bottom",
                 fontsize=8, color=MUTED, style="italic")
        fig.subplots_adjust(left=0.08, right=0.97, bottom=0.19, top=0.85)
        path = output / filename
        fig.savefig(path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)
        written.append(path)
    if daily is not None:
        data = daily[daily["date"] >= "2020-01-01"]
        latest = data.iloc[-1]
        fig, ax = plt.subplots(figsize=(13.5, 7.5))
        series = data.set_index("date")["value"]
        series = series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="B"))
        ax.plot(series.index, series.values, color=ACCENT, linewidth=2)
        ax.scatter([latest["date"]], [latest["value"]], color=ACCENT, s=35, zorder=3)
        ax.set_xlim(pd.Timestamp("2020-01-01"), latest["date"] + pd.Timedelta(days=14))
        ax.set_xticks([pd.Timestamp(year=year, month=1, day=1)
                      for year in range(2020, latest["date"].year + 1)])
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100))
        ax.set_xlabel("Year")
        ax.set_ylabel("Nominal 10-year gilt yield (% per year)")
        ax.grid(axis="y", linewidth=0.5)
        ax.set_axisbelow(True)
        fig.suptitle("UK borrowing rates: latest daily observations", x=0.08, y=0.97,
                     ha="left", fontsize=22, fontweight="bold")
        fig.text(0.08, 0.91,
                 f"10-year nominal par gilt yield; latest {latest['date']:%d %b %Y}: "
                 f"{latest['value']:.2f}%", fontsize=11, color=MUTED)
        source = (
            "Source: Bank of England, IUDMNPY. Daily fitted 10-year nominal par gilt yield; "
            "not Bank Rate or the average interest paid on existing debt. "
            "Shown separately from OECD monthly benchmark averages; series are not spliced. "
            "Non-trading days and missing observations are not filled."
        )
        fig.text(0.08, 0.02, textwrap.fill(source, width=155), va="bottom",
                 fontsize=8, color=MUTED, style="italic")
        fig.subplots_adjust(left=0.08, right=0.97, bottom=0.19, top=0.85)
        path = output / "uk_borrowing_costs_daily.png"
        fig.savefig(path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)
        written.append(path)
    return written
