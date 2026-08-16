# foodbank_data — Trussell emergency food parcels

A separate, reproducible analysis of emergency food parcels distributed by food banks
in **Trussell's UK community**. It uses Trussell's official downloadable workbooks and
the repository's shared Substack chart style.

## How far back can the evidence go?

Trussell opened its first food bank in Salisbury in **2000** and launched the Foodbank
Network in **2004**, but those are milestones—not national parcel observations. The
earliest exact nationwide annual count located in Trussell's archive is **2005/06:
2,814 people fed**, where the report describes each recipient as receiving three days'
emergency food.

The historical chart therefore begins its timeline in 2000, labels 2000–04 as
**unreported rather than zero**, and starts quantitative bars in 2005/06.

There are three deliberately separate statistical views:

1. **Archived financial-year reports, 2005/06–2017/18.** Wording evolves from
   "people fed" to "three-day emergency food supplies". These are counts of supplies
   or recipient instances, not unique annual users.
2. **Modern financial-year table, 2018/19–2023/24.** Extracted from the Excel table
   embedded in Trussell's official 2023/24 presentation. Trussell's methodology says
   its modern figures are comparable from 2017/18 and notes revisions to older data.
   From April 2020, three-day and seven-day parcels are combined.
3. **Calendar years, 2015–2025.** Trussell changed its headline reporting basis to
   calendar years for the 2025 release. This series is never appended to the fiscal
   series.

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
- `data/food_bank_fiscal_year.csv` — sourced fiscal history, 2005/06–2023/24,
  including source-vintage and comparability fields.
- `outputs/food_banks/trussell_food_parcels_history.png` — timeline from 2000 and
  financial-year bars from the first defensible annual observation.
- `outputs/food_banks/trussell_food_parcels_annual.png` — primary full-year chart.
- `outputs/food_banks/trussell_food_parcels_midyear.png` — separate mid-year chart.
- `outputs/food_banks/summary.md` — exact headline values, definitions, and citations.

The raw official XLSX/PPTX files are preserved under `data/raw/food_bank_*`. The fetcher
writes downloads atomically and accepts an injected byte-fetch function, so its
network behavior is unit-testable without network access. The fiscal history also
uses `data/raw/food_bank_trussell_fiscal_archive.tsv`, a row-level transcription with
an exact official source URL and document location for every value, plus the official
2023/24 PPTX's embedded Excel table for later years.

## Sources

Accessed **16 August 2026**:

- Trussell, [Our story](https://www.trussell.org.uk/our-work/what-we-do/our-story).
- Trussell, [UK foodbank network report (2012)](https://data.parliament.uk/DepositedPapers/Files/DEP2013-0499/Trussell_Trust_report_147805.pdf).
- Trussell accounts filed at Companies House:
  [2012/13](https://find-and-update.company-information.service.gov.uk/company/05434524/filing-history/MzA4NjgzNzExMWFkaXF6a2N4/document?format=pdf&download=0),
  [2013/14](https://find-and-update.company-information.service.gov.uk/company/05434524/filing-history/MzExMDQ0MTk5NWFkaXF6a2N4/document?format=pdf&download=0),
  [2014/15](https://find-and-update.company-information.service.gov.uk/company/05434524/filing-history/MzEzNjkxOTY4NmFkaXF6a2N4/document?format=pdf&download=0),
  [2015/16](https://find-and-update.company-information.service.gov.uk/company/05434524/filing-history/MzE2NTkzMjUxN2FkaXF6a2N4/document?format=pdf&download=0).
- Trussell annual reports:
  [2016/17](https://cms.trussell.org.uk/sites/default/files/2024-09/Annual-Report-and-Accounts-2016-2017-Updated-Feb2018.pdf),
  [2017/18](https://cms.trussell.org.uk/sites/default/files/2024-09/Trussell-Trust-Annual-Report-and-Account-2017-18.pdf).
- Trussell, [official 2023/24 presentation](https://hub.foodbank.org.uk/wp-content/uploads/2024/05/Template-2024-End-of-Year-stats-presentation-slides.pptx)
  and [methodology](https://cms.trussell.org.uk/sites/default/files/wp-assets/EYS-methodology.pdf).
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
