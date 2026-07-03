"""Compute headline trends and emit a short markdown summary.

The framing is UK-vs-US: for each metric, report the UK and US first/latest
values and the UK-as-a-share-of-US ratio over time (with its peak), so the
relative decline (or not) of the UK market is visible. Reference regions are
listed for context. Definitional caveats are included to keep comparisons honest.
"""

from __future__ import annotations

from pathlib import Path

from . import markets, regions
from .paths import DEFAULT_CSV, DEFAULT_SUMMARY


def _load(source):
    import pandas as pd

    if source is None:
        source = DEFAULT_CSV
    if hasattr(source, "columns"):
        return source
    return pd.read_csv(source)


def _fmt(value: float, unit: str) -> str:
    if value is None:
        return "n/a"
    if "US$" in unit:
        return markets.format_usd(value)
    if unit == "% of GDP":
        return f"{value:.0f}%"
    if unit == "companies":
        return f"{value:,.0f}"
    return f"{value:g}"


def _first_last(sub, code):
    g = sub[sub["region_code"] == code].dropna(subset=["value"]).sort_values("year")
    if g.empty:
        return None, None
    return g.iloc[0], g.iloc[-1]


def build_summary(source=None, path: Path | str = DEFAULT_SUMMARY) -> Path:
    """Write a markdown UK-vs-US trend summary and return its path."""
    df = _load(source)
    lines: list[str] = []
    lines.append("# UK vs US stock-market size \u2014 trend summary\n")

    if df.empty:
        lines.append("_No data available._\n")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        return path

    df = df.copy()
    ylo, yhi = int(df["year"].min()), int(df["year"].max())
    all_sources = sorted(str(s) for s in df["source"].dropna().unique())
    real = df[df["metric"] == "market_cap_usd_real"]
    base_year = int(real["year"].max()) if not real.empty else None
    lines.append(
        f"Coverage: **{ylo}\u2013{yhi}** across {df['region_code'].nunique()} regions. "
        f"Sources: {', '.join(all_sources)} (no API key). The comparison is anchored on "
        "the UK vs the US; World / EU / Japan / China are shown for context."
    )
    if base_year is not None:
        lines.append(
            f"Real (inflation-adjusted) figures are in **constant {base_year} US$**, the "
            f"nominal series deflated by US CPI ({markets.CPI_INDICATOR}).\n"
        )
    else:
        lines.append("")

    for metric_id, meta in markets.METRICS.items():
        sub = df[df["metric"] == metric_id]
        if sub.empty:
            continue
        lines.append(f"\n## {meta.label} ({meta.unit})\n")
        lines.append(f"{meta.description}\n")

        lines.append("| Region | First | Latest |")
        lines.append("|---|---|---|")
        for code in regions.codes():
            first, last = _first_last(sub, code)
            if first is None:
                continue
            lines.append(
                f"| {regions.name_for_code(code)} "
                f"| {_fmt(first['value'], meta.unit)} ({int(first['year'])}) "
                f"| {_fmt(last['value'], meta.unit)} ({int(last['year'])}) |"
            )

        # UK-as-share-of-US ratio, where both exist in the same year.
        ratio = markets.uk_us_ratio(sub)
        if ratio is not None:
            peak_year = int(ratio.idxmax())
            last_year = int(ratio.index.max())
            lines.append(
                f"\n**UK / US:** {ratio.loc[last_year] * 100:.0f}% in {last_year} "
                f"(peak {ratio.max() * 100:.0f}% in {peak_year})."
            )

        # Cite the exact source(s) and indicator behind this metric.
        srcs = sorted(str(s) for s in sub["source"].dropna().unique())
        indicator = meta.wb_indicator or f"derived: nominal deflated by {markets.CPI_INDICATOR}"
        lines.append(f"\n_Source: {'; '.join(srcs)} — indicator {indicator}._")

        caveat = markets.CAVEATS.get(metric_id)
        if caveat:
            lines.append(f"\n> Caveat: {caveat}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path
