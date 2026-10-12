# london_data — London's concentration of UK GDP

How much of the UK's economic output is produced in **London**, and how far the capital
sits above the rest of the country — the regional-imbalance strand of the "UK decline"
story, using the authoritative **Office for National Statistics (ONS)** regional GDP data.

## The story

| Measure | What it is | Trend (1998 → 2024) |
|---|---|---|
| **Share of UK GDP** (`share_of_uk_gdp_pct`) | London's GDP ÷ UK GDP | **Risen: 19.6% → 22.8%.** Nearly a quarter of all UK output is produced in London. |
| **GDP per head vs UK** (`gdp_per_head_index_uk100`) | London GDP/head ÷ UK GDP/head (UK = 100) | **Widened: 162 → 173** — i.e. from ~1.62× to ~1.73× the UK average. |

These figures and regenerated charts use the 1998–2024 edition, retrieved 12 October 2026.
GDP per head is GDP divided by residents, not income per resident or productivity per worker:
commuters contribute to London's output but are counted as residents elsewhere.

## Why nominal (current-price) figures are correct here

Both headline measures are **same-year ratios** (London ÷ UK, in the same year). The
figures measure **nominal concentration**. Applying the same national deflator to both
would cancel, but region-specific price movements need not cancel. Changes in these
ratios can reflect relative prices as well as real activity: they are not measures of
real-output concentration. Raw £ levels are emitted in the CSV for transparency.

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

**Availability checked 12 October 2026:** ONS published the **1998–2024** edition on
**23 September 2026**. Its notice suppresses some ITL2 and lower-level estimates while
correcting geography conversion, but explicitly says **ITL1 countries and regions are
unaffected**, including London. The resolver uses the latest dated edition; the pinned
1998–2023 workbook is only a network-failure fallback. No values are nowcast or fabricated.

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
needed for new editions. `--require-year` turns stale data into an
explicit failure rather than silently rebuilding a chart that still ends in 2023.

## Outputs

- `data/london_gdp.csv` — tidy long table: `region, year, metric, value, unit, source`
  (metrics: `gdp_current_gbp_m`, `share_of_uk_gdp_pct`, `gdp_per_head_gbp`,
  `gdp_per_head_index_uk100`). Git-ignored, regenerable.
- `outputs/london/london_share_of_uk_gdp.png` — London's % of UK GDP over time.
- `outputs/london/london_gdp_per_head_vs_uk.png` — London GDP per head as an index (UK = 100).

Charts follow the shared house style (warm tan background, serif type, London in the
terracotta accent, italic ONS source note).
