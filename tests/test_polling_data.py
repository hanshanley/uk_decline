from __future__ import annotations

import hashlib
import json
from statistics import mean

from matplotlib.backends.backend_agg import FigureCanvasAgg
import pandas as pd
import pytest

from polling_data import polling


def _html(rows):
    headings = ["Date(s) conducted", "Pollster", "Client", "Area", "Sample size",
                "Lab", "Con", "Ref", "LD", "Grn", "RB", "Others", "Lead"]
    body, references = [], []
    for i, row in enumerate(rows):
        end = pd.Timestamp(row.get("end", "2024-08-01"))
        label = row.get("label", end.strftime("%d %b"))
        firm = row.get("firm", f"Firm {i}")
        shares = row.get("shares", (30, 25, 20, 10, 5))
        values = "".join(f"<td>{value}%</td>" if value is not None else "<td>-</td>"
                         for value in shares)
        sort_end = row.get("sort_end", end.strftime("%Y-%m-%d"))
        body.append(
            f'<tr><td data-sort-value="{sort_end}">{label}</td>'
            f'<td>{firm}<sup><a href="#cite_note-{i}">[{i}]</a></sup></td>'
            f'<td>Client</td><td>{row.get("area", "GB")}</td><td>1,000</td>'
            f'{values}<td colspan="2">10%</td><td>5</td></tr>'
        )
        references.append(
            f'<li id="cite_note-{i}"><a class="external" '
            f'href="{row.get("url", f"https://example.org/poll-{i}")}">Published result</a></li>'
        )
    header = "".join(f"<th>{name}</th>" for name in headings)
    return ("<h2>National poll results</h2><h3>2024</h3><table><tr>" + header +
            "</tr>" + "".join(body) + "</table><ol>" + "".join(references) + "</ol>")


def _parse(rows):
    return polling.parse(_html(rows), "2026-10-18T20:00:00+00:00")


@pytest.fixture
def polls():
    return _parse([
        dict(firm="Firm A", end="2024-07-20", shares=(35, 25, 20, 10, 5)),
        dict(firm="Firm A", shares=(10, 25, 20, 10, 5)),
        dict(firm="Firm A", shares=(30, 25, 20, 10, 5)),
        dict(firm="Firm B", end="2024-07-31", shares=(25, 25, 20, 10, 5)),
        dict(firm="Firm C", shares=(39, 25, 20, 10, 5)),
    ])


def test_parser_preserves_spanned_results_and_uses_each_physical_rows_citation():
    html = _html([dict(firm="Firm A"), dict(firm="Firm B")])
    date = '<td data-sort-value="2024-08-01">01 Aug</td>'
    html = html.replace(date, date.replace("<td ", '<td rowspan="2" '), 1)
    html = html.replace(date, "", 1)
    html = html.replace("</table>", '<tr><td colspan="13">An editorial event</td></tr></table>')
    frame = polling.parse(html, "2026-10-18T20:00:00+00:00")
    assert len(frame) == 2
    assert frame["fieldwork_end"].eq(pd.Timestamp("2024-08-01")).all()
    assert dict(zip(frame["pollster"], frame["source_url"])) == {
        "Firm A": "https://example.org/poll-0", "Firm B": "https://example.org/poll-1",
    }
    assert all(json.loads(text)["RB / Others"] == "10%" for text in frame["reported_results"])
    assert frame["labour"].tolist() == [30, 30]
    assert frame["snapshot_sha256"].eq(hashlib.sha256(html.encode()).hexdigest()).all()


def test_parser_retains_exclusions_and_ignores_election_and_regional_rows():
    html = _html([
        {}, dict(area="UK"), dict(area="TBA"), dict(firm="Firm (MRP)"),
        dict(shares=(30, 25, 20, 10, None)), dict(end="2024-07-01"),
    ])
    html = html.replace(
        "</table>",
        '<tr><td>4 Jul 2024</td><td>2024 general election</td>'
        '<td colspan="11">Actual votes, not a poll</td></tr></table>',
    )
    html += _html([dict(firm="Regional firm")]).replace("National poll results", "Scotland")
    frame = polling.parse(html, "2026-10-18T20:00:00+00:00")
    assert len(frame) == 6
    assert frame["exclusion_reason"].value_counts().to_dict() == {
        "not explicitly Great Britain": 2, "": 1, "standalone MRP-labelled study": 1,
        "one or more selected parties unreported": 1, "before the post-election comparison": 1,
    }
    assert pd.isna(frame.loc[frame["greens"].isna(), "greens"].iloc[0])


