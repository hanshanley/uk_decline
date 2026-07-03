"""Offline unit tests for the markets_data pipeline (no network required).

Run directly:  python tests/test_markets.py
Or with pytest: pytest tests/test_markets.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from markets_data import combine, markets, regions, worldbank  # noqa: E402


def test_metric_indicator_mapping() -> None:
    # Every metric maps to a World Bank indicator and back.
    assert markets.METRICS["market_cap_usd"].wb_indicator == "CM.MKT.LCAP.CD"
    assert markets.BY_INDICATOR["CM.MKT.LCAP.CD"] == "market_cap_usd"
    assert markets.BY_INDICATOR["CM.MKT.LCAP.GD.ZS"] == "market_cap_pct_gdp"
    assert markets.BY_INDICATOR["CM.MKT.LDOM.NO"] == "listed_domestic_companies"
    # Units are derived from the metric id by make_row.
    row = markets.make_row("United Kingdom", "GBR", 2020, "market_cap_usd", 3.2e12)
    assert row["unit"] == "current US$"
    assert set(row) == set(markets.ROW_FIELDS)


def test_regions_core_and_colours() -> None:
    core = regions.codes(core_only=True)
    assert core == ["GBR", "USA"]
    assert "WLD" in regions.codes()
    assert regions.name_for_code("USA") == "United States"
    # Every region has a stable chart colour.
    for code in regions.codes():
        assert code in regions.COLOURS


def test_worldbank_parse_paged(monkeypatch) -> None:
    # Two-page World Bank payload; nulls are dropped, values coerced to float.
    pages = {
        1: [
            {"pages": 2},
            [
                {"countryiso3code": "GBR", "date": "2020", "value": 3.2e12,
                 "country": {"id": "GB", "value": "United Kingdom"}},
                {"countryiso3code": "USA", "date": "2020", "value": None,
                 "country": {"id": "US", "value": "United States"}},
            ],
        ],
        2: [
            {"pages": 2},
            [
                {"countryiso3code": "USA", "date": "2020", "value": 40e12,
                 "country": {"id": "US", "value": "United States"}},
            ],
        ],
    }

    def fake_get_json(url, params=None, timeout=60):
        return pages[params["page"]]

    monkeypatch.setattr(worldbank, "get_json", fake_get_json)
    rows = worldbank.fetch(2020, 2020, codes=["GBR", "USA"],
                           indicators=["CM.MKT.LCAP.CD"])
    by_code = {r["region_code"]: r for r in rows}
    assert set(by_code) == {"GBR", "USA"}  # null USA on page 1 dropped
    assert by_code["GBR"]["value"] == 3.2e12
    assert by_code["GBR"]["metric"] == "market_cap_usd"
    assert by_code["USA"]["value"] == 40e12


def test_to_wide_shape() -> None:
    rows = [
        markets.make_row("United Kingdom", "GBR", 2020, "market_cap_usd", 3.2e12),
        markets.make_row("United Kingdom", "GBR", 2020, "market_cap_pct_gdp", 120.0),
        markets.make_row("United States", "USA", 2020, "market_cap_usd", 40e12),
    ]
    df = combine.to_frame(rows)
    wide = combine.to_wide(df)
    assert list(wide.columns) == ["region", "region_code", "year", *combine.METRIC_ORDER]
    uk = wide[wide["region_code"] == "GBR"].iloc[0]
    assert uk["market_cap_usd"] == 3.2e12
    assert uk["market_cap_pct_gdp"] == 120.0
    us = wide[wide["region_code"] == "USA"].iloc[0]
    # Missing metric for the US row is null, not an error.
    import pandas as pd
    assert pd.isna(us["market_cap_pct_gdp"])


def _run() -> int:
    # Minimal monkeypatch shim so the file also runs without pytest.
    class _MP:
        def __init__(self) -> None:
            self._undo: list = []

        def setattr(self, obj, name, value) -> None:
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

        def undo(self) -> None:
            for obj, name, old in reversed(self._undo):
                setattr(obj, name, old)
            self._undo.clear()

    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, t in tests:
        mp = _MP()
        try:
            if "monkeypatch" in t.__code__.co_varnames[: t.__code__.co_argcount]:
                t(mp)
            else:
                t()
            print(f"ok   {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
        finally:
            mp.undo()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
