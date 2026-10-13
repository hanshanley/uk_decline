# rail_data — London rail delays (ORR passenger performance)

Tracks how reliable **London & South East** trains have been over time, using the
authoritative **Office of Rail and Road (ORR)** performance statistics, and puts them
against a **Great Britain** reference.

## The story

Two metrics, both drawn as a 4-quarter moving average (the standard way to read
seasonal rail statistics):

| Metric | What it is | Trend |
|---|---|---|
| **CaSL** (`casl_pct`) | % of trains **cancelled or significantly late** — the disruption measure | Roughly **doubled**: ~2.4% (2007) → ~5% (2025); Q1 2026 was 4.6%. Now back near the early-2000s (post-Hatfield) crisis level. |
| **PPM** (`ppm_pct`) | Public Performance Measure — % arriving at final destination within 5 min (10 min for long-distance services in the GB comparator) | Broadly **flat** (~90% → ~87%). |

CaSL includes full/part cancellations and arrivals at the final destination more
than 30 minutes late. Neither measure is a count of delayed passengers or all
station stops. The GB comparator includes different PPM thresholds.
The plotted smoother is an arithmetic mean of **four consecutive quarters**, not
ORR's trains-weighted annual moving average; it is omitted across missing quarters.

## Data source & method

- **Source:** ORR Data Portal, **Table 3103 — historic passenger trains planned, PPM
  and CaSL by operator** (quarterly, from 1997-98).
  <https://dataportal.orr.gov.uk/statistics/performance/passenger-rail-performance/>
- The ORR does **not** publish a *historic* sector aggregate (its sector table, 3113,
  starts 2019), so `orr.py` rebuilds the **London and South East** sector itself by taking
  each operator's figure **weighted by the trains it planned** that quarter:

  ```
  sector_value = Σ(operator_value × trains_planned) / Σ(trains_planned)
  ```

- The operator → sector membership (`LONDON_SE_FRANCHISES`) is grouped by *franchise
  title*, so operator renames (Connex South Eastern → South Eastern Trains →
  Southeastern) fold into one continuous series.
- `quarter` uses calendar quarters, consistent with `year` and the quarter-end
  `date` (Jan–Mar is Q1). Positional weighting rejects mismatched operator/period
  layouts; blank/non-finite cells are not valid observations.
  An operator with positive planned trains but a missing metric causes an explicit
  error, rather than silently reweighting the remaining operators.
- Reconstructed sector aggregates are approximate, rather than the official
  Table 3113 series. Across **28 quarters, April–June
  2019 to January–March 2026**, the maximum absolute difference from official
  Table 3113 PPM is **0.51 percentage points for London and South East** and
  **0.19 points for Great Britain**.
- Charts smooth each reconstructed percentage with an **arithmetic mean of four
  consecutive quarters**, not ORR's trains-weighted moving annual average.
  Missing quarters invalidate the window and remain gaps in plotted lines.

## Run

```bash
# fetch ORR data, write data/rail_performance.csv, render charts to outputs/rail/
./.venv/bin/python -m rail_data

# rebuild charts from an existing CSV (no fetch):
./.venv/bin/python -m rail_data --from-csv data/rail_performance.csv
```

## Outputs

- `data/rail_performance.csv` — tidy long table: `region, period, date, year, quarter,
  metric, value, unit, source` (git-ignored, regenerable).
- `outputs/rail/rail_london_casl.png` — cancellations & significant lateness (the
  disruption story; London highlighted vs GB).
- `outputs/rail/rail_london_ppm.png` — PPM "on time" (the broadly-flat headline).

Charts follow the shared house style (warm tan background, serif type, London in the
terracotta accent, italic source note).
