# nhs_data — UK NHS waiting times & waiting lists over time

Fetches NHS waiting-time statistics for **all four UK nations** (England,
Scotland, Wales, Northern Ireland) and produces a combined tidy dataset, trend
**charts**, and a short written **summary**.

Health is devolved, so each nation publishes separately, on its own definitions
and cadence. This package harmonises them onto a common schema while keeping the
`source` on every row so comparisons stay honest — **compare trends, not exact
levels** (see caveats below).

Charts do not connect lines across registered definition/recording changes.
England's RTT scope excludes sexual-health pathways from **April 2013** and
community-service pathways from **February 2024**; its cancer
standards changed on **1 October 2023**. Northern Ireland's encompass system rolled
out on **9 November 2023, 6 June 2024, 7 November 2024 and 8 May 2025**; aggregate
RTT/diagnostic/cancer series are split at each step, not just the first implementation.
NI emergency-care lines are also split as a conservative recording-quality safeguard,
not a claim that DoH explicitly declares its emergency-care series non-comparable.
Endpoint summaries suppress better/worse claims across these breaks. Indexed waiting
counts start at the first exact date shared by all nations **after the last applicable
change in the observed data**, so a system rollout is not labelled waiting-list growth.
See [NHS England's comparability guidance](https://www.england.nhs.uk/statistics/statistical-work-areas/cancer-waiting-times/)
and [DoH NI's rollout and quality statement](https://www.health-ni.gov.uk/news/publication-quarterly-northern-ireland-outpatient-inpatient-and-day-case-and-diagnostic-waiting-times-statistics-position-31-march-2026).

## Metrics

| Metric id | Meaning | Unit |
|---|---|---|
| `rtt_waiting_list_total` | Recorded elective pathways / ongoing waits, not unique people | pathways / waits |
| `rtt_waiting_list_per_1000` | Pathways / waits per 1,000 residents, not the share of residents waiting | waits per 1,000 residents |
| `rtt_median_wait_weeks` | England's band-midpoint estimate and Wales's reported median; no Scottish pooled median | weeks |
| `ae_4hr_pct` | Four-hour A&E performance; NI uses classified waiting-time records | percent |
| `cancer_62day_pct` | Cancer treatments started within 62 days of urgent referral | percent |
| `diagnostics_6week_breach_pct` | Diagnostic-test six-week threshold; Welsh detailed bands start August 2024 | percent |
| `diagnostics_8week_breach_pct` | Welsh pathways waiting over 8 weeks; separate from six-week measures | percent |

## Data sources

| Nation / series | Source | Access |
|---|---|---|
| England | NHS England statistical work areas | CSV/Excel downloads; official WordPress REST API for publication discovery when HTML is empty/challenged |
| Scotland | Public Health Scotland `opendata.nhs.scot` | CKAN JSON API |
| Wales | StatsWales `stats.gov.wales` | Paginated `api.stats.gov.wales/v1` JSON API |
| Northern Ireland | Department of Health (NI) | Excel/ODS downloads and structured JSON count tables embedded in official interactive HTML |
| Population | ONS/NRS/NISRA mid-year estimates via **Nomis** (`NM_2002_1`) | JSON API |

Counts come from official sources. England uses the **reported-total column** of
the historical overview and totals from monthly extracts; estimates for missing
providers are **not** added, even though the historical workbook also contains an
estimated-total column. Changes in reporting coverage can affect these counts.
Monthly extracts also contain `NONC` pathways commissioned outside England;
these are excluded from both totals and band-midpoint medians to match NHS England's
published outputs. The August 2026 extract independently reconciles with the
current overview: **7,158,164 reported pathways**, not 7,189,213 including `NONC`
or 7,370,100 including estimates for missing providers.
All 130 refreshed monthly totals reconcile exactly with that overview;
band-midpoint medians differ from its interpolated medians by at most 0.50 weeks.
England's median is approximated from
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
  and its NISRA-hosted interactive publications, https://datavis.nisra.gov.uk/health/.
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
  England's sexual-health/community-service scope changes are also registered.
  [The August 2026 RTT statistical notice](https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/10/Aug26-RTT-statistical-press-notice-PDF-389K-vjgRdG.pdf)
  explains reporting coverage and the exclusion of non-English commissioned
  pathways from published outputs.
- **A&E 4-hour:** scope differs (all A&E types vs major/Type-1 only) and cadence
  varies (weekly/monthly). **Northern Ireland:** the current interactive release
  contains an underlying count table, not just PDF charts. The loader discovers
  that release and aggregates all Types 1–3, including urgent care centres, whose
  inclusion changes the service mix. It sums within-four-hour counts and divides
  by the sum of published waiting-time bands, **not all attendances or an average
  of rounded department percentages**. Records outside the bands are not in that
  denominator. All 4,045 positive-denominator department-month percentages reconcile
  within the source's 0.1-point rounding; incomplete department/trust months are
  excluded. June 2026 reproduces the [published report](https://datavis.nisra.gov.uk/health/ni-emergency-care-waiting-times-apr-jun-26.html):
  71,018 attendances, 11,605 waits over twelve hours and 42.8% four-hour performance
  (29,720 / 69,424 classified waits).
  The whole April 2008–June 2026 history comes from that same current table.
  Compared with the former cached series, the 123 overlapping months differ by
  up to 1.99 percentage points; the old and current extracts are not spliced.
  Encompass-affected statistics are in development. This project conservatively
  splits emergency-care lines at rollout dates without attributing a cross-break
  change to performance.
- **Cancer 62-day:** lines and endpoint summaries are split at England's
  **1 October 2023** standards change and Wales's **June 2019** move from the
  urgent suspected pathway to the broader suspected cancer pathway. The Welsh
  clock starts earlier; the old and new percentages must not be treated as a
  like-for-like deterioration.
  [Welsh Government quality report](https://www.gov.wales/nhs-activity-and-performance-summary-quality-report-html).
  NI's encompass rollout is also a comparability break. The
  [April–June 2026 release, published 1 October 2026](https://www.health-ni.gov.uk/publications/northern-ireland-waiting-time-statistics-cancer-waiting-times-april-june-2026),
  revises 31/62-day waits for quarters ending December 2023 through March 2026
  after an adjusted-wait calculation error. The loader discovers the current
  publication and identifies its 62-day **trust** table by column schema, not
  the obsolete sheet name. It uses revised monthly counts and excludes
  April–June 2024, when Belfast's validated counts are missing; the sum of
  the other four trusts is not a complete NI result.
  The refreshed April–June 2026 counts independently reproduce the
  [published quarter total](https://www.health-ni.gov.uk/news/publication-northern-ireland-cancer-waiting-time-statistics-april-june-2026):
  414 of 1,459 patients within 62 days (28.4%). This is a quarter aggregate,
  not June's monthly percentage (30.8%).
- **Diagnostics:** each nation covers a different set of tests. England/Scotland/
  NI have six-week measures here (NI's current official target is **9 weeks**,
  and its encompass figures are not comparable to legacy figures);
  **Wales's target is 8 weeks**. Welsh detailed
  weekly bands allow a separate six-week series from August 2024. Older grouped
  over-eight-week observations are kept under `diagnostics_8week_breach_pct`,
  never spliced into the six-week series.

Charts do not draw lines through the registered changes. Indexed RTT charts use
the earliest exact common observation date after the latest observed NI encompass
rollout step (9 November 2023, 6 June 2024, 7 November 2024 and 8 May 2025).
This avoids attributing a reporting-system change to waiting-list growth; it does
not make the four nations' underlying definitions identical.

NI loaders discover current publications before their pinned June 2026 releases;
discovery failures produce explicit warnings. NHS England's empty/challenged HTML
pages are handled through the official REST API, with exact canonical-page validation.
Older root-level publication aliases are normalised against the relevant work-area
landing page before lookup. A pinned cancer fallback remains explicit and warning-bearing.

### Verified coverage as of 12 October 2026

| Nation | RTT / median where available | Cancer | Diagnostics | A&E |
|---|---|---|---|---|
| England | August 2026 | August 2026 | August 2026 | September 2026 |
| Scotland | June 2026 (no pooled median) | June 2026 | June 2026 | August 2026 |
| Wales | July 2026 | July 2026 | July 2026 (separate six/eight-week series) | August 2026 |
| Northern Ireland | June 2026 (outpatient total only) | June 2026 | June 2026 | June 2026 |

Derived per-capita observations end in 2025: no 2026 population estimate is
invented or carried forward. Different endpoint dates and nation definitions remain
real comparability constraints; successful retrieval does not remove them.

## Tests

```bash
.venv/bin/python -m pytest tests/test_nhs_data.py -q   # offline, no network
```
