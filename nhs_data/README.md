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
| `rtt_waiting_list_per_1000` | Waiting list per 1,000 residents (derived; real ONS population) | per 1,000 people |
| `rtt_median_wait_weeks` | Median wait of those still waiting | weeks |
| `ae_4hr_pct` | A&E attendances seen within 4 hours | percent |
| `cancer_62day_pct` | Cancer treatments started within 62 days of urgent referral | percent |
| `diagnostics_6week_breach_pct` | Diagnostic-test list waiting 6+ weeks | percent |

## Data sources

| Nation / series | Source | Access |
|---|---|---|
| England | NHS England statistical work areas | CSV/Excel bulk downloads (no API) |
| Scotland | Public Health Scotland `opendata.nhs.scot` | CKAN JSON API |
| Wales | StatsWales `statswales.gov.wales` | OData JSON API |
| Northern Ireland | Department of Health (NI) | Excel/ODS downloads (no API) |
| Population | ONS/NRS/NISRA mid-year estimates via **Nomis** (`NM_2002_1`) | JSON API |

Every value is fetched from these official sources — nothing is synthesised or
interpolated. The one derived series, `rtt_waiting_list_per_1000`, is computed as
`waiting_list ÷ real ONS mid-year population × 1,000`, and is only produced for
years that have a published ONS estimate (no projection/extrapolation).

### Citations

Cite the collecting/publishing organisation for each dataset (single source of
truth: `nhs_data/sources.py`, rendered into the generated summary):

- **NHS England** — *Consultant-led Referral to Treatment (RTT) Waiting Times;
  A&E Attendances and Emergency Admissions; Cancer Waiting Times; and Monthly
  Diagnostic Waiting Times and Activity (DM01).* NHS England statistical work
  areas, https://www.england.nhs.uk/statistics/statistical-work-areas/.
- **Public Health Scotland** — *NHS Scotland waiting times: Stage of Treatment
  (ongoing waits); Accident & Emergency activity and waiting times; Cancer
  waiting times; and Diagnostic waiting times.* Scottish Health and Social Care
  Open Data platform, https://www.opendata.nhs.scot/.
- **Welsh Government (StatsWales)** — *NHS activity and performance: Referral to
  treatment times; A&E 4-hour performance; Suspected cancer pathway; and
  Diagnostic and therapy services waiting times.* StatsWales open data API,
  https://statswales.gov.wales/.
- **Department of Health (Northern Ireland), Information & Analysis Directorate**
  — *Northern Ireland Waiting Time Statistics: Outpatient, Diagnostic and Cancer
  Waiting Times; and Emergency Care Waiting Times.* https://www.health-ni.gov.uk/
  and OpenDataNI, https://www.opendatani.gov.uk/.
- **Office for National Statistics (ONS); National Records of Scotland (NRS);
  Northern Ireland Statistics and Research Agency (NISRA)** — *Mid-year
  population estimates (dataset NM_2002_1)*, used only for the derived per-1,000
  series. Nomis (operated by Durham University on behalf of ONS),
  https://www.nomisweb.co.uk/.

Contains public sector information licensed under the Open Government Licence v3.0.

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
# Fetch everything, write ../outputs/nhs/nhs_waiting_times.csv, charts, and summary:
.venv/bin/python -m nhs_data

# Restrict the year range:
.venv/bin/python -m nhs_data --start 2015 --end 2025

# Rebuild charts/summary from an existing CSV (no fetching):
.venv/bin/python -m nhs_data --from-csv ../outputs/nhs/nhs_waiting_times.csv
```

Outputs:
- `../outputs/nhs/nhs_waiting_times.csv` — combined tidy table
- `../outputs/nhs/<metric>.png` — one per-nation trend chart per metric (each chart
  embeds a source-attribution note; the per-1,000 chart also credits ONS)
- `../outputs/nhs/nhs_waiting_times_summary.md` — headline trend summary

The chart-generation code is `nhs_data/charts.py` (matplotlib; run via the CLI
above or `nhs_data.charts.make_charts(df)`).

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
  varies (weekly/monthly). **Northern Ireland:** only the machine-readable
  OpenDataNI Emergency Care extract is ingested; DoH NI's most recent Emergency
  Care releases are PDF-only, so the NIR A&E series may lag the other three
  nations (which run to the latest published month).
- **Cancer 62-day:** pathway definitions and standards were revised at different
  times per nation — watch for series breaks.
- **Diagnostics:** each nation covers a different set of tests. England/Scotland/
  NI measure the 6-week standard; **Wales's target is 8 weeks**, so the Welsh
  series counts 8+ week waits and understates the 6-week breach share.

## Tests

```bash
.venv/bin/python -m pytest tests/test_nhs_data.py -q   # offline, no network
```
