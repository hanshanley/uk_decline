# Tuition sub-analysis — cost of a four-year degree: UK vs EU vs US

Part of the `uk_decline` study. Determines the **median** and **average** cost of a
four-year bachelor's degree across the **UK**, the **EU-27**, and the **US**, to test the
claim that *the UK has a higher average cost of degrees*.

> **On this mixed-definition snapshot**, England's maximum annual
> tuition (~**$12,890**, the published £9,790 cap for 2026/27, converted at nearby-year FX) is **higher than both**
> the EU-27 average (~**$425/yr**, median **$0**) and the US average published **in-state public** tuition
> (~**$11,610/yr**). This compares a statutory maximum with a US institutional average
> and an unweighted EU country compilation, not like-for-like student averages.
> England's cap is not a UK-wide average; rules differ in Scotland, Wales and Northern Ireland.

## Scope

| Dimension | Choice |
|---|---|
| Cost | **Tuition / fees only** (no living costs) |
| Cohort | **Domestic / in-country (EU) students** at public institutions |
| Regions | **UK** (own category), **EU-27**, **US** |
| Aggregation | **Per country, unweighted** median & average |
| Degree totals | Summary table: annual tuition **× 4** normalized; chart annotations: typical 3-year UK/EU and 4-year US |
| Currency | normalized to **USD** (nominal, market FX) and **constant 2022 USD** (CPI-adjusted) |

## Results

Latest run (nominal USD, annual domestic tuition, one figure per country):

| Region | n | Avg / yr | Median / yr | Avg 4-yr | Median 4-yr |
|---|---:|---:|---:|---:|---:|
| **UK** | 1 | $12,890 | $12,890 | $51,562 | $51,562 |
| **EU-27** | 27 | $425 | $0 | $1,701 | $0 |
| **US** | 1 | $11,610 | $11,610 | $46,440 | $46,440 |

Constant-2022-USD values require the tuition source year's US CPI. The published 2026/27
England cap has no same-year CPI yet, so its real value is blank rather than silently
using the 2025 CPI or publishing nominal dollars under a real-dollar label.
Market exchange rates express fees in US dollars at the year's exchange rate.
GDP PPP expresses them against an economy-wide purchasing-power basket, not a
tuition-specific price index. The two answer different questions; neither alone
measures student affordability.

> **The PPP alternative, for comparison.** [`../ppp_data/`](../ppp_data/README.md) builds a
> PPP-converted twin of the history chart, plus a **tuition-as-a-share-of-GDP-per-capita**
> chart that is unit-free (the currency cancels, so it reads the same at market rates and at
> PPP). The PPP chart carries the legally fixed nominal cap through every applicable year,
> then recomputes each year's PPP, market-rate and inflation-adjusted value; it does not draw
> flat real-value steps between policy changes. In 2022 — the last year both fee series
> cover — a year's fees took **24% of UK
> GDP per head against 12% in the US**.

Full per-country data: `data/processed/tuition_by_country.csv`.
Region summary: `data/processed/summary.csv`.

## Historical trend — real (inflation-adjusted) tuition back to the 1970s

The snapshot above is a nominal cross-section. The **US/England primary-sourced, inflation-
adjusted** view is the historical series in **constant 2022 USD** (`../outputs/tuition/tuition_history_real_usd.png`):

