# trust_data — Trust in UK government over time

Measures **trust in government in the UK over time**, UK-first with **EU-27 + US**
comparators. Two complementary angles (different scales — read each on its own):

| Angle | Metric(s) | What it is |
|---|---|---|
| **Survey (subjective)** | `trust_national_govt_pct` | Share of people who say they trust the national government (%) |
| **Governance quality (perceptions-based composite)** | `wgi_voice_accountability`, `wgi_government_effectiveness`, `wgi_rule_of_law`, `wgi_control_of_corruption` | World Bank Worldwide Governance Indicators, estimate ≈ −2.5…+2.5; not a direct public-trust measure |

## Headline finding (UK)

- **Survey trust in national government:** 42.5% in the pooled period ending 2007 →
  **34.5% in the period ending 2024** — lower at these endpoints, ~9.6 pts below
  the reporting EU countries' mean (44.1%).
- **WGI governance quality:** all four indicators are lower in 2024 than at the 1996 series
  start; Control of Corruption and Government Effectiveness fell most.

---

## Data sources & citations

Every value in this pipeline is fetched from, or traceable to, the sources below, **credited
to the organisation that collected the data**. **The tooling does not fabricate source
observations**; WGI itself consists of source-published estimates. The
`source` column on every tidy row records which one it came from; each chart prints a short
citation caption; and `trust_data/citations.py` is the single source of truth for the full
citations reproduced here.

### 1. World Bank — Worldwide Governance Indicators (WGI)  → governance metrics

> Kaufmann, Daniel & Aart C. Kraay (2024). "The Worldwide Governance Indicators: Methodology
> and 2024 Update." Policy Research Working Paper. Washington, DC: World Bank Group. Dataset:
> *Worldwide Governance Indicators (WGI)*, 2024 update, World Bank Group, Washington, DC.
> https://www.govindicators.org

- **Collected/compiled by:** the World Bank Group (WGI draws on 30+ underlying sources).
- **Accessed via:** `https://api.worldbank.org/v2/country/{ISO3}/indicator/{IND}?source=3` —
  indicators `GOV_WGI_VA.EST`, `GOV_WGI_GE.EST`, `GOV_WGI_RL.EST`, `GOV_WGI_CC.EST` (estimate
  series, ≈ −2.5…+2.5).
- **Coverage:** UK 1996–2024. **Fetched live** by `trust_data/worldbank.py`.
- **`source` column value:** `World Bank WGI`.

### 2. OECD — trust in national government (via Our World in Data)  → survey metric

> OECD (2026), with major processing by Our World in Data. "OECD average trust in
> governments" [dataset]. Original data: OECD, *How's Life? Well-being Database* — survey item
> from the Gallup World Poll ("In this country, do you have confidence in national government,
> or not?"). https://ourworldindata.org/grapher/oecd-average-trust-in-governments

- **Collected/compiled by:** the OECD (in its *How's Life? Well-being Database*); the
  underlying survey is the **Gallup World Poll**. Redistributed/processed by **Our World in
  Data**.
- **Machine-readable file used:**
  `https://ourworldindata.org/grapher/oecd-average-trust-in-governments.csv?csvType=full&useColumnShortNames=true`
  (column `trust_in_government`, a percentage).
- **Coverage:** UK pooled-period end years 2007–2024; 27 of the 29 selected countries.
- **Period definition:** OECD publishes 2- and 3-year pooled Gallup averages.
  OWID labels each observation by its final year (for example, the 2020–2022
  average is labelled 2022). These are not annual readings or instant snapshots.
- **Live retrieval:** `trust_data/owid.py` downloads and parses the machine-readable CSV on
  every production run. `trust_data/oecd.py` can validate the separate OECD Drivers of Trust
  SDMX dataflow (`TRUST_NG`, scale `HMH`), but those observations are not spliced into this
  trend because they come from a different survey instrument.
- **`source` column value:**
  `OECD Trust in Government via Our World in Data (grapher: oecd-average-trust-in-governments)`.

---

## How to run

```bash
python -m trust_data.fetch_trust                 # all sources, 1974-current (WGI 1996+, survey 2007+)
python -m trust_data.fetch_trust --charts --summary
python -m trust_data.fetch_trust --sources worldbank --start 1996 --end 2024
```

Outputs (written to `data/trust/`):

| File | Contents |
|---|---|
| `worldbank_wgi.csv` | Live WGI rows (tidy long) |
| `oecd_trust_national_govt.csv` | Live OWID/OECD historical survey rows |
| `trust_combined_long.csv` / `trust_combined_wide.csv` | Combined tidy tables |
| `manifest.json` | Run metadata: row counts, year span, **the exact `sources` list** |
| `processed/trust_summary.csv` | UK trend summary (first/latest/change/direction, vs EU-27 & US) |
| `../outputs/trust/*.png` | One trend chart per metric, UK highlighted, **with a source caption** |

## Figures

`trust_data/charts.py` renders one PNG per metric (`make_charts()`): the **UK bold/red**,
US green, and an unweighted median plus interquartile band for reporting EU-27 countries.
This is not a population-weighted EU aggregate; coverage can vary by year, and the
caption states the number of reporting countries. The summary uses a reporting-country
mean instead, so its comparator is not the chart's median. Each figure prints a **source caption** taken
directly from the plotted rows' `source` column plus the covered year range — so a figure can
never claim a source the underlying data didn't carry.

## Schema

Tidy long rows (`trust_data/metrics.py`, `ROW_FIELDS`):
`iso3, country, year, metric, value, unit, source`.
For the OWID/OECD survey series, `year` denotes the end of the pooled period;
for WGI it denotes the observation year.

---

## How far back does this go, and why not the 1970s?

- **WGI** genuinely begins in **1996** (World Bank does not publish earlier estimates).
- **OECD survey trust** first covers a UK pooled period ending in **2007**
  (Gallup World Poll basis).

Older **British Election Study** and **British Social Attitudes** series ask about
trusting governments of any party to put the nation's needs above their party's
interests. That is a different question from the Gallup confidence-in-national-government
item. Those observations are not spliced into this series; a longer history would
need a separate metric with its own survey definition and source attribution.

## A note on inflation

These metrics are **not monetary** — they are survey percentages (0–100) and governance index
scores (≈ −2.5…+2.5). There is no price/currency component, so **inflation adjustment does not
apply** and none is performed. (Inflation-adjustment *is* relevant in the sibling `europe_data`
and `tuition` projects, which deal with GDP/income and fees in currency.)

## Data integrity

- WGI rows are fetched live from the World Bank API every run.
- Survey values are read from the live OWID/OECD CSV.
- Chart captions and `manifest.json` echo the exact `source` recorded on the data.
- The pipeline does not interpolate missing survey waves or governance observations.
  Reporting-country means, medians and interquartile ranges are derived summaries.
