# uk_decline — European per-capita GDP & median income (PPP)

Reproducible Python pipeline that pulls, for **geographic Europe** (EU + UK, Norway,
Switzerland, the Balkans, etc.) as a **time series**, two complementary measures of
living standards — with a focus on the **UK's relative decline**:

1. **GDP per capita, PPP** — total economic output per person, purchasing-power adjusted.
2. **Median disposable income (PPP/PPS)** — what a *typical* person/household actually has.

All data comes from **free, key-less public APIs**.

## Data sources

| Metric (column) | Source | Series | Notes |
|---|---|---|---|
| `gdp_per_capita_ppp_current` | World Bank WDI | `NY.GDP.PCAP.PP.CD` | Current international $. All European countries, to latest year. |
| `gdp_per_capita_ppp_constant` | World Bank WDI | `NY.GDP.PCAP.PP.KD` | Constant 2021 international $ (real trend). |
| `median_disposable_income` | Eurostat `ilc_di03` | `MED_EI`, `unit=PPS` | Median equivalised net income in Purchasing Power Standard. **UK ends ~2018** (left EU-SILC after Brexit). |
| `mean_disposable_income` | Eurostat `ilc_di03` | `MEAN_EI`, `unit=PPS` | Mean counterpart, same coverage. |
| `median_income_pip` | World Bank PIP | `/pip/v1/pip` | Median income, **2017 PPP $ per day**. Globally comparable; **covers the UK through ~2021**, filling the Eurostat gap. Multiply by 365 for an annual figure. |

Eurostat aggregates `EU27_2020` (EU-27) and `EA20` (euro area) are pulled as reference
lines for the income metrics; the World Bank aggregates `EUU` (European Union) and `EMU`
(euro area) are pulled for GDP per capita PPP.

### Why three sources for "median"?
The UK stopped reporting to EU-SILC after Brexit, so **Eurostat's PPS median income for the
UK stops around 2018**. World Bank PIP provides a globally comparable median (in 2017 PPP $)
that continues through ~2021. Both are reported separately and clearly labeled — they are
**not** silently spliced together, because they use different price bases and units.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

No API keys are required.

## Usage

```bash
# All sources, years 2000..current (default):
./.venv/bin/python fetch_data.py

# Custom range / subset of sources / output dir:
./.venv/bin/python fetch_data.py --start 2005 --end 2024
./.venv/bin/python fetch_data.py --sources worldbank eurostat
./.venv/bin/python fetch_data.py --out data
```

## Outputs (written to `data/`, git-ignored)

| File | Description |
|---|---|
| `gdp_per_capita_ppp.csv` | World Bank GDP-per-capita rows (long). |
| `eurostat_median_income_pps.csv` | Eurostat median & mean income (long). |
| `pip_median_income.csv` | World Bank PIP median income (long). |
| `europe_combined_long.csv` | All sources, tidy long: `iso3, country, year, metric, value, unit, source`. |
| `europe_combined_wide.csv` | One row per country-year, one column per metric. |
| `manifest.json` | Run metadata: sources, year span, countries, timestamp. |

## Example: the UK decline

From `europe_combined_wide.csv`, UK GDP per capita (PPP) as a share of Germany's:

| Year | UK | Germany | UK / DE |
|---|---|---|---|
| 2000 | 26,536 | 27,474 | 0.97 |
| 2010 | 36,484 | 39,726 | 0.92 |
| 2019 | 50,065 | 59,271 | 0.85 |
| 2024 | 62,009 | 73,552 | 0.84 |

The UK also slipped below France on this measure around 2019.

## Figures

After fetching the data, render the headline figures (styled to match the
`pre1870_reapportionment_package` "Substack" theme — warm tan background, serif fonts,
muted palette) into `outputs/`:

```bash
./.venv/bin/python plot_uk_decline.py            # reads data/europe_combined_wide.csv
./.venv/bin/python plot_uk_decline.py --out outputs
```

| File | Shows |
|---|---|
| `gdp_per_capita_real_over_time.png` | Real GDP/capita (Maddison, 2011 PPP, 1970–2022), UK vs US/Germany/France/Italy. |
| `uk_gdp_relative_to_peers.png` | UK real GDP/capita as a % of Germany and the US, 1970–2022 (the decline). |
| `median_disposable_income_pps.png` | Eurostat median income (PPS); UK line ends ~2018. |
| `median_income_pip.png` | World Bank PIP real median income (2017 PPP $/day); UK to ~2021. |

