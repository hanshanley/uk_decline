# Bug Hunter report — `nhs_data`

**Summary: 3 HIGH, 6 MEDIUM, 8 LOW** across 14 files, from 6 parallel review dimensions
(correctness, logic, docs, readability, security, performance).

---

## HIGH

### Docs
- **`nhs_data/__main__.py:7`** — Documented usage `python -m nhs_data --from-csv data/nhs_waiting_times.csv --charts --summary` **errors** (`unrecognized arguments: --charts --summary`): argparse only defines `--no-charts`/`--no-summary`. → Drop the non-existent flags (both default on).

### Performance
- **`nhs_data/scotland.py:152,181`** — `_fetch_rtt_total` and `_fetch_rtt_median` each page the *entire* `RTT_ONGOING_RESOURCE` datastore with identical filters → the full RTT dataset is downloaded **twice** per run (dominant cost). → Fetch once, accumulate both total and weighted-median in one loop.
- **`nhs_data/wales.py:128,138`** — `_fetch_rtt_waiting_list_total` and `_fetch_rtt_median_wait_weeks` both paginate the identical StatsWales RTT view → paged **twice**. → Iterate once, dispatch rows to both outputs by `Data description`.

---

## MEDIUM

### Correctness
- **`nhs_data/england.py:383-384`** — A&E indexes `numeric[attendance_cols]` where `numeric = subset.select_dtypes(include="number")` but the column names come from `subset.columns`; if any count column is object dtype (thousands separators), this raises `KeyError`, the month is dropped, and a fully-object series silently loses all England A&E data. → Apply `_to_numeric` to `subset[...cols]` directly instead of indexing the `select_dtypes` result.

### Logic
- **`nhs_data/wales.py:196-201,221`** — Wales feeds an **8-week** breach count into `diagnostics_6week_breach_pct` (grouped path counts only `"Over 8 Weeks"`), whereas England/Scotland/NI all measure ~6 weeks. Wales's diagnostic standard is genuinely 8 weeks, so the shared metric silently mixes thresholds and understates Wales. → Source true 6-week bands where available, and add a Wales-specific 8-week caveat to `metrics.CAVEATS`.

### Readability
- **`nhs_data/northern_ireland.py:137`** — `_find_attachment` is dead code (never called; near-duplicate of `_find_attachment_on_pages`). → Delete it.
- **`scotland.py:43 / wales.py:277 / northern_ireland.py:86 / england.py:556`** — the "default to last ~10 years" range logic is reimplemented 4× under 3 names, inconsistently (only Scotland raises on `start > end`). → Extract one shared `year_bounds()` helper.
- **`scotland.py:39 / england.py:110 / northern_ireland.py:72 / wales.py:295`** — a `_warn(metric, exc)` stderr helper is duplicated with inconsistent prefixes. → Move one uniform helper to a shared module.
- **`wales.py:291 / england.py:573 / northern_ireland.py:387`** — end-of-`fetch()` year filtering is repeated 3 different ways. → Factor a single `filter_rows_by_year(rows, start, end)` helper.

---

## LOW

### Correctness
- **`nhs_data/wales.py:102-106`** — `_number(None)` does `float(str(None).strip())` → `ValueError` instead of returning `None`; a row missing `"Data values"` aborts the whole Wales metric. → Return `None` for `None`/NaN first.
- **`nhs_data/summary.py:50-52`** — the empty-DataFrame branch calls `path.write_text` without the `mkdir(parents=True)` the non-empty branch does → `FileNotFoundError` if the dir doesn't exist. → `mkdir` before writing in both branches.

### Readability
- **`charts.py:25 / summary.py:19`** — `_load(source)` is duplicated verbatim. → Hoist to a shared helper.
- **`summary.py:16`** — `DEFAULT_SUMMARY` is redefined even though `paths.py:10` defines it. → Import from `paths`.

### Security (threat model: official gov/NHS sources)
- **`nhs_data/england.py:229`** — `_csv_text_from_zip` decompresses a ZIP member in-memory with no size/ratio cap (zip-bomb vector on a scraped `.zip`). → Check `ZipInfo.file_size` against a cap before `read()`.
- **`nhs_data/_http.py:56`** — `get_bytes` buffers the entire body with no cap (memory exhaustion on a huge/redirected body). → Stream with a byte cap.
- **`england.py:117 / northern_ireland.py:131 / wales.py:83`** — download targets come from scraped HTML / server-supplied `odata.nextLink` and are fetched with default cross-host redirects (SSRF). → Restrict to an allow-list of `*.gov`/NHS hosts and validate redirects.

### Docs
- **`nhs_data/README.md:80-83`** — the NIR A&E caveat asserts a fixed "2015–2018" endpoint not enforced anywhere in code (risks going stale). → Reword to describe the source without hard-coding the endpoint.

---

## Files reviewed
`nhs_data/{__init__,__main__,_http,paths,nations,metrics,scotland,wales,england,northern_ireland,combine,charts,summary}.py`, `nhs_data/README.md`, `tests/test_nhs_data.py`

## Dimensions run
correctness · logic · docs · readability · security · performance
