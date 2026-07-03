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

## Data sources (all free, no API key)

Every value in this pipeline is fetched from, or traceable to, one of the sources below.
**Nothing is hand-authored or estimated.** The `source` column on every tidy row records
which one it came from, and each chart prints that same attribution as a caption.

### 1. World Bank — Worldwide Governance Indicators (WGI)  → governance metrics
- **Endpoint:** `https://api.worldbank.org/v2/country/{ISO3}/indicator/{IND}?source=3&format=json`
- **Indicators (database `source=3`):**
  `GOV_WGI_VA.EST` (Voice & Accountability), `GOV_WGI_GE.EST` (Government Effectiveness),
  `GOV_WGI_RL.EST` (Rule of Law), `GOV_WGI_CC.EST` (Control of Corruption) — the *estimate*
  series (≈ −2.5…+2.5).
- **Coverage:** UK 1996–2024 (biennial 1996–2002, annual thereafter).
- **Fetched live** each run by `trust_data/worldbank.py`.
- **Source column value:** `World Bank WGI`.

### 2. OECD "Trust in national government" (via Our World in Data)  → survey metric
- **Primary source:** OECD *Trust in Government* / *Government at a Glance* (based on the
  Gallup World Poll question on confidence in national government).
- **Machine-readable file actually used:** Our World in Data grapher CSV, which republishes
  the OECD series per country:
  `https://ourworldindata.org/grapher/oecd-average-trust-in-governments.csv?csvType=full&useColumnShortNames=true`
  (column `trust_in_government`).
- **Coverage:** UK 2007–2024 (survey waves, roughly triennial); 27 of our 29 countries.
- **How the seed was built:** `data/trust/raw/manual_trust.csv` was generated **verbatim**
  from the OWID CSV above (filtered to our country set; values only rounded to 2 dp). It is
  re-verified against a fresh download in `tests`/audit — 187/187 rows match exactly.
- **Live attempt:** `trust_data/oecd.py` also tries the OECD SDMX API directly
  (`OECD.GOV.GIP,DSD_GOV_INT@DF_GOV_TDG_2025`, measure `TRUST_NG`). The OECD API rate-limits
  aggressively (HTTP 429), so the pipeline falls back to the OWID-sourced seed above. Live
  OECD rows, when available, take precedence over the seed.
- **Source column value:**
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
python fetch_trust.py                 # all sources, 1974-current (WGI 1996+, survey 2007+)
python fetch_trust.py --charts --summary
python fetch_trust.py --sources worldbank --start 1996 --end 2024
```

Outputs (written to `data/trust/`):

| File | Contents |
|---|---|
| `worldbank_wgi.csv` | Live WGI rows (tidy long) |
| `oecd_trust_national_govt.csv` | OECD survey rows (live if available, else OWID-sourced seed) |
| `trust_combined_long.csv` / `trust_combined_wide.csv` | Combined tidy tables |
| `manifest.json` | Run metadata: row counts, year span, **the exact `sources` list** |
| `processed/trust_summary.csv` | UK trend summary (first/latest/change/direction, vs EU-27 & US) |
| `charts/*.png` | One trend chart per metric, UK highlighted, **with a source caption** |

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
