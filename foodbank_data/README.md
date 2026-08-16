# foodbank_data — Trussell emergency food parcels

A separate, reproducible analysis of emergency food parcels distributed by food banks
in **Trussell's UK community**. It uses Trussell's official downloadable workbooks and
the repository's shared Substack chart style.

## Headline

In calendar 2025, Trussell food banks distributed **2,644,835 emergency food parcels**:
**1,732,619 for adults** and **912,216 for children**. That was **11.7% fewer than
2024**, but still **44.9% above 2019**. The calendar-year series peaked at **3,237,114
in 2023**.

The latest mid-year release covers **1 April–30 September 2024**: **1,428,681 parcels**,
down 4.5% from the same six months of 2023 but 69.3% above the same period in 2019.
Trussell did not publish 2025/26 mid-year figures while moving to calendar-year
reporting. The analysis therefore never joins the six-month and full-year series.

## Run

```bash
# Rebuild from the preserved official workbooks (no network needed)
./.venv/bin/python -m foodbank_data

# Redownload the official workbooks, then rebuild
./.venv/bin/python -m foodbank_data --refresh

# Offline tests
./.venv/bin/python -m pytest tests/test_foodbank.py -q
```

## Outputs

- `data/food_bank_calendar_year.csv` — calendar-year UK series, 2015–2025.
- `data/food_bank_midyear.csv` — like-for-like April–September series, 2018–2024.
- `outputs/food_banks/trussell_food_parcels_annual.png` — primary full-year chart.
- `outputs/food_banks/trussell_food_parcels_midyear.png` — separate mid-year chart.
- `outputs/food_banks/summary.md` — exact headline values, definitions, and citations.

The raw official XLSX files are preserved under `data/raw/food_bank_*`. The fetcher
writes downloads atomically and accepts an injected byte-fetch function, so its
network behavior is unit-testable without network access.

## Sources

Accessed **16 August 2026**:

- Trussell, [End of year food bank stats](https://www.trussell.org.uk/news-and-research/latest-stats/end-of-year-stats).
- Trussell, [official 2025 parcel-statistics XLSX](https://cms.trussell.org.uk/sites/default/files/2026-03/eys_2025_parcel_stats.xlsx).
- Trussell, [Mid-year stats](https://www.trussell.org.uk/news-and-research/latest-stats/mid-year-stats).
- Trussell, [official April–September 2024 XLSX](https://trusselltrustprod.prod.acquia-sites.com/sites/default/files/2024-11/MYS%202024%20parcel%20statistics%20%28web%29.xlsx).
- The chart's 2016 context marker follows the
  [Welfare Reform and Work Act 2016 explanatory notes](https://www.legislation.gov.uk/ukpga/2016/7/notes/division/3/index.htm).

## Definitions and caveats

- A parcel is an emergency food supply recorded for **one recipient**. It is a measure
  of distribution volume, **not unique people**; repeat referrals are counted again.
- Trussell combines three-day and seven-day parcels without duration-equivalising them.
- The figures cover Trussell's community, not every UK food bank or food-aid provider.
- "Parcels for children" describes recipient age. It is not the same statistic as
  parcels received by a household containing children.
- Trussell says some food banks had not completed data entry at publication and may
  revise earlier observations.
- Policy and economic annotations are timing context, not causal claims.
