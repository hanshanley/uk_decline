"""Tuition converted at PPP, and tuition measured against income.

The ``tuition`` package converts fees at **market exchange rates** and deflates by US CPI,
which answers "how does a UK degree compare with a US one, in dollars?". This module asks
the domestic-burden question instead: **how much of a British household's own purchasing
power does a UK degree consume, compared with an American one?**

Two figures come out of it:

``ppp_tuition_history``
    The statutory England fee cap is carried through every year in which it applies, then
    converted using that year's PPP factor and market exchange rate and deflated by that
    year's US CPI. Both lines therefore move annually even when the nominal cap is frozen.

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

from . import peers, series
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
    real_base_usd: float | None     # market exchange rates; None if CPI lacks that year
    real_base_intl: float | None    # purchasing power parity; None if the CPI lacks that year
    share_of_gdp_pc_pct: float      # unit-free: currency cancels


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

    The ratio is identical for every country (the same US CPI deflates them all), but the two
    metrics must be read from the *same* country or the ratio is meaningless — so this reads
    the United States explicitly rather than whichever row happens to sort last.
    """
    out: dict[int, float] = {}
    by_year: dict[int, dict[str, float]] = {}
    for row in rows:
        if (row["iso3"] == peers.US
                and row["metric"] in ("gdp_per_capita_real_usd", "gdp_per_capita_nominal_usd")):
            by_year.setdefault(row["year"], {})[row["metric"]] = row["value"]
    for year, pair in by_year.items():
        real = pair.get("gdp_per_capita_real_usd")
        nominal = pair.get("gdp_per_capita_nominal_usd")
        if real and nominal:
            # real/nominal == CPI_base/CPI_year, so CPI_year is proportional to its inverse.
            out[year] = 100.0 * nominal / real
    return out


def expand_uk_fee_schedule(history: list[dict], years: set[int]) -> list[dict]:
    """Expand sparse England fee-cap changes into an annual statutory schedule.

    The manual history records only years in which the legal cap or its cited status
    changes. Between those points the *nominal* cap is genuinely fixed, so carrying it
    forward is not interpolation. Exchange rates, PPP factors and inflation are applied
    later for each individual year and are never carried forward.
    """
    uk_changes = sorted(
        (row for row in history if row["iso3"] == peers.UK),
        key=lambda row: int(row["year"]),
    )
    other = [row for row in history if row["iso3"] != peers.UK]
    if not uk_changes:
        return history

    first_fee_year = next(
        (int(row["year"]) for row in uk_changes if float(row["nominal_local"]) > 0),
        None,
    )
    if first_fee_year is None:
        return history

    expanded: list[dict] = []
    for year in sorted(y for y in years if y >= first_fee_year):
        applicable = [row for row in uk_changes if int(row["year"]) <= year]
        if not applicable:
            continue
        row = dict(applicable[-1])
        row["year"] = year
        expanded.append(row)
    return other + expanded


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

    # The policy input is sparse (fee-change years), while the conversion inputs are annual.
    # Expand the cap wherever the four annual conversion/income series exist. CPI coverage
    # may end earlier; that should suppress only the real-dollar lines, not the unit-free
    # tuition-as-share-of-GDP series.
    required_metrics = (
        "ppp_conversion_factor",
        "gdp_per_capita_ppp_current",
        "gdp_per_capita_nominal_usd",
        "market_exchange_rate",
    )
    uk_metric_years = set.intersection(*[
        {
            year
            for metric, iso3, year in values
            if metric == required and iso3 == peers.UK
        }
        for required in required_metrics
    ])
    history = expand_uk_fee_schedule(history, uk_metric_years)

    out: list[TuitionPoint] = []
    for row in history:
        iso3, year = row["iso3"], int(row["year"])
        nominal = float(row["nominal_local"])
        cpi_year = cpi.get(year)
        ppp_factor = values.get(("ppp_conversion_factor", iso3, year))
        gdp_ppp = values.get(("gdp_per_capita_ppp_current", iso3, year))
        gdp_usd = values.get(("gdp_per_capita_nominal_usd", iso3, year))
        fx = values.get(("market_exchange_rate", iso3, year))
        # The share of GDP per capita is unit-free and needs no deflator, so it is NOT gated
        # on the CPI: the WDI publishes GDP for a year before the CPI-deflated series catches
        # up, and dropping the whole row would silently truncate the share chart.
        if not (ppp_factor and gdp_ppp and gdp_usd and fx):
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
            real_base_usd=tuition_usd * (cpi_base / cpi_year) if cpi_year else None,
            real_base_intl=tuition_intl * (cpi_base / cpi_year) if cpi_year else None,
            share_of_gdp_pc_pct=(share_ppp + share_fx) / 2.0 * 100.0,
        ))
    out.sort(key=lambda p: (p.region, p.year))
    return out


