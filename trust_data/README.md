# trust_data — Trust in UK government over time

Measures **trust in government in the UK over time**, UK-first with **EU-27 + US**
comparators. Two complementary angles (different scales — read each on its own):

| Angle | Metric(s) | What it is |
|---|---|---|
| **Survey (subjective)** | `trust_national_govt_pct` | Share of people who say they trust the national government (%) |
| **Governance quality (objective proxy)** | `wgi_voice_accountability`, `wgi_government_effectiveness`, `wgi_rule_of_law`, `wgi_control_of_corruption` | World Bank Worldwide Governance Indicators, estimate ≈ −2.5…+2.5 |

## Headline finding (UK)

- **Survey trust in national government:** 42.5% (2007) → **34.5% (2024)** — a falling trend,
  ~9.6 pts below the EU-27 mean (44.1%).
- **WGI governance quality:** all four indicators are lower in 2024 than at the 1996 series
  start; Control of Corruption and Government Effectiveness fell most.

---

## Data sources & citations

Every value in this pipeline is fetched from, or traceable to, the sources below, **credited
to the organisation that collected the data**. **Nothing is hand-authored or estimated.** The
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
- **Coverage:** UK 2007–2024 (survey waves); 27 of our 29 countries.
- **How the seed was built:** `data/trust/raw/manual_trust.csv` was generated **verbatim**
  from the OWID CSV above (filtered to our country set; values only rounded to 2 dp), and is
  re-verified against a fresh download — 187/187 rows match exactly (audit below).
- **Live attempt:** `trust_data/oecd.py` also tries the OECD SDMX API directly
  (`OECD.GOV.GIP,DSD_GOV_INT@DF_GOV_TDG_2025`, measure `TRUST_NG`); it rate-limits (HTTP 429),
  so the pipeline falls back to the OWID-sourced seed. Live rows take precedence when present.
- **`source` column value:**
  `OECD Trust in Government via Our World in Data (grapher: oecd-average-trust-in-governments)`.

> **Provenance guarantee.** Run the audit below to confirm every seed value still matches the
> live OWID/OECD source (0 mismatches expected):
>
> ```bash
> curl -s "https://ourworldindata.org/grapher/oecd-average-trust-in-governments.csv?csvType=full&useColumnShortNames=true" -o /tmp/src.csv
> .venv/bin/python - <<'PY'
> import csv
> src={(x['code'],int(x['year'])):round(float(x['trust_in_government']),2)
>      for x in csv.DictReader(open('/tmp/src.csv')) if x['code'] and x['trust_in_government']!=''}
> bad=[(r['iso3'],r['year']) for r in csv.DictReader(open('data/trust/raw/manual_trust.csv'))
>      if src.get((r['iso3'],int(r['year']))) != round(float(r['value']),2)]
> print('untraceable rows:', len(bad))
> PY
> ```

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
| `oecd_trust_national_govt.csv` | OECD survey rows (live if available, else OWID-sourced seed) |
| `trust_combined_long.csv` / `trust_combined_wide.csv` | Combined tidy tables |
| `manifest.json` | Run metadata: row counts, year span, **the exact `sources` list** |
| `processed/trust_summary.csv` | UK trend summary (first/latest/change/direction, vs EU-27 & US) |
| `../outputs/trust/*.png` | One trend chart per metric, UK highlighted, **with a source caption** |

## Figures

`trust_data/charts.py` renders one PNG per metric (`make_charts()`): a line per country with
the **UK bold/red**, EU-27 faded, US green. Each figure prints a **source caption** taken
directly from the plotted rows' `source` column plus the covered year range — so a figure can
never claim a source the underlying data didn't carry.

## Schema

Tidy long rows (`trust_data/metrics.py`, `ROW_FIELDS`):
`iso3, country, year, metric, value, unit, source`.

---

## How far back does this go, and why not the 1970s?

- **WGI** genuinely begins in **1996** (World Bank does not publish earlier estimates).
- **OECD survey trust** genuinely begins in **2007** for the UK (Gallup World Poll basis).

There is **no free, machine-readable source** that carries UK *trust-in-government* back to
the 1970s. The only UK series reaching that far is the survey question *"trust governments of
any party to place the needs of the nation above their own party"* — **British Election Study
(1974)** and **British Social Attitudes (1986+)**. That data lives only in:
- **UK Data Service microdata** (registration-gated; `britishelectionstudy.com`, `natcen.ac.uk`), and
- **NatCen BSA report PDFs** (headline figures in tables/charts, not a downloadable series).

To honour the project's integrity rule — *every value must trace to a real, downloadable
source* — those pre-1996/pre-2007 figures are **deliberately not included**, because doing so
would mean transcribing/estimating numbers rather than pulling them from a verifiable file. If
you register with the UK Data Service and download the BES/BSA cumulative files, they can be
added as a new metric (`trust_govt_nation_above_party_pct`) via the same `manual.py` seed
mechanism, with the UK Data Service study number recorded in the `source` column.

## A note on inflation

These metrics are **not monetary** — they are survey percentages (0–100) and governance index
scores (≈ −2.5…+2.5). There is no price/currency component, so **inflation adjustment does not
apply** and none is performed. (Inflation-adjustment *is* relevant in the sibling `europe_data`
and `tuition` projects, which deal with GDP/income and fees in currency.)

## Data integrity

- WGI rows are fetched live from the World Bank API every run.
- Survey rows come verbatim from the OWID/OECD CSV (audit above proves 0 untraceable rows).
- Chart captions and `manifest.json` echo the exact `source` recorded on the data.
- No value in this pipeline is generated, interpolated, or estimated by the tooling.
