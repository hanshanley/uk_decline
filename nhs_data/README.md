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
| `rtt_waiting_list_total` | Recorded elective pathways / ongoing waits, not unique people | pathways / waits |
| `rtt_waiting_list_per_1000` | Pathways / waits per 1,000 residents, not the share of residents waiting | waits per 1,000 residents |
| `rtt_median_wait_weeks` | England's band-midpoint estimate and Wales's reported median; no Scottish pooled median | weeks |
| `ae_4hr_pct` | A&E attendances admitted, transferred or discharged within 4 hours | percent |
| `cancer_62day_pct` | Cancer treatments started within 62 days of urgent referral | percent |
| `diagnostics_6week_breach_pct` | Diagnostic-test six-week threshold; Welsh detailed bands start August 2024 | percent |
| `diagnostics_8week_breach_pct` | Welsh pathways waiting over 8 weeks; separate from six-week measures | percent |

## Data sources

| Nation / series | Source | Access |
|---|---|---|
| England | NHS England statistical work areas | CSV/Excel bulk downloads (no API) |
| Scotland | Public Health Scotland `opendata.nhs.scot` | CKAN JSON API |
| Wales | StatsWales `stats.gov.wales` | Paginated `api.stats.gov.wales/v1` JSON API |
| Northern Ireland | Department of Health (NI) | Excel/ODS downloads (no API) |
| Population | ONS/NRS/NISRA mid-year estimates via **Nomis** (`NM_2002_1`) | JSON API |

Counts come from official sources, including NHS England's historical overview
with official estimates for missing data. England's median is approximated from
weekly count bands; a weighted average of Scottish stage medians is **not** a pooled
median, so Scotland is omitted from that metric. The derived `rtt_waiting_list_per_1000` is computed as
`waiting_list ÷ real ONS mid-year population × 1,000`, and is only produced for
years that have a published ONS estimate (no projection/extrapolation).
It is **not** the proportion of unique residents waiting: a person can have more
than one pathway, and Scotland's total includes two stages of treatment.

### Citations

Cite the collecting/publishing organisation for each dataset (single source of
truth: `nhs_data/sources.py`, rendered into the generated summary):

- **NHS England** — *Consultant-led Referral to Treatment (RTT) Waiting Times;
  A&E Attendances and Emergency Admissions; Cancer Waiting Times; and Monthly
  Diagnostic Waiting Times and Activity (DM01).* NHS England statistical work
  areas, https://www.england.nhs.uk/statistics/statistical-work-areas/. The RTT
  waiting-list total is extended back to the **start of the collection (Aug 2007)**
  using the published *RTT Overview* time series, so England spans 2007–present
  (median wait is monthly-file only, so it starts 2015).
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
  counts are **not** directly comparable across nations and are **not unique people**.
  [PHS explicitly warns](https://publichealthscotland.scot/publications/stage-of-treatment-waiting-times/stage-of-treatment-waiting-times-new-outpatients-inpatients-and-day-cases-28-april-2026/)
  against interpreting summed waits as the proportion of the population waiting.
  NI's **encompass rollout from November 2023** creates a series break:
  [DoH says the new and legacy figures are not directly comparable](https://www.health-ni.gov.uk/news/publication-quarterly-northern-ireland-outpatient-inpatient-and-day-case-and-diagnostic-waiting-times-statistics-position-31-march-2026).
  Full five-trust coverage does not repair this definition break, so the summary
  does not label a change across it as better or worse.
- **A&E 4-hour:** scope differs (all A&E types vs major/Type-1 only) and cadence
  varies (weekly/monthly). **Northern Ireland:** only the machine-readable
  OpenDataNI Emergency Care extract is ingested; DoH NI's most recent Emergency
  Care releases are PDF-only, so the NIR A&E series may lag the other three
  nations (which run to the latest published month).
- **Cancer 62-day:** pathway definitions and standards were revised at different
  times per nation — watch for series breaks.
- **Diagnostics:** each nation covers a different set of tests. England/Scotland/
  NI have six-week measures here (NI's current official target is **9 weeks**,
  and its encompass figures are not comparable to legacy figures);
  **Wales's target is 8 weeks**. Welsh detailed
  weekly bands allow a separate six-week series from August 2024. Older grouped
  over-eight-week observations are kept under `diagnostics_8week_breach_pct`,
  never spliced into the six-week series.

## Tests

```bash
.venv/bin/python -m pytest tests/test_nhs_data.py -q   # offline, no network
```
