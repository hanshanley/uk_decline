"""Like-for-like UK/US GDP comparisons and independent annual conversion checks."""

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

from vizstyle import ACCENT, BLUE, GREEN, MUTED, TEXT, house_style, save_chart, with_year_gaps

NOMINAL = "gdp_per_capita_nominal_usd"
CURRENT_PPP = "gdp_per_capita_ppp_current"
CONSTANT_PPP = "gdp_per_capita_ppp_constant"
REAL = "gdp_per_capita_constant_usd"
LOCAL = "gdp_per_capita_current_lcu"
FX = "market_exchange_rate"
PPP = "ppp_conversion_factor"


def validate_conversions(frame: pd.DataFrame) -> None:
    """Reconcile independently published GDP, annual FX and PPP observations."""
    required = ["iso3", "year", NOMINAL, CURRENT_PPP, CONSTANT_PPP, REAL, LOCAL, FX, PPP]
    if missing := set(required) - set(frame.columns):
        raise ValueError(f"Missing GDP comparison inputs: {sorted(missing)}")
    selected = frame.loc[frame["iso3"].isin(["GBR", "USA"]), required]
    if set(selected["iso3"]) != {"GBR", "USA"} or selected.duplicated(["iso3", "year"]).any():
        raise ValueError("GDP comparison requires unique UK and US country-year observations")
    for iso3, part in selected.groupby("iso3"):
        for metric in required[2:]:
            values = part[metric].dropna()
            if values.empty or not np.isfinite(values).all() or (values <= 0).any():
                raise ValueError(f"Invalid or missing GDP input: {iso3}/{metric}")
        for converted, factor in ((NOMINAL, FX), (CURRENT_PPP, PPP)):
            available = part.dropna(subset=[converted])
            if available[[LOCAL, factor]].isna().any().any():
                raise ValueError(f"Missing same-year conversion inputs for {iso3}/{converted}")
            error = (available[LOCAL] / available[factor] / available[converted] - 1).abs()
            if (error > .005).any():
                years = available.loc[error > .005, "year"].tolist()
                raise ValueError(f"GDP conversion mismatch: {iso3}/{converted} in {years}")
        volumes = part.dropna(subset=[CONSTANT_PPP])
        if volumes[REAL].isna().any():
            raise ValueError(f"Missing independent national-accounts volumes for {iso3}")
        # Fixed conversion factors cancel from each country's real growth rates.
        scale = volumes[CONSTANT_PPP] / volumes[REAL]
        if ((scale / scale.iloc[0] - 1).abs() > .002).any():
            raise ValueError(f"Real PPP and national-accounts growth disagree for {iso3}")


def make_chart(frame: pd.DataFrame, out: Path) -> None:
    validate_conversions(frame)
    uk = frame.loc[frame["iso3"] == "GBR"].set_index("year").sort_index()
    us = frame.loc[frame["iso3"] == "USA"].set_index("year").sort_index()
    ratios = {
        metric: (100 * us[metric] / uk[metric]).dropna()
        for metric in (NOMINAL, CURRENT_PPP, CONSTANT_PPP)
    }
    shared = sorted(set.intersection(*(set(values.index) for values in ratios.values())))
    shared = [year for year in shared if year >= 1990]
    if not shared:
        raise ValueError("No common UK/US GDP observations from 1990")
    end = shared[-1]
    ratio_ceiling = max(180, max(values.loc[values.index >= 1990].max() for values in ratios.values()) * 1.15)
    house_style()
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    definitions = (
        (NOMINAL, "Nominal: annual market exchange rates", TEXT,
         "Current US dollars; includes GDP prices and currency changes"),
        (CURRENT_PPP, "PPP: each year's prices and parities", TEXT,
         "Current international dollars; not a pure real-growth measure"),
        (CONSTANT_PPP, "Real output: fixed 2021 PPP benchmark", TEXT,
         "Constant 2021 international dollars; benchmark-valued volumes"),
    )
    for ax, (metric, title, color, description) in zip(axes.flat, definitions):
        values = ratios[metric].loc[lambda s: (s.index >= 1990) & (s.index <= end)]
        annual = with_year_gaps(values)
        ax.plot(annual.index, annual.values, color=color, linewidth=2.4, label=title,
                marker="o", markevery=[len(annual) - 1], markersize=4)
        ax.axhline(100, color=ACCENT, linestyle="--", linewidth=.8)
        ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=40)
        ax.text(0, 1.015, f"{end}: {values.loc[end]:.1f}% of the UK "
                f"({abs(values.loc[end] - 100):.1f}% "
                f"{'higher' if values.loc[end] >= 100 else 'lower'})", transform=ax.transAxes,
                fontsize=11, color=color, va="bottom")
        ax.set_ylabel("US / UK GDP per person (%)", fontsize=10)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.set_xlabel("Year", fontsize=10)
        ax.text(0, -.30, description, transform=ax.transAxes, fontsize=9, color=MUTED)
        ax.set_ylim(bottom=0, top=ratio_ceiling)
    ax = axes[1, 1]
    dollars = (1 / uk[FX]).dropna().loc[lambda s: (s.index >= 1990) & (s.index <= end)]
    annual = with_year_gaps(dollars)
    ax.plot(annual.index, annual.values, color=TEXT, linewidth=2.4, label="Annual USD per GBP",
            marker="o", markevery=[len(annual) - 1], markersize=4)
    ax.set_title("Sterling: actual annual exchange rates", fontsize=13, fontweight="bold", loc="left", pad=40)
    ax.text(0, 1.015, f"{end}: £1 = ${dollars.loc[end]:.3f}",
            transform=ax.transAxes, fontsize=11, color=TEXT, va="bottom")
    ax.set_ylabel("US dollars per pound (annual average)", fontsize=10)
    ax.set_xlabel("Year", fontsize=10)
    ax.text(0, -.30, "Nominal dollars = current pounds ÷ that year's GBP per USD",
            transform=ax.transAxes, fontsize=9, color=MUTED)
    ax.set_ylim(bottom=0)
    for ax in axes.flat:
        ax.grid(axis="x", visible=False)
        ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:.0f}"))
    fig.suptitle("US and UK GDP per person: different measures, different answers",
                 x=.08, y=.99, ha="left", fontsize=20, fontweight="bold")
    fig.text(.08, .94, "Every GDP ratio is US / UK: 166% of the UK means 66% higher, not 166% higher.",
             fontsize=12, color=MUTED)
    note = (
        "Source: World Bank WDI, NY.GDP.PCAP.CD / PP.CD / PP.KD; PA.NUS.FCRF "
        "(period-average exchange rates), ICP 2021 PPP vintage. Same-year country observations only. "
        "Nominal and current-PPP conversions are independently reconciled with current local-currency GDP "
        "(NY.GDP.PCAP.CN) and PA.NUS.FCRF / PA.NUS.PPP. Real growth is checked against NY.GDP.PCAP.KD. "
        "PPP and real-volume series must not be converted again at market exchange rates. "
        "Recent source estimates are revisable; missing years are not interpolated. GDP is not household income."
    )
    fig.text(.08, .015, textwrap.fill(note, 175), fontsize=8, color=MUTED)
    fig.subplots_adjust(left=.08, right=.98, top=.83, bottom=.20, wspace=.25, hspace=1.05)
    save_chart(fig, out / "us_uk_gdp_measures.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
