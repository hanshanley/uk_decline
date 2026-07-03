# Age-distribution sub-analysis — how the UK is ageing: UK vs Europe vs US

Part of the `uk_decline` study. Shows **how the UK's age distribution has changed over
time** (1960–2024) — the population-ageing story — benchmarked against the **US** and
**European countries**.

> **Short answer:** the UK **is ageing, but more slowly than continental Europe.** The
> share aged **65+ rose from ~11.7% (1960) to ~19.5% (2024)**; the derived **median age
> rose to ~41**. Yet the UK remains **younger than the European median** (65+: 20.6%,
> median age ~43) and **older than the US** (65+: 17.9%, median age ~39).

## What it shows (three views)

| View | Metric(s) | Definition | Source |
|---|---|---|---|
| **Broad structure** | `pop_share_0_14_pct`, `pop_share_15_64_pct`, `pop_share_65plus_pct` | Share of the population in each broad age group | World Bank WDI |
| **Dependency** | `old_age_dependency_ratio`, `child_dependency_ratio` | 65+ (or 0–14) per 100 people of working age (15–64) | World Bank WDI |
| **Population pyramid** | `pop_band_share_pct` | Share of total population in each 5-year band, by sex | World Bank WDI |
| **Median age** | `median_age_years` | **Derived** from the 5-year band counts (see below) | derived from World Bank WDI |

"**Median** country" is the cross-country median of each metric — UK vs the median
European country vs US, computed in `age_data/stats.py`.

## Results (latest live run, 1960–2024; 2024 headline)

| Metric | UK | Europe median | Europe mean | US |
|---|---:|---:|---:|---:|
| Population aged 0–14 (%) | 17.2 | 15.0 | 15.2 | 17.3 |
| Population aged 15–64 (%) | 63.3 | 64.6 | 64.5 | 64.7 |
| Population aged 65+ (%) | **19.5** | 20.6 | 20.3 | 17.9 |
| Old-age dependency ratio | 30.8 | 31.9 | 31.9 | 27.7 |
| Child dependency ratio | 27.1 | 23.2 | 23.6 | 26.8 |
| Median age (years, *derived*) | **41.0** | 43.3 | 43.4 | 39.3 |

Full per-country, per-year data: `data/age_combined_long.csv` (tidy) and
`data/age_combined_wide.csv`. Run metadata + citations: `data/age_manifest.json`.

## Data sources — who actually collected the data

**All data is real and directly traceable.** The age-structure figures are **collected by
the United Nations Population Division** and **redistributed by the World Bank**; both are
credited in full below, in `data/age_manifest.json` (`citations` block), and in every
figure's source note. The pipeline fetches live from the free, key-less World Bank API;
every output row carries a `source` field.

**Primary source (data collector):**

> United Nations, Department of Economic and Social Affairs, Population Division (2024).
> *World Population Prospects 2024*. New York: United Nations.
> <https://population.un.org/wpp/>

**Access point (redistributor):**

> World Bank (2025). *World Development Indicators*. Washington, DC: The World Bank.
> <https://databank.worldbank.org/source/world-development-indicators>. Retrieved
> 2026-07-03 via the World Bank API (`https://api.worldbank.org/v2`), indicators `SP.POP.*`.

Indicators used: `SP.POP.0014.TO.ZS`, `SP.POP.1564.TO.ZS`, `SP.POP.65UP.TO.ZS`,
`SP.POP.DPND.OL`, `SP.POP.DPND.YG`, and the 5-year age-sex bands `SP.POP.{00-04…80UP}.{MA,FE}`.
Per the World Bank's own metadata, the 5-year age/sex bands are *"World Bank staff estimates
using the World Bank's total population and age/sex distributions of the United Nations
Population Division's World Population Prospects."*

You can reproduce any single number directly, e.g. the UK's 2024 share aged 65+:

```bash
curl -s "https://api.worldbank.org/v2/country/GBR/indicator/SP.POP.65UP.TO.ZS?format=json&date=2024:2024"
```

### Median age — a transparent derivation (not a published figure)

The World Bank does **not** publish median age, so it is **computed transparently from the
published 5-year age-band counts** — it is **not fabricated or modelled**. The method is the
standard *grouped median* (linear interpolation of the cumulative population distribution
within the band containing the 50th percentile):

```
median_age = L + ((50 − CF_below) / f_band) × 5
```

