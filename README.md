# uk_decline

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

### GDP per capita — the US pulls away from the UK
![UK GDP per capita relative to the US and Germany](outputs/gdp_income/uk_gdp_relative_to_peers.png)
UK real GDP per capita slid from **~83% of the US in 2007 to ~72% in 2024** (it stays above
Germany). *Source: World Bank, World Development Indicators (NY.GDP.PCAP.KD), constant 2015 US$.*

### Stock market — the UK shrinks against the US
![UK/US stock-market cap ratio (real)](outputs/stock_markets/stock_uk_us_ratio_market_cap_usd_real.png)
UK listed-market capitalisation fell from a peak of **~27% of the US (1990) to ~8% (2022)**.
*Source: World Federation of Exchanges via World Bank WDI (CM.MKT.LCAP.CD).*

### NHS — waiting lists balloon
![NHS RTT waiting list total](outputs/nhs/rtt_waiting_list_total.png)
*Source: NHS England / StatsWales / Public Health Scotland / NI Dept of Health.*

### Tax burden — rising tax-to-GDP
![Tax-to-GDP over time](outputs/tax/tax_to_gdp_over_time.png)
*Source: OECD Revenue Statistics & Taxing Wages.*

### Tuition — the cost of a UK degree
![Tuition region comparison (real)](outputs/tuition/tuition_region_comparison_real.png)
*Source: World Bank / NCES / national caps; constant 2022 USD (CPI-adjusted).*

### Institutional trust — confidence in government
![Trust in national government](outputs/trust/trust_national_govt_pct.png)
*Source: OECD & World Bank Worldwide Governance Indicators.*

### Migration — net migration over time
![UK net migration](outputs/migration/net_migration.png)
*Source: ONS Long-Term International Migration; UK Home Office.*

### Ageing — median age rises
![UK median age over time](outputs/age/median_age_over_time.png)
*Source: World Bank WDI (UN Population Division data).*

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
