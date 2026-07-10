"""Offline unit tests for the crime_data pipeline (no network required).

Run directly:  python tests/test_crime.py
Or with pytest: pytest tests/test_crime.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crime_data import countries, csew, homicide  # noqa: E402


def test_country_mappings() -> None:
    assert countries.COUNTRIES[0].iso3 == countries.UK_ISO3 == "GBR"
    assert countries.group_for_iso3("GBR") == countries.UK
    assert countries.group_for_iso3("DEU") == countries.EU
    assert countries.group_for_iso3("USA") == countries.US
    assert countries.name_for_iso3("FRA") == "France"
    iso3s = countries.iso3_codes()
    assert len(iso3s) == len(set(iso3s)) == 29
    assert sum(1 for c in countries.COUNTRIES if c.group == countries.EU) == 27


def _synthetic_a1a() -> pd.DataFrame:
    """A tiny header-less frame shaped like ONS Table_A1a (2 periods x a few rows)."""
    return pd.DataFrame([
        ["Table A1a: Trends in incidents of CSEW headline crime (1,000s)", None, None],
        ["England and Wales, year ending December 1981 to 2002", None, None],
        [None, None, None],
        [None, None, None],
        [None, None, None],
        [None, None, None],
        [None, None, None],
        ["Offence group\n[note 5]", "Jan 1981 to Dec 1981", "Apr 2001 to Mar 2002"],
        ["VIOLENCE", 2063, 2551],
        ["    Violence with injury", 1226, 1507],
        ["ROBBERY", 164, 340],
        ["Unweighted base - number of people aged 16 and over", 9898, 32787],
        ["ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE [note 8]", 11303, 12500],
        ["    Fraud [note 9][note 10]", "[x]", "[x]"],
    ])


def test_csew_parser_basic() -> None:
    rows = csew.build_rows(_synthetic_a1a())
    # 'Unweighted base' rows are dropped; '[x]' fraud cells are skipped.
    assert not any("unweighted base" in r["offence_group"].lower() for r in rows)
    assert not any(r["offence_group"].lower().startswith("fraud") for r in rows)
    # Note markers are stripped from labels.
    assert any(r["offence_group"] == "ALL CSEW HEADLINE CRIME EXCLUDING FRAUD AND COMPUTER MISUSE"
               for r in rows)
    assert all("[note" not in r["offence_group"] for r in rows)


def test_csew_period_and_years() -> None:
    rows = csew.build_rows(_synthetic_a1a())
    violence = sorted((r for r in rows if r["offence_group"] == "VIOLENCE"),
                      key=lambda r: r["date"])
    assert [r["year"] for r in violence] == [1981, 2002]
    assert violence[0]["period"] == "Jan 1981 to Dec 1981"
    assert violence[0]["date"] == "1981-12-31"
    # Apr 2001 to Mar 2002 -> year ending 2002, period end 31 March.
    assert violence[1]["date"] == "2002-03-31"
    assert violence[1]["value"] == 2551.0
    assert violence[0]["region"] == "England and Wales"
    assert violence[0]["unit"] == "incidents (thousands)"
    assert "Crime Survey for England and Wales" in violence[0]["source"]


def test_csew_indent_level() -> None:
    rows = csew.build_rows(_synthetic_a1a())
    top = next(r for r in rows if r["offence_group"] == "VIOLENCE")
    sub = next(r for r in rows if r["offence_group"] == "Violence with injury")
    assert top["level"] == 0
    assert sub["level"] == 1


def test_homicide_parser(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    payload = [
        {"pages": 1},
        [
            {"countryiso3code": "GBR", "date": "2020", "value": 1.1},
            {"countryiso3code": "GBR", "date": "2019", "value": None},   # skipped
            {"countryiso3code": "USA", "date": "2020", "value": 6.5},
            {"countryiso3code": "ZZZ", "date": "2020", "value": 9.9},    # not in set
        ],
    ]

    class _Resp:
        def raise_for_status(self):  # noqa: D401
            pass

        def json(self):
            return payload

    monkeypatch.setattr(homicide.requests, "get", lambda *a, **k: _Resp())
    rows = homicide.build_rows(2019, 2020, iso3s=["GBR", "USA"])
    assert len(rows) == 2
    by = {r["iso3"]: r for r in rows}
    assert by["GBR"]["value"] == 1.1
    assert by["GBR"]["metric"] == "homicide_rate_per_100k"
    assert by["GBR"]["unit"] == "per 100,000 population"
    assert "UNODC" in by["GBR"]["source"]
    assert "USA" in by


def test_ons_host_allowlist() -> None:
    for bad in ("https://evil.example.com/x.xlsx", "http://ons.gov.uk.evil.com/x"):
        try:
            csew._ensure_ons_host(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"expected rejection of {bad!r}")
    csew._ensure_ons_host("https://www.ons.gov.uk/file?uri=x")  # ok, no raise


def _run() -> int:
    class _MP:
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
