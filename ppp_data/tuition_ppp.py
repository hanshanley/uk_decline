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
from vizstyle import ACCENT, BLUE, GOLD, MUTED, save_fig, source_note, white_stroke

from . import series
from .figure import labelled_ends, note, subtitle, themed_plt, tidy
from .metrics import ICP_VINTAGE
from .paths import CHART_DIR, TUITION_HISTORY_CSV

# The base year the tuition package deflates to, and the name of the column it publishes in
# that base. Both are derived from `tuition.config` so the PPP twin can never drift onto a
# different base from the market-FX figure it is paired with — deriving the column name (not
# hard-coding `real_2022_usd`) is what makes that guarantee real rather than aspirational.
BASE_YEAR = tuition_config.REAL_BASE_YEAR
MARKET_FX_COLUMN = f"real_{BASE_YEAR}_usd"

# How far the two routes to "tuition as a share of GDP per capita" may differ. They are
# algebraically identical, so the only gap should come from the rounding in the World Bank's
# published series — in practice a few parts in 100,000. Anything larger means the fee year
# has been matched to the wrong conversion factor or GDP observation.
SHARE_TOLERANCE = 1e-3  # 0.1%


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
        rows = list(csv.DictReader(fh))
    if rows and MARKET_FX_COLUMN not in rows[0]:
        raise RuntimeError(
            f"{path} has no {MARKET_FX_COLUMN!r} column (found: {sorted(rows[0])}). "
            f"tuition.config.REAL_BASE_YEAR is {BASE_YEAR}; rebuild the tuition history "
            "with `python -m tuition.build_history` so both analyses share a base year."
        )
    return rows


def us_cpi_from_rows(rows: list[dict]) -> dict[int, float]:
    """Recover the US CPI deflator ratios already implied by the fetched rows.

    ``europe_data.worldbank.deflate_to_real_usd`` builds ``gdp_per_capita_real_usd`` as
    ``nominal x (CPI_base / CPI_year)``, so the ratio of the real to the nominal series is
    exactly ``CPI_base / CPI_year`` for that year. Returning a CPI index scaled so the base
    year is 100 reproduces what :func:`europe_data.worldbank.us_cpi` would return, up to a
    constant factor that cancels in every deflation.

    This lets ``--from-csv`` re-chart entirely offline: the CPI is already encoded in the
    CSV, so there is no need to go back to the network for it.
    """
    out: dict[int, float] = {}
    by_year: dict[int, dict[str, float]] = {}
    for row in rows:
        if row["metric"] in ("gdp_per_capita_real_usd", "gdp_per_capita_nominal_usd"):
            by_year.setdefault(row["year"], {})[row["metric"]] = row["value"]
    for year, pair in by_year.items():
        real = pair.get("gdp_per_capita_real_usd")
        nominal = pair.get("gdp_per_capita_nominal_usd")
        if real and nominal:
            # real/nominal == CPI_base/CPI_year, so CPI_year is proportional to its inverse.
            out[year] = 100.0 * nominal / real
    return out


def build(rows: list[dict], history: list[dict] | None = None,
          cpi: dict[int, float] | None = None) -> list[TuitionPoint]:
    """Re-express each fee at PPP and as a share of GDP per capita.

    ``rows`` are the tidy PPP rows; ``history`` defaults to the published tuition history.
    ``cpi`` defaults to the deflator implied by ``rows`` (see :func:`us_cpi_from_rows`), and
    falls back to a live World Bank fetch only if the rows do not carry it — so the
    documented offline path stays offline.

    A fee year is skipped entirely when the PPP conversion factor or GDP per capita is
    unavailable for it — the World Bank's PPP series begins in 1990, and nothing is
    extrapolated backwards to fill the gap.
    """
    history = history if history is not None else load_history()
    values = series.index(rows)
    years = [int(r["year"]) for r in history]
    if cpi is None:
        cpi = us_cpi_from_rows(rows)
        if BASE_YEAR not in cpi:  # the rows did not carry the deflator; go to the source
            cpi = us_cpi(min(years), max(max(years), BASE_YEAR))
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
        # Identical by construction (the local currency cancels), so computing both is a
        # free consistency check that the fee year lines up with the conversion factor and
        # the GDP observation. They are averaged because neither route is more authoritative
        # than the other; the check above bounds how far they may disagree first.
        share_ppp = tuition_intl / gdp_ppp
        share_fx = tuition_usd / gdp_usd
        if share_ppp and abs(share_ppp - share_fx) / share_ppp > SHARE_TOLERANCE:
            raise RuntimeError(
                f"tuition share of GDP per capita disagrees between the PPP and market-FX "
                f"routes for {iso3} {year}: {share_ppp:.8f} vs {share_fx:.8f}; the fee year "
                "is not aligned with the conversion factor and GDP observations"
            )

        out.append(TuitionPoint(
            country=row["country"], iso3=iso3, region=row["region"], year=year,
            nominal_local=nominal, currency=row["currency"],
            real_base_usd=float(row[MARKET_FX_COLUMN]),
            real_base_intl=tuition_intl * (cpi_base / cpi_year),
            share_of_gdp_pc_pct=(share_ppp + share_fx) / 2.0 * 100.0,
        ))
    out.sort(key=lambda p: (p.region, p.year))
    return out


