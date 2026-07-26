"""Splitting a market-exchange-rate comparison into a real part and a currency part.

For any country ``c`` in any year, GDP per capita converted at the market exchange rate and
GDP per capita converted at PPP differ by exactly one factor — the price level index::

    GDPpc(current US$)  =  GDPpc(current int'l $)  x  PLI      where PLI = PPP factor / FX

Taking a ratio against the United States (whose PLI is 1.00 by construction) gives::

    R_fx  =  R_ppp  x  R_pli

so any change in how the UK compares to the US at market rates is the product of a change in
**relative PPP-converted output** and a change in **relative prices / the exchange rate**.

One caveat the identity above quietly hides: ``R_ppp`` here is the *current-price* PPP ratio,
and its year-to-year movement is **not** pure volume growth — it also carries shifts in the
PPP price structure. Reading a change in ``R_ppp`` as a change in real output understates the
real divergence roughly four-fold. So the production caller
(:func:`ppp_data.charts.uk_us_decomposition`) does not use the identity as written: it feeds
the **constant-price volume ratio** as the real factor and derives the second factor as the
residual ``R_fx / R_real``, which therefore carries ICP re-benchmarking drift as well as
prices and the exchange rate. That is why the chart labels the second bar "prices, exchange
rate and re-benchmarking" rather than "price level", and why
:func:`ppp_data.validate.check_decomposition_real_component_is_volume` recomputes the real
component from each country's own growth rates on every run.

The split uses the symmetric (Shapley) decomposition of a two-factor product rather than a
sequential one, so it is exact *and* independent of which factor you vary first — there is
no arbitrary "hold X constant" choice biasing the answer. :func:`decompose_ratio_change`
returns contributions in percentage points of the US level, which is the unit the charts
and the README quote.
"""

from __future__ import annotations

import math
from typing import NamedTuple


def price_level_index_direct(ppp_conversion_factor: float,
                             market_exchange_rate: float) -> float:
    """PPP conversion factor divided by the market exchange rate (US = 1.00).

    Above 1.00 the country is expensive relative to the United States; below 1.00, cheap.

    This is the *textbook* definition. It is not called by the pipeline: the equivalent
    row-level implementation :func:`ppp_data.worldbank.derive_price_level_index_direct` emits
    the ``price_level_index_direct`` metric that
    :func:`ppp_data.validate.check_price_level_agreement` reconciles against the headline
    index. This function is the scalar form of the same formula, kept for tests and for
    readers who want the definition in one line. The headline index is built instead from the
    two GDP-per-capita series, where the local-currency units cancel; see
    :func:`ppp_data.worldbank.derive_price_level_index` for why that distinction matters
    across the euro changeover.

    The two routes are reconciled by :func:`ppp_data.validate.check_price_level_agreement`,
    which is the package's real end-to-end check that the right series were pulled and
    aligned. :func:`ppp_data.validate.check_price_level_identity` is the weaker companion: the
    headline index is *defined* as ``nominal_usd / ppp_current``, so that identity holds by
    construction at derivation time and the check guards only the emitted dataset — it exists
    because mutation testing showed a one-year shift of a single series was otherwise
    undetected.
    """
    if market_exchange_rate == 0:
        raise ValueError("market exchange rate of zero: cannot form a price level index")
    return ppp_conversion_factor / market_exchange_rate


class Decomposition(NamedTuple):
    """Contributions to the change in a country's GDP per capita relative to the US.

    All ratio and effect fields are in **percentage points of the US level**, so a
    ``start_ratio`` of 105.0 means "105% of the US". ``real_effect + price_effect`` equals
    ``total_change`` exactly.
    """

    start_year: int
    end_year: int
    start_ratio: float
    end_ratio: float
    total_change: float
    real_effect: float    # from relative real output (PPP volumes)
    price_effect: float   # from the relative price level / exchange rate
    log_real: float       # the same split in log points, for reference
    log_price: float


def decompose_ratio_change(
    *,
    start_year: int,
    end_year: int,
    ppp_ratio_start: float,
    ppp_ratio_end: float,
    pli_ratio_start: float,
    pli_ratio_end: float,
) -> Decomposition:
    """Split the change in ``R_fx = R_ppp * R_pli`` into real and price-level parts.

    Each ``*_ratio_*`` argument is a country-vs-US ratio expressed as a fraction (0.62 for
    "62% of the US"), not a percentage. The returned effects are in percentage points.
    """
    for name, value in (
        ("ppp_ratio_start", ppp_ratio_start), ("ppp_ratio_end", ppp_ratio_end),
        ("pli_ratio_start", pli_ratio_start), ("pli_ratio_end", pli_ratio_end),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value!r}")

    fx_start = ppp_ratio_start * pli_ratio_start
    fx_end = ppp_ratio_end * pli_ratio_end

    # Symmetric (Shapley) split: average the two orderings of "vary real first" and
    # "vary prices first". The two halves sum to the total change exactly.
    real = 0.5 * (
        (ppp_ratio_end - ppp_ratio_start) * pli_ratio_start
        + (ppp_ratio_end - ppp_ratio_start) * pli_ratio_end
    )
    price = 0.5 * (
        (pli_ratio_end - pli_ratio_start) * ppp_ratio_start
        + (pli_ratio_end - pli_ratio_start) * ppp_ratio_end
    )

    return Decomposition(
        start_year=start_year,
        end_year=end_year,
        start_ratio=fx_start * 100.0,
        end_ratio=fx_end * 100.0,
        total_change=(fx_end - fx_start) * 100.0,
        real_effect=real * 100.0,
        price_effect=price * 100.0,
        log_real=math.log(ppp_ratio_end / ppp_ratio_start) * 100.0,
        log_price=math.log(pli_ratio_end / pli_ratio_start) * 100.0,
    )
