"""Write a concise, cited markdown summary of the parsed statistics."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .sources import (
    ACCESSED_DATE,
    CALENDAR_SOURCE,
    END_YEAR_PAGE,
    FISCAL_METHODOLOGY_URL,
    FISCAL_SLIDES_SOURCE,
    MIDYEAR_SOURCE,
    MID_YEAR_PAGE,
    OUTPUT_DIR,
    STORY_PAGE,
)

def build_summary(
    annual: pd.DataFrame,
    midyear: pd.DataFrame,
    fiscal: pd.DataFrame,
    path: Path = OUTPUT_DIR / "summary.md",
) -> Path:
    annual = annual.sort_values("year")
    midyear = midyear.sort_values("year")
    fiscal = fiscal.sort_values("start_year")
    latest = annual.iloc[-1]
    peak = annual.loc[annual["total"].idxmax()]
    first = annual.iloc[0]
    latest_midyear = midyear.iloc[-1]
    earliest_fiscal = fiscal.iloc[0]
    latest_fiscal = fiscal.iloc[-1]
    archive_latest = fiscal.loc[fiscal["period_label"] == "2017/18"].iloc[0]

    text = f"""# Trussell food-bank-use analysis

## Earliest defensible history

Trussell's first food bank opened in Salisbury in **2000**, and its Foodbank Network
was launched in **2004**. There is no national annual parcel series for those early
years, so the analysis treats 2000–04 as milestones rather than zeros.

The earliest exact UK-wide annual observation found in Trussell's own archive is
**{earliest_fiscal['period_label']}: {earliest_fiscal['total']:,} people fed**, shown
in a Trussell report as recipients of three-day emergency food. The archived
financial-year series reaches **{archive_latest['total']:,} in 2017/18**. A separate
modern Trussell fiscal table covers 2018/19–2023/24 and ends at
**{latest_fiscal['total']:,} parcels in {latest_fiscal['period_label']}**.

These source vintages are coloured separately. Trussell's 2023/24 methodology says
its modern financial-year figures are comparable from 2017/18, notes revisions to
earlier releases, and says that releases from April 2020 combine three-day and
seven-day parcels. The fiscal history is not joined to the separate calendar-year
series.

## Headline

- Food banks in Trussell's UK community distributed **{latest['total']:,} emergency
  food parcels in calendar 2025**: {latest['adults']:,} for adults and
  {latest['children']:,} for children.
- That was **{abs(latest['change_vs_previous_pct']):.1f}% lower than 2024**, but still
  **{latest['change_vs_2019_pct']:.1f}% above 2019**.
- The calendar-year series rose from **{first['total']:,} in {int(first['year'])}** to a
  peak of **{peak['total']:,} in {int(peak['year'])}**. The 2025 total was
  **{abs((latest['total'] / peak['total'] - 1) * 100):.1f}% below that peak**.

## Latest mid-year release

The latest comparable mid-year observation remains **1 April–30 September 2024**:
**{latest_midyear['total']:,} parcels**, including {latest_midyear['children']:,} for
children. This was **{abs(latest_midyear['change_vs_previous_pct']):.1f}% lower than the same
six months of 2023**, but **{latest_midyear['change_vs_2019_pct']:.1f}% above the same
period in 2019**. Trussell did not publish 2025/26 mid-year statistics while changing
to calendar-year reporting; these six-month values are therefore kept separate from
the full-year chart.

## Definitions and caveats

- A parcel is a supply of emergency food recorded for one recipient. Parcel counts
  measure **volume, not unique people**; repeat referrals are counted again.
- Trussell combines three-day and seven-day parcels without converting them to a
  common duration.
- The figures cover food banks in Trussell's community, not the hundreds of
  independent food-aid providers across the UK.
- "Parcels for children" identifies the recipient's age. It is not the same measure
  as parcels received by households that include children.
- Trussell says some food banks had not completed data entry by publication, and
  earlier figures can be revised in later releases.
- The charts' policy/economic labels provide timing context only; they do not claim
  that any one event caused the observed change.

## Sources

- Trussell, [Our story]({STORY_PAGE}) (2000 first food bank; network expansion from
  2004).
- Trussell, [UK foodbank network report (2012)](https://data.parliament.uk/DepositedPapers/Files/DEP2013-0499/Trussell_Trust_report_147805.pdf),
  which charts annual UK totals from 2005/06 through 2011/12.
- Trussell accounts filed at Companies House for
  [2012/13](https://find-and-update.company-information.service.gov.uk/company/05434524/filing-history/MzA4NjgzNzExMWFkaXF6a2N4/document?format=pdf&download=0),
  [2013/14](https://find-and-update.company-information.service.gov.uk/company/05434524/filing-history/MzExMDQ0MTk5NWFkaXF6a2N4/document?format=pdf&download=0),
  [2014/15](https://find-and-update.company-information.service.gov.uk/company/05434524/filing-history/MzEzNjkxOTY4NmFkaXF6a2N4/document?format=pdf&download=0), and
  [2015/16](https://find-and-update.company-information.service.gov.uk/company/05434524/filing-history/MzE2NTkzMjUxN2FkaXF6a2N4/document?format=pdf&download=0).
- Trussell annual reports for
  [2016/17](https://cms.trussell.org.uk/sites/default/files/2024-09/Annual-Report-and-Accounts-2016-2017-Updated-Feb2018.pdf)
  and [2017/18](https://cms.trussell.org.uk/sites/default/files/2024-09/Trussell-Trust-Annual-Report-and-Account-2017-18.pdf).
- Trussell, [official 2023/24 end-of-year slide deck]({FISCAL_SLIDES_SOURCE.url})
  (embedded UK table for 2018/19–2023/24) and
  [methodology note]({FISCAL_METHODOLOGY_URL}).
- Trussell, [End of year food bank stats]({END_YEAR_PAGE}) and
  [official 2025 parcel-statistics workbook]({CALENDAR_SOURCE.url}).
- Trussell, [Mid-year stats]({MID_YEAR_PAGE}) and
  [official April–September 2024 workbook]({MIDYEAR_SOURCE.url}).
- Welfare Reform and Work Act 2016, explanatory notes on the four-year freeze:
  <https://www.legislation.gov.uk/ukpga/2016/7/notes/division/3/index.htm>.
- Accessed **{ACCESSED_DATE}**.
"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
