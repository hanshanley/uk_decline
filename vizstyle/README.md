# vizstyle — shared "Substack" plotting style

A tiny Python utility that gives every `uk_decline` analysis the **same house style** in one
import: warm off-white background, serif type, muted grid, no top/right spines, a consistent
palette (UK / London always in terracotta), and a standard italic source note.

It exists so charts don't each re-declare the theme dict and colours (they used to — see the
duplication across `*_data/charts.py`). New analyses should import from here.

## Quick start

```python
from vizstyle import house_style, PALETTE, source_note, end_label, save_fig
import matplotlib.pyplot as plt

house_style()                      # apply the shared rcParams (once, before plotting)

fig, ax = plt.subplots(figsize=(11, 6))
ax.plot(x, uk,   color=PALETTE["accent"], linewidth=2.8, label="UK")      # focus series
ax.plot(x, peer, color=PALETTE["blue"],   linewidth=1.8, label="Peers")   # reference
ax.grid(axis="y"); ax.set_axisbelow(True)

end_label(ax, x[-1], uk[-1], "UK", PALETTE["accent"])   # end-of-line label with white halo
source_note(fig, "Data: Office for National Statistics (ONS).")
save_fig(fig, "outputs/london/example.png")             # tight layout + dpi=200 + close
```

## Palette

| Name | Hex | Use |
|---|---|---|
| `bg` | `#F7F5F0` | figure / axes background |
| `card` | `#EFEDE8` | slightly darker panel fill |
| `text` | `#1A1A1A` | primary ink |
| `muted` | `#6B6B6B` | ticks, secondary text, source notes |
| `grid` | `#D6D3CC` | gridlines, spines |
| `accent` | `#C85A3D` | **focus series** — UK / London (terracotta) |
| `blue` | `#3D6F8C` | reference / comparison series |
| `gold` | `#C2993E` | third series |
| `green` | `#4A7C59` | "better" / positive series |

Access as module constants (`vizstyle.ACCENT`) or via the `PALETTE` dict
(`PALETTE["accent"]`).

## API

| Symbol | What it does |
|---|---|
| `house_style()` | Apply the shared rcParams to `plt.rcParams`. Call once before plotting. Idempotent. |
| `RC_PARAMS` | The rcParams dict itself (if you want to merge/inspect). |
| `PALETTE`, `BG`, `TEXT`, `MUTED`, `GRID`, `ACCENT`, `BLUE`, `GOLD`, `GREEN` | Colours. |
| `source_note(fig, text, *, x=0.01, y=0.01, ha="left")` | Standard italic muted source note at the figure margin. |
| `end_label(ax, x, y, text, color, *, fontsize=10.5)` | Label a series at its end point, with a white halo for legibility. |
| `white_stroke()` | The path-effects list for a white text outline (labels over data). |
| `save_fig(fig, path, *, dpi=200, bottom=0.12, pad=0.6)` | `tight_layout` + bottom margin, save at house DPI, and close the figure. |

## Conventions

- **UK / London is always the terracotta `accent`;** comparators use `blue` (then `gold`,
  `green`). This keeps the "subject of the story" visually consistent across analyses.
- **Every figure carries a `source_note`** naming the data's collecting organisation.
- **Titles** are bold; add a muted one-line subtitle with
  `ax.text(0.5, 1.015, subtitle, transform=ax.transAxes, ha="center", va="bottom",
  color=vizstyle.MUTED)` when a chart needs a takeaway line.
- **Save at `dpi=200`, `bbox_inches="tight"`** (handled by `save_fig`).
- Charts render headless (`matplotlib.use("Agg")` is set on import) — no display needed.

## Reference implementation

`london_data/charts.py` is the canonical example: it imports `vizstyle`, uses a single
shared line-chart helper for both figures, and derives axis bounds from the data.

**All sibling analyses now use `vizstyle`** — `rail_data`, `markets_data`, `age_data`,
`tax`, `nhs_data`, `trust_data`, `uk_migration`, `europe_data/plot_uk_decline.py`, and
`tuition` (via a back-compat `tuition/theme.py` shim). `scorecard.py` sources its palette
from here but keeps a bespoke rcParams (it hides the left spine for the small-multiples).

### Note on `text.parse_math`

`RC_PARAMS` sets `text.parse_math: False` so that literal `$` in labels (e.g. `$11.4k`
tuition) is drawn verbatim rather than parsed as LaTeX math. If a chart uses a **log axis**
(whose tick labels are mathtext like `10⁶`), re-enable it locally after `house_style()`:

```python
house_style()
plt.rcParams["text.parse_math"] = True   # only if you use log-scale / mathtext labels
```

`uk_migration` does exactly this for its log-scale immigration chart.
