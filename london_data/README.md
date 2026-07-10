# london_data — London's concentration of UK GDP

How much of the UK's economic output is produced in **London**, and how far the capital
sits above the rest of the country — the regional-imbalance strand of the "UK decline"
story, using the authoritative **Office for National Statistics (ONS)** regional GDP data.

## The story

| Measure | What it is | Trend (1998 → 2023) |
|---|---|---|
| **Share of UK GDP** (`share_of_uk_gdp_pct`) | London's GDP ÷ UK GDP | **Risen: 19.6% → 22.7%.** Nearly a quarter of all UK output is now produced in London (~13% of the population). |
| **GDP per head vs UK** (`gdp_per_head_index_uk100`) | London GDP/head ÷ UK GDP/head (UK = 100) | **Widened: 162 → 173** — i.e. from ~1.62× to ~1.73× the UK average. |

Both point the same way: economic activity has become **more**, not less, concentrated in
London over the past quarter-century — one of the widest capital-vs-nation gaps of any large
advanced economy.

## Why nominal (current-price) figures are correct here

Both headline measures are **same-year ratios** (London ÷ UK, in the same year). The
numerator and denominator share the same price base, so **inflation cancels** — there is no
nominal-vs-real distortion, and deflating would change nothing. Current-price £ levels are
therefore the correct, standard input. (The raw £ levels are also emitted in the CSV for
transparency.)

## Data source

- **Office for National Statistics (ONS)** — *Regional economic activity by gross domestic
  product, UK*, dataset **"Regional gross domestic product: all ITL regions"**.
  <https://www.ons.gov.uk/economy/grossdomesticproductgdp/datasets/regionalgrossdomesticproductallnutslevelregions>
- Tables used: **Table 5** (GDP at current market prices, £m) and **Table 7** (GDP per head
  at current market prices, £). London is the **ITL1** region (ONS code `TLI`); the UK total
  is the workbook's `UK` row.
- `ons.py` resolves the newest `.xlsx` edition on the dataset page automatically (falling
  back to a pinned URL), so re-running picks up future ONS revisions.
- Full citation: [`CITATIONS.md`](CITATIONS.md).

**Data vintage:** the ONS annual ITL series currently ends at **2023** (edition released
2025-04-17). Regional *annual* GDP requires the full annual UK supply-use balancing, so it
lags ~1.5 years: per the ONS release calendar, the **1998→2024** edition is scheduled for
**23 September 2026** (the prior editions landed 1998→2022 in Apr 2024 and 1998→2023 in Apr
2025). No 2024 outturn exists anywhere before then — verified across the annual regional GDP
dataset, the regional GVA(balanced) dataset (also ends 2023), the ONS CMD data API
(`regional-gdp-by-year`, stale at 2021), and direct-guessed `1998to2024` URLs (404). The
quarterly regional product can't substitute (ONS discontinued it — an "update on reinstating
quarterly regional GDP estimates" is due 2026-07-31 — and it excludes Scotland & NI and is an
index, not £ levels, so no UK-wide share can be formed). 1998–2023 is therefore the maximum
defensible range; no later values are estimated, nowcast, or fabricated.

## Run

```bash
# fetch ONS data, write data/london_gdp.csv, render charts to outputs/london/
./.venv/bin/python -m london_data

# rebuild charts from an existing CSV (no fetch):
./.venv/bin/python -m london_data --from-csv data/london_gdp.csv

# report the latest official edition and the next scheduled release
./.venv/bin/python -m london_data --status

# after publication, refresh and refuse to accept an older edition silently
./.venv/bin/python -m london_data --require-year 2024
```

The resolver selects the highest `1998toYYYY` edition linked by ONS, so no code change is
needed when the September 2026 release appears. `--require-year` turns stale data into an
explicit failure rather than silently rebuilding a chart that still ends in 2023.

## Outputs

- `data/london_gdp.csv` — tidy long table: `region, year, metric, value, unit, source`
  (metrics: `gdp_current_gbp_m`, `share_of_uk_gdp_pct`, `gdp_per_head_gbp`,
  `gdp_per_head_index_uk100`). Git-ignored, regenerable.
- `outputs/london/london_share_of_uk_gdp.png` — London's % of UK GDP over time.
- `outputs/london/london_gdp_per_head_vs_uk.png` — London GDP per head as an index (UK = 100).

Charts follow the shared house style (warm tan background, serif type, London in the
terracotta accent, italic ONS source note).
