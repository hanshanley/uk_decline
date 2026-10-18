"""Newer national and European income observations, separate from OECD levels."""

from __future__ import annotations

import argparse
from datetime import date
import io
from pathlib import Path
import re
import textwrap
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import requests

from europe_data import eurostat
from vizstyle import (
    ACCENT, BLUE, GOLD, GREEN, MUTED, house_style, mark_year_breaks,
    save_chart, source_note, with_year_gaps,
)

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "data/recent_disposable_income.csv"
OUTPUT = ROOT / "outputs/gdp_income"
ONS_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/personalandhouseholdfinances/"
    "incomeandwealth/datasets/householddisposableincomeandinequality"
)
CENSUS_PAGE = "https://www.census.gov/topics/income-poverty/income/data/tables.html"
EU_COUNTRIES = {"DE": "Germany", "FR": "France", "IT": "Italy", "PL": "Poland"}
FIELDS = [
    "country", "year", "survey_year", "period", "value", "unit", "price_base",
    "definition", "status", "source_url",
]
DEFINITIONS = {
    "United Kingdom": ("GBP", "ONS modified-OECD scale, two-adult reference"),
    "United States": ("USD", "Census post-tax whole-household median"),
    **{country: ("PPS", "Eurostat modified-OECD scale, single-adult reference")
       for country in EU_COUNTRIES.values()},
}