England's source file records statutory change points, including annual upratings before
2012 ([Hansard, 1 March 2013](https://publications.parliament.uk/pa/cm201213/cmhansrd/cm130301/text/130301w0003.htm)).
The pipeline carries each legally
fixed **nominal** cap through the years in which it applies, then recalculates the market
exchange-rate and inflation-adjusted value annually; real-dollar values are not held flat.

| Year | UK (England cap) | US (public in-state) | Germany |
|---|---:|---:|---:|
| 1971 | $0 (free) | $3,093 | $0 |
| 1998 | $2,973 | ~$5,797 | $0 |
| 2012 | **$18,122** | $10,287 | $0 |
| 2022 | $11,401 | $9,750 | $0 |
| 2024 | $11,030 | — | — |

**Key finding:** in real terms the UK went from **free (until 1998)** to **overtaking US
public college in 2012** ($18,122 vs $10,287). The cap stayed at £9,250 from 2017 through
2024/25, then rose to £9,535 in 2025/26. Higher caps are published for 2025/26 and
2026/27, but the real-dollar history does not plot them until same-year FX and CPI exist. Germany
has zero-fee reference observations plotted as points, not an uninterrupted free series:
some German states charged general tuition during 2006–14. Germany is not an EU average.

Historical data: `data/processed/tuition_history.csv`.

## Data sources & provenance

**Full formal citations** (organization, title, year, access date) are in
**[`CITATIONS.md`](CITATIONS.md)**. Every figure is traceable to the source
below (each output CSV row also carries `source` / `source_url`). **Primary** =
fetched/derived from an authoritative primary dataset;
**secondary** = compiled from a published summary of the primary report (flagged for
verification in-row).

| Series | Source | Access | Provenance |
|---|---|---|---|
| US tuition history + snapshot | **NCES** Digest 2023, Table 330.10 (Public 4-year, in-district) — current & **constant 2022-23 $** (BLS CPI) | `fetch_nces.py` downloads & parses the real table ([link](https://nces.ed.gov/programs/digest/d23/tables/dt23_330.10.asp)); raw HTML cached in `data/raw/sources/` | **primary** |
| UK fee-cap history | England statutory caps — Acts / SIs on **legislation.gov.uk** (1998, 2004, 2010, 2016), Hansard 1 March 2013 annual maxima, and House of Commons Library CBP-8151 | `data/raw/tuition_history_manual.csv` (per-row `source_url`) | **primary** (statutory / parliamentary answer) |
| Inflation & FX | **World Bank** CPI `FP.CPI.TOTL`, exchange rate `PA.NUS.FCRF` (keyless API) | `tuition/rates.py` (`fetch_series`) | **primary** |
| EU-27 snapshot fees | **Eurydice** *National Student Fee & Support Systems 2023/24* | `data/raw/manual_tuition.csv` | **secondary** (summary; a few rows flagged `APPROXIMATE`) |
| Germany history | German HE fee history / Eurydice | `data/raw/tuition_history_manual.csv` | secondary |

> **Honesty note:** the EU-27 snapshot fees come from a published *summary* of the Eurydice
> report, not the primary PDF; three rows that could not be pinned to an exact primary
> figure (Bulgaria, Spain, and Belgium's blended communities) are marked `APPROXIMATE` in
> their `notes`. US nominal fees and England caps are primary-sourced and deflated with
> the **same calendar-year World Bank US CPI**, not mixed with NCES's academic-year
> constant-2022–23 column. Academic-year fees are indexed by their starting calendar year.
> Germany's secondary-source points do not establish a continuous national fee history.

## How it works (hybrid data pipeline)

1. **Curated snapshot source** — `data/raw/manual_tuition.csv`: domestic annual
   first-cycle tuition per country, each row carrying its own `source` + `year`.
   EU-27 from the **Eurydice** *National Student Fee and Support Systems 2023/24*
   report (secondary summary; approximate rows flagged); US from **College Board** /
   **NCES**; UK from the statutory England fee cap.
2. **Historical series** — `fetch_nces.py` downloads & parses the real **NCES** US table;
   `data/raw/tuition_history_manual.csv` holds UK statutory caps (legislation.gov.uk) and
   Germany; `build_history.py` deflates to **constant 2022 USD** using real World Bank CPI
   + FX (see *Data sources & provenance*).
3. **Currency normalization** — `tuition/rates.py` pulls live **World Bank** data
   (`PA.NUS.FCRF` exchange rate, `FP.CPI.TOTL` CPI; no API key). Nominal figures use
   market FX; constant-2022-USD figures deflate the nominal USD by US CPI. An offline
   fallback FX table lives in `tuition/config.py` (snapshot only — the historical
   deflators have no fabricated fallback).
4. **Aggregation** — `analyze.py` computes per-region median & average (annual and ×4).

## Run

```bash
# runtime deps in requirements.txt (requests, tenacity, matplotlib, pandas, lxml); tests need pytest
# --- current cross-sectional snapshot ---
.venv/bin/python -m tuition.build_dataset      # fetch WB rates + normalize  (--offline to skip network)
.venv/bin/python -m tuition.analyze            # print table + write summary.csv
.venv/bin/python -m tuition.plot_tuition       # snapshot figures -> ../outputs/tuition/  (add --real for constant 2022 USD)

# --- historical, inflation-adjusted series (back to the 1970s) ---
.venv/bin/python -m tuition.fetch_nces         # download + parse the real NCES US tuition table
.venv/bin/python -m tuition.build_history      # combine NCES US + UK caps + Germany, deflate to real 2022 USD
.venv/bin/python -m tuition.plot_history       # historical chart -> ../outputs/tuition/tuition_history_real_usd.png

.venv/bin/python -m pytest tests/test_tuition.py -q
```

## Figures (written to `../outputs/tuition/`)

All figures use the shared Substack style (matching `pre1870_reapportionment_package`) and
carry an italic **source note citing the data provenance**:

- `tuition_history_real_usd.png` — real (constant 2022 USD) tuition 1963/71→2026, UK vs US
  vs Germany. *(the primary-sourced, inflation-adjusted headline chart)*
- `tuition_region_comparison.png` — average & median annual tuition, UK vs EU-27 vs US.
- `tuition_by_country.png` — per-country ranking, colored by region.
- `*_real.png` — constant 2022 USD (CPI-adjusted) variants of the two snapshot charts.

## Layout (tuition sub-analysis files)

```
tuition/            # self-contained package
  config.py         #   countries, regions, sources/URLs, paths, fallback rates
  http.py           #   pooled requests session with retry/backoff
  rates.py          #   World Bank FX + CPI fetchers (fetch_series)
  stats.py          #   median/average + per-region aggregation
  dataset.py        #   shared primary-row loader (filter + value coercion)
  theme.py          #   shared Substack plotting theme
fetch_nces.py       # download + parse the real NCES US tuition table (primary source)
fetch_oecd.py       # checks the OECD SDMX API for a usable fee series
fetch_eurostat.py   # checks Eurostat/Eurydice for a usable fee series
build_dataset.py    # snapshot: merge curated + fetched, convert to nominal + constant-2022 USD
build_history.py    # historical: NCES US + UK caps + Germany -> real 2022 USD
analyze.py          # per-region median & average + verdict
plot_tuition.py     # snapshot figures -> ../outputs/tuition/
plot_history.py     # historical real-USD figure -> ../outputs/tuition/
data/raw/           # manual_tuition.csv, tuition_history_manual.csv, nces_*.csv,
                    #   wb_rates.csv, sources/ (cached raw NCES HTML)
data/processed/     # tuition_by_country.csv, summary.csv, tuition_history.csv
../outputs/tuition/   # generated PNG figures
tests/test_tuition.py
```

## Caveats

- **US private colleges are excluded from the headline.** Average published US *private
  nonprofit* tuition is ~**$43,350/yr** — far above the UK. "Domestic US cost" here means
  the **in-state public** figure most students face; the private figure is kept as a
  reference row (`include_primary=0`).
- **UK is nation-split.** The headline is **England (£9,790 published for 2026/27)**; **Scotland** charges
  Scottish-domiciled students **£0** (reference row). **Wales** tracks England closely
  (~£9,000), but **Northern Ireland** caps NI-domiciled fees materially lower (~£4,750).
- **Many EU states charge €0** for domestic students (Germany, the Nordics, etc.). These
  zeros are legitimate data points and are kept, which is why the EU **median is $0**.
- **3-vs-4-year programmes.** The results table's ×4 total is a normalized comparison;
  the region chart separately annotates typical 3-year UK/EU and 4-year US degrees.
- **Reference years differ** (EU 2023/24, US 2024/25, England 2026/27); nominal figures prefer
  source-year FX, falling back to a nearby published year within three years; the actual
  FX year is recorded per row. Real values require exact source-year CPI.
- Figures are **most-common statutory fees**, not enrollment-weighted averages.
