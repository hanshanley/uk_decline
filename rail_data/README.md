# rail_data — London rail delays (ORR passenger performance)

Tracks how reliable **London & South East** trains have been over time, using the
authoritative **Office of Rail and Road (ORR)** performance statistics, and puts them
against a **Great Britain** reference.

## The story

Two metrics, both drawn as a 4-quarter moving average (the standard way to read
seasonal rail statistics):

| Metric | What it is | Trend |
|---|---|---|
| **CaSL** (`casl_pct`) | % of trains **cancelled or significantly late** — the disruption measure | Roughly **doubled**: ~2.4% (2007) → ~5% (2024). Now back near the early-2000s (post-Hatfield) crisis level. |
| **PPM** (`ppm_pct`) | Public Performance Measure — % of trains **"on time"** (within 5 min) — the lenient headline | Broadly **flat** (~90% → ~87%). |

The headline "on time" figure hides the deterioration: serious disruption
(cancellations and significant lateness) has roughly doubled while PPM barely moved.

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
- **Validation:** on the 2019+ quarters where ORR *does* publish a "London and South
  East" sector figure (Table 3113), this reconstruction matches to within **~0.2
  percentage points**, confirming both the membership set and the weighting. The same
  method reproduces ORR's official **Great Britain** PPM exactly (e.g. Jan–Mar 2020 =
  85.8%).

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