def _by_country(points: list[TuitionPoint], country: str,
                attr: str) -> tuple[list[int], list[float]]:
    """Years and values for one country, dropping years where the value is unavailable.

    ``real_base_intl`` is None when the US CPI does not yet cover a fee year, so each series
    is filtered independently rather than dropping the whole point.
    """
    chosen = [p for p in points if p.country == country and getattr(p, attr) is not None]
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
    """UK tuition on both conversion bases, with the US for scale.

    The two UK lines are deliberately given different weights and colours rather than two
    dashes of the same colour: the whole point of the figure is the gap between them, and
    the shaded band makes it readable at a glance. The band flips sign around 2016 — when
    sterling was strong a UK degree looked dearer in dollars than it felt at home, and since
    then the reverse.
    """
    plt = themed_plt()

    # This figure exists to compare the two conversion bases, so it is drawn only over years
    # where both exist. `real_base_intl` is None when the US CPI has not yet caught up with
    # the fee year, which would otherwise leave the two series unequal lengths.
    ppp_by_year = dict(zip(*_by_country(points, "United Kingdom", "real_base_intl")))
    fx_by_year = dict(zip(*_by_country(points, "United Kingdom", "real_base_usd")))
    uk_years = sorted(ppp_by_year.keys() & fx_by_year.keys())
    uk_ppp = [ppp_by_year[y] for y in uk_years]
    uk_fx = [fx_by_year[y] for y in uk_years]
    us_years, us_ppp = _by_country(points, "United States", "real_base_intl")
    if not uk_years:
        return None

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.fill_between(uk_years, uk_ppp, uk_fx, color=MUTED, alpha=0.16, zorder=1)
    ax.plot(uk_years, uk_fx, color=MUTED, linewidth=1.8, linestyle="--", zorder=3)
    ax.plot(uk_years, uk_ppp, color=ACCENT, linewidth=3.0, zorder=4)
    if us_years:
        ax.plot(us_years, us_ppp, color=GOLD, linewidth=2.0, zorder=2)

    labels = [(uk_ppp[-1], "UK, at PPP", ACCENT),
              (uk_fx[-1], "UK, at market rates", MUTED)]
    if us_years:
        labels.append((us_ppp[-1], "United States", GOLD))
    labelled_ends(ax, labels, min_gap=max(uk_ppp) * 0.085,
                  x=max(uk_years[-1], us_years[-1] if us_years else uk_years[-1]),
                  fontsize=10)

    ax.set_title("England's tuition cap at market exchange rates and PPP",
                 fontweight="bold", pad=30)
    subtitle(ax, f"Annual conversion of the statutory cap; latest complete year "
                 f"${uk_ppp[-1]:,.0f} at PPP and ${uk_fx[-1]:,.0f} at market rates")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    tidy(ax, ylabel=f"Annual tuition (constant {BASE_YEAR} $)")
    ax.set_ylim(bottom=0)
    ax.margins(x=0.13)

    source_note(fig, note(
        "Sources: UK \u2014 England statutory fee caps (legislation.gov.uk / GOV.UK); US "
        "\u2014 NCES Digest 2023 Table 330.10. UK fees converted at the World Bank PPP "
        f"factor (PA.NUS.PPP, {ICP_VINTAGE}) and at the market rate, both deflated by US CPI "
        f"to constant {BASE_YEAR} dollars. The US is the PPP numeraire, so the conversion "
        "leaves its fees unchanged; its line is deflated by World Bank CPI here rather than "
        "by the NCES series' own BLS deflator, so it differs from the market-rate tuition "
        "chart by up to about 3%. PPP factors start in 1990; earlier fee years are omitted."))
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
        "Sources: UK \u2014 England statutory fee caps (legislation.gov.uk / GOV.UK); US "
        "\u2014 NCES Digest 2023 Table 330.10; GDP per capita from the World Bank "
        "(NY.GDP.PCAP.CD, NY.GDP.PCAP.PP.CD). Fees and income are taken in the same "
        "currency, so the units cancel and the figure reads the same at market rates as at "
        f"PPP ({ICP_VINTAGE} parities)."))
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