def download(url: str) -> bytes:
    if urlsplit(url).hostname not in {"www.ons.gov.uk", "www.census.gov", "www2.census.gov"}:
        raise ValueError(f"Unexpected national income source host: {url}")
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def ons_link(html: bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for link in soup.select("a[href]"):
        href = urljoin(ONS_PAGE, link["href"])
        match = re.search(r"/financialyearending(\d{4})/[^&]+\.xlsx$", href)
        if match:
            candidates.append((int(match[1]), href))
    if not candidates:
        raise ValueError("ONS has no dated household-income workbook")
    return max(candidates)[1]


def parse_ons(payload: bytes, url: str) -> list[dict]:
    table = pd.read_excel(io.BytesIO(payload), sheet_name="Table 1", header=None)
    title = str(table.iloc[0, 0])
    base = re.search(r"\((\d{4}/\d{2}) prices\)", title)
    if (
        "mean and median equivalised household disposable income" not in title
        or base is None
        or table.iloc[5, 1] != "All people"
        or table.iloc[6, 2] != "Median"
    ):
        raise ValueError("Unexpected ONS median-income table or price basis")
    rows = []
    for _, row in table.iterrows():
        match = re.fullmatch(r"(\d{4})/(\d{2})", str(row.iloc[0]).strip())
        if match is None:
            continue
        year = int(match[1]) + 1
        if match[2] != str(year)[-2:]:
            raise ValueError("Invalid ONS financial-year label")
        if year < 2018:
            continue
        rows.append({
            "country": "United Kingdom", "year": year, "survey_year": year,
            "period": match[0], "value": float(row.iloc[2]), "unit": "GBP",
            "price_base": base[1], "definition": DEFINITIONS["United Kingdom"][1],
            "status": "Reduced survey sample" if year == 2025 else "",
            "source_url": url,
        })
    return rows


def census_link(html: bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")
    candidates = [
        urljoin(CENSUS_PAGE, a["href"]) for a in soup.select("a[href]")
        if re.fullmatch(r"/data/tables/\d{4}/demo/income-poverty/p60-\d+\.html", a["href"])
    ]
    if not candidates:
        raise ValueError("Census has no dated national-income tables")
    latest = max(candidates, key=lambda url: int(urlsplit(url).path.split("/")[3]))
    soup = BeautifulSoup(download(latest), "html.parser")
    links = [
        urljoin(latest, a["href"]) for a in soup.select("a[href]")
        if "Selected Measures of Household Post-Tax Income Dispersion" in a.get_text(" ", strip=True)
        and a["href"].endswith(".xlsx")
    ]
    if len(links) != 1:
        raise ValueError("Census post-tax historical income table is missing or ambiguous")
    return links[0]


def parse_census(payload: bytes, url: str) -> list[dict]:
    table = pd.read_excel(io.BytesIO(payload), header=None)
    title, note = str(table.iloc[1, 0]), str(table.iloc[2, 0])
    base = re.search(r"Income in (\d{4}) dollars", note)
    if (
        "Selected Measures of Household Post-Tax Income Dispersion" not in title
        or base is None
        or re.sub(r"\s+", " ", str(table.iloc[5, 5])) != "50th percentile (median)"
    ):
        raise ValueError("Unexpected Census post-tax median table or price basis")
    rows = []
    footnotes = {}
    for value in table.iloc[:, 0].dropna():
        match = re.match(r"(\d+) (.+)", str(value))
        if match and not re.fullmatch(r"\d{4}", match[1]):
            footnotes[match[1]] = match[2]
    for _, row in table.iterrows():
        match = re.fullmatch(r"(\d{4})(?:\s+(\d+))?", str(row.iloc[0]).strip())
        if match is None or int(match[1]) < 2018:
            continue
        if match[2] and match[2] not in footnotes:
            raise ValueError(f"Census income source is missing footnote {match[2]}")
        rows.append({
            "country": "United States", "year": int(match[1]), "survey_year": int(match[1]) + 1,
            "period": match[1], "value": float(row.iloc[5]), "unit": "USD",
            "price_base": base[1], "definition": DEFINITIONS["United States"][1],
            "status": footnotes[match[2]] if match[2] else "",
            "source_url": url,
        })
    return rows


def fetch() -> pd.DataFrame:
    uk = ons_link(download(ONS_PAGE))
    us = census_link(download(CENSUS_PAGE))
    rows = parse_ons(download(uk), uk) + parse_census(download(us), us)
    european = eurostat.fetch(
        2019, date.today().year, geos=EU_COUNTRIES, statinfos=["MED_EI"],
    )
    for row in european:
        rows.append({
            "country": row["country"], "year": row["year"] - 1, "survey_year": row["year"],
            "period": str(row["year"] - 1), "value": row["value"], "unit": "PPS",
            "price_base": "current", "definition": DEFINITIONS[row["country"]][1],
            "status": row["status"],
            "source_url": "https://ec.europa.eu/eurostat/databrowser/view/ilc_di03/default/table",
        })
    return validate(pd.DataFrame(rows))


def validate(frame: pd.DataFrame, previous: pd.DataFrame | None = None) -> pd.DataFrame:
    if not set(FIELDS).issubset(frame.columns) or frame.empty:
        raise ValueError("Recent income data is empty or has missing columns")
    frame = frame[FIELDS].copy()
    frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    frame["year"] = pd.to_numeric(frame["year"], errors="raise")
    frame["survey_year"] = pd.to_numeric(frame["survey_year"], errors="raise")
    if (
        frame.drop(columns="status").isna().any().any()
        or not frame["value"].map(lambda v: 0 < v < float("inf")).all()
        or frame.duplicated(["country", "year"]).any()
        or set(frame["country"]) != set(DEFINITIONS)
        or not frame["year"].between(2018, date.today().year).all()
        or not frame["year"].mod(1).eq(0).all()
        or not frame["survey_year"].mod(1).eq(0).all()
        or frame["survey_year"].gt(date.today().year).any()
    ):
        raise ValueError("Invalid or duplicate recent-income observations")
    for country, (unit, definition) in DEFINITIONS.items():
        sub = frame[frame["country"] == country]
        end = 2025 if country in {"United Kingdom", "United States"} else 2024
        offset = 0 if country == "United Kingdom" else 1
        base = str(sub.iloc[0]["price_base"])
        expected_periods = sub["year"].map(
            lambda year: f"{int(year) - 1}/{str(int(year))[-2:]}"
            if country == "United Kingdom" else str(int(year))
        )
        if (
            not sub["unit"].eq(unit).all()
            or not sub["definition"].eq(definition).all()
            or not sub["survey_year"].eq(sub["year"] + offset).all()
            or not set(range(2018, end + 1)).issubset(sub["year"])
            or sub["price_base"].nunique() != 1
            or (unit == "PPS" and not sub["price_base"].eq("current").all())
            or not sub["period"].astype(str).eq(expected_periods).all()
            or (unit == "GBP" and re.fullmatch(r"\d{4}/\d{2}", base) is None)
            or (unit == "USD" and re.fullmatch(r"\d{4}", base) is None)
        ):
            raise ValueError(f"Recent-income coverage, units or definitions changed: {country}")
    if previous is not None:
        before = set(zip(previous["country"], previous["year"]))
        if not before.issubset(zip(frame["country"], frame["year"])):
            raise ValueError("Recent-income refresh lost previously published observations")
    return frame.sort_values(["country", "year"]).reset_index(drop=True)


def charts(frame: pd.DataFrame, out: Path = OUTPUT) -> list[Path]:
    frame = validate(frame)
    house_style()
    out.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 7))
    for ax, country, color, symbol in zip(
        axes, ["United Kingdom", "United States"], [ACCENT, BLUE], ["£", "$"],
    ):
        sub = frame[frame["country"] == country].sort_values("year")
        values = sub.set_index("year")["value"]
        breaks = sub.loc[sub["status"].fillna("").ne(""), "year"].tolist()
        if country == "United Kingdom":
            breaks = []
        series = with_year_gaps(values, breaks=breaks)
        ax.plot(series.index, series.values, color=color, linewidth=2.5, marker="o", label=country)
        mark_year_breaks(ax, values, breaks=breaks, color=color, linewidth=2.5)
        last = sub.iloc[-1]
        ax.annotate(f"{symbol}{last['value']:,.0f}", (last["year"], last["value"]),
                    xytext=(-5, 12), textcoords="offset points", ha="right",
                    color=color, fontweight="bold")
        definition = "Disposable income\nAdjusted for household size" if country == "United Kingdom" else (
            "Post-tax household income\nNot adjusted for household size"
        )
        ax.set_title(f"{country} · {last['period']}\n{definition}", loc="left", fontsize=12, pad=17)
        ax.set_ylabel(f"Median annual income ({sub.iloc[0]['price_base']} {symbol})")
        ticks = sorted({*sub["year"][::2], int(last["year"])})
        ax.set_xticks(ticks)
        if country == "United Kingdom":
            ax.set_xticklabels([str(int(y) - 1) + "/" + str(int(y))[-2:] for y in ticks],
                               rotation=25, ha="right")
        ax.set_xlabel("Financial year (April–March)" if country == "United Kingdom" else "Calendar year")
        ax.yaxis.set_major_locator(mtick.MaxNLocator(nbins=5))
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda value, _, s=symbol: f"{s}{value / 1000:g}k"))
        ax.margins(x=.06, y=.2)
        ax.grid(axis="y")
    fig.suptitle("UK and US household income: latest national series", x=.075, ha="left", fontweight="bold")
    fig.text(.075, .89, "Separate national measures and price bases—not comparable income levels or an extension of the OECD series.",
             fontsize=10.5, color=MUTED)
    note = (
        "Sources: ONS, Household disposable income and inequality, Table 1; US Census Bureau, historical post-tax income dispersion table. "
        "Each panel uses source-published inflation-adjusted values. UK: modified-OECD scale, two-adult reference; 2024/25 has a reduced survey sample. "
        "US: whole households; dotted links mark population-control changes. Neither subtracts ordinary living costs. No currency conversion or splicing."
    )
    source_note(fig, textwrap.fill(note, 168), x=.075, y=.025)
    fig.subplots_adjust(left=.075, right=.97, bottom=.27, top=.74, wspace=.3)
    national = out / "median_income_recent_national.png"
    save_chart(fig, national, dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12.5, 7))
    for country, color in zip(EU_COUNTRIES.values(), [BLUE, GREEN, GOLD, ACCENT]):
        sub = frame[frame["country"] == country].sort_values("year")
        values = sub.set_index("year")["value"]
        breaks = sub.loc[sub["status"].fillna("").str.contains("b"), "year"].tolist()
        series = with_year_gaps(values, breaks=breaks)
        ax.plot(series.index, series.values, color=color, linewidth=2.5, label=country, marker="o")
        mark_year_breaks(ax, values, breaks=breaks, color=color, linewidth=2.5)
    ax.set_title("Newer European median disposable income", loc="left", pad=36, fontsize=20)
    latest = int(frame.loc[frame["country"].isin(EU_COUNTRIES.values()), "year"].max())
    ax.text(0, 1.035, f"Income years through {latest}; survey years are one year later. UK and US not covered.",
            transform=ax.transAxes, fontsize=10.5, color=MUTED)
    ax.set_xlabel("Income year (survey year minus one)")
    ax.set_ylabel("Annual household-size-adjusted income\n(current purchasing power standards)")
    ax.xaxis.set_major_locator(mtick.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda value, _: f"{value / 1000:.0f}k"))
    ax.legend(loc="upper left", ncol=2)
    ax.grid(axis="y")
    ax.margins(x=.035, y=.15)
    note = (
        "Source: Eurostat, EU Statistics on Income and Living Conditions, ilc_di03 (median, total age and sex, PPS). "
        "Modified-OECD equivalence scale, single-adult reference. Current-price purchasing power standards—not US dollars or real-income growth. "
        "Survey year N refers to income in N–1 for these four countries. Missing years stay blank; dotted links mark source-flagged method breaks. "
        "Not spliced to OECD or UK national data; no modelled 2025 income estimates added."
    )
    source_note(fig, textwrap.fill(note, 155), x=.085, y=.025)
    fig.subplots_adjust(left=.085, right=.97, bottom=.24, top=.82)
    european = out / "median_income_recent_europe.png"
    save_chart(fig, european, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return [national, european]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--csv", type=Path, default=SAVED)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    if args.from_csv:
        frame = validate(pd.read_csv(args.from_csv))
    else:
        previous = pd.read_csv(args.csv) if args.csv.exists() else None
        frame = validate(fetch(), previous)
    written = charts(frame, args.out)
    if not args.from_csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False)
    for path in written:
        print(f"[recent_income] chart -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