@pytest.mark.parametrize(("end", "label", "start"), [
    ("2026-10-14", "14 Oct", "2026-10-14"),
    ("2026-10-14", "5\u201314 Oct", "2026-10-05"),
    ("2026-10-14", "5-14 October", "2026-10-05"),
    ("2026-01-03", "30 Dec\u20133 Jan", "2025-12-30"),
    ("2026-01-03", "30\u20133 Jan", "2025-12-30"),
    ("2026-05-05", "16 Apr\u20145 May", "2026-04-16"),
    ("2026-01-03", "30 Dec 2025\u20133 Jan 2026", "2025-12-30"),
    ("2026-10-14", "2026-10-14", "2026-10-14"),
])
def test_parser_fieldwork_dates_cross_month_and_year_boundaries(end, label, start):
    row = _parse([dict(end=end, label=label)]).iloc[0]
    assert row["fieldwork_start"] == pd.Timestamp(start)
    assert row["fieldwork_end"] == pd.Timestamp(end)


def test_reported_fieldwork_takes_precedence_over_a_different_hidden_sort_day():
    row = _parse([dict(end="2025-09-11", label="1 Aug\u201311 Sep", sort_end="2025-09-15")]).iloc[0]
    assert row["fieldwork_start"] == pd.Timestamp("2025-08-01")
    assert row["fieldwork_end"] == pd.Timestamp("2025-09-11")
    assert row["fieldwork_sort_date"] == "2025-09-15"


@pytest.mark.parametrize(("old", "new"), [
    ('data-sort-value="2024-08-01"', ""),
    ("01 Aug", "32 Aug"), ("30%", "not published"), ("30%", "101%"),
    ('href="#cite_note-0"', 'href="#missing"'),
])
def test_parser_refuses_malformed_substantive_poll_rows(old, new):
    html = _html([{}]).replace(old, new)
    with pytest.raises(ValueError):
        polling.parse(html, "2026-10-18T20:00:00+00:00")


def test_duplicate_polls_are_coalesced_but_conflicting_results_fail():
    row = dict(firm="Firm", url="https://example.org/same-report")
    assert len(_parse([row, row])) == 1
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        _parse([row, {**row, "shares": (31, 25, 20, 10, 5)}])


@pytest.mark.parametrize(("field", "value"), [
    ("labour", float("inf")), ("labour", -1), ("labour", 31),
    ("poll_id", "made up"), ("pollster_id", "wrong-firm"),
    ("snapshot_sha256", "not-a-hash"), ("source_url", "https:///missing-host"),
    ("exclusion_reason", "unexpected exclusion"),
    ("retrieved_utc", "2099-01-01T00:00:00+00:00"),
])
def test_source_validation_refuses_inconsistent_values_and_provenance(polls, field, value):
    frame = polls.copy()
    frame.loc[0, field] = value
    with pytest.raises(ValueError):
        polling.validate_polls(frame, as_of=pd.Timestamp("2026-10-18"))


def test_source_validation_guards_freshness_history_future_dates_and_lost_records(polls):
    with pytest.raises(ValueError, match="45 days"):
        polling.validate_polls(polls, require_recent=True)
    with pytest.raises(ValueError, match="incomplete post-2024"):
        polling.validate_polls(polls, require_history=True)
    with pytest.raises(ValueError, match="previously published"):
        polling.validate_polls(polls.iloc[1:], previous=polls)
    frame = polls.copy()
    frame.loc[0, "fieldwork_end"] = pd.Timestamp("2099-01-01")
    with pytest.raises(ValueError, match="future-dated"):
        polling.validate_polls(frame)
    frame = polls.copy()
    frame.loc[0, "area"] = "UK"
    frame.loc[0, "exclusion_reason"] = "not explicitly Great Britain"
    with pytest.raises(ValueError, match="qualifying poll coverage"):
        polling.validate_polls(frame, previous=polls)


def test_average_weights_firms_equally_and_averages_latest_day_ties_within_firm(polls):
    averages = polling.average(polls)
    assert averages["date"].unique().tolist() == [pd.Timestamp("2024-08-01")]
    labour = averages[averages["party_id"].eq("labour")].iloc[0]
    assert labour["value"] == 28  # ((10 + 30) / 2 + 25 + 39) / 3, not a four-poll mean.
    assert labour["pollster_count"] == 3
    assert labour["poll_count"] == 4
    assert labour["window_poll_count"] == 5
    old_id = polls.loc[polls["fieldwork_end"].eq("2024-07-20"), "poll_id"].iloc[0]
    assert old_id not in json.loads(labour["poll_ids"])
    assert averages["value"].sum() == 88
    assert averages["poll_ids"].nunique() == 1


def test_average_has_inclusive_30_day_boundary_minimum_coverage_gaps_and_no_extrapolation():
    polls = _parse([dict(end=end, firm=f"Firm {i}")
                    for i, end in enumerate(["2024-07-12"] * 3 + ["2024-08-20"] * 3)])
    averages = polling.average(polls)
    dates = set(averages["date"])
    assert min(dates) == pd.Timestamp("2024-07-12")
    assert pd.Timestamp("2024-08-10") in dates
    assert all(date not in dates for date in pd.date_range("2024-08-11", "2024-08-19"))
    assert max(dates) == pd.Timestamp("2024-08-20")
    with pytest.raises(ValueError, match="at least three"):
        polling.average(polls.iloc[:2])