where `L` is the lower age bound of the median band, `CF_below` is the cumulative
population % below `L`, `f_band` is the band's % of the population, and 5 is the band width
(the open-ended 80+ band is treated as 80–85). Every derived row is tagged
`source = "World Bank WDI (derived: median from 5-year age bands)"` so it is never confused
with a published value, and it is fully reproducible from the same band counts. (See
`age_data/median_age.py`; a hand-verified derivation is covered in `tests/test_age.py`.)

### Offline fallback (`data/raw/manual_age.csv`)

For offline reproducibility, the pipeline falls back to `data/raw/manual_age.csv` **only**
when the live fetch returns nothing. **It is not hand-typed** — it is a verifiable
**snapshot of the live World Bank data** (latest-year broad structure + derived median age
for all countries, plus the UK pyramid bands for 1960 and 2024), each row keeping its World
Bank `source` + `year`.

## A note on inflation adjustment

**Not applicable.** Every metric here is a **share, ratio, or age (in years)** — there are
**no monetary (£/$/€) values anywhere**, so there is nothing to deflate, and inflation
adjustment would be meaningless. Age shares and dependency ratios are already comparable
across years and countries by construction.

## Run

```bash
# runtime deps in requirements.txt (requests, tenacity, tqdm, matplotlib); tests need pytest
.venv/bin/python -m age_data.fetch_age --start 1960 --end 2024     # live WB fetch + CSVs + charts
.venv/bin/python -m age_data.fetch_age --no-charts                 # data only
.venv/bin/python -m age_data.fetch_age --sources structure         # skip pyramids/median age
.venv/bin/python -m pytest tests/test_age.py -q
```

`fetch_age.py` prints a UK vs Europe-median vs US summary, writes the CSVs + manifest to
`data/`, and (by default) renders charts to `../outputs/age/`.

## Figures

Rendered by `age_data/charts.py` in the shared **Substack style** (matching the `tax`
section and `pre1870_reapportionment_package`). **Every figure carries a source note
crediting the UN Population Division & World Bank.** Written to `../outputs/age/`:

- `uk_age_structure_over_time.png` — stacked area, UK 0–14 / 15–64 / 65+ share, 1960–2024.
- `share_65plus_over_time.png` — % aged 65+ over time, UK vs Europe median vs US.
- `median_age_over_time.png` — derived median age over time, UK vs Europe median vs US.
- `uk_population_pyramid.png` — UK population pyramid, 1960 (outline) vs 2024 (filled).

## Layout (age sub-analysis files)

```
age_data/             # self-contained package
  config.py           #   countries/regions (reuses europe_data), WB indicators, bands, CITATIONS
  _http.py            #   pooled requests session with retry/backoff
  worldbank.py        #   broad age-structure shares + dependency ratios
  pyramids.py         #   5-year age-band population shares by sex
  median_age.py       #   transparent median-age derivation from band counts
  combine.py          #   tidy-row schema + long/wide CSV + manifest (with citations)
  stats.py            #   UK vs Europe-median/mean vs US aggregation
  fallback.py         #   offline loader for the manual_age.csv WB snapshot
  charts.py           #   figures in the shared Substack theme (with source notes)
fetch_age.py          # CLI: fetch -> derive median -> combine -> charts -> summary
data/raw/manual_age.csv         # verifiable snapshot of live WB data (each row cites source+year)
data/age_combined_long.csv      # tidy long output (every row carries its source)
data/age_combined_wide.csv      # one row per country-year, a column per metric variant
data/age_manifest.json          # run metadata: sources, citations, caveats
../outputs/age/                  # committable Substack-style figures (with source notes)
  uk_age_structure_over_time.png
  share_65plus_over_time.png
  median_age_over_time.png
  uk_population_pyramid.png
tests/test_age.py
```

## Caveats

- **Median age is derived, not published** — see the method above. It is a standard,
  reproducible interpolation on the published band counts, clearly labelled as derived.
- **Open-ended top band.** The oldest World Bank 5-year band is 80+; the pyramid shows it
  as a single bar and the median derivation treats it as 80–85.
- **European scope** reuses `europe_data`'s geographic-Europe list (transcontinental
  Turkey excluded); the "Europe median/mean" is unweighted across countries with data.
- **UN revisions.** Figures reflect the *World Population Prospects 2024* revision as
  redistributed by the World Bank; earlier revisions differ slightly. The access date is
  recorded in the manifest and figure notes.
