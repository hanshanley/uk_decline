# Tax-burden sub-analysis — average & median tax burden: UK vs Europe vs US

Part of the `uk_decline` study. Measures the **average** and **median** tax burden on
people in the **UK**, benchmarked against the **US** and **European countries**, using
two complementary lenses.

> **Short answer:** the UK's tax burden sits **clearly below the European median/average
> on every measure, and roughly level with the US.** In 2024 the UK's total tax take was
> **34.4% of GDP** (Europe median **38.0%**, US **25.6%**), and the labour tax wedge on an
> average-wage single worker was **29.9%** (Europe median **41.0%**, US **30.1%**).

## What "tax burden" means here (two lenses)

| Lens | Metric | Definition | Source |
|---|---|---|---|
| **Macro** | `tax_to_gdp_pct` | Total tax revenue **incl. social security contributions**, general government, as a share of GDP (net basis) | OECD *Revenue Statistics* |
| **Individual** | `tax_wedge_pct` | Income tax + employee **and employer** SSC − cash benefits, as a share of **total labour cost** | OECD *Taxing Wages* |
| **Individual** | `net_personal_avg_tax_rate_pct` | Income tax + employee SSC − cash benefits, as a share of **gross wage** ("what the worker feels") | OECD *Taxing Wages* |

"**Median**" is answered two ways: (a) the **cross-country median** of each metric — UK vs
the median European country vs US, computed in `tax/stats.py`; and (b) the **average-wage
tax wedge** as the standard proxy for the typical/median worker. The individual metrics are
reported at **67% / 100% / 167% of the average wage** (a single person, no children) plus a
**one-earner married couple with 2 children** at 100% AW.

## Results (latest live run, 2015–2024)

Headline comparison, latest year with data per metric:

| Metric (single worker at avg wage unless noted) | Year | UK | Europe median | Europe mean | US |
|---|---:|---:|---:|---:|---:|
| Total tax revenue (% of GDP) | 2024 | **34.4%** | 38.0% | 37.5% | 25.6% |
| Labour tax wedge — 67% AW | 2024 | **25.6%** | 36.3% | 35.8% | 27.6% |
| Labour tax wedge — 100% AW | 2024 | **29.9%** | 41.0% | 40.3% | 30.1% |
| Labour tax wedge — 167% AW | 2024 | **37.7%** | 44.5% | 44.7% | 34.4% |
| Labour tax wedge — one-earner couple, 2 kids, 100% AW | 2024 | **26.1%** | 32.0% | 29.2% | 20.1% |
| Net personal avg tax rate — 100% AW | 2024 | **21.9%** | 27.9% | 28.6% | 24.4% |

Full per-country data: `data/tax_combined_long.csv` (tidy) and `data/tax_combined_wide.csv`
(one row per country-year). Run metadata + source list: `data/tax_manifest.json`.

## Data sources — everything is real and traceable

**All figures come live from the OECD, via the free, key-less OECD SDMX REST API.** Nothing
is hand-authored, modelled, or estimated by this project. Every output row carries a
`source` column naming the exact OECD dataset it came from.

