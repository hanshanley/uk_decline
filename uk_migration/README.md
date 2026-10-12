# uk_migration — UK immigration over time (legal + irregular)

Fetches and charts UK migration flows over time — immigration, emigration, net migration,
visas by category, asylum, and irregular arrivals — using **only real, publicly-sourced
data**. No values are hand-entered, interpolated, or synthesised; each traces to a source
below (full list in [`../outputs/migration/SOURCES.md`](../outputs/migration/SOURCES.md)).

## Headline results (figures in [`../outputs/migration/`](../outputs/migration))

![UK long-term immigration over time](../outputs/migration/immigration_over_time.png)

The ONS-only series shows the long-run rise without relying on the World Bank's modelled net
migration series: annual long-term immigration was roughly **200k in the 1960s–70s**, reached
about **600k by the mid-2000s**, and peaked at **1.44M in 2023** before falling to **813k in
2025**. The chart shows separate segments: IPS through 2011 and revised/admin-based
estimates from 2012, with a visible method-break marker and no line connecting the
two methods. ONS warns that these methods are not directly comparable; the jump
between segments must not be read as a measured year-on-year increase.

| File | Shows |
|---|---|
| `immigration_over_time.png` | ONS-only long-run immigration inflow, with the method break shown. |
| `net_migration.png` / `net_migration_per_capita.png` | ONS-only net migration, total and per-capita. |
| `immigration_vs_emigration.png` | Inflows vs outflows over time. |
| `immigration_by_origin.png` / `net_migration_by_origin.png` | Flows by citizenship/origin. |
| `visas_by_category.png` | Entry-clearance visas by category (Home Office). |
| `asylum_applications.png` | Asylum applications over time. |
| `irregular_arrivals.png` / `legal_vs_irregular.png` | Detected irregular arrivals (incl. small boats), and a separate comparison with total ONS long-term immigration—not a legal/illegal split. |

## Data sources & citations

- **Office for National Statistics (ONS)** — Long-Term International Migration
  (immigration, emigration, net migration), incl. the 1964–2015 IPS-by-citizenship series.
- **UK Home Office** — Immigration System Statistics (visas, asylum, irregular arrivals).
- **World Bank** — World Development Indicators `SP.POP.TOTL`, used only as the population
  denominator in per-capita charts. Its modelled migration series remains in the downloadable
  dataset for reference but is not plotted in the headline charts.

`*_per_1000_pop` / per-capita series are **derived** (flow ÷ World Bank population × 1000).
Home Office annual series omit categories with incomplete quarterly coverage. An
all-method irregular total is published only if every method observed that year has
four quarters; complete small-boat figures cannot disguise partial air-arrival data.
Detected arrivals are not the entire irregular population. Total ONS immigration has
a different long-term residence definition and is not a legal-only count: these
measures are not a mutually exclusive legal/illegal partition.

Migration figures are counts, so no CPI/inflation adjustment applies. Full citations
with URLs: [`../outputs/migration/SOURCES.md`](../outputs/migration/SOURCES.md).

## Usage

```bash
python -m uk_migration.run                 # fetch + chart -> ../outputs/migration/
python -m uk_migration.run --no-charts     # data only
```

Raw/intermediate data lands in `../data/` (git-ignored); charts and `SOURCES.md` in
`../outputs/migration/`.

## Modules
`run.py` (CLI) · `combine.py` · `normalize.py` · `charts.py` · `schema.py` · `_aggregate.py` ·
`_govuk.py` · `_spreadsheet.py` · `_http.py`. Tests: `../tests/` (`test_uk_migration`, etc.).
