# Bug Hunter report — `uk_decline` (europe_data pipeline + figures)

> Scoped to the `europe_data/` GDP & median-income pipeline, `fetch_data.py`,
> `plot_uk_decline.py`, and `tests/test_pipeline.py`. (The shared `bug-hunter-report.md`
> is used by a parallel `uk_migration` session, hence this project-scoped file.)

**Summary across two passes: 0 HIGH, 0 MEDIUM open, 5 LOW + 1 MEDIUM — all resolved or
intentionally deferred.**

## Pass 1 — data pipeline (6 dimensions)
Correctness, Logic, Comments/docs, Security = **clean** (reviewers validated the Eurostat
JSON-stat decoder, World Bank paging, and PIP dedup against the live APIs).

Findings, all LOW, **fixed**:
- `worldbank.py` — explicit curated-name-then-API-name resolution (dropped misleading `or`).
- `pip.py` — same name resolution; preference rank stored as `(pref, record)` tuples
  instead of a transient `_pref` field popped in a second pass.
- `combine.py` — removed the no-op `write_source_csv` wrapper; call `write_long` directly.

LOW **deferred** (acceptable for a one-shot ETL): `worldbank.py` fetches each indicator as
its own paginated sweep. Combining/parallelizing would add complexity and change error
semantics for little gain.

## Pass 2 — re-check incl. `plot_uk_decline.py` + style parity
- **Correctness / Logic / Docs / Security**: clean. The correctness agent ran the plot
  pipeline on synthetic edge cases (empty DataFrame, empty series, UK-income-ends-2018) —
  no runtime errors; ratio index-alignment, EU-aggregate-by-metric split (World Bank EUU
  for GDP vs Eurostat EU27_2020 for income), and PIP aggregate exclusion all verified.
- **Style parity vs `pre1870_reapportionment_package`**: exact match. Palette
  byte-identical; all 20 `rcParams` identical (programmatic diff: 0 missing / 0 extra /
  0 divergent); title/label/tick/source-note/savefig(dpi=200,tight)/path-effects all match
  `generate_figures.py`.
- **Readability (1 MEDIUM, fixed)**: `fig_gdp_over_time` and `fig_median_income`
  duplicated the same plot loop + finalization block. → Extracted a shared `_line_chart(...)`
  helper; both are now thin calls from `main`. Provably behavior-preserving — all four
  output PNGs are **byte-identical** (same MD5) before and after.

## Verification
- `tests/test_pipeline.py`: 3/3 pass (after all fixes).
- Pipeline re-run end-to-end (2000–2024): 44 countries + EU/euro-area aggregates, correct data.
- Figures re-rendered; MD5s unchanged across the refactor.

## Files reviewed
`fetch_data.py`, `europe_data/{_http,countries,worldbank,eurostat,pip,combine}.py`,
`plot_uk_decline.py`, `tests/test_pipeline.py`, `README.md` (docs dimension),
`pre1870_reapportionment_package/scripts/{generate_figures,plot_immigration_by_region}.py`
(style reference).

## Dimensions run
Correctness, Logic, Comments/docs, Security, Readability, Performance, Style-parity.

## Pass 3 — fresh re-verification
Confirmed no drift (files untouched since pass 2). Re-ran correctness, logic+readability,
and style-parity agents; recompiled, re-tested (3/3), re-rendered all four figures.
- **Correctness / Logic / Style-parity**: clean. Correctness agent re-verified the
  `_line_chart` refactor and PIP/WDI field names against the live APIs.
- **Style parity**: palette + all 20 `rcParams` byte-identical to `generate_figures.py`
  (re-checked programmatically and by agent).
- **Readability (1 LOW, intentionally kept)**: `SUBSTACK_CARD` is defined-but-unused —
  but the reference `generate_figures.py` *also* defines it unused (line 49). Kept to
  preserve exact palette parity with the reference theme (removing it would break the
  9-constant palette match).