@pytest.mark.parametrize(("field", "value"), [
    ("value", float("nan")), ("value", 101), ("pollster_count", 2),
    ("pollster_count", 3.5), ("window_days", 31), ("method", "all-poll mean"),
    ("party", "Different party"), ("poll_ids", "[]"), ("unit", "raw respondents"),
    ("source_url", "https://example.org/unrelated"),
])
def test_average_validation_rejects_invalid_values_and_definitions(polls, field, value):
    frame = polling.average(polls)
    if field == "pollster_count":
        frame[field] = frame[field].astype(float)
    frame.loc[0, field] = value
    with pytest.raises(ValueError):
        polling.validate_average(frame)


def test_average_validation_requires_shared_dates_and_contributor_sets(polls):
    frame = polling.average(polls)
    with pytest.raises(ValueError):
        polling.validate_average(frame.iloc[1:])
    frame.loc[0, "poll_ids"] = json.dumps(["a" * 20, "b" * 20, "c" * 20, "d" * 20])
    with pytest.raises(ValueError, match="identical contributors"):
        polling.validate_average(frame)


def test_chart_preserves_daily_gaps_exact_percent_values_and_readable_geometry(polls, tmp_path, monkeypatch):
    averages = polling.average(polls)
    second = averages.copy()
    second["date"] += pd.Timedelta(days=3)
    second["window_start"] += pd.Timedelta(days=3)
    averages = pd.concat([averages, second])
    captured = {}
    original = polling.save_chart

    def save(fig, *args, **kwargs):
        captured["figure"] = fig
        original(fig, *args, **kwargs)

    monkeypatch.setattr(polling, "save_chart", save)
    path = polling.make_chart(averages, tmp_path)
    fig = captured["figure"]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer, ax = canvas.get_renderer(), fig.axes[0]
    assert ax.get_ylim()[0] == 0
    assert ax.get_legend() is None
    for line in ax.lines:
        if line.get_label() in {label for label, _ in polling.PARTIES.values()}:
            assert pd.isna(line.get_ydata()[1:3]).all()
    bounds = sorted((text.get_window_extent(renderer) for text in ax.texts), key=lambda b: b.y0)
    assert all(left.y1 < right.y0 for left, right in zip(bounds, bounds[1:]))
    assert all(box.y0 > ax.bbox.y0 and box.y1 < ax.bbox.y1 for box in bounds)
    title, subtitle, footnote = fig.texts
    assert title.get_window_extent(renderer).y0 > subtitle.get_window_extent(renderer).y1 + 5 * fig.dpi / 72
    assert footnote.get_window_extent(renderer).y1 < ax.xaxis.label.get_window_extent(renderer).y0
    assert max(box.x1 for box in bounds) < fig.bbox.x1
    data = json.loads(path.with_suffix(".json").read_text())
    assert data["image_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert {series["label"] for series in data["series"]} == {label for label, _ in polling.PARTIES.values()}
    for series in data["series"]:
        expected = averages[averages["party"].eq(series["label"])]
        assert [point[2] for point in series["points"]] == expected["date"].dt.strftime("%Y-%m-%d").tolist()
        assert [float(point[3].rstrip("%")) for point in series["points"]] == expected["value"].tolist()


@pytest.mark.skipif(not polling.SAVED_POLLS.exists(), reason="Saved polling snapshot is not available")
def test_saved_average_reconciles_every_day_party_and_contributor_to_the_complete_source():
    raw = polling.validate_polls(pd.read_csv(polling.SAVED_POLLS, keep_default_na=False))
    saved = polling.validate_average(pd.read_csv(
        polling.SAVED_AVERAGES, keep_default_na=False, float_precision="round_trip",
    )).set_index(["date", "party_id"])
    eligible = raw[raw["exclusion_reason"].eq("")].to_dict("records")
    dates = set()
    for date in pd.date_range(min(row["fieldwork_end"] for row in eligible),
                              max(row["fieldwork_end"] for row in eligible)):
        window = [row for row in eligible
                  if date - pd.Timedelta(days=29) <= row["fieldwork_end"] <= date]
        firms = {}
        for row in window:
            firm = firms.setdefault(row["pollster_id"], [])
            if not firm or row["fieldwork_end"] > firm[0]["fieldwork_end"]:
                firms[row["pollster_id"]] = [row]
            elif row["fieldwork_end"] == firm[0]["fieldwork_end"]:
                firm.append(row)
        if len(firms) < 3:
            continue
        dates.add(date)
        ids = sorted(row["poll_id"] for firm in firms.values() for row in firm)
        for party in polling.PARTIES:
            expected = mean(mean(row[party] for row in firm) for firm in firms.values())
            observed = saved.loc[(date, party)]
            assert observed["value"] == pytest.approx(expected, abs=1e-12)
            assert json.loads(observed["poll_ids"]) == ids
            assert observed["pollster_count"] == len(firms)
            assert observed["poll_count"] == len(ids)
            assert observed["window_poll_count"] == len(window)
    assert set(saved.index.get_level_values("date")) == dates
