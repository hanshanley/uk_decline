# Bug Hunter report — `uk_migration/`

**Summary: 0 HIGH, 5 MEDIUM, 7 LOW** (1 agent finding rejected as factually incorrect).

Dimensions run: Correctness, Logic consistency, Comments/Docs, Readability.
(Security & Performance skipped — read-only data pipeline, no untrusted input, no hot paths.)

---

## MEDIUM

### Correctness
- **`_aggregate.py:63,80,83`** — Quarter-completeness tracked per **year** (union across all
  categories) but totals are per `(year, category)`. A category whose quarters are incomplete in a
  year survives if *another* category fills that year's quarter set — silently publishing a
  partial-year sum as a full annual figure. Reproduced: method `a`=Q2–Q4, `b`=Q1–Q4 for 2018 → `a`
  kept as a 3-quarter total. Latent hazard for `small_boats.py`.
  -> Track quarters per `(year, category)`; drop incomplete `(year, category)` pairs.

### Comments / docs
- **`sources/ons_ltim.py:8`** — Docstring's "UK left EU-SILC after Brexit" is false (EU-SILC is the
  income survey, unrelated to LTIM migration flows). -> Remove the EU-SILC sentence.

### Readability
- **`sources/small_boats.py`** — Named `small_boats` but parses all irregular methods
  (air/port/in_country/+all) under `irregular_arrivals`. -> Rename module to `irregular.py`.
- **`schema.py:12,26`** — `legality` conflates legal/irregular with measure type (`net`,`stock`);
  filtering `legality=='legal'` silently drops stock/net rows. -> Split a `flow_type` field.
- **`sources/{visas,asylum,small_boats}.py fetch()`** — Identical
  `govuk_attachment -> get_bytes -> parse(read_rows(...))` body copied 3x. -> Extract shared helper.

---

## LOW

### Correctness
- **`sources/ons_ltim.py:36`** — `(\d{2})` + search grabs only first 2 digits; a 4-digit label
  `"YE Dec 2024"` would match `20` -> year 2020 (silent). -> Accept `\d{2,4}`, map explicitly.
- **`sources/worldbank.py:64`** — `end=2025` hard-coded; from 2026 on, 2026+ data excluded.
  -> Default `end` to current year.

### Logic consistency
- **`_govuk.py:36`** — `govuk_attachment` first-match, no date tiebreak if >1 match. -> Assert single/sort.
- **`_govuk.py:54`** — `ons_latest_download` trusts `datasets[0]` is newest, unvalidated. -> Sort editions.

### Comments / docs
- **`__init__.py:7`** — "small-boats data set -> irregular Channel arrivals" understates scope.
  -> "irregular arrivals by route (incl. small boats)".
- **`README.md ## Caveats`** — Europe-pipeline caveats (PPP, micro-states, Russia/Turkey) don't
  apply to UK migration. -> Scope to Europe section.

### Readability
- **`charts.py:38`** — `_thousands(ax)` also silently enables the grid. -> Rename/split.

---

## Rejected (verified incorrect)
- ~~`worldbank.py:6` — "SM.POP.NETM is 5-year, not annual"~~ — Rejected. `data/raw/worldbank.csv`
  has 66 values 1960–2025, no gaps, distinct year-over-year. Series is annual as fetched.

## Files reviewed
`uk_migration/{__init__,schema,_http,_govuk,_spreadsheet,_aggregate,combine,charts,run}.py`,
`sources/{worldbank,ons_ltim,visas,asylum,small_boats}.py`,
`tests/{test_uk_migration,test_govuk,test_spreadsheet_combine}.py`.
