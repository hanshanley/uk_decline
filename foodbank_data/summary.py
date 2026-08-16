"""Write a concise, cited markdown summary of the parsed statistics."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .sources import (
    ACCESSED_DATE,
    CALENDAR_SOURCE,
    END_YEAR_PAGE,
    MIDYEAR_SOURCE,
    MID_YEAR_PAGE,
    OUTPUT_DIR,
)

def build_summary(
    annual: pd.DataFrame,
    midyear: pd.DataFrame,
    path: Path = OUTPUT_DIR / "summary.md",
) -> Path:
    annual = annual.sort_values("year")
    midyear = midyear.sort_values("year")
    latest = annual.iloc[-1]
    peak = annual.loc[annual["total"].idxmax()]
    first = annual.iloc[0]
    latest_midyear = midyear.iloc[-1]

    text = f"""# Trussell food-bank-use analysis

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
