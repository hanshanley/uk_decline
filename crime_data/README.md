# crime_data — Crime in the UK over time

Tracks crime in the UK across the long run and against international peers, using the
authoritative **Crime Survey for England & Wales (CSEW)** and the internationally comparable
**homicide rate**. The story is deliberately **nuanced** — it is not a simple "everything got
worse".

## The story

| Measure | What it shows | Trend |
|---|---|---|
| **Total CSEW crime** (excl. fraud) | The ONS-preferred long-run trend measure | **Fell sharply**: peak **19.8M** incidents (1995) → **~4.3M** (year ending March 2026). |
| **Total CSEW crime incl. fraud & computer misuse** | The broader headline definition (from 2017) | **~9.6M** (year ending March 2026) — **more than double** the excluding-fraud-and-computer-misuse figure. |
| **Homicide rate** | The most internationally comparable crime statistic | UK **~1.1 per 100k** — far below the **US (~5.8)** and now around/below the **EU-27 mean**. |

The long-run fall applies to the excluding-fraud-and-computer-misuse series.
The broader total includes substantial additional harms, but cannot be compared
with the historical narrower total as if coverage had stayed constant. These two
totals alone do not establish that traditional crime was displaced online.

The front-page scorecard uses the **excluding-fraud-and-computer-misuse incident
count**, starting with the year ending March 2007, so it has a comparable 2007
baseline. The detailed gap chart retains the combined fraud-and-computer-misuse
share, but that is a composition measure: it can rise when other crime falls.
It is neither fraud alone nor the percentage of people experiencing fraud.

## Data sources & method

The pipeline retrieves published official statistics and derives rates where needed.
Northern Ireland homicide counts are extracted from a published chart rather than
a numeric table, as described below. Each chart prints its source as a caption,
taken from the data's own `source` column.

### 1. ONS — Crime Survey for England & Wales (CSEW) → long-run trend

> Crime Survey for England and Wales, Office for National Statistics (ONS).
> *Crime in England and Wales: Appendix Tables*, Table A1a (Trends in incidents of CSEW
> headline crime, year ending December 1981 to latest).
> <https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/datasets/crimeinenglandandwalesappendixtables>

- **Collected by:** the ONS, via the Crime Survey for England & Wales (a large annual
  victimisation survey; formerly the British Crime Survey). It is the ONS-preferred measure
  of long-run *trends* because it is unaffected by changes in police recording practice.
- **Coverage:** **England & Wales only** (Scotland and Northern Ireland run their own
  surveys). Year ending Dec 1981 → latest; values in **1,000s of incidents**.
- `csew.py` resolves the current xlsx download URL from the ONS dataset page at run time
  (the filename changes each release), restricted to the `ons.gov.uk` host, and parses sheet
  `Table_A1a` — skipping "Unweighted base" rows and ONS `[x]` (not-available) cells.
- Generic burglary subcategory labels such as `Attempts` and `With loss` are prefixed
  with their parent offence category so distinct observations have distinct names.
- Comparable CSEW estimates are unavailable for the years ending March 2021 and
  March 2022 because face-to-face interviewing was suspended during the pandemic.
  Charts leave a gap rather than connecting or substituting telephone-survey estimates.

### 2. World Bank — intentional homicide rate (per 100,000) → peer comparison

> UN Office on Drugs and Crime (UNODC), *Intentional homicides (per 100,000 people)*,
> indicator `VC.IHR.PSRC.P5`, via the World Bank World Development Indicators.
> <https://data.worldbank.org/indicator/VC.IHR.PSRC.P5>

- **Collected by:** the **UNODC** (compiled from national criminal-justice and public-health
  sources); redistributed by the World Bank. Fetched live via `https://api.worldbank.org/v2`.
- **Coverage:** UK + EU-27 + US; UK ~1990–2021.

### 3. UK official homicide series → nation comparison since 2000

The broad crime surveys and police-recorded crime categories are not harmonised across the
UK nations, so the country breakdown uses homicide: the most consistently defined measure.
England and Wales are combined because that is how the ONS Homicide Index publishes the
official series.

- **England & Wales:** ONS Homicide Index, rate per million population.
- **Scotland:** Scottish Government *Homicide in Scotland 2024-25*, using the complete
  1999–00 to 2024–25 victim-count table reproduced in the government's
  [written answer S6W-43088](https://www.parliament.scot/chamber-and-committees/questions-and-answers/question?ref=S6W-43088)
  on 26 January 2026, divided by ONS mid-year population estimates. This is the same
  official series, not a different crime definition. The release edition is curated;
  each fetch checks the answer, victim-count heading and complete reporting-year coverage.
- **Northern Ireland:** PSNI *Trends in Police Recorded Crime*, divided by ONS mid-year
  population estimates. Counts are reconstructed from the PDF's vector-bar heights
  and rounded to integers, not read from a machine-readable table. Treat this as
  chart-derived data, with potential extraction/rounding error.
- **Coverage:** reporting year 2000 to latest available.
- Reporting periods differ slightly: England & Wales and Scotland use financial years
  ending in the labelled year, while the PSNI chart uses calendar years. Scotland's
  denominator is the mid-year population within that financial year (for example,
  mid-2024 for 2024–25); Northern Ireland uses the same calendar year's population.

*(Not built: `data.police.uk` publishes a key-less police-recorded-crime API, but it is
street-level and only spans recent years, so it is unsuitable for the long-run trend. It
would be a natural extension for local/street-level analysis.)*

## Run

```bash
# fetch both sources, write data/crime_*.csv, render charts to outputs/crime/
./.venv/bin/python -m crime_data

# only the CSEW long-run trend:
./.venv/bin/python -m crime_data --sources csew

# rebuild charts from existing CSVs (no fetch):
./.venv/bin/python -m crime_data --from-csv
```

## Outputs

- `data/crime_csew_long.csv` — tidy: `region, offence_group, level, period, date, year,
  metric, value, unit, source` (git-ignored, regenerable).
- `data/crime_homicide_long.csv` — tidy: `iso3, country, year, metric, value, unit, source`.
- `data/crime_homicide_nations_long.csv` — homicide rates for England & Wales, Scotland,
  and Northern Ireland from 2000.
- `outputs/crime/crime_csew_total.png` — long-run total crime, England & Wales (the fall).
- `outputs/crime/crime_csew_21st_century.png` — the same CSEW series zoomed to the
  21st century.
- `outputs/crime/crime_fraud_gap.png` — total crime excl. vs incl. fraud & computer misuse.
- `outputs/crime/crime_homicide_peers.png` — homicide rate, UK vs US vs EU-27 mean.
- `outputs/crime/crime_homicide_nations.png` — homicide rates across UK jurisdictions
  since 2000.

Charts follow the shared house style (`vizstyle`: warm tan background, serif type, UK in the
terracotta accent, italic source note).

## Notes

- **Missing observations:** source gaps are not filled by interpolation. Northern
  Ireland homicide counts are chart-derived and subject to extraction/rounding error.
  Citations identify the collecting organisation and access route.
- **Inflation:** crime metrics are counts and rates, not monetary values, so no
  inflation adjustment applies.
