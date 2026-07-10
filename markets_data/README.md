# markets_data — UK vs US stock-market size

Documents the relative decline of the UK stock market vs the US (with World / EU / Japan /
China for context), using **only real, publicly-sourced data** from the World Bank's World
Development Indicators (no API key).

## Headline results (figures in [`../outputs/stock_markets/`](../outputs/stock_markets))

![UK/US market cap ratio (real)](../outputs/stock_markets/stock_uk_us_ratio_market_cap_usd_real.png)

The UK's listed-market capitalisation has fallen sharply relative to the US — from a peak of
~27% (1990) to ~8% by 2022. Charts cover market cap (nominal & real US$), market cap as a
share of GDP, and the number of listed domestic companies.

| File | Shows |
|---|---|
| `stock_market_cap_usd.png` / `_real.png` | Market cap, current US$ / constant 2024 US$ (CPI-deflated). |
| `stock_market_cap_pct_gdp.png` | Market cap as a share of GDP. |
| `stock_listed_domestic_companies.png` | Number of listed domestic companies. |
| `stock_uk_us_ratio_*` | UK-as-a-share-of-US variants of the above. |

## Data source & citation

- **World Bank** (2026). *World Development Indicators* — Market capitalization of listed
  domestic companies, current US$ (`CM.MKT.LCAP.CD`); % of GDP (`CM.MKT.LCAP.GD.ZS`); listed
  domestic companies (`CM.MKT.LDOM.NO`); US CPI (`FP.CPI.TOTL`, used to deflate to constant
  2024 US$). Washington, DC: World Bank Group. Underlying data compiled by the **World
  Federation of Exchanges** and **S&P Global**. Accessed 3 July 2026.
  <https://data.worldbank.org/indicator/CM.MKT.LCAP.CD>

Real figures are the nominal series deflated by US CPI to **constant 2024 US$** (market
exchange rates, not PPP). Series have tail-year gaps (the UK is missing after 2022); values
are never spliced or interpolated. Full per-metric citations are in
[`../outputs/stock_markets/stock_market_size_summary.md`](../outputs/stock_markets/stock_market_size_summary.md).

> **UK listed-company counts past 2022 (LSE factsheets).** The World Bank/WFE
> `CM.MKT.LDOM.NO` series ends at 2022 for the UK, but the LSE publishes the underlying
> counts monthly as machine-readable factsheets on its documents host (e.g.
> `docs.londonstockexchange.com/.../Main%20Market%20factsheet%20December%202024.xlsx` and the
> `AIM factsheet`). `lse_factsheets.py` reads the December factsheets and sums Main Market +
> AIM to a **UK-domiciled** count, which matches the WB/WFE "listed domestic companies" figure
> to within **<1%** at the 2022 overlap (WB 1,606 vs LSE 1,619) — so it continues that series
> almost seamlessly. Regenerate with `python -m markets_data.lse_factsheets` (writes the cited
> `data/uk_listed_companies_lse.csv`). The scorecard's "UK-listed companies" panel uses the WB
> series through 2022 and the LSE UK-domiciled count for 2023+ (**1,538 / 1,413 / 1,306** for
> 2023–2025), with the source switch noted. Every value is read straight from the LSE
> factsheet; none are estimated or interpolated.

## Usage

```bash
python -m markets_data                 # fetch + combine + charts + summary (1975..current)
python -m markets_data --no-charts     # data only
```

Combined CSVs/manifest are written to `../data/` (git-ignored, regenerable); charts and the
trend summary are written to `../outputs/stock_markets/`.

## Modules
`markets.py` · `worldbank.py` · `regions.py` · `combine.py` · `charts.py` · `summary.py` ·
`paths.py` · `_http.py`. Entry point: `python -m markets_data`. Tests: `../tests/test_markets.py`.
