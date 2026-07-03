# Tuition sub-analysis — cost of a four-year degree: UK vs EU vs US

Part of the `uk_decline` study. Determines the **median** and **average** cost of a
four-year bachelor's degree across the **UK**, the **EU-27**, and the **US**, to test the
claim that *the UK has a higher average cost of degrees*.

> **Short answer: yes.** On **domestic, tuition-only** figures, the UK's average annual
> tuition (~**$12,179**, England's £9,250 cap) is **higher than both** the EU-27 average
> (~**$424/yr**, median **$0**) and the US average published **in-state public** tuition
> (~**$11,610/yr**). See caveats — the picture flips for US *private* colleges.

## Scope

| Dimension | Choice |
|---|---|
| Cost | **Tuition / fees only** (no living costs) |
| Cohort | **Domestic / in-country (EU) students** at public institutions |
| Regions | **UK** (own category), **EU-27**, **US** |
| Aggregation | **Per country, unweighted** median & average |
| "Four-year" | annual tuition **× 4** (bachelor's are often 3 yrs in UK/EU — normalized) |
| Currency | normalized to **USD** (nominal) and **PPP-adjusted USD** |

## Results

Latest run (nominal USD, annual domestic tuition, one figure per country):

| Region | n | Avg / yr | Median / yr | Avg 4-yr | Median 4-yr |
|---|---:|---:|---:|---:|---:|
| **UK** | 1 | $12,179 | $12,179 | $48,718 | $48,718 |
| **EU-27** | 27 | $424 | $0 | $1,697 | $0 |
| **US** | 1 | $11,610 | $11,610 | $46,440 | $46,440 |

PPP-adjusted USD tells the same story (UK ~$13,661/yr, EU-27 ~$629/yr, US ~$11,610/yr).

Full per-country data: `data/processed/tuition_by_country.csv`.
Region summary: `data/processed/summary.csv`.

## How it works (hybrid data pipeline)

1. **Curated source of truth** — `data/raw/manual_tuition.csv`: domestic annual
   first-cycle tuition per country, each row carrying its own `source` + `year`.
   EU-27 from the **Eurydice** *National Student Fee and Support Systems 2023/24*
   report; US from **College Board** *Trends in College Pricing 2024*; UK from the
   statutory England fee cap.
2. **Automated fetchers (best-effort)** — `fetch_oecd.py`, `fetch_eurostat.py` attempt
   the OECD SDMX / Eurostat APIs. Neither publishes a clean per-student *tuition-fee*
   series (OECD EAG is Excel/PDF; Eurostat covers expenditure, not statutory fees), so
   they defer to the curated CSV and only *fill* countries missing from it.
3. **Currency normalization** — `tuition/rates.py` pulls live **World Bank** rates
   (`PA.NUS.FCRF` exchange rate, `PA.NUS.PPP` PPP factor; no API key) to convert every
   figure to USD and PPP-USD. Offline fallback tables live in `tuition/config.py`.
4. **Aggregation** — `analyze.py` computes per-region median & average (annual and ×4).

## Run

```bash
# runtime deps in requirements.txt (requests, tenacity, matplotlib); tests need pytest
.venv/bin/python fetch_oecd.py         # optional, best-effort
.venv/bin/python fetch_eurostat.py     # optional, best-effort
.venv/bin/python build_dataset.py      # fetch WB rates + normalize  (--offline to skip network)
.venv/bin/python analyze.py            # print table + write summary.csv
.venv/bin/python plot_tuition.py       # figures (nominal); add --ppp for PPP-adjusted
.venv/bin/python -m pytest tests/test_tuition.py -q
```

## Figures

`plot_tuition.py` writes to `data/processed/` in the shared Substack style (matching
`pre1870_reapportionment_package`): `tuition_region_comparison.png` (average & median
annual tuition, UK vs EU-27 vs US) and `tuition_by_country.png` (per-country ranking,
colored by region). Pass `--ppp` for the PPP-adjusted variants (`*_ppp.png`).

## Layout (tuition sub-analysis files)

```
tuition/            # self-contained package
  config.py         #   countries (EU-27/UK/US), regions, sources, paths, fallback rates
  http.py           #   pooled requests session with retry/backoff
  rates.py          #   World Bank FX + PPP fetcher
  stats.py          #   median/average + per-region aggregation
  dataset.py        #   shared primary-row loader (filter + value coercion)
  theme.py          #   shared Substack plotting theme
fetch_oecd.py       # best-effort OECD SDMX pull
fetch_eurostat.py   # best-effort Eurostat/Eurydice pull
build_dataset.py    # merge curated + fetched, convert to USD/PPP-USD
analyze.py          # per-region median & average + verdict
plot_tuition.py     # figures in the shared Substack style
data/raw/manual_tuition.csv   # curated source of truth (+ fetched raw + wb_rates.csv)
data/processed/     # tuition_by_country.csv, summary.csv, *.png figures
tests/test_tuition.py
```

## Caveats

- **US private colleges are excluded from the headline.** Average published US *private
  nonprofit* tuition is ~**$43,350/yr** — far above the UK. "Domestic US cost" here means
  the **in-state public** figure most students face; the private figure is kept as a
  reference row (`include_primary=0`).
- **UK is nation-split.** The headline is **England (£9,250)**; **Scotland** charges
  Scottish-domiciled students **£0** (reference row). **Wales** tracks England closely
  (~£9,000), but **Northern Ireland** caps NI-domiciled fees materially lower (~£4,750).
- **Many EU states charge €0** for domestic students (Germany, the Nordics, etc.). These
  zeros are legitimate data points and are kept, which is why the EU **median is $0**.
- **3-vs-4-year programmes.** Most UK/EU bachelor's are 3 years; the ×4 total is a
  normalized comparison, not literal programme length.
- **Reference years differ** (EU 2023/24, US & UK 2024/25) and FX/PPP use the latest
  World Bank year available per country; these are recorded per row in the outputs.
- Figures are **most-common statutory fees**, not enrollment-weighted averages.
