"""Reproducible, pollster-balanced averages of published GB polling headlines."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import textwrap
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from europe_data._http import get_text
from ppp_data.figure import labelled_ends
from vizstyle import MUTED, house_style, save_chart

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://en.wikipedia.org/wiki/Opinion_polling_for_the_next_United_Kingdom_general_election"
SAVED_POLLS = ROOT / "data/gb_voting_intention_polls.csv"
SAVED_AVERAGES = ROOT / "data/gb_voting_intention_average.csv"
OUTPUT = ROOT / "outputs/polling"
START = pd.Timestamp("2024-07-05")
WINDOW_DAYS = 30
MIN_POLLSTERS = 3
METHOD = "equal-pollster latest-poll mean; trailing 30 calendar days"
UNIT = "percent of published voting intention"
PARTIES = {
    "labour": ("Labour", "#B44A44"),
    "conservatives": ("Conservatives", "#3D6F8C"),
    "reform_uk": ("Reform UK", "#4E8580"),
    "liberal_democrats": ("Liberal Democrats", "#C2993E"),
    "greens": ("Greens", "#4A7C59"),
}
COLUMNS = dict(zip(("Lab", "Con", "Ref", "LD", "Grn"), PARTIES))
RAW_FIELDS = [
    "poll_id", "fieldwork_start", "fieldwork_end", "fieldwork_label", "fieldwork_sort_date",
    "pollster", "pollster_id", "client", "area", "sample_size_reported",
    *PARTIES, "reported_results", "source_url", "source_title",
    "compilation_url", "retrieved_utc", "snapshot_sha256", "exclusion_reason",
]
AVERAGE_FIELDS = [
    "date", "party_id", "party", "value", "unit", "window_start", "window_days",
    "pollster_count", "poll_count", "window_poll_count", "poll_ids", "method",
    "source_url", "retrieved_utc", "snapshot_sha256",
]
MONTHS = {
    name: month for month, names in enumerate((
        ("jan", "january"), ("feb", "february"), ("mar", "march"),
        ("apr", "april"), ("may",), ("jun", "june"), ("jul", "july"),
        ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"),
        ("nov", "november"), ("dec", "december"),
    ), 1) for name in names
}


def _text(tag) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\[[^]]*\]", "", tag.get_text(" ", strip=True))).strip()


def _grid(table):
    pending = {}
    for tr in table.find_all("tr"):
        row = {column: cell for column, (cell, _) in pending.items()}
        pending = {
            column: (cell, remaining - 1)
            for column, (cell, remaining) in pending.items() if remaining > 1
        }
        column = 0
        for cell in tr.find_all(["th", "td"], recursive=False):
            while column in row:
                column += 1
            width, height = int(cell.get("colspan", 1)), int(cell.get("rowspan", 1))
            for index in range(column, column + width):
                if index in row:
                    raise ValueError("Polling source has overlapping table spans")
                row[index] = cell
                if height > 1:
                    pending[index] = cell, height - 1
            column += width
        yield tr, [row.get(index) for index in range(max(row, default=-1) + 1)]


def _dates(cell) -> tuple[str, str]:
    end = cell.get("data-sort-value", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
        raise ValueError("Polling source is missing an ISO fieldwork end date")
    sort_date = pd.Timestamp(end)
    label = _text(cell)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", label):
        if pd.Timestamp(label).year != sort_date.year:
            raise ValueError(f"Inconsistent polling fieldwork date: {label}")
        return label, label
    parts = re.split(r"\s*[-\u2013\u2014]\s*", label)
    visible_end = re.fullmatch(r"(\d{1,2})\s*([A-Za-z]+)(?:\s*(20\d{2}))?", parts[-1])
    if (
        not visible_end or visible_end[2].lower() not in MONTHS
        or (visible_end[3] and int(visible_end[3]) != sort_date.year)
    ):
        raise ValueError(f"Inconsistent polling fieldwork end date: {label}")
    finish = pd.Timestamp(
        year=sort_date.year, month=MONTHS[visible_end[2].lower()], day=int(visible_end[1]),
    )
    end = finish.strftime("%Y-%m-%d")
    if len(parts) == 1:
        return end, end
    if len(parts) != 2:
        raise ValueError(f"Unrecognized polling fieldwork range: {label}")
    match = re.fullmatch(r"(\d{1,2})(?:\s*([A-Za-z]+))?(?:\s*(20\d{2}))?", parts[0])
    if not match or (match[2] and match[2].lower() not in MONTHS):
        raise ValueError(f"Unrecognized polling fieldwork start: {label}")
    month = MONTHS[match[2].lower()] if match[2] else finish.month
    year = int(match[3]) if match[3] else finish.year
    if not match[3] and month > finish.month:
        year -= 1
    if not match[2] and int(match[1]) > finish.day:
        previous = finish - pd.DateOffset(months=1)
        year, month = previous.year, previous.month
    start = pd.Timestamp(year=year, month=month, day=int(match[1]))
    if start > finish:
        raise ValueError(f"Polling fieldwork ends before it starts: {label}")
    return start.strftime("%Y-%m-%d"), end


def _reference(row, references) -> tuple[str, str]:
    for anchor in row.select("sup a[href]"):
        reference = references.get(anchor["href"].split("#")[-1])
        if reference is None:
            continue
        for link in reference.select("a.external[href]"):
            url = urljoin(SOURCE, link["href"])
            if urlsplit(url).scheme in ("http", "https"):
                return url, _text(reference)
    raise ValueError("A published polling row has no underlying source citation")


def _percentage(value: str) -> float | None:
    if value in ("", "-", "\u2013", "\u2014", "N/A", "TBA"):
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)%", value)
    if not match or not 0 <= float(match[1]) <= 100:
        raise ValueError(f"Invalid published polling percentage: {value}")
    return float(match[1])


def _reason(row) -> str:
    if row["area"] != "GB":
        return "not explicitly Great Britain"
    if re.search(r"\bMRP\b", row["pollster"], re.IGNORECASE):
        return "standalone MRP-labelled study"
    if any(pd.isna(row[party]) for party in PARTIES):
        return "one or more selected parties unreported"
    if pd.Timestamp(row["fieldwork_end"]) < START:
        return "before the post-election comparison"
    return ""


def _poll_id(pollster_id: str, start: str, end: str, source_url: str) -> str:
    key = pollster_id, start, end, source_url
    return hashlib.sha256(json.dumps(key).encode()).hexdigest()[:20]


def parse(html: str, retrieved: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    references = {tag["id"]: tag for tag in soup.find_all(id=True)}
    digest = hashlib.sha256(html.encode()).hexdigest()
    records = {}
    tables = 0
    for table in soup.select("table"):
        rows = iter(_grid(table))
        _, header = next(rows, (None, []))
        names = [_text(cell) if cell else "" for cell in header]
        if not {"Pollster", "Area", "Sample size", *COLUMNS} <= set(names):
            continue
        section = table.find_previous("h2")
        if section is None or _text(section).casefold() not in {
            "national poll results", "national polling results", "voting intention", "polling results",
        }:
            continue
        tables += 1
        for tr, cells in rows:
            if not cells or cells[0] is None or cells[0].name == "th":
                continue
            row = dict(zip(names, cells))
            if row.get("Pollster") is not None and "general election" in _text(row["Pollster"]).casefold():
                continue
            if not cells[0].get("data-sort-value"):
                if len({id(cell) for cell in cells if cell}) <= 2 or not _text(cells[0]):
                    continue
                raise ValueError("Polling source has an undated national row")
            if len(cells) != len(names) or any(cell is None for cell in cells):
                raise ValueError("National polling table columns changed")
            pollster = _text(row["Pollster"])
            if any(row[name] is row["Pollster"] for name in COLUMNS):
                continue
            start, end = _dates(cells[0])
            sort_date = cells[0]["data-sort-value"]
            if end != sort_date:
                print(f"[polling] {pollster}: reported fieldwork ends {end}; hidden sort date is {sort_date}")
            source_url, source_title = _reference(tr, references)
            reported = {}
            for index, name in enumerate(names):
                if name in COLUMNS or index > names.index("Grn"):
                    shared = [other for other in names if row[other] is row[name]]
                    reported[" / ".join(shared)] = _text(row[name])
            item = dict(
                fieldwork_start=start, fieldwork_end=end, fieldwork_label=_text(cells[0]),
                fieldwork_sort_date=sort_date,
                pollster=pollster, pollster_id=re.sub(r"[^a-z0-9]", "", pollster.lower()),
                client=_text(row["Client"]) if "Client" in row else "",
                area=_text(row["Area"]), sample_size_reported=_text(row["Sample size"]),
                reported_results=json.dumps(reported, sort_keys=True),
                source_url=source_url, source_title=source_title, compilation_url=SOURCE,
                retrieved_utc=retrieved, snapshot_sha256=digest,
            )
            for name, party in COLUMNS.items():
                item[party] = (
                    _percentage(_text(row[name]))
                    if sum(cell is row[name] for cell in cells) == 1 else None
                )
            item["poll_id"] = _poll_id(item["pollster_id"], start, end, source_url)
            item["exclusion_reason"] = _reason(item)
            if item["poll_id"] in records:
                if records[item["poll_id"]] != item:
                    raise ValueError(f"Conflicting duplicate poll: {pollster} {end}")
                print(f"[polling] coalesced an exact duplicate: {pollster} {end}")
            records[item["poll_id"]] = item
    if not tables or not records:
        raise ValueError("No national Westminster polling tables found")
    return validate_polls(pd.DataFrame(records.values(), columns=RAW_FIELDS))


def validate_polls(
    frame: pd.DataFrame, previous: pd.DataFrame | None = None, *,
    require_recent: bool = False, require_history: bool = False,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if set(RAW_FIELDS) - set(frame.columns) or frame.empty:
        raise ValueError("Polling data is empty or missing required fields")
    frame = frame[RAW_FIELDS].copy().fillna("")
    today = pd.Timestamp(as_of if as_of is not None else datetime.now(timezone.utc).date())
    for column in ("fieldwork_start", "fieldwork_end"):
        frame[column] = pd.to_datetime(frame[column], errors="raise")
    for party in PARTIES:
        frame[party] = pd.to_numeric(frame[party].replace("", None), errors="raise")
        reported = frame[party].dropna()
        if not reported.map(math.isfinite).all() or not reported.between(0, 100).all():
            raise ValueError("Polling percentages must be finite and between zero and 100")
    if (
        frame["fieldwork_start"].gt(frame["fieldwork_end"]).any()
        or frame["fieldwork_end"].gt(today).any()
        or frame.duplicated("poll_id").any()
        or frame[list(PARTIES)].sum(axis=1).gt(102.5).any()
    ):
        raise ValueError("Invalid, duplicate or future-dated polling observations")
    retrieved = pd.to_datetime(frame["retrieved_utc"], utc=True, errors="raise")
    if (
        retrieved.isna().any() or retrieved.dt.tz_localize(None).dt.normalize().gt(today).any()
        or retrieved.dt.tz_localize(None).lt(frame["fieldwork_end"]).any()
        or frame["retrieved_utc"].nunique() != 1 or frame["snapshot_sha256"].nunique() != 1
    ):
        raise ValueError("Polling provenance must describe one consistent source snapshot")
    for row in frame.to_dict("records"):
        reported = json.loads(row["reported_results"])
        if (
            not row["pollster"] or not row["pollster_id"]
            or row["pollster_id"] != re.sub(r"[^a-z0-9]", "", row["pollster"].lower())
            or row["poll_id"] != _poll_id(
                row["pollster_id"], row["fieldwork_start"].strftime("%Y-%m-%d"),
                row["fieldwork_end"].strftime("%Y-%m-%d"), row["source_url"],
            )
            or urlsplit(row["source_url"]).scheme not in ("http", "https")
            or not urlsplit(row["source_url"]).netloc or not row["source_title"]
            or row["compilation_url"] != SOURCE
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["fieldwork_sort_date"])
            or pd.Timestamp(row["fieldwork_sort_date"]).year != row["fieldwork_end"].year
            or not re.fullmatch(r"[0-9a-f]{64}", row["snapshot_sha256"])
            or row["exclusion_reason"] != _reason(row)
            or not isinstance(reported, dict)
        ):
            raise ValueError("Polling data has invalid provenance or eligibility metadata")
        for name, party in COLUMNS.items():
            original = _percentage(reported[name]) if name in reported else None
            if not (pd.isna(original) and pd.isna(row[party])) and original != row[party]:
                raise ValueError("Polling percentages do not match the reported source results")
    eligible = frame[frame["exclusion_reason"].eq("")]
    if eligible.empty:
        raise ValueError("No qualifying GB voting-intention polls")
    if require_recent and (today - eligible["fieldwork_end"].max()).days > 45:
        raise ValueError("Latest qualifying GB poll is more than 45 days old")
    if require_history and (
        len(eligible) < 100 or eligible["pollster_id"].nunique() < 6
        or eligible["fieldwork_end"].min() > START + pd.Timedelta(days=90)
    ):
        raise ValueError("Polling source returned incomplete post-2024 coverage")
    if previous is not None and not set(previous["poll_id"]).issubset(frame["poll_id"]):
        raise ValueError("Polling refresh lost previously published poll records")
    if previous is not None and not set(
        previous.loc[previous["exclusion_reason"].eq(""), "poll_id"]
    ).issubset(eligible["poll_id"]):
        raise ValueError("Polling refresh lost previously published qualifying poll coverage")
    return frame.sort_values(["fieldwork_end", "pollster_id", "poll_id"]).reset_index(drop=True)


def average(polls: pd.DataFrame) -> pd.DataFrame:
    polls = validate_polls(polls)
    eligible = polls[polls["exclusion_reason"].eq("")]
    rows = []
    for date in pd.date_range(eligible["fieldwork_end"].min(), eligible["fieldwork_end"].max()):
        start = date - pd.Timedelta(days=WINDOW_DAYS - 1)
        window = eligible[eligible["fieldwork_end"].between(start, date)]
        newest = window.groupby("pollster_id")["fieldwork_end"].transform("max")
        selected = window[window["fieldwork_end"].eq(newest)]
        by_firm = selected.groupby("pollster_id")[list(PARTIES)].mean()
        if len(by_firm) < MIN_POLLSTERS:
            continue
        values = by_firm.mean()
        for party, (label, _) in PARTIES.items():
            rows.append(dict(
                date=date, party_id=party, party=label, value=float(values[party]),
                unit=UNIT, window_start=start,
                window_days=WINDOW_DAYS, pollster_count=len(by_firm), poll_count=len(selected),
                window_poll_count=len(window), poll_ids=json.dumps(sorted(selected["poll_id"])),
                method=METHOD, source_url=SOURCE, retrieved_utc=polls["retrieved_utc"].max(),
                snapshot_sha256=polls["snapshot_sha256"].iloc[0],
            ))
    return validate_average(pd.DataFrame(rows, columns=AVERAGE_FIELDS))


def validate_average(frame: pd.DataFrame) -> pd.DataFrame:
    if set(AVERAGE_FIELDS) - set(frame.columns) or frame.empty:
        raise ValueError("No polling averages with at least three pollsters")
    frame = frame[AVERAGE_FIELDS].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["window_start"] = pd.to_datetime(frame["window_start"], errors="raise")
    counts = frame[["pollster_count", "poll_count", "window_poll_count"]]
    if (
        set(frame["party_id"]) != set(PARTIES)
        or frame.duplicated(["date", "party_id"]).any()
        or frame["date"].isna().any() or frame["window_start"].isna().any()
        or not frame["date"].eq(frame["date"].dt.normalize()).all()
        or not frame["value"].map(math.isfinite).all()
        or not frame["value"].between(0, 100).all()
        or not counts.map(math.isfinite).all().all() or not counts.mod(1).eq(0).all().all()
        or frame["pollster_count"].lt(MIN_POLLSTERS).any()
        or frame["poll_count"].lt(frame["pollster_count"]).any()
        or frame["window_poll_count"].lt(frame["poll_count"]).any()
        or not frame["window_days"].eq(WINDOW_DAYS).all()
        or not frame["method"].eq(METHOD).all()
        or not frame["unit"].eq(UNIT).all() or not frame["source_url"].eq(SOURCE).all()
        or frame["snapshot_sha256"].nunique() != 1 or frame["retrieved_utc"].nunique() != 1
        or not (frame["date"] - frame["window_start"]).eq(pd.Timedelta(days=29)).all()
    ):
        raise ValueError("Invalid polling-average values, coverage or method")
    for _, group in frame.groupby("date"):
        if set(group["party_id"]) != set(PARTIES):
            raise ValueError("Polling-average parties do not share the same dates")
        shared = ["pollster_count", "poll_count", "window_poll_count", "poll_ids"]
        if not group[shared].nunique().eq(1).all():
            raise ValueError("Polling-average parties must share identical contributors")
    if (
        not frame["snapshot_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
        or pd.to_datetime(frame["retrieved_utc"], utc=True, errors="raise").isna().any()
    ):
        raise ValueError("Polling-average source provenance is incomplete")
    for row in frame.itertuples():
        ids = json.loads(row.poll_ids)
        if (
            not isinstance(ids, list) or row.party != PARTIES[row.party_id][0]
            or len(ids) != row.poll_count or len(set(ids)) != len(ids)
            or any(not re.fullmatch(r"[0-9a-f]{20}", poll_id) for poll_id in ids)
        ):
            raise ValueError("Polling-average provenance does not match its contributors")
    return frame.sort_values(["party_id", "date"]).reset_index(drop=True)


def make_chart(frame: pd.DataFrame, out: Path = OUTPUT) -> Path:
    frame = validate_average(frame)
    dates = frame["date"].drop_duplicates().sort_values()
    after_gap = dates[dates.diff().gt(pd.Timedelta(days=1))]
    first = after_gap.iloc[-1] if not after_gap.empty else dates.iloc[0]
    latest = dates.iloc[-1]
    if first == latest:
        raise ValueError("Polling chart needs at least two consecutive days of qualifying averages")
    frame = frame[frame["date"].ge(first)]
    house_style()
    fig, ax = plt.subplots(figsize=(13.5, 7.4))
    end = mdates.date2num(latest)
    ends = []
    for party, (label, color) in PARTIES.items():
        part = frame[frame["party_id"].eq(party)].set_index("date")["value"]
        ax.plot(part.index, part.values, color=color, label=label, linewidth=2.1)
        ends.append((float(part.iloc[-1]), f"{label}  {part.iloc[-1]:.1f}%", color, end))
    upper = max(30, math.ceil((frame["value"].max() + 3) / 5) * 5)
    ax.set_ylim(0, upper)
    ax.set_xlim(first, latest + pd.Timedelta(days=1))
    labelled_ends(ax, ends, min_gap=upper * .05, x=end, fontsize=9)
    for label in ax.texts:
        label.set_path_effects([])
        label.set_fontweight("normal")
    locator = mdates.AutoDateLocator(minticks=5, maxticks=9)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel("Date (polls dated by fieldwork end)", fontsize=10.5, labelpad=6)
    ax.set_ylabel("Voting intention", fontsize=10.5, labelpad=6)
    ax.tick_params(labelsize=10)
    ax.grid(axis="y", linewidth=.5)
    ax.set_axisbelow(True)
    fig.suptitle("Britain: general-election polling averages", x=.09, y=.96,
                 ha="left", fontsize=18, fontweight="bold")
    fig.text(.09, .89, "Great Britain only \u00b7 equal-pollster, trailing 30-day averages"
             f" \u00b7 latest {latest:%d %b %Y}",
             fontsize=11, color=MUTED)
    note = (
        "Source: Wikipedia's national polling compilation and linked pollsters; our calculations (CC BY-SA 4.0). "
        "Each pollster contributes its latest qualifying poll in the previous 30 calendar days; "
        "same-day ties are averaged within that pollster. "
        f"Minimum three pollsters; continuous coverage shown from {first:%d %b %Y}. "
        "Earlier averages remain in the CSV; no interpolation. "
        "UK-wide and MRP-labelled entries excluded; undecided/turnout treatment varies by pollster. "
        "Selected parties are not renormalised to 100%. No house-effect adjustment; not an election forecast."
    )
    fig.text(.09, .025, textwrap.fill(note, width=165), fontsize=8.5,
             color=MUTED, style="italic", va="bottom")
    fig.subplots_adjust(left=.09, right=.79, top=.80, bottom=.23)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "gb_voting_intention_average.png"
    save_chart(fig, path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-csv", type=Path, help="Recalculate from saved polls without fetching")
    args = parser.parse_args()
    previous = pd.read_csv(SAVED_POLLS, keep_default_na=False) if SAVED_POLLS.exists() else None
    if args.from_csv:
        polls = validate_polls(pd.read_csv(args.from_csv, keep_default_na=False, float_precision="round_trip"))
    else:
        html = get_text(SOURCE, timeout=120, headers={"Accept": "text/html"})
        polls = validate_polls(
            parse(html, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            previous, require_recent=True, require_history=True,
        )
    averages = average(polls)
    if not args.from_csv and averages["date"].max() != polls.loc[
        polls["exclusion_reason"].eq(""), "fieldwork_end"
    ].max():
        raise ValueError("Newest polling window has fewer than three pollsters; refusing a stale average")
    path = make_chart(averages)
    for frame, target in ((polls, SAVED_POLLS), (averages, SAVED_AVERAGES)):
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(target, index=False, date_format="%Y-%m-%d")
    print(f"[polling] {len(polls)} source polls; {len(averages)} averages -> {path}")


if __name__ == "__main__":
    main()
