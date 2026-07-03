"""Compute headline trends and emit a short markdown summary.

For each metric, report each nation's earliest and latest observed value, the
change over the covered period, and a plain-language direction. Definitional
caveats from :data:`nhs_data.metrics.CAVEATS` are included so the summary stays
honest about cross-nation comparability.
"""

from __future__ import annotations

from pathlib import Path

from . import _util, metrics, nations, sources
from .paths import DEFAULT_CSV, DEFAULT_SUMMARY


def _load(source):
    return _util.load_frame(source, DEFAULT_CSV)


def _fmt(value: float, unit: str) -> str:
    if unit == "patients":
        if value >= 1e6:
            return f"{value/1e6:.2f}M"
        return f"{value/1e3:.0f}k"
    if unit == "percent":
        return f"{value:.1f}%"
    if unit == "weeks":
        return f"{value:.1f} wks"
    if unit == "per 1,000 people":
        return f"{value:.1f}/1k"
    return f"{value:g}"


def build_summary(source=None, path: Path | str = DEFAULT_SUMMARY) -> Path:
    """Write a markdown trend summary and return its path."""
    import pandas as pd

    df = _load(source)
    lines: list[str] = []
    lines.append("# UK NHS waiting times & waiting lists \u2014 trend summary\n")
    if df.empty:
        lines.append("_No data available._\n")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines))
        return path

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    lo, hi = df["date"].min(), df["date"].max()
    lines.append(
        f"Coverage: **{lo:%b %Y} \u2013 {hi:%b %Y}** across "
        f"{df['nation_code'].nunique()} nations. Source data is devolved and "
        "defined differently per nation \u2014 read each metric's caveat and compare "
        "*trends*, not exact levels.\n"
    )

    for metric_id, meta in metrics.METRICS.items():
        sub = df[df["metric"] == metric_id]
        if sub.empty:
            continue
        lines.append(f"\n## {meta.label} ({meta.unit})\n")
        lines.append(f"{meta.description}\n")
        lines.append("| Nation | First | Latest | Change |")
        lines.append("|---|---|---|---|")
        for code in nations.codes():
            g = sub[sub["nation_code"] == code].dropna(subset=["date"]).sort_values("date")
            if g.empty:
                continue
            first, last = g.iloc[0], g.iloc[-1]
            delta = last["value"] - first["value"]
            arrow = "\u2192"
            if delta > 0:
                arrow = "\u2191"
            elif delta < 0:
                arrow = "\u2193"
            worse = (delta > 0) != meta.higher_is_better and delta != 0
            tag = " (worse)" if worse else (" (better)" if delta != 0 else "")
            lines.append(
                f"| {nations.name_for_code(code)} "
                f"| {_fmt(first['value'], meta.unit)} ({first['date']:%b %Y}) "
                f"| {_fmt(last['value'], meta.unit)} ({last['date']:%b %Y}) "
                f"| {arrow} {_fmt(abs(delta), meta.unit)}{tag} |"
            )
        caveat = metrics.CAVEATS.get(metric_id)
        if caveat:
            lines.append(f"\n> Caveat: {caveat}")

    lines.append("\n" + sources.render_markdown())

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path
