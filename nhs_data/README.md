# nhs_data — UK NHS waiting times & waiting lists over time

Fetches NHS waiting-time statistics for **all four UK nations** (England,
Scotland, Wales, Northern Ireland) and produces a combined tidy dataset, trend
**charts**, and a short written **summary**.

Health is devolved, so each nation publishes separately, on its own definitions
and cadence. This package harmonises them onto a common schema while keeping the
`source` on every row so comparisons stay honest — **compare trends, not exact
levels** (see caveats below).

## Metrics

| Metric id | Meaning | Unit |
|---|---|---|
| `rtt_waiting_list_total` | Patients waiting to start elective treatment (the "waiting list") | patients |
| `rtt_median_wait_weeks` | Median wait of those still waiting | weeks |
| `ae_4hr_pct` | A&E attendances seen within 4 hours | percent |
| `cancer_62day_pct` | Cancer treatments started within 62 days of urgent referral | percent |
| `diagnostics_6week_breach_pct` | Diagnostic-test list waiting 6+ weeks | percent |

## Data sources

| Nation | Source | Access |
|---|---|---|
| England | NHS England statistical work areas | CSV/Excel bulk downloads (no API) |
| Scotland | Public Health Scotland `opendata.nhs.scot` | CKAN JSON API |
| Wales | StatsWales `statswales.gov.wales` | OData JSON API |
| Northern Ireland | Department of Health (NI) | Excel/ODS downloads (no API) |

## Tidy schema (long format)

Every source module returns rows with these columns
(`nhs_data.metrics.ROW_FIELDS`):

```
nation, nation_code, period, date, metric, value, unit, source
```

`period` is `YYYY-MM` (monthly) or `YYYY-Qn` (quarterly); `date` is the ISO
period-end.

## Usage

```bash
# Fetch everything, write data/nhs_waiting_times.csv, charts, and summary:
.venv/bin/python -m nhs_data

# Restrict the year range:
.venv/bin/python -m nhs_data --start 2015 --end 2025

# Rebuild charts/summary from an existing CSV (no fetching):
.venv/bin/python -m nhs_data --from-csv data/nhs_waiting_times.csv
```

Outputs:
- `data/nhs_waiting_times.csv` — combined tidy table
- `data/charts/<metric>.png` — one per-nation trend chart per metric
- `data/nhs_waiting_times_summary.md` — headline trend summary

Programmatic use:

```python
from nhs_data import combine, charts, summary
df = combine.build(2015, 2025)      # fetch + write CSV
charts.make_charts(df)
summary.build_summary(df)
```

## Comparability caveats

Metric definitions differ by nation. Key differences (full text in
`nhs_data.metrics.CAVEATS`):

- **RTT waiting list:** England/Wales report "incomplete pathways"; Scotland
  reports "ongoing waits" by stage of treatment; NI reports outpatient /
  inpatient / day-case separately (we map the **outpatient** total). Absolute
  counts are **not** directly comparable across nations.
- **A&E 4-hour:** scope differs (all A&E types vs major/Type-1 only) and cadence
  varies (weekly/monthly). **Northern Ireland:** only machine-readable A&E data
  (2015–2018, via OpenDataNI) is ingested; DoH NI's recent Emergency Care
  releases are PDF-only, so the NIR A&E series ends in 2018. The other three
  nations run to the latest month.
- **Cancer 62-day:** pathway definitions and standards were revised at different
  times per nation — watch for series breaks.
- **Diagnostics:** each nation covers a different set of tests.

## Tests

```bash
.venv/bin/python -m pytest tests/test_nhs_data.py -q   # offline, no network
```