def _by_country(points: list[TuitionPoint], country: str,
                attr: str) -> tuple[list[int], list[float]]:
    chosen = [p for p in points if p.country == country]
    return [p.year for p in chosen], [getattr(p, attr) for p in chosen]


def _share_subtitle(uk_years: list[int], uk: list[float],
                    us_years: list[int], us: list[float]) -> str:
    """The UK-vs-US sentence, quoted at the latest year both series actually cover.

    The two fee series end in different years — the England fee cap runs ahead of the NCES
    US series — so quoting each at its own last point would compare (say) 2024 with 2022
    while saying "now". On the one figure whose selling point is that it is immune to
    methodological choices, that would be the only sloppy comparison on it.
    """
    if not us_years:
        return (f"A year's fees took {uk[-1]:.1f}% of UK GDP per head in {uk_years[-1]}"
                " \u2014 a comparison no exchange rate or PPP basket can move")
    shared = sorted(set(uk_years) & set(us_years))
    tail = "\u2014 a comparison no exchange rate or PPP basket can move"
    if not shared:
        return (f"UK fees took {uk[-1]:.1f}% of GDP per head in {uk_years[-1]}; US fees "
                f"{us[-1]:.1f}% in {us_years[-1]} {tail}")
    year = shared[-1]
    uk_at = uk[uk_years.index(year)]
    us_at = us[us_years.index(year)]
    return (f"In {year} a year's fees took {uk_at:.1f}% of UK GDP per head, against "
            f"{us_at:.1f}% in the US {tail}")


def chart_tuition_ppp(points: list[TuitionPoint], out_dir: Path) -> Path | None:
    """UK and US tuition in constant base-year international dollars, PPP vs market FX."""
    plt = themed_plt()

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
        labels.append((us_ppp[-1], "United States\n(the numeraire, so unchanged)", GOLD))
    labelled_ends(ax, labels, min_gap=max(uk_ppp) * 0.10,
                  x=max(uk_years[-1], us_years[-1] if us_years else uk_years[-1]),
                  fontsize=9.5)

    latest = uk_ppp[-1]
    ax.set_title("A UK degree costs even more measured against British prices",
                 fontweight="bold", pad=30)
    subtitle(ax, f"Converted at PPP the England fee cap is worth ${latest:,.0f} a year in "
                 f"constant {BASE_YEAR} international dollars, against ${uk_fx[-1]:,.0f} "
                 "at market exchange rates")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    tidy(ax, ylabel=f"Annual tuition (constant {BASE_YEAR} international $)")
    ax.set_ylim(bottom=0)
    ax.margins(x=0.10)

    source_note(fig, note(
        "Sources: UK \u2014 England statutory fee caps (legislation.gov.uk / GOV.UK); US "
        "\u2014 NCES Digest 2023 Table 330.10. Converted at the World Bank PPP conversion "
        f"factor (PA.NUS.PPP, {ICP_VINTAGE} benchmark) for the fee year, then deflated by "
        f"US CPI to constant {BASE_YEAR} international dollars. PPP factors start in 1990, "
        "so earlier fee years are omitted rather than extrapolated."))
    return save_fig(fig, out_dir / "ppp_tuition_history.png", bottom=0.18)


def chart_tuition_share(points: list[TuitionPoint], out_dir: Path) -> Path | None:
    """Annual tuition as a percentage of GDP per capita — free of any currency choice."""
    plt = themed_plt()

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
        ax.step(de_years, de, where="post", color=BLUE, linewidth=2.4)
        # Germany sits flat on zero, so its label goes inline above the line rather than
        # at the right-hand end, where it would collide with the axis.
        ax.text(sum(de_years) / len(de_years), max(uk) * 0.03,
                "Germany \u2014 no general tuition", fontsize=9.5, fontweight="bold",
                color=BLUE, ha="center", va="bottom", path_effects=white_stroke())

    labels = [(uk[-1], "United Kingdom", ACCENT)]
    if us_years:
        labels.append((us[-1], "United States", GOLD))
    labelled_ends(ax, labels, min_gap=max(uk) * 0.09,
                  x=max(uk_years[-1], us_years[-1] if us_years else uk_years[-1]),
                  fontsize=9.5)

    ax.set_title("Tuition as a share of GDP per capita", fontweight="bold", pad=30)
    subtitle(ax, _share_subtitle(uk_years, uk, us_years, us))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    tidy(ax, ylabel="Annual tuition as % of GDP per capita")
    ax.set_ylim(bottom=0)
    ax.margins(x=0.10)

    source_note(fig, note(
        "Sources: fees as above; GDP per capita from the World Bank (NY.GDP.PCAP.CD and "
        "NY.GDP.PCAP.PP.CD). Fees and income are taken in the same currency, so the units "
        f"cancel and the figure is the same at market rates as at PPP. PPP parities are on "
        f"the {ICP_VINTAGE} benchmark."))
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
           "chart_tuition_ppp", "chart_tuition_share"]
