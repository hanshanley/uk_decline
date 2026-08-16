# austerity_data — the spending squeeze behind UK austerity

This analysis turns the fiscal story described by the
[New York Times in February 2019](https://www.nytimes.com/2019/02/24/world/europe/britain-austerity-may-budget.html)
into a reproducible chart using current official UK outturn data.

The chart now runs from **2000–01 through 2025–26**. HM Treasury's current functional table begins
in 2003–04, so the first three observations come from the official PESA 2012
historical table. Both vintages are indexed independently to 2010–11 = 100; at
their 2003–04 overlap they differ by no more than one index point.

![Austerity spending and investment](../outputs/austerity/uk_austerity_spending_investment.png)

## What the graph shows

The broad public-spending total barely fell across the 2010s, but that headline conceals a
large redistribution:

- real spending on **housing and community amenities** fell by roughly one-third at its trough;
- **culture and recreation**, **public order and safety**, and **defence** also sustained
  substantial real cuts;
- **health** was protected and rose over the decade;
- **public sector net investment** fell from 2.5% of GDP in 2010–11 to 1.5% in 2013–14.

This reconciles the apparent contradiction between a fairly stable aggregate budget and the
visible deterioration of particular services. The article's quoted Institute for Fiscal
Studies estimate—about **£40bn of departmental cuts**, with some budgets down **30–40%**—is
used as context, not inserted into the Treasury time series.

## Data

**HM Treasury, Public Spending Statistics, July 2026**, Accredited Official Statistics:

- Table 4.1: Total Managed Expenditure, current expenditure, and public sector net investment;
- Table 4.3: real public expenditure on services by function.

Historical extension: **HM Treasury, Public Expenditure Statistical Analyses 2012,
Table 4.3**, which publishes the same high-level functional classification back to
1988–89. Only 2000–01 to 2002–03 is used to extend the current chart.

Real values are in **2025–26 prices**, deflated by HM Treasury using the ONS GDP deflator.
The pipeline resolves the latest July PSS release and its Chapter 4 workbook from GOV.UK.

Education is intentionally omitted from the comparison chart because HM Treasury warns that
student-loan accounting changed between 2010–11 and 2011–12, breaking direct comparability.
Net investment is after depreciation and includes net capital grants.

## Run

```bash
python -m austerity_data
python -m austerity_data --from-csv data/austerity_spending.csv
pytest tests/test_austerity.py -q
```

Outputs:

- `outputs/austerity/uk_austerity_spending_investment.png`
- `outputs/austerity/austerity_summary.md`
