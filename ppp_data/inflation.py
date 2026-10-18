"""Published national consumer-price inflation, separate from output PPP measures."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
import math
from pathlib import Path
import re
import textwrap

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from europe_data._http import get_text
from investment_data.sources import flags
from ppp_data.figure import labelled_ends
from vizstyle import BG, MUTED, country_color, house_style, save_chart

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "data/consumer_inflation.csv"
SAVED_EU = ROOT / "data/consumer_inflation_eu.csv"
OUTPUT = ROOT / "outputs/ppp"
BASE = "https://sdmx.oecd.org/public/rest/v1/data"
COUNTRIES = {
    "GBR": "United Kingdom", "USA": "United States", "DEU": "Germany",
    "FRA": "France", "ITA": "Italy", "POL": "Poland",
}
EU_CODE = "EU27_2020"
AREAS = {**COUNTRIES, EU_CODE: "European Union"}
COMPARISONS = {
    "all": tuple(COUNTRIES),
    "four_country": ("GBR", "USA", "DEU", "FRA"),
    "uk_us_eu": ("GBR", "USA", EU_CODE),
}
FLOWS = {
    "1999": ("OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0", ("GBR", "USA", "DEU", "POL")),
    "2018": (
        "OECD.SDD.TPS,DSD_PRICES_COICOP2018@DF_PRICES_C2018_ALL,1.0",
        ("FRA", "ITA", "POL"),
    ),
}
DIMENSIONS = dict(
    REF_AREA="", FREQ="M", METHODOLOGY="N", MEASURE="CPI", UNIT_MEASURE="PA",
    EXPENDITURE="_T", ADJUSTMENT="N", TRANSFORMATION="GY",
)
UNIT = "percent change from same month a year earlier"
FIELDS = [
    "iso3", "country", "date", "value", "unit", "status", "classification",
    "series_id", "source_url", "retrieved_utc",
]


def _source_codes(classification: str) -> tuple[str, ...]:
    codes = FLOWS[classification][1]
    return (*codes, EU_CODE) if classification == "2018" else codes


def parse(text: str, classification: str, retrieved: str) -> pd.DataFrame:
    flow = FLOWS[classification][0]
    codes = _source_codes(classification)
    reader = csv.DictReader(io.StringIO(text))
    required = {"DATAFLOW", *DIMENSIONS, "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS", "UNIT_MULT"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("OECD inflation response has missing columns")
    agency, dataset, version = flow.split(",")
    rows, seen = [], set()
    for row in reader:
        if (
            None in row or any(row[field] is None for field in required)
            or row["DATAFLOW"] != f"{agency}:{dataset}({version})"
            or row["REF_AREA"] not in codes
            or any(row[dim] != expected for dim, expected in DIMENSIONS.items() if dim != "REF_AREA")
            or row["UNIT_MULT"] not in ("", "0")
        ):
            raise ValueError("Unexpected OECD national all-items inflation definition or units")
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", row["TIME_PERIOD"]):
            raise ValueError("Invalid OECD monthly inflation period")
        key = row["REF_AREA"], row["TIME_PERIOD"]
        if key in seen:
            raise ValueError(f"Duplicate OECD inflation observation: {key}")
        seen.add(key)
        status = flags(*(row.get(field, "") for field in ("OBS_STATUS", "OBS_STATUS_2", "OBS_STATUS_3")))
        if not row["OBS_VALUE"] or "F" in status:
            continue
        value = float(row["OBS_VALUE"])
        if not math.isfinite(value) or value <= -100:
            raise ValueError(f"Invalid OECD inflation rate: {key}")
        series_id = flow + "/" + ".".join(row[dim] for dim in DIMENSIONS)
        rows.append(dict(
            iso3=key[0], country=AREAS[key[0]], date=key[1] + "-01",
            value=value, unit=UNIT, status=status, classification=classification,
            series_id=series_id, source_url=f"{BASE}/{series_id}?format=csvfile",
            retrieved_utc=retrieved,
        ))
    return pd.DataFrame(rows, columns=FIELDS)


def validate(
    frame: pd.DataFrame, previous: pd.DataFrame | None = None, *,
    require_recent: bool = False, as_of: pd.Timestamp | None = None,
    countries: tuple[str, ...] = tuple(COUNTRIES),
) -> pd.DataFrame:
    if not countries or set(countries) - set(AREAS):
        raise ValueError("Unknown inflation comparison areas")
    if missing := set(FIELDS) - set(frame.columns):
        raise ValueError(f"Inflation data has missing fields: {sorted(missing)}")
    frame = frame[FIELDS].copy()
    frame["status"] = frame["status"].fillna("").map(flags)
    frame["classification"] = frame["classification"].astype(str)
    if frame.empty or frame.isna().any().any():
        raise ValueError("Inflation data has missing observations or provenance")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    today = pd.Timestamp(as_of if as_of is not None else datetime.now(timezone.utc).date())
    retrieved = pd.to_datetime(frame["retrieved_utc"], errors="raise", utc=True)
    if (
        not frame["value"].map(math.isfinite).all() or frame["value"].le(-100).any()
        or frame["date"].dt.day.ne(1).any() or frame["date"].lt("2000-01-01").any()
        or frame["date"].gt(today).any() or retrieved.isna().any()
        or frame.duplicated(["iso3", "date"]).any() or not frame["unit"].eq(UNIT).all()
        or frame["status"].str.split(";").map(lambda codes: "F" in codes).any()
        or set(frame["iso3"]) != set(countries)
    ):
        raise ValueError("Invalid inflation values, dates, units, forecasts or country coverage")
    for row in frame.itertuples():
        if row.classification not in FLOWS or row.iso3 not in _source_codes(row.classification):
            raise ValueError("Unexpected inflation country/classification pairing")
        flow = FLOWS[row.classification][0]
        dimensions = dict(DIMENSIONS, REF_AREA=row.iso3)
        expected = flow + "/" + ".".join(dimensions.values())
        if (
            row.country != AREAS[row.iso3] or row.series_id != expected
            or row.source_url != f"{BASE}/{expected}?format=csvfile"
        ):
            raise ValueError("Inflation data has incompatible series or source provenance")
    for code in countries:
        part = frame[frame["iso3"] == code]
        start = "2000-12-01" if code == EU_CODE else "2000-01-01"
        baseline = pd.date_range(start, "2025-12-01", freq="MS")
        if code == "USA":
            baseline = baseline[baseline != pd.Timestamp("2025-10-01")]
        if not baseline.isin(part["date"]).all():
            raise ValueError(f"Inflation source lost published monthly coverage: {code}")
        if require_recent and (today - part["date"].max()).days > 120:
            raise ValueError(f"Inflation source is more than 120 days old: {code}")
    if previous is not None:
        old = previous[["iso3", "date"]].copy()
        old["date"] = pd.to_datetime(old["date"], errors="raise")
        if not pd.MultiIndex.from_frame(old).isin(
            pd.MultiIndex.from_frame(frame[["iso3", "date"]])
        ).all():
            raise ValueError("Inflation refresh lost previously published observations")
    return frame.sort_values(["iso3", "date"]).reset_index(drop=True)


def fetch() -> pd.DataFrame:
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    parts = []
    for classification, (flow, codes) in FLOWS.items():
        dimensions = dict(DIMENSIONS, REF_AREA="+".join(codes))
        url = f"{BASE}/{flow}/" + ".".join(dimensions.values())
        parts.append(parse(
            get_text(url, params={"format": "csvfile", "startPeriod": "2000-01"}, timeout=120),
            classification, retrieved,
        ))
    legacy, current = parts
    if current.empty:
        raise ValueError("OECD current-classification inflation response is empty")
    first_current = current.groupby("iso3")["date"].min()
    legacy = legacy[
        legacy.apply(lambda row: row["date"] < first_current.get(row["iso3"], "9999"), axis=1)
    ]
    return validate(pd.concat([legacy, current], ignore_index=True), require_recent=True)


def fetch_eu() -> pd.DataFrame:
    flow = FLOWS["2018"][0]
    dimensions = dict(DIMENSIONS, REF_AREA=EU_CODE)
    url = f"{BASE}/{flow}/" + ".".join(dimensions.values())
    return validate(parse(
        get_text(url, params={"format": "csvfile", "startPeriod": "2000-12"}, timeout=120),
        "2018", datetime.now(timezone.utc).isoformat(timespec="seconds"),
    ), countries=(EU_CODE,), require_recent=True)


def make_chart(
    frame: pd.DataFrame, out: Path = OUTPUT, *, comparison: str = "all",
    eu_frame: pd.DataFrame | None = None,
) -> Path:
    if comparison not in COMPARISONS:
        raise ValueError(f"Unknown inflation comparison: {comparison}")
    frame = validate(frame)
    countries = COMPARISONS[comparison]
    frame = frame[frame["iso3"].isin(countries)]
    if comparison == "uk_us_eu":
        if eu_frame is None:
            raise ValueError("UK/US/EU inflation requires the published EU-27 aggregate")
        eu_frame = validate(eu_frame, countries=(EU_CODE,))
        frame = pd.concat([frame, eu_frame], ignore_index=True)
    house_style()
    fig, ax = plt.subplots(figsize=(13.5, 7.5))
    ends, endpoint_flags = [], []
    for code in countries:
        country = AREAS[code]
        part = frame[frame["iso3"] == code]
        values = part.set_index("date")["value"]
        monthly = values.reindex(pd.date_range(values.index.min(), values.index.max(), freq="MS"))
        color = country_color("EU" if code == EU_CODE else code)
        ax.plot(monthly.index, monthly.values, color=color, label=country,
                linewidth=2.7 if code == "GBR" else 1.6,
                linestyle="--" if code == "POL" else "-")
        last = part.iloc[-1]
        ends.append((
            float(last["value"]), f"{country} {last['value']:.1f}% ({last['date']:%b %Y})",
            color, mdates.date2num(last["date"]),
        ))
        if last["status"]:
            endpoint_flags.append(f"{country} ({last['date']:%b %Y}): {last['status']}")
    end = frame["date"].max() + pd.DateOffset(months=2)
    lo, hi = float(frame["value"].min()), float(frame["value"].max())
    spread = max(hi - lo, 1)
    ax.set_ylim(min(0, lo - spread * .07), hi + spread * .12)
    labelled_ends(ax, ends, min_gap=spread * .045, x=mdates.date2num(end), fontsize=9)
    ax.set_xlim(frame["date"].min(), end)
    ax.axhline(0, color=MUTED, linewidth=.7)
    ax.xaxis.set_major_locator(mdates.YearLocator(5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100))
    ax.set_xlabel("Year")
    ax.set_ylabel("Change from the same month a year earlier (%)")
    ax.grid(axis="y", linewidth=.5)
    ax.set_axisbelow(True)
    titles = {
        "all": "Consumer-price inflation: UK vs peers",
        "four_country": "Consumer-price inflation: UK, US, Germany and France",
        "uk_us_eu": "Consumer-price inflation: UK, US and EU",
    }
    fig.suptitle(titles[comparison], x=.08, y=.97,
                 ha="left", fontsize=22, fontweight="bold")
    subtitle = (
        "Monthly all-items indices; published EU-27 aggregate, not a country average"
        if comparison == "uk_us_eu" else
        "Monthly all-items national indices; latest published observations, not forecasts"
    )
    fig.text(.08, .91, subtitle,
             fontsize=11, color=MUTED)
    note = (
        "Source: OECD Consumer Price Indices, "
        + ("UK/US national indices and published EU-27 aggregate, " if comparison == "uk_us_eu"
           else "national all-items, ")
        + "monthly year-on-year rates (GY). "
        "UK: CPIH, including owner-occupiers' housing costs; US: CPI-U. National baskets and housing "
        "treatment differ; these are not identical harmonised indices. Lower positive inflation means "
        "prices rise more slowly, not that the price level falls. This is not a PPP price-level comparison. "
        "COICOP 2018 replaces 1999 where published; source classification and status retained in the CSV. "
        "Missing months are not filled; US October 2025 was not collected during the federal shutdown."
    )
    if comparison == "uk_us_eu":
        note += (
            " EU: published OECD EU27_2020 aggregate, current 27-member composition throughout; "
            "not the euro area or an average of the displayed countries. "
            "The EU series starts in December 2000; no earlier rates are invented."
        )
    if endpoint_flags:
        note += " Latest flags: " + "; ".join(endpoint_flags) + ". E = estimated; P = provisional."
    fig.text(.08, .02, textwrap.fill(note, width=155), va="bottom",
             fontsize=8, color=MUTED, style="italic")
    fig.subplots_adjust(left=.08, right=.77, bottom=.23, top=.85)
    out.mkdir(parents=True, exist_ok=True)
    suffix = "" if comparison == "all" else f"_{comparison}"
    path = out / f"consumer_price_inflation{suffix}.png"
    save_chart(fig, path, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=.15)
    plt.close(fig)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=SAVED)
    parser.add_argument("--eu-csv", type=Path, default=SAVED_EU)
    parser.add_argument("--from-csv", type=Path)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    if args.from_csv:
        frame = validate(pd.read_csv(args.from_csv))
        eu_frame = validate(pd.read_csv(args.eu_csv), countries=(EU_CODE,))
    else:
        previous = pd.read_csv(args.csv) if args.csv.exists() else None
        frame = validate(fetch(), previous)
        previous_eu = pd.read_csv(args.eu_csv) if args.eu_csv.exists() else None
        eu_frame = validate(fetch_eu(), previous_eu, countries=(EU_CODE,))
    charts = [
        make_chart(frame, args.out, comparison=comparison, eu_frame=eu_frame)
        for comparison in COMPARISONS
    ]
    if not args.from_csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False, date_format="%Y-%m-%d")
        args.eu_csv.parent.mkdir(parents=True, exist_ok=True)
        eu_frame.to_csv(args.eu_csv, index=False, date_format="%Y-%m-%d")
    print(f"[inflation] wrote {len(frame)} national and {len(eu_frame)} EU observed rates; charts -> {charts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