See [`europe_data/README.md`](europe_data/README.md) for the full sources table (incl. the
Maddison Project Database) and the inflation-adjustment basis of each metric.

## Project layout

```
uk_decline/
  fetch_data.py            # CLI entry point (europe_data)
  plot_uk_decline.py       # render Substack-styled figures into outputs/
  europe_data/
    countries.py           # curated Europe list + ISO3/ISO2/Eurostat-geo mapping
    worldbank.py           # WDI: GDP per capita PPP (nominal + constant)
    eurostat.py            # ilc_di03: median & mean disposable income (PPS)
    pip.py                 # World Bank PIP: median income (2017 PPP $/day)
    combine.py             # merge -> long/wide CSVs + manifest
    _http.py               # shared requests session with retry/backoff
  markets_data/            # UK vs US stock-market size (World Bank WDI)
    markets.py             # 3 size metrics (market cap $, % of GDP, listed cos)
    regions.py             # UK/US core + World/EU/Japan/China reference
    worldbank.py           # WDI fetcher; combine/charts/summary; python -m markets_data
  tests/test_pipeline.py   # offline unit tests (europe_data)
  tests/test_markets.py    # offline unit tests (markets_data)
  data/                    # data outputs (git-ignored)
  outputs/                 # figures (PNG)
```

## Tests

```bash
./.venv/bin/python tests/test_pipeline.py     # or: pytest tests/ -q
```

## Stock-market size (UK vs US)

A self-contained sibling pipeline, `markets_data/`, sizes the **UK stock market over time
against the US** (with World / EU / Japan / China as reference lines), using free, key-less
**World Bank** data. Every value traces directly to a World Bank API series — nothing is
interpolated, spliced, or synthesised, and null observations are dropped rather than filled.

| Metric (column) | Source | Indicator | Notes |
|---|---|---|---|
| `market_cap_usd` | World Bank WDI | `CM.MKT.LCAP.CD` | Market value of listed domestic companies, **nominal** current US$. |
| `market_cap_usd_real` | World Bank WDI ÷ World Bank US CPI | `CM.MKT.LCAP.CD` deflated by `FP.CPI.TOTL` | **Inflation-adjusted**: the nominal series in **constant US$** (see below). |
| `market_cap_pct_gdp` | World Bank WDI | `CM.MKT.LCAP.GD.ZS` | Market cap as a share of GDP (size relative to the economy; a same-year ratio, so inflation-neutral). |
| `listed_domestic_companies` | World Bank WDI | `CM.MKT.LDOM.NO` | Count of domestically listed companies (breadth). |

**Inflation adjustment.** The headline market-cap series is nominal (current US$), which mixes
real growth with inflation. `market_cap_usd_real` deflates it by the US Consumer Price Index
(World Bank `FP.CPI.TOTL`, 1970–2024) and rebases every figure to **constant US$ of the latest
CPI year** (currently 2024; recorded as `real_base_year` in the manifest). Only years present in
both the market-cap and CPI series are computed — the newest market-cap year (2025) has no CPI
yet and is left blank rather than extrapolated. For non-US markets this removes US-dollar
inflation but not exchange-rate effects.

### Usage

```bash
./.venv/bin/python -m markets_data                    # fetch + CSVs + charts + summary
./.venv/bin/python -m markets_data --start 1970 --end 2024
./.venv/bin/python -m markets_data --no-charts --no-summary
./.venv/bin/python -m markets_data --from-csv data/stock_market_size.csv
```

The default span starts in 1970. World Bank stock-market data begins in **1975** (the
`CM.MKT.*` series derive from the S&P/IFC database), so the pipeline reaches back to the
1970s — as far as this free source allows — with earlier empty years dropped.

### Outputs

Regenerable **data** is written to `data/` (git-ignored); the **showcase artifacts** (charts +
summary), which cite their sources inline, go to `outputs/` so they can be committed.

