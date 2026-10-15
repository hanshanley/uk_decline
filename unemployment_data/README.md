# Unemployment and youth unemployment

Two UK Labour Force Survey measures, published by the Office for National
Statistics (ONS), are shown separately from 2000 onward:

![UK unemployment](../outputs/unemployment/uk_unemployment.png)

![UK youth unemployment](../outputs/unemployment/uk_youth_unemployment.png)

- **Overall unemployment:** ages **16 and over**, ONS series **MGSX**.
- **Youth unemployment:** ages **16-24**, ONS series **MGWY**.

Both rates divide unemployed people by the **economically active population
(employed plus unemployed)** within the stated age band. Neither is the proportion
of all people in that age group who are without work. The overall rate includes
young people; it is not a rate for those aged 25 and over.

Unemployed people are without a job and available to start work within two weeks,
and have either sought work in the previous four weeks or already obtained a job
that starts within the next two weeks. Economic inactivity is different: someone who is neither
employed nor unemployed is not in the rate's denominator.

Youth unemployment **includes full-time students** who meet that definition.
It is not the share of young people who are not in education, employment or
training. These UK youth figures start at age 16, so they must not be spliced with
international series covering ages 15-24.

## Reference periods and survey uncertainty

These are seasonally adjusted **rolling three-month estimates**, not independent
monthly unemployment rates. ONS labels each observation with its **centre month**:
`2026 JUN` means **May-July 2026**, not June alone or June-August. The saved table
includes `period_start` and `period_end`, as well as that centre-month `date`.
Latest chart labels show the full period. Adjacent points have overlapping survey
windows and must not be treated as independent monthly samples.

Recent Labour Force Survey estimates have additional uncertainty because of
response and collection problems. Collection and population-weighting changes
also affect comparisons through time. Youth estimates are particularly volatile;
small movements should not be overinterpreted. These charts use the current ONS
vintage throughout, without adding forecasts, smoothing observations, or
interpolating missing values. They do not add an invented confidence interval
when the source CSV does not provide one.

The public page contains only the two charts and short captions; detailed
documentation stays here rather than in a duplicated website methods section.

## Sources and reproducibility

- [ONS overall rate, MGSX](https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms).
- [ONS youth rate, MGWY](https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgwy/lms).
- [ONS labour-market quality and methodology information](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/methodologies/labourforcesurveylfsqmi).
- [ONS September 2026 labour-market bulletin](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket/september2026).

Both series are downloaded directly through the official ONS CSV generator,
dataset `LMS`. The tracked [source table](../data/unemployment_long.csv) records
the series, age group, seasonal adjustment, units and release date for each
observation. This analysis is included in the scheduled full refresh.

```bash
./.venv/bin/python -m unemployment_data
./.venv/bin/python -m unemployment_data --from-csv data/unemployment_long.csv
```

All sources must pass validation before the saved table is replaced: correct
series titles and identifiers, percentage units, UK coverage, age bands,
seasonal adjustment, finite rates between 0 and 100, unique dates, correctly
centred periods, the same publication vintage and latest period, full 2000-2025
coverage, and retention of every previously published observation. Live fetches
also reject releases more than 90 days old. Offline rebuilds do not enforce that
freshness limit.
