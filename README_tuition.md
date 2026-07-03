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

## Historical trend — real (inflation-adjusted) tuition back to the 1970s

The snapshot above is a nominal cross-section. The **fully primary-sourced, inflation-
adjusted** view is the historical series in **constant 2022 USD** (`outputs/tuition_history_real_usd.png`):

| Year | UK (England cap) | US (public in-state) | Germany |
|---|---:|---:|---:|
| 1971 | $0 (free) | $3,115 | $0 |
| 1998 | $2,082 | ~$5,880 | $0 |
| 2012 | **$13,919** | $10,454 | $0 |
| 2022 | $11,401 | $9,750 | $0 |

**Key finding:** in real terms the UK went from **free (until 1998)** to **overtaking US
public college in 2012** ($13,919 vs $10,454), peaking then; the £9,250 cap has been frozen
since 2017, so its *real* value has since eroded to ~$11,401 — still above the US public
in-state figure ($9,750, 2022). Germany (representative EU) has stayed free throughout.

Historical data: `data/processed/tuition_history.csv`.

## Data sources & provenance

Every figure is traceable to the source below (each output CSV row carries `source` /
`source_url`). **Primary** = fetched/derived from an authoritative primary dataset;
**secondary** = compiled from a published summary of the primary report (flagged for
verification in-row).

| Series | Source | Access | Provenance |
|---|---|---|---|
| US tuition history + snapshot | **NCES** Digest 2023, Table 330.10 (Public 4-year, in-district) — current & **constant 2022-23 $** (BLS CPI) | `fetch_nces.py` downloads & parses the real table ([link](https://nces.ed.gov/programs/digest/d23/tables/dt23_330.10.asp)); raw HTML cached in `data/raw/sources/` | **primary** |
| UK fee-cap history | England statutory caps — Acts / SIs on **legislation.gov.uk** (1998, 2004, 2010, 2016) + House of Commons Library CBP-8151 | `data/raw/tuition_history_manual.csv` (per-row `source_url`) | **primary** (statutory) |
| Inflation & FX | **World Bank** CPI `FP.CPI.TOTL`, exchange rate `PA.NUS.FCRF`, PPP `PA.NUS.PPP` (keyless API) | `tuition/rates.py` (`fetch_series`) | **primary** |
| EU-27 snapshot fees | **Eurydice** *National Student Fee & Support Systems 2023/24* | `data/raw/manual_tuition.csv` | **secondary** (summary; a few rows flagged `APPROXIMATE`) |
| Germany history | German HE fee history / Eurydice | `data/raw/tuition_history_manual.csv` | secondary |

> **Honesty note:** the EU-27 snapshot fees come from a published *summary* of the Eurydice
> report, not the primary PDF; three rows that could not be pinned to an exact primary
> figure (Bulgaria, Spain, and Belgium's blended communities) are marked `APPROXIMATE` in
> their `notes`. The **historical US/UK/Germany series is fully primary-sourced and
> inflation-adjusted**, and is the most defensible basis for the UK-vs-US comparison.

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
3. **Currency normalization** — `tuition/rates.py` pulls live **World Bank** rates
   (`PA.NUS.FCRF` exchange rate, `PA.NUS.PPP` PPP factor, `FP.CPI.TOTL` CPI; no API key).
   Offline fallback FX/PPP tables live in `tuition/config.py` (snapshot only — the
   historical deflators have no fabricated fallback).
4. **Aggregation** — `analyze.py` computes per-region median & average (annual and ×4).

## Run

```bash
# runtime deps in requirements.txt (requests, tenacity, matplotlib, pandas, lxml); tests need pytest
# --- current cross-sectional snapshot ---
.venv/bin/python build_dataset.py      # fetch WB rates + normalize  (--offline to skip network)
.venv/bin/python analyze.py            # print table + write summary.csv
.venv/bin/python plot_tuition.py       # snapshot figures -> outputs/  (add --ppp for PPP variants)

# --- historical, inflation-adjusted series (back to the 1970s) ---
.venv/bin/python fetch_nces.py         # download + parse the real NCES US tuition table
.venv/bin/python build_history.py      # combine NCES US + UK caps + Germany, deflate to real 2022 USD
.venv/bin/python plot_history.py       # historical chart -> outputs/tuition_history_real_usd.png

.venv/bin/python -m pytest tests/test_tuition.py -q
```

## Figures (written to `outputs/`)

All figures use the shared Substack style (matching `pre1870_reapportionment_package`) and
carry an italic **source note citing the data provenance**:

- `tuition_history_real_usd.png` — real (constant 2022 USD) tuition 1963/71→2022, UK vs US
  vs Germany. *(the primary-sourced, inflation-adjusted headline chart)*
- `tuition_region_comparison.png` — average & median annual tuition, UK vs EU-27 vs US.
- `tuition_by_country.png` — per-country ranking, colored by region.
- `*_ppp.png` — PPP-adjusted variants of the two snapshot charts.

## Layout (tuition sub-analysis files)

```
tuition/            # self-contained package
  config.py         #   countries, regions, sources/URLs, paths, fallback rates
  http.py           #   pooled requests session with retry/backoff
  rates.py          #   World Bank FX + PPP + CPI fetchers (fetch_series)
  stats.py          #   median/average + per-region aggregation
  dataset.py        #   shared primary-row loader (filter + value coercion)
  theme.py          #   shared Substack plotting theme
fetch_nces.py       # download + parse the real NCES US tuition table (primary source)
fetch_oecd.py       # best-effort OECD SDMX pull
fetch_eurostat.py   # best-effort Eurostat/Eurydice pull
build_dataset.py    # snapshot: merge curated + fetched, convert to USD/PPP-USD
build_history.py    # historical: NCES US + UK caps + Germany -> real 2022 USD
analyze.py          # per-region median & average + verdict
plot_tuition.py     # snapshot figures -> outputs/
plot_history.py     # historical real-USD figure -> outputs/
data/raw/           # manual_tuition.csv, tuition_history_manual.csv, nces_*.csv,
                    #   wb_rates.csv, sources/ (cached raw NCES HTML)
data/processed/     # tuition_by_country.csv, summary.csv, tuition_history.csv
outputs/            # generated PNG figures
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
