# crime_data — Crime in the UK over time

Tracks crime in the UK across the long run and against international peers, using the
authoritative **Crime Survey for England & Wales (CSEW)** and the internationally comparable
**homicide rate**. The story is deliberately **nuanced** — it is not a simple "everything got
worse".

## The story

| Measure | What it shows | Trend |
|---|---|---|
| **Total CSEW crime** (excl. fraud) | The ONS-preferred long-run trend measure | **Fell sharply**: peak **19.8M** incidents (1995) → **~4.4M** (2025). |
| **Total CSEW crime incl. fraud & computer misuse** | The same headline once online harms are counted (from 2017) | **~9.6M** (2025) — i.e. **roughly double** the excl.-fraud figure. Crime has shifted **online**, not simply vanished. |
| **Homicide rate** | The most internationally comparable crime statistic | UK **~1.1 per 100k** — far below the **US (~5.8)** and now around/below the **EU-27 mean**. |

The headline "crime has halved" narrative is true for traditional victim-based crime, but
incomplete: once fraud and computer misuse (measured from 2017) are added, total crime is
about twice the headline, and specific harms have not all fallen. The charts let the data
show both sides.

## Data sources & method

Every value is fetched live or parsed **verbatim** from the source; nothing is hand-entered.
Each chart prints its source as a caption, taken from the data's own `source` column.

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

### 2. World Bank — intentional homicide rate (per 100,000) → peer comparison

> UN Office on Drugs and Crime (UNODC), *Intentional homicides (per 100,000 people)*,
> indicator `VC.IHR.PSRC.P5`, via the World Bank World Development Indicators.
> <https://data.worldbank.org/indicator/VC.IHR.PSRC.P5>

- **Collected by:** the **UNODC** (compiled from national criminal-justice and public-health
  sources); redistributed by the World Bank. Fetched live via `https://api.worldbank.org/v2`.
- **Coverage:** UK + EU-27 + US; UK ~1990–2021.

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
- `outputs/crime/crime_csew_total.png` — long-run total crime, England & Wales (the fall).
- `outputs/crime/crime_fraud_gap.png` — total crime excl. vs incl. fraud & computer misuse.
- `outputs/crime/crime_homicide_peers.png` — homicide rate, UK vs US vs EU-27 mean.

Charts follow the shared house style (`vizstyle`: warm tan background, serif type, UK in the
terracotta accent, italic source note).

## Notes

- **Data integrity:** all figures are fetched/parsed directly from ONS and the World Bank;
  none are interpolated, mocked, or hand-entered. Citations credit the collecting
  organisation (ONS/CSEW; UNODC via the World Bank).
- **Inflation:** crime metrics are counts and rates, not monetary values, so no
  inflation adjustment applies.
