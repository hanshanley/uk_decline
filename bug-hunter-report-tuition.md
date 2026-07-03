# Bug Hunter report — tuition sub-analysis (pass 3, post-refactor)

**Summary: 0 HIGH, 1 MEDIUM, 2 LOW — converged.** Third pass over the surface changed
since pass 2 (new `tuition/dataset.py`, refactored `plot_tuition.py`, `config.is_primary`
/`REGION_LABELS`, new tests). Logic and security returned "No issues found"; only cosmetic
polish remained. Pipeline re-verified: UK $12,179 / EU-27 $424 / US $11,610.

## MEDIUM
### Readability
- **plot_tuition.py:25** — local alias `REGION_LABEL` (singular) rebinds
  `config.REGION_LABELS` (plural), inconsistent with `analyze.py`. → rename to
  `REGION_LABELS`. **Fixed.**

## LOW
- **tuition/dataset.py:27** (correctness) — `value_keys: Iterable[str]` is iterated once
  per row; a one-shot generator would exhaust after row 1, leaving later rows uncoerced.
  → materialize with `list(value_keys)` at entry. **Fixed.**
- **README_tuition.md:76-81** (docs) — layout omitted the new `dataset.py` module. → added
  a `dataset.py` entry. **Fixed.**

## Verified clean
- **Logic:** analyze.py and plot_tuition.py now apply an identical primary-row filter via
  the single `dataset.load_primary` → `config.is_primary`; region-presence filter matches
  the subsequent indexing; in-place coercion harms no caller. **No issues found.**
- **Security:** no unsafe path handling or parsing in the new loader. **No issues found.**
- **Correctness:** 10/10 tests pass; zeros preserved; all callers pass lists.

## Plot-style parity (vs pre1870_reapportionment_package)
Compared against BOTH theme variants in that project: `theme.py` is a byte-for-byte match
of the canonical/fuller `scripts/generate_figures.py` theme (serif, size 12, spines off,
full palette); the lighter `plot_immigration_by_region.py` variant shares the same
`#F7F5F0` / `#1A1A1A` / `#6B6B6B` / `#D6D3CC` colors. Rendered figures confirmed consistent.

## Files reviewed
tuition/{dataset,config,stats,theme}.py, plot_tuition.py, analyze.py, tests/test_tuition.py,
README_tuition.md

## Dimensions run
Correctness · Logic consistency · Comments/docs · Readability · Security
(Performance skipped — no perf-relevant change since pass 2, which was clean.)