**Proper citations** (the organisation that collected the data — also in
`data/tax_manifest.json` under `citations`, and on every figure's source note):

> OECD (2024). *Revenue Statistics — Comparative tables*. OECD Tax Statistics (database).
> Paris: Organisation for Economic Co-operation and Development. Retrieved 2026-07-03 via
> the OECD SDMX API (`https://sdmx.oecd.org/public/rest/data`), dataflow
> `OECD.CTP.TPS,DSD_REV_COMP_OECD@DF_RSOECD,2.0`.
>
> OECD (2024). *Taxing Wages — Comparative tables*. OECD Tax Statistics (database). Paris:
> Organisation for Economic Co-operation and Development. Retrieved 2026-07-03 via the OECD
> SDMX API, dataflow `OECD.CTP.TPS,DSD_TAX_WAGES_COMP@DF_TW_COMP,2.1`.

| Source | OECD SDMX dataflow | Exact query key |
|---|---|---|
| Revenue Statistics (comparative) | `OECD.CTP.TPS,DSD_REV_COMP_OECD@DF_RSOECD,2.0` | `{areas}.TAX_REV.S13._T._T.PT_B1GQ.A` |
| Taxing Wages (comparative) | `OECD.CTP.TPS,DSD_TAX_WAGES_COMP@DF_TW_COMP,2.1` | `{areas}.{AV_TW\|NPATR}.{PT_COS_LB\|PT_WG_EARN_G}.{S_C0\|C_C2}.{AW67\|AW100\|AW167}..A` |

- **Endpoint:** `https://sdmx.oecd.org/public/rest/data/{dataflow}/{key}?startPeriod=…&endPeriod=…&format=csvfilewithlabels`
- **Revenue Statistics** dimensions pinned: general government (`S13`), total tax revenue
  (`_T`), percentage of GDP (`PT_B1GQ`) — exactly one observation per country-year.
- **Taxing Wages** family types are pinned so every value maps to **one** OECD household:
  singles have no spouse (`INCOME_SPOUSE=_Z`); the couple variant is the standard
  **one-earner** married couple (spouse not employed, `INCOME_SPOUSE=NOEARN_UNEMP`). This
  avoids collapsing the several spouse-income configurations OECD publishes for couples.

You can reproduce any single number directly, e.g. the UK's 2024 tax wedge at the average wage:

```bash
curl -s "https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_WAGES_COMP@DF_TW_COMP,2.1/GBR.AV_TW.PT_COS_LB.S_C0.AW100._Z.A?startPeriod=2024&endPeriod=2024&format=csvfilewithlabels"
```

### Offline fallback (`data/raw/manual_tax.csv`)

For offline reproducibility (and CI), the pipeline can fall back to
`data/raw/manual_tax.csv`. **This file is not hand-typed data** — it is a verifiable
**snapshot of the live OECD data** (latest year, all 27 countries, the headline variants),
regenerated from `data/tax_combined_long.csv`. Every row keeps its OECD `source` + `year`,
so it traces back to the same API. The fallback is used **only** when the live fetch returns
nothing, and each source only ever contributes its own metrics (no cross-source mixing).

## A note on inflation adjustment

**No inflation adjustment is needed — and applying one would be wrong here.** Every metric
in this analysis is a **ratio / percentage**, not a monetary amount:

- `tax_to_gdp_pct` = tax revenue ÷ GDP (both nominal, same year → the price level cancels).
- `tax_wedge_pct` = taxes ÷ total labour cost (same year → price level cancels).
- `net_personal_avg_tax_rate_pct` = taxes ÷ gross wage (same year → price level cancels).

Because numerator and denominator are in the **same year's currency**, these ratios are
inherently **inflation-neutral and directly comparable across years and countries**. There
are **no nominal currency (£/$/€) values** anywhere in the outputs, so there is nothing to
deflate. (Had we reported, say, tax **paid in pounds**, we would deflate by CPI — but that
is deliberately not a metric here.) Cross-country comparability is instead handled by the
OECD's own harmonised definitions; where a level isn't strictly apples-to-apples, the
`tax_manifest.json` `caveats` block documents it.

## Run

```bash
# runtime deps in requirements.txt (requests, tenacity, tqdm, matplotlib); tests need pytest
.venv/bin/python -m tax.fetch_tax --start 2015 --end 2024     # live OECD fetch + CSVs + charts
.venv/bin/python -m tax.fetch_tax --no-charts                 # data only
.venv/bin/python -m pytest tests/test_tax.py -q
```

`fetch_tax.py` prints a UK vs Europe-median vs US summary, writes the CSVs + manifest to
`data/`, and (by default) renders charts to `../outputs/tax/`.

## Figures

Charts are rendered by `tax/charts.py` in the shared **Substack style** (matching
`pre1870_reapportionment_package`: cream `#F7F5F0` background, serif type, muted grid, bold
titles, italic source note, `dpi=200`). Every figure carries a **source note citing OECD
Revenue Statistics & Taxing Wages**. Written to `../outputs/tax/`:

- `tax_burden_headline_bars.png` — UK / Europe median / US across the three headline metrics.
- `tax_to_gdp_over_time.png` — total tax revenue (% of GDP), UK vs Europe median vs US, 2015–2024.
- `tax_wedge_by_earnings.png` — single-worker tax wedge at 67 / 100 / 167% of the average wage.

## Layout (tax sub-analysis files)

```
tax/                  # self-contained package
  config.py           #   countries (UK/US/25 European), OECD dataflow keys, metric defs, paths
  _http.py            #   pooled requests session + OECD SDMX csvfilewithlabels helper
  revenue.py          #   OECD Revenue Statistics fetcher (tax-to-GDP)
  taxing_wages.py     #   OECD Taxing Wages fetcher (tax wedge + net personal avg tax rate)
  combine.py          #   tidy-row schema + long/wide CSV + manifest writers
  stats.py            #   UK vs Europe-median/mean vs US aggregation
  fallback.py         #   offline loader for the manual_tax.csv OECD snapshot
  charts.py           #   figures in the shared Substack theme
fetch_tax.py          # CLI: fetch -> combine -> charts -> summary
data/raw/manual_tax.csv         # offline snapshot of live OECD data (each row cites OECD source+year)
data/tax_combined_long.csv      # tidy long output (every row carries its OECD source)
data/tax_combined_wide.csv      # one row per country-year, a column per metric variant
data/tax_manifest.json          # run metadata: sources, years, countries, caveats
../outputs/tax/                  # committable Substack-style figures (with OECD source notes)
  tax_burden_headline_bars.png
  tax_to_gdp_over_time.png
  tax_wedge_by_earnings.png
tests/test_tax.py
```

## Caveats

- **Two different burdens.** Tax-to-GDP is a **macro** ratio for the whole economy (income,
  payroll, VAT, corporate, property). The tax wedge / net personal rate are **modelled for a
  stylised worker** — they do **not** include VAT/consumption taxes. They answer different
  questions; read them together.
- **"Median worker" proxy.** OECD does not publish a per-country **median-earner** wedge, so
  the **average-wage** worker is used as the standard proxy. The 67% / 167% AW rows bracket
  lower- and higher-paid workers.
- **European scope.** 25 European OECD members are included (see `tax/config.py`).
  Transcontinental Turkey is excluded, matching the geographic-Europe scope of the sibling
  `europe_data` package. The "Europe median/mean" is unweighted across these countries.
- **Reporting vintages differ.** OECD releases arrive at different times per country; the
  summary/charts pin the latest year for which the **UK (then US)** has data so the headline
  is never blanked by a single country reporting one year ahead.
- **Comparability.** OECD harmonises these series, but definitions still differ at the
  margin; per-metric caveats are recorded in `data/tax_manifest.json`.
