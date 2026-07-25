"""Tuition converted at PPP, and tuition measured against income.

The ``tuition`` package converts fees at **market exchange rates** and deflates by US CPI,
which answers "how does a UK degree compare with a US one, in dollars?". This module asks
the domestic-burden question instead: **how much of a British household's own purchasing
power does a UK degree consume, compared with an American one?**

Two figures come out of it:

``ppp_tuition_history``
    The same fee series converted at the PPP conversion factor instead of the market rate,
    then deflated by US CPI to constant base-year international dollars — the exact PPP
    analogue of :func:`tuition.build_history.real_base_usd`. Both the PPP and the market-FX
    line are drawn, because the difference between them is the point.

``tuition_share_of_gdp_per_capita``
    Annual fees as a percentage of GDP per capita. This is unit-free: the currency cancels,
    so it is identical whether you compute it at market rates or at PPP, and it is immune
    both to the exchange rate and to the choice of PPP basket. It is the most robust
    affordability comparison available, and the module checks that the two routes to it
    really do agree.

Nothing in ``tuition/`` is modified; this reads its published output.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import NamedTuple

import matplotlib.ticker as mtick

from europe_data.worldbank import us_cpi
from tuition import config as tuition_config
from vizstyle import ACCENT, BLUE, GOLD, MUTED, TEXT, house_style, save_fig, source_note

from . import series
from .charts import NOTE_WRAP, _labelled_ends, _note, _subtitle, _tidy
from .paths import CHART_DIR, TUITION_HISTORY_CSV

# The base year the tuition package deflates to; imported rather than repeated so the PPP
# twin can never drift onto a different base from the figure it is paired with.
BASE_YEAR = tuition_config.REAL_BASE_YEAR

# Where the two routes to "tuition as a share of GDP per capita" are allowed to differ.
# They are algebraically identical, so any gap is floating-point noise.
SHARE_TOLERANCE = 1e-9


class TuitionPoint(NamedTuple):
    country: str
    iso3: str
    region: str
    year: int
    nominal_local: float
    currency: str
    real_base_usd: float        # market exchange rates (as published by ``tuition``)
    real_base_intl: float       # purchasing power parity
    share_of_gdp_pc_pct: float  # unit-free: currency cancels


def load_history(path: Path | str = TUITION_HISTORY_CSV) -> list[dict]:
    """Read the tuition history published by ``tuition.build_history``."""
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def build(rows: list[dict], history: list[dict] | None = None,
          cpi: dict[int, float] | None = None) -> list[TuitionPoint]:
    """Re-express each fee at PPP and as a share of GDP per capita.

    ``rows`` are the tidy PPP rows; ``history`` defaults to the published tuition history.
    A fee year is skipped entirely when the PPP conversion factor or GDP per capita is
    unavailable for it — the World Bank's PPP series begins in 1990, and nothing is
    extrapolated backwards to fill the gap.
    """
    history = history if history is not None else load_history()
    values = series.index(rows)
    years = [int(r["year"]) for r in history]
    cpi = cpi if cpi is not None else us_cpi(min(years), max(max(years), BASE_YEAR))
    cpi_base = cpi.get(BASE_YEAR)
    if not cpi_base:
        raise RuntimeError(f"no US CPI for the {BASE_YEAR} base year; cannot deflate")

    out: list[TuitionPoint] = []
    for row in history:
        iso3, year = row["iso3"], int(row["year"])
        nominal = float(row["nominal_local"])
        cpi_year = cpi.get(year)
        ppp_factor = values.get(("ppp_conversion_factor", iso3, year))
        gdp_ppp = values.get(("gdp_per_capita_ppp_current", iso3, year))
        gdp_usd = values.get(("gdp_per_capita_nominal_usd", iso3, year))
        fx = values.get(("market_exchange_rate", iso3, year))
        if not (cpi_year and ppp_factor and gdp_ppp and gdp_usd and fx):
            continue

        tuition_intl = nominal / ppp_factor          # current international $
        tuition_usd = nominal / fx                   # current US$
        # Identical by construction (the local-currency GDP cancels); computing both is a
        # free consistency check on the conversion factors, asserted below.
        share_ppp = tuition_intl / gdp_ppp
        share_fx = tuition_usd / gdp_usd
        if abs(share_ppp - share_fx) > SHARE_TOLERANCE * max(1.0, share_ppp):
            raise RuntimeError(
                f"tuition share of GDP per capita disagrees between the PPP and market-FX "
                f"routes for {iso3} {year}: {share_ppp:.9f} vs {share_fx:.9f}; the "
                "conversion factors and the GDP series are not mutually consistent"
            )

        out.append(TuitionPoint(
            country=row["country"], iso3=iso3, region=row["region"], year=year,
            nominal_local=nominal, currency=row["currency"],
            real_base_usd=float(row["real_2022_usd"]),
            real_base_intl=tuition_intl * (cpi_base / cpi_year),
            share_of_gdp_pc_pct=share_ppp * 100.0,
        ))
    out.sort(key=lambda p: (p.region, p.year))
    return out


def _by_country(points: list[TuitionPoint], country: str,
                attr: str) -> tuple[list[int], list[float]]:
    chosen = [p for p in points if p.country == country]
    return [p.year for p in chosen], [getattr(p, attr) for p in chosen]


def chart_tuition_ppp(points: list[TuitionPoint], out_dir: Path) -> Path | None:
    """UK and US tuition in constant base-year international dollars, PPP vs market FX."""
    import matplotlib.pyplot as plt

    house_style()
    uk_years, uk_ppp = _by_country(points, "United Kingdom", "real_base_intl")
    _, uk_fx = _by_country(points, "United Kingdom", "real_base_usd")
    us_years, us_ppp = _by_country(points, "United States", "real_base_intl")
    if not uk_years:
        return None

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.step(uk_years, uk_ppp, where="post", color=ACCENT, linewidth=2.8)
    ax.plot(uk_years, uk_ppp, "o", color=ACCENT, markersize=5,
            markeredgecolor="white", markeredgewidth=1.0)
    ax.step(uk_years, uk_fx, where="post", color=ACCENT, linewidth=1.8, linestyle=":")
    if us_years:
        ax.plot(us_years, us_ppp, color=GOLD, linewidth=2.0)

    labels = [(uk_ppp[-1], "UK, at PPP", ACCENT), (uk_fx[-1], "UK, at market rates", MUTED)]
    if us_years:
        labels.append((us_ppp[-1], "US (unchanged \u2014\nthe US is the numeraire)", GOLD))
    _labelled_ends(ax, labels, min_gap=max(uk_ppp) * 0.08,
                   x=max(uk_years[-1], us_years[-1] if us_years else uk_years[-1]),
                   fontsize=9.5)

    latest = uk_ppp[-1]
    ax.set_title("A UK degree costs even more measured against British prices",
                 fontweight="bold", pad=30)
    _subtitle(ax, f"Converted at PPP the England fee cap is worth ${latest:,.0f} a year in "
                  f"constant {BASE_YEAR} international dollars, against ${uk_fx[-1]:,.0f} "
                  "at market exchange rates")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    _tidy(ax, ylabel=f"Annual tuition (constant {BASE_YEAR} international $)")
    ax.set_ylim(bottom=0)
    ax.margins(x=0.10)

    source_note(fig, _note(
        "Sources: UK \u2014 England statutory fee caps (legislation.gov.uk / GOV.UK); "
        "US \u2014 NCES Digest 2023 Table 330.10. Converted at the World Bank PPP "
        "conversion factor (PA.NUS.PPP) for the fee year and deflated by US CPI "
        f"(FP.CPI.TOTL) to constant {BASE_YEAR} international dollars.",
        "The World Bank publishes PPP factors from 1990, so earlier fee years are omitted "
        "rather than extrapolated. A national fee cap is a single price and the PPP factor "
        "is an economy-wide basket, so read this alongside the share-of-income chart."))
    return save_fig(fig, out_dir / "ppp_tuition_history.png")


def chart_tuition_share(points: list[TuitionPoint], out_dir: Path) -> Path | None:
    """Annual tuition as a percentage of GDP per capita — free of any currency choice."""
    import matplotlib.pyplot as plt

    house_style()
    uk_years, uk = _by_country(points, "United Kingdom", "share_of_gdp_pc_pct")
    us_years, us = _by_country(points, "United States", "share_of_gdp_pc_pct")
    de_years, de = _by_country(points, "Germany", "share_of_gdp_pc_pct")
    if not uk_years:
        return None

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.step(uk_years, uk, where="post", color=ACCENT, linewidth=2.8)
    ax.plot(uk_years, uk, "o", color=ACCENT, markersize=5,
            markeredgecolor="white", markeredgewidth=1.0)
    if us_years:
        ax.plot(us_years, us, color=GOLD, linewidth=2.0)
    if de_years:
        ax.step(de_years, de, where="post", color=BLUE, linewidth=2.0)

    labels = [(uk[-1], "United Kingdom", ACCENT)]
    if us_years:
        labels.append((us[-1], "United States", GOLD))
    if de_years:
        labels.append((de[-1], "Germany (free)", BLUE))
    _labelled_ends(ax, labels, min_gap=max(uk) * 0.09,
                   x=max(uk_years[-1], us_years[-1] if us_years else uk_years[-1]),
                   fontsize=9.5)

    ax.set_title("Tuition as a share of GDP per capita", fontweight="bold", pad=30)
    _subtitle(ax, f"A year's fees now take {uk[-1]:.1f}% of UK GDP per head, against "
                  f"{us[-1]:.1f}% in the US \u2014 a comparison no exchange rate or PPP "
                  "basket can move")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _tidy(ax, ylabel="Annual tuition as % of GDP per capita")
    ax.set_ylim(bottom=0)
    ax.margins(x=0.10)

    source_note(fig, _note(
        "Sources: fees as above; GDP per capita from the World Bank (NY.GDP.PCAP.CD and "
        "NY.GDP.PCAP.PP.CD). Fees and income are taken in the same currency, so the units "
        "cancel and the figure is identical at market rates and at PPP.",
        "Germany charges no general tuition, so its line sits on zero throughout."))
    return save_fig(fig, out_dir / "tuition_share_of_gdp_per_capita.png")


def make_charts(rows: list[dict], out_dir: Path | str = CHART_DIR) -> list[Path]:
    """Build the tuition figures. Returns the paths written (empty if inputs are absent)."""
    out_dir = Path(out_dir)
    if not Path(TUITION_HISTORY_CSV).exists():
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    points = build(rows)
    written = [chart_tuition_ppp(points, out_dir), chart_tuition_share(points, out_dir)]
    return [p for p in written if p is not None]


__all__ = ["BASE_YEAR", "TuitionPoint", "build", "load_history", "make_charts",
           "chart_tuition_ppp", "chart_tuition_share", "NOTE_WRAP"]
