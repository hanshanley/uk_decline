"""Offline unit tests for the trust_data pipeline (no network required).

Run directly:  python tests/test_trust.py
Or with pytest: pytest tests/test_trust.py -q
"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trust_data import combine, countries, manual, metrics, oecd, owid, report, worldbank  # noqa: E402


def test_country_mappings() -> None:
    # UK is primary and first in the list.
    assert countries.COUNTRIES[0].iso3 == countries.UK_ISO3 == "GBR"
    assert countries.group_for_iso3("GBR") == countries.UK
    assert countries.group_for_iso3("DEU") == countries.EU
    assert countries.group_for_iso3("USA") == countries.US
    assert countries.name_for_iso3("FRA") == "France"
    # No duplicate ISO3 codes; EU-27 + UK + US = 29 countries.
    iso3s = countries.iso3_codes()
    assert len(iso3s) == len(set(iso3s)) == 29
    assert sum(1 for c in countries.COUNTRIES if c.group == countries.EU) == 27


def test_metric_schema() -> None:
    row = metrics.make_row("GBR", "United Kingdom", 2020, "trust_national_govt_pct", 41.0, "x")
    assert set(row) == set(metrics.ROW_FIELDS)
    assert row["unit"] == "percent"
    assert "trust_national_govt_pct" in metrics.SURVEY_METRICS
    assert "wgi_rule_of_law" in metrics.GOVERNANCE_METRICS
    try:
        metrics.make_row("GBR", "UK", 2020, "not_a_metric", 1.0, "x")
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected KeyError for unknown metric")


def test_oecd_decoder() -> None:
    # Minimal SDMX-JSON v2: REF_AREA x MEASURE x SCALE x TIME.
    payload = {
        "data": {
            "structures": [
                {
                    "dimensions": {
                        "observation": [
                            {"id": "REF_AREA", "values": [{"id": "GBR"}, {"id": "XXX"}]},
                            {"id": "MEASURE", "values": [{"id": "TRUST_NG"}, {"id": "OTHER"}]},
                            {"id": "SCALE", "values": [
                                {"id": "HMH"}, {"id": "L"}, {"id": "NEU"}, {"id": "DK"}
                            ]},
                            {"id": "TIME_PERIOD", "values": [{"id": "2018"}, {"id": "2020"}]},
                        ]
                    }
                }
            ],
            "dataSets": [
                {
                    "observations": {
                        "0:0:0:0": [34.0],     # GBR, TRUST_NG, HMH, 2018
                        "0:0:0:1": [41.0],     # GBR, TRUST_NG, HMH, 2020
                        "0:0:1:1": [42.0],     # low trust -> dropped
                        "0:0:2:1": [15.0],     # neutral -> dropped
                        "0:0:3:1": [2.0],      # don't know -> dropped
                        "1:0:0:1": [50.0],     # XXX (not in set) -> dropped
                        "0:1:0:0": [99.0],     # OTHER measure -> dropped
                    }
                }
            ],
        }
    }
    rows = oecd._decode(payload)
    by_year = {r["year"]: r["value"] for r in rows}
    assert by_year == {2018: 34.0, 2020: 41.0}
    assert all(r["iso3"] == "GBR" and r["metric"] == "trust_national_govt_pct" for r in rows)


def test_oecd_fetch_requests_sdmx_v2(monkeypatch) -> None:
    captured = {}

    def fake_get_json(url, params=None, headers=None, timeout=60):
        captured["headers"] = headers
        return {}

    monkeypatch.setattr(oecd, "get_json", fake_get_json)
    assert oecd._fetch_dataflow(oecd.DATAFLOWS[0], ["GBR"], 2023) == []
    assert captured["headers"] == oecd._ACCEPT


def test_owid_parser_keeps_real_country_year_rows() -> None:
    text = (
        "Entity,Code,Year,trust_in_government\n"
        "United Kingdom,GBR,2023,26.7\n"
        "United Kingdom,GBR,2024,34.5\n"
        "Unknown,XXX,2024,99\n"
    )
    rows = owid.parse(text, 2024, 2024)
    assert [(r["iso3"], r["year"], r["value"]) for r in rows] == [
        ("GBR", 2024, 34.5)
    ]
    assert rows[0]["source"] == owid.SOURCE


def test_showcase_uses_actual_relative_chart_path(tmp_path) -> None:
    data_dir = tmp_path / "data" / "trust"
    chart_dir = tmp_path / "outputs" / "trust"
    data_dir.mkdir(parents=True)
    chart_dir.mkdir(parents=True)
    long_csv = data_dir / "trust_combined_long.csv"
    long_csv.write_text(
        "iso3,country,year,metric,value,unit,source\n"
        "GBR,United Kingdom,2023,trust_national_govt_pct,26.7,percent,"
        "OECD (Trust in national government)\n"
    )
    chart = chart_dir / "trust_national_govt_pct.png"
    chart.write_bytes(b"png")
    output = report.write_showcase(
        str(data_dir), long_csv=str(long_csv), chart_files=[str(chart)]
    )
    text = Path(output).read_text()
    assert "../../outputs/trust/trust_national_govt_pct.png" in text


def test_worldbank_parser(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Synthetic World Bank WDI payload: [meta, rows].
    payload = [
        {"pages": 1},
        [
            {"countryiso3code": "GBR", "date": "2020", "value": 1.23},
            {"countryiso3code": "GBR", "date": "2019", "value": None},   # skipped
            {"countryiso3code": "ZZZ", "date": "2020", "value": 9.9},    # not in set -> skipped
        ],
    ]
    monkeypatch.setattr(worldbank, "get_json", lambda *a, **k: payload)
    rows = worldbank.fetch(2019, 2020, iso3s=["GBR"], indicators=["GOV_WGI_RL.EST"])
    assert len(rows) == 1
    assert rows[0]["iso3"] == "GBR"
    assert rows[0]["metric"] == "wgi_rule_of_law"
    assert rows[0]["value"] == 1.23


def test_manual_seed_loads() -> None:
    rows = manual.load()
    assert rows, "manual seed CSV should contain rows"
    uk = [r for r in rows if r["iso3"] == "GBR"]
    assert uk, "seed should include UK rows"
    assert all(r["metric"] == "trust_national_govt_pct" for r in rows)
    assert all(r["iso3"] in countries.BY_ISO3 for r in rows)


def test_combine_long_wide_and_dedupe() -> None:
    rows = [
        metrics.make_row("GBR", "United Kingdom", 2020, "trust_national_govt_pct", 41.0, "live"),
        metrics.make_row("GBR", "United Kingdom", 2020, "trust_national_govt_pct", 99.0, "seed"),
        metrics.make_row("GBR", "United Kingdom", 2020, "wgi_rule_of_law", 1.5, "WGI"),
        metrics.make_row("DEU", "Germany", 2020, "trust_national_govt_pct", 60.0, "seed"),
    ]
    deduped = combine.dedupe(rows)
    # Duplicate (GBR, 2020, trust) collapses to the first (live) value.
    assert len(deduped) == 3
    uk_trust = [r for r in deduped if r["iso3"] == "GBR" and r["metric"] == "trust_national_govt_pct"]
    assert uk_trust[0]["value"] == 41.0

    with tempfile.TemporaryDirectory() as d:
        long_path = Path(d) / "long.csv"
        wide_path = Path(d) / "wide.csv"
        combine.write_long(deduped, str(long_path))
        combine.write_wide(deduped, str(wide_path))

        long_rows = list(csv.DictReader(open(long_path)))
        assert len(long_rows) == 3
        assert set(long_rows[0]) == set(combine.LONG_FIELDS)

        wide = {r["country"]: r for r in csv.DictReader(open(wide_path))}
        assert wide["United Kingdom"]["trust_national_govt_pct"] == "41.0"
        assert wide["United Kingdom"]["wgi_rule_of_law"] == "1.5"
        # Missing metric is blank, not an error.
        assert wide["Germany"]["wgi_rule_of_law"] == ""


def _run() -> int:
    import types

    class _MP:
        """Minimal monkeypatch shim so tests run without pytest."""

        def __init__(self) -> None:
            self._undo: list = []

        def setattr(self, obj, name, value):  # type: ignore[no-untyped-def]
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

        def undo(self) -> None:
            for obj, name, old in reversed(self._undo):
                setattr(obj, name, old)
            self._undo.clear()

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        mp = _MP()
        try:
            if "monkeypatch" in t.__code__.co_varnames[: t.__code__.co_argcount]:
                t(mp)
            else:
                t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        finally:
            mp.undo()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