| File | Location | Description |
|---|---|---|
| `stock_market_size.csv` | `data/` | Tidy long: `region, region_code, year, metric, value, unit, source`. |
| `stock_market_size_wide.csv` | `data/` | One row per region-year, one column per metric. |
| `stock_market_size_manifest.json` | `data/` | Run metadata: regions, year span, metrics, per-indicator sources, `real_base_year`. |
| `stock_market_size_summary.md` | `outputs/` | UK-vs-US trend summary; every metric cites its source + indicator. |
| `charts/stock_*.png` | `outputs/` | Per-metric trends (incl. real) + UK-as-share-of-US ratio charts. Each figure footnotes its data source(s) + indicator. |

Generated charts (all in `outputs/charts/`, source cited in each figure's footnote):
`stock_market_cap_usd.png`, `stock_market_cap_usd_real.png`, `stock_market_cap_pct_gdp.png`,
`stock_listed_domestic_companies.png`, and the three `stock_uk_us_ratio_*.png` charts. To
regenerate them, run `python -m markets_data` (or `--from-csv data/stock_market_size.csv` to
rebuild charts/summary from existing data). The chart code is in `markets_data/charts.py`.

### Example: the UK market's relative decline

The UK's stock-market capitalisation as a share of the US:

| Year | UK / US market cap |
|---|---|
| 1990 | 27% (peak) |
| 2022 | 8% |

Listed domestic companies fell from ~2,820 (1975) to ~1,606 (2022), while the US rose past
3,900. **WDI caveat:** the market-cap series is compiled from S&P/WFE data and has tail-year
gaps — the UK is missing after 2022, so recent years are blank (never spliced).

## UK immigration over time (legal + irregular)

A self-contained sibling pipeline, `uk_migration/`, builds a UK-only picture of
**immigration over time** — both **legal** flows and **irregular ("illegal")** arrivals —
from free, key-less public sources, and renders summary time-series charts.

| Metric (column) | Source | Series / dataset | legality / flow_type | Notes |
|---|---|---|---|---|
| `immigration`, `emigration` | ONS Long-Term International Migration | Table 1, `YE Dec`, All Nationalities | legal / inflow, outflow | Annual inflow / outflow (year ending December). |
| `net_migration` | ONS LTIM | Table 1, Net migration | total / net | Headline UK net migration. |
| `visas_granted` | Home Office Immigration System Statistics | `entry-clearance-visa-outcomes` (issued) | legal / count | By category: `work`, `study`, `family`, `visitor`, `other`. From 2005. |
| `asylum_applications` | Home Office | `asylum-claims` detailed dataset | legal / count | Main applicants only (headline). From 2001. |
| `irregular_arrivals` | Home Office | `illegal-entry-routes` detailed dataset | irregular / count | By method: `small_boat`, `air`, `port`, `in_country`, plus `all`. From 2018. |
| `migrant_stock`, `migrant_stock_pct`, `net_migration_wb`, `uk_population` | World Bank WDI | `SM.POP.TOTL`, `SM.POP.TOTL.ZS`, `SM.POP.NETM`, `SP.POP.TOTL` (GBR) | total / stock, net | Long historical backdrop + population denominator (from 1960/1990). |
| `*_per_1000_pop` | **Derived** (not a new source) | flow ÷ `uk_population` × 1000 | inherits | Population-adjusted views of each flow (see below). |

Each row carries two orthogonal facets: **`legality`** (`legal` / `irregular` / `total`) and
**`flow_type`** (`inflow` / `outflow` / `net` / `stock` / `count`). Aggregate measures (net
migration, migrant stock) use `legality = total`, so filtering `legality == 'legal'` never
silently drops them.

### How the sources are resolved

Home Office spreadsheets are re-published quarterly with dated filenames (e.g.
`asylum-claims-datasets-mar-2026.xlsx`). The pipeline resolves the **current** file via the
gov.uk content API by matching a stable filename **prefix** (newest date wins on ties), so it
keeps working after each release. ONS LTIM is resolved via the dataset page's `/data` JSON
(newest edition by embedded date). Annual figures sum all four quarters; any `(year, category)`
lacking four quarters — including the partial most-recent year — is dropped so trends don't
show a false dip.

### Data integrity & "adjusting for inflation"

**Nothing in this pipeline is hand-entered or synthesised** — no manual tables, no
interpolation, no random or filled values. Every row is fetched live and can be re-derived
by re-running `fetch_all()` (the committed CSVs are byte-identical to a fresh fetch). The
only literals in the code are spreadsheet column indices and HTTP parameters.

Immigration figures are **headcounts** (people, visas, claims, detections), not monetary
amounts, so **CPI inflation adjustment does not apply**. The meaningful "real-terms"
comparison across decades is to divide each flow by the UK population of the same year (the
population grew from ~55.7M in 1970 to ~69M today). The `*_per_1000_pop` series do exactly
that: `flow ÷ uk_population × 1000`, using World Bank `SP.POP.TOTL`. These derived rows carry
a `Derived: … ÷ World Bank SP.POP.TOTL` source label and exist only for years with a real
population value — they are transparent ratios of two real series, never new data.

### Caveats (UK immigration)

- ONS LTIM recent years are **provisional** (`P`) / revised (`R`) and change between releases.
- `irregular_arrivals` counts **detected** arrivals only — not total irregular entry.
- **Historical depth:** annual **net migration reaches 1960** (World Bank); gross ONS
  inflow/outflow start 2012, visas 2005, asylum 2001, irregular arrivals 2018 — because the
  underlying official series do not go back further.
- Charts use the shared "Substack" serif theme to match `pre1870_reapportionment_package`.

### Usage

```bash
./.venv/bin/python -m uk_migration.run                 # fetch all -> CSVs -> charts
./.venv/bin/python -m uk_migration.run --no-charts     # data only
./.venv/bin/python -m uk_migration.run --only visas asylum
```

### Outputs

Per-source raw and combined tidy CSVs (git-ignored, regenerable):

| File | Description |
|---|---|
| `data/raw/<source>.csv` | Per-source tidy rows (`worldbank`, `ons_ltim`, `visas`, `asylum`, `irregular`). |
| `data/processed/uk_migration_long.csv` | All sources, tidy long: `iso3, country, period, metric, category, value, unit, legality, flow_type, source`. |

Committable showcase (written to `outputs/uk_migration/`, **not** git-ignored):

| File | Description |
|---|---|
| `outputs/uk_migration/*.png` | Seven charts, each with a data-source caption: net migration; immigration vs emigration; visas by category; asylum; irregular arrivals; legal-vs-irregular (log); net migration per 1,000 population (population-adjusted, 1960+). |
| `outputs/uk_migration/SOURCES.md` | Data-source reference for every figure (auto-generated by `charts.write_sources_doc`). |
| `outputs/uk_migration/uk_migration_long.csv` | Self-contained copy of the combined data next to the charts. |

### Example: scale of legal vs irregular

Detected irregular arrivals (~40–55k/year recently) are roughly **an order of magnitude
smaller** than legal immigration (~0.7–1.4M/year), which the `legal_vs_irregular.png` log
chart makes explicit. Small-boat crossings rose from ~300 (2018) to ~46k (2022).

### Layout

```
uk_migration/
  schema.py          # tidy-row schema + validation
  _http.py           # requests session w/ retry (get_json + get_bytes)
  _govuk.py          # resolve current gov.uk / ONS download URLs
  _spreadsheet.py    # xlsx / ods / csv row reader
  _aggregate.py      # stream-sum by (year, category); drop partial years
  sources/           # worldbank, ons_ltim, visas, asylum, irregular
  normalize.py       # derived per-1,000-population views (÷ World Bank SP.POP.TOTL)
  combine.py         # per-source raw CSVs + combined long CSV
  charts.py          # seven matplotlib PNGs
  run.py             # CLI: python -m uk_migration.run
```

## Caveats (European GDP & income pipeline)

- **Different price bases:** WDI/Eurostat use current-year PPP/PPS; PIP uses 2017 PPP.
  Compare *within* a metric across countries/years, not raw values *across* metrics.
- **Micro-states** (Andorra, Monaco, San Marino, Liechtenstein) and Kosovo have sparse or no
  survey-based income data; rows will be blank where unavailable.
- **Russia and Turkey** are excluded by default as transcontinental.

(For the UK immigration pipeline's caveats, see its section above.)
