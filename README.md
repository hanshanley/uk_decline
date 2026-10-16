<div align="center">
  <h1>Social, Economic, and Political Change in the United Kingdom</h1>
  <p>
    <a href="#uk-since-2007">Overview</a> ·
    <a href="#explore-the-evidence">Analyses</a> ·
    <a href="#setup">Setup</a> ·
    <a href="https://www.themarginoferror.com/uk_decline/">Live site</a>
  </p>
</div>

---

## UK since 2007

The overview combines eight source-backed indicators, including official statistics,
charity administrative counts and a constructed tuition-fee series. It uses 2007 as
the common framing; each panel uses its own available baseline and latest year.
It is not a composite index or an exhaustive measure of UK performance. Colours
describe the selected direction of change between endpoints, not the latest annual trend.
The overview uses **year-only labels**: financial and academic years use their
starting year; pooled trust surveys and CSEW periods use their ending year.
Monthly waiting-list and company counts use the latest available snapshot in
each year. These periods are not interchangeable annual observations.

<p align="center">
  <img src="outputs/uk_decline_scorecard.png" width="1200" alt="Eight source-backed indicators showing change in the UK since 2007">
</p>

The GDP comparison uses **constant-price purchasing-power parity (PPP)**, not
market-exchange-rate dollars. 

## Explore the evidence

**Economy and living standards:** [GDP and incomes](europe_data/README.md),
[stock markets](markets_data/README.md), [sterling](sterling_data/README.md),
[trade](trade_data/README.md), [London's economy](london_data/README.md), and
[purchasing power parity](ppp_data/README.md).
[Government debt and borrowing costs](debt_data/README.md) distinguish the UK
public-debt stock relative to GDP from market yields on government bonds.
[Unemployment and youth unemployment](unemployment_data/README.md) compare the UK
with EU and US reference rates in separate charts, with explicit age bands,
labour-force denominators and reference periods.

**Public services and infrastructure:** [austerity](austerity_data/README.md),
[NHS performance](nhs_data/README.md), and [rail performance](rail_data/README.md).
[Infrastructure investment, research funding and defence](investment_data/README.md)
compare five distinct spending measures as shares of GDP, with source limitations explicit.

**Household pressure:** [tax](tax/README.md), [tuition](tuition/README.md), and
[food-bank use](foodbank_data/README.md).

**Population and institutions:** [migration](uk_migration/README.md),
[ageing](age_data/README.md), [crime](crime_data/README.md), and
[institutional trust](trust_data/README.md).

## Working with the charts

Each analysis is a self-contained pipeline with its own methodology, caveats, charts, and
primary-source citations. The complete figure collection is in [`outputs/`](outputs).

Separate [page-background versions](outputs/page_background) use **#F5F5F5** to
match the article background. Filenames and analysis folders mirror the originals;
only opaque background pixels change, preserving chart colours, labels, dimensions
and transparency. Original plots are unchanged. Regenerate these copies after
rendering charts with:

```bash
./.venv/bin/python -m scripts.export_page_plots
```

Automatic source refreshes regenerate these versions too.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Each analysis runs as a module from the repo root, e.g.:

```bash
./.venv/bin/python -m europe_data.fetch_data      # fetch data -> data/
./.venv/bin/python -m europe_data.plot_uk_decline # figures -> outputs/gdp_income/
./.venv/bin/python -m markets_data                # UK vs US markets -> outputs/stock_markets/
./.venv/bin/python -m austerity_data              # austerity -> outputs/austerity/
./.venv/bin/python -m debt_data                   # debt/GDP and bond yields -> outputs/debt/
./.venv/bin/python -m unemployment_data           # UK overall and youth unemployment -> outputs/unemployment/
./.venv/bin/python -m foodbank_data               # food-bank use -> outputs/food_banks/
./.venv/bin/python -m sterling_data               # pound exchange rates -> outputs/sterling/
./.venv/bin/python -m trade_data                  # trade share of GDP -> outputs/trade/
./.venv/bin/python -m nhs_data                    # NHS -> outputs/nhs/
./.venv/bin/python -m rail_data                   # London rail delays -> outputs/rail/
./.venv/bin/python -m london_data                 # London's share of UK GDP -> outputs/london/
./.venv/bin/python -m crime_data                  # crime trend & homicide -> outputs/crime/
./.venv/bin/python -m ppp_data                    # PPP alternative view -> outputs/ppp/
```

See each analysis's README for its exact commands and full source citations.

## Data integrity
No API keys are required. Derived measures, source-published estimates, method breaks and coverage limitations 
are documented in each analysis. Downloaded/intermediate data generally lives under `data/`
(git-ignored, regenerable); cited historical input snapshots are tracked where needed.
The curated figures are under `outputs/` . Series reflecttheir available source vintages; 
revisions and missing observations can change future releases.
