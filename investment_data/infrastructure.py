"""Complete ONS UK infrastructure series; market volumes and government GDP shares."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import re
import textwrap
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

from europe_data._http import get_bytes, get_text
from vizstyle import ACCENT, BG, MUTED, house_style, save_chart

URL = (
    "https://www.ons.gov.uk/economy/economicoutputandproductivity/"
    "productivitymeasures/datasets/experimentalinfrastructurestatistics"
)
MARKET = "market_infrastructure_real"
GOVERNMENT = "government_infrastructure_pct_gdp"
FIELDS = [
    "metric", "year", "value", "unit", "numerator", "gdp", "price_base_year",
    "source", "source_url", "retrieved_utc",
]


def _row(table: pd.DataFrame, label: str, after: int) -> int:
    matches = [
        index for index in range(after + 1, len(table))
        if str(table.iloc[index, 0]).strip() == label
    ]
    if not matches:
        raise ValueError(f"Missing ONS infrastructure table row: {label}")
    return matches[0]


def _years(table: pd.DataFrame, header: int) -> dict[int, int]:
    years = {}
    for column in range(1, table.shape[1]):
        value = table.iloc[header, column]
        if pd.isna(value):
            continue
        year = int(value)
        if year != float(value) or year in years or not 1990 <= year < datetime.now().year:
            raise ValueError("Invalid or duplicate ONS infrastructure year")
        years[year] = column
    if not years:
        raise ValueError("ONS infrastructure table contains no years")
    return years


def parse(content: bytes, source_url: str, retrieved: str) -> pd.DataFrame:
    tables = {name.strip(): table for name, table in
              pd.read_excel(BytesIO(content), sheet_name=None, header=None).items()}
    if not {"Government investment", "Market sector investment"} <= tables.keys():
        raise ValueError("ONS infrastructure workbook lacks investment sheets")
    rows = []
    for sheet, metric in (("Market sector investment", MARKET), ("Government investment", GOVERNMENT)):
        table = tables[sheet]
        if "\u00a3m" not in str(table.iloc[0, 0]):
            raise ValueError("ONS infrastructure investment must be in GBP millions")
        if metric == MARKET:
            matches = [
                (index, re.fullmatch(r"Chained volume measures, (\d{4}) prices", str(value).strip()))
                for index, value in enumerate(table.iloc[:, 0])
            ]
            matches = [(index, match) for index, match in matches if match]
            if len(matches) != 1:
                raise ValueError("ONS market infrastructure requires one identified constant-price table")
            block, match = matches[0]
            price_year = int(match[1])
            header = _row(table, "Industry group", block)
        else:
            if "current prices" not in str(table.iloc[0, 0]):
                raise ValueError("ONS government infrastructure must use current prices")
            price_year = None
            header = _row(table, "Infrastructure investment type", 0)
        total = _row(table, "Total", header)
        gdp_row = _row(table, "GDP", header) if metric == GOVERNMENT else None
        share_row = _row(table, "Infrastructure share of GDP", header) if metric == GOVERNMENT else None
        for year, column in _years(table, header).items():
            numerator = float(table.iloc[total, column]) * 1e6
            gdp = float(table.iloc[gdp_row, column]) * 1e6 if gdp_row is not None else None
            if gdp is not None and (not np.isfinite(gdp) or gdp <= 0):
                raise ValueError("ONS infrastructure GDP must be finite and positive")
            value = 100 * numerator / gdp if gdp is not None else numerator / 1e9
            if share_row is not None and not np.isclose(
                value / 100, float(table.iloc[share_row, column]), atol=.00051, rtol=0,
            ):
                raise ValueError("ONS government infrastructure/GDP does not reconcile with its published share")
            rows.append(dict(
                metric=metric, year=year, value=value,
                unit=f"GBP billion, constant {price_year} prices" if metric == MARKET else "percent of GDP",
                numerator=numerator, gdp=gdp, price_base_year=price_year,
                source="ONS Infrastructure statistics", source_url=source_url, retrieved_utc=retrieved,
            ))
    return validate(pd.DataFrame(rows, columns=FIELDS))


def validate(frame: pd.DataFrame, previous: pd.DataFrame | None = None) -> pd.DataFrame:
    if not set(FIELDS) <= set(frame.columns):
        raise ValueError("Missing ONS infrastructure provenance or value columns")
    frame = frame[FIELDS].copy()
    for column in ("year", "value", "numerator", "gdp", "price_base_year"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if (
        set(frame["metric"]) != {MARKET, GOVERNMENT}
        or frame.duplicated(["metric", "year"]).any()
        or not np.isfinite(frame[["year", "value", "numerator"]]).all().all()
        or not frame["year"].eq(frame["year"].round()).all()
        or not frame["year"].between(1997, datetime.now().year - 1).all()
        or not frame["value"].ge(0).all() or not frame["numerator"].ge(0).all()
    ):
        raise ValueError("Invalid or duplicate ONS infrastructure observations")
    frame["year"] = frame["year"].astype(int)
    for metric, first in ((MARKET, 1997), (GOVERNMENT, 2006)):
        part = frame[frame["metric"] == metric]
        if part["year"].max() < 2025 or set(part["year"]) != set(range(first, int(part["year"].max()) + 1)):
            raise ValueError(f"Incomplete ONS infrastructure annual history: {metric}")
        if metric == MARKET:
            bases = part["price_base_year"]
            if (
                bases.nunique() != 1 or bases.isna().any() or not bases.eq(bases.round()).all()
                or not bases.between(1997, datetime.now().year - 1).all()
                or not part["unit"].eq(f"GBP billion, constant {int(bases.iloc[0])} prices").all()
                or part["gdp"].notna().any()
                or not np.allclose(part["value"], part["numerator"] / 1e9, rtol=1e-12)
            ):
                raise ValueError("Invalid ONS constant-price infrastructure units")
        elif (
            not part["unit"].eq("percent of GDP").all()
            or not np.isfinite(part["gdp"]).all() or not part["gdp"].gt(0).all()
            or not part["price_base_year"].isna().all()
            or not np.allclose(part["value"], 100 * part["numerator"] / part["gdp"], rtol=1e-12)
        ):
            raise ValueError("Invalid ONS same-year nominal infrastructure/GDP ratio")
    if any(frame[field].isna().any() or frame[field].eq("").any()
           for field in ("source", "source_url", "retrieved_utc")):
        raise ValueError("Missing ONS infrastructure provenance")
    retrieved = pd.to_datetime(frame["retrieved_utc"], utc=True, errors="raise")
    if (retrieved > pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)).any():
        raise ValueError("Invalid ONS infrastructure retrieval date")
    if previous is not None:
        saved = validate(previous)
        if not set(zip(saved["metric"], saved["year"])) <= set(zip(frame["metric"], frame["year"])):
            raise ValueError("ONS infrastructure refresh lost previously published observations")
    return frame.sort_values(["metric", "year"]).reset_index(drop=True)


def fetch() -> pd.DataFrame:
    soup = BeautifulSoup(get_text(URL, headers={"Accept": "text/html"}, timeout=90), "html.parser")
    links = [urljoin(URL, link["href"]) for link in soup.select("a[href]")
             if ".xlsx" in link["href"].lower()]
    if not links:
        raise ValueError("ONS infrastructure release contains no workbook")
    source_url = links[0]
    return parse(get_bytes(source_url, timeout=90), source_url,
                 datetime.now(timezone.utc).isoformat(timespec="seconds"))


def make_chart(frame: pd.DataFrame, output: Path) -> Path:
    frame = validate(frame)
    house_style()
    output.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.5))
    price_year = int(frame.loc[frame["metric"] == MARKET, "price_base_year"].iloc[0])
    for ax, metric, title, ylabel, label in (
        (axes[0], MARKET, "Market-sector investment", f"Real investment (\u00a3billion, {price_year} prices)",
         "UK market sector"),
        (axes[1], GOVERNMENT, "Government infrastructure investment", "Share of GDP (%)",
         "UK general government"),
    ):
        part = frame[frame["metric"] == metric]
        ax.plot(part["year"], part["value"], color=ACCENT, linewidth=2.6, marker="o",
                markersize=3.5, label=label)
        latest = part.iloc[-1]
        value = f"{latest['value']:.2f}%" if metric == GOVERNMENT else f"\u00a3{latest['value']:.1f}bn"
        ax.text(.98, .95, f"{int(latest['year'])}: {value}", transform=ax.transAxes,
                ha="right", va="top", fontsize=11, fontweight="bold", color=ACCENT)
        ax.set_title(title, fontsize=14.5, pad=12)
        ax.set_xlabel("Year")
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, part["value"].max() * 1.18)
        ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6, integer=True))
        if metric == GOVERNMENT:
            ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100))
        ax.grid(axis="y", linewidth=.5)
        ax.set_axisbelow(True)
    end = int(frame["year"].max())
    fig.suptitle(f"UK infrastructure investment, 1997\u2013{end}", x=.065, y=.97,
                 ha="left", fontsize=22, fontweight="bold")
    fig.text(.065, .905, "Complete annual ONS series; different sectors and units \u2014 do not add the panels",
             fontsize=11, color=MUTED)
    note = (
        "Source: ONS Infrastructure statistics, latest workbook. Left: market-sector investment, "
        f"chained volume measures in {price_year} prices, 1997\u2013{end}; published total, "
        "not a sum of non-additive chained-volume components. Right: general-government infrastructure "
        f"investment / same-year nominal GDP from the same workbook, 2006\u2013{end}. "
        "ONS narrow infrastructure definitions; official statistics in development. Market and government "
        "coverage differs: not a combined national investment total. No forecasts, interpolation or "
        "foreign-country proxies. The separate public-capital chart provides the international comparison."
    )
    fig.text(.065, .02, textwrap.fill(note, width=170), va="bottom",
             fontsize=8.3, color=MUTED, style="italic")
    fig.subplots_adjust(left=.065, right=.975, bottom=.23, top=.79, wspace=.27)
    path = output / "uk_infrastructure_investment.png"
    save_chart(fig, path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=.15)
    plt.close(fig)
    return path
