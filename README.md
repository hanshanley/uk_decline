# Social, Economic, and Political Decline in the United Kingdom

A data-driven look at the **United Kingdom's relative decline** across the economy, financial
markets, public services, and society — benchmarked against the US and European peers.

Every analysis is a **self-contained, reproducible pipeline** that pulls **only real,
publicly-sourced data** from official APIs (World Bank, OECD, Eurostat, ONS, UK Home Office,
UN Population Division via the World Bank, Maddison Project Database). **No values are
hand-entered, mocked, interpolated, or synthesised** — each figure traces to a cited source,
and monetary series are inflation-adjusted (real) unless explicitly labelled nominal.

## Analyses

| Analysis | Folder | What it shows |
|---|---|---|
| GDP & incomes | [`europe_data/`](europe_data/README.md) | Real GDP per capita & median incomes: UK vs US/Europe |
| Stock markets | [`markets_data/`](markets_data/README.md) | UK vs US listed-market size (cap, % of GDP, listings) |
| NHS | [`nhs_data/`](nhs_data/README.md) | NHS waiting times & lists across the four nations |
| Tax burden | [`tax/`](tax/README.md) | Tax-to-GDP, tax wedge: UK vs Europe vs US |
| Tuition | [`tuition/`](tuition/README.md) | Cost of a four-year degree: UK vs EU vs US |
| Institutional trust | [`trust_data/`](trust_data/README.md) | Trust in government & governance indicators |
| Migration | [`uk_migration/`](uk_migration/README.md) | UK immigration over time (legal + irregular) |
| Ageing | [`age_data/`](age_data/README.md) | Age structure & median age: UK vs US/Europe |

All output images live in one place: **[`outputs/`](outputs)**, one subfolder per analysis.

## Key results

**The whole thesis in one image — a scorecard of eight measures:**

![The UK in relative decline — a scorecard](outputs/uk_decline_scorecard.png)

Each measure below in detail.

### GDP per capita — the US pulls away, and even Poland is catching up
![Real GDP per capita relative to the UK (UK = 100)](outputs/gdp_income/uk_gdp_relative_to_peers.png)
In real terms (constant 2015 US$), the UK drew level with the US in 2007 — but the US then
surged to **162% of the UK by 2024**, while **Poland climbed from 9% to 47%** of UK GDP per
capita. *Source: World Bank WDI (NY.GDP.PCAP.CD deflated by US CPI, FP.CPI.TOTL), constant 2015 US$.*

### Stock market — the UK shrinks against the US
![UK/US stock-market cap ratio (real)](outputs/stock_markets/stock_uk_us_ratio_market_cap_usd_real.png)
UK listed-market capitalisation fell from a peak of **~27% of the US (1990) to ~8% (2022)**,
and the number of UK-listed companies has nearly halved since its 2006 peak.
*Source: World Federation of Exchanges via World Bank WDI.*

### NHS — waiting lists have ballooned, and per-head the smaller nations fare worst
![NHS RTT waiting list per 1,000 people](outputs/nhs/rtt_waiting_list_per_1000.png)
Adjusted for population, the referral-to-treatment waiting list has roughly doubled across all
four nations — and **Wales (251) and Northern Ireland (240 per 1,000) now exceed England (128)**.
*Source: NHS England / Public Health Scotland / StatsWales / DoH Northern Ireland.*

### Tax burden — rising tax-to-GDP
![Tax-to-GDP over time](outputs/tax/tax_to_gdp_over_time.png)
*Source: OECD Revenue Statistics & Taxing Wages.*

### Tuition — a UK degree now costs as much as a US one
![Tuition: UK vs US vs EU-27](outputs/tuition/tuition_region_comparison_real.png)
UK annual tuition (~$11.4k) now matches the US, while most of the EU remains free.
*Source: Eurydice / NCES / UK fee cap; constant 2022 USD (CPI-adjusted).*

### Institutional trust — confidence in government
![Trust in national government](outputs/trust/trust_national_govt_pct.png)
*Source: OECD / Gallup World Poll via Our World in Data.*

### Ageing — median age rises
![UK median age over time](outputs/age/median_age_over_time.png)
*Source: UN Population Division via World Bank WDI.*

*(The repo also includes a standalone [UK migration](uk_migration/README.md) analysis, presented
descriptively — migration is **not** framed here as a measure of "decline".)*

## Repository layout

```
uk_decline/
  europe_data/   markets_data/   nhs_data/   tax/
  tuition/       trust_data/     uk_migration/   age_data/
      └─ each: analysis code + README.md (+ CITATIONS where relevant)
  outputs/       # ALL figures, one subfolder per analysis (tracked; render on GitHub)
    gdp_income/  stock_markets/  nhs/  tax/  tuition/  trust/  migration/  age/
  data/          # raw / intermediate inputs (git-ignored, regenerable)
  tests/         # test suites
  requirements.txt
```

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
./.venv/bin/python -m nhs_data                    # NHS -> outputs/nhs/
```

See each analysis's README for its exact commands and full source citations.

## Data integrity
No API keys are required, and no data is fabricated. Downloaded raw data lives under `data/`
(git-ignored, regenerable); the curated, citation-bearing figures under `outputs/` are the
committed showcase. Values have been spot-checked against the live official APIs.
