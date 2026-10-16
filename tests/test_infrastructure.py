from datetime import datetime, timezone
from io import BytesIO
import numpy as np
import pandas as pd
import pytest

from investment_data import infrastructure as infra
from scripts.chart_data import load_chart_data


def workbook(*, missing=False, unit="\u00a3m", bad_share=False):
    years = list(range(1997, 2026))
    market = pd.DataFrame([
        [f"Market sector investment in infrastructure, UK, {unit}"],
        ["Current prices"], ["Industry group", *years], ["Total", *([99999] * len(years))],
        ["Chained volume measures, 2023 prices"], ["Industry group ", *years],
        ["Energy", *([99999] * len(years))],
        ["Total", *([20000] * (len(years) - 1)), 31329],
    ])
    years = list(range(2006, 2026))
    totals = [12000] * (len(years) - 1) + [30799]
    gdps = [1500000] * (len(years) - 1) + [3036899]
    shares = [round(n / d, 3) for n, d in zip(totals, gdps)]
    if missing:
        totals[3] = None
    if bad_share:
        shares[-1] = .5
    government = pd.DataFrame([
        [f"Government infrastructure investment estimates in current prices, UK, {unit}"],
        ["Infrastructure investment type", *years], ["Total", *totals],
        ["GDP ", *gdps], ["Infrastructure share of GDP", *shares],
        ["Percentage change from previous year"], ["Total", *([.01] * len(years))],
    ])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        market.to_excel(writer, sheet_name="Market sector investment ", header=False, index=False)
        government.to_excel(writer, sheet_name="Government investment", header=False, index=False)
    return output.getvalue()


def parse(**kwargs):
    return infra.parse(workbook(**kwargs), "https://www.ons.gov.uk/latest.xlsx",
                       datetime.now(timezone.utc).isoformat())


def test_ons_infrastructure_selects_constant_price_total_and_same_workbook_nominal_gdp():
    frame = parse()
    market = frame[frame.metric == infra.MARKET]
    government = frame[frame.metric == infra.GOVERNMENT]
    assert len(market) == 29 and len(government) == 20
    assert market.iloc[-1].value == 31.329
    assert market.price_base_year.eq(2023).all()
    assert government.iloc[-1].value == pytest.approx(100 * 30799 / 3036899)
    assert government.iloc[-1].gdp == 3036899e6
    assert market.gdp.isna().all()
    assert government.price_base_year.isna().all()


@pytest.mark.parametrize("kwargs", [
    {"missing": True}, {"unit": "\u00a3bn"}, {"bad_share": True},
])
def test_infrastructure_rejects_spotty_data_wrong_units_and_unreconciled_shares(kwargs):
    with pytest.raises(ValueError):
        parse(**kwargs)


def test_infrastructure_plot_has_complete_continuous_lines_and_no_mixed_units(monkeypatch, tmp_path):
    frame = parse()
    captured = []
    save = infra.save_chart

    def capture(fig, path, **kwargs):
        captured.append(fig)
        save(fig, path, **kwargs)

    monkeypatch.setattr(infra, "save_chart", capture)
    path = infra.make_chart(frame, tmp_path)
    payload = load_chart_data(tmp_path, path.relative_to(tmp_path))
    assert len(payload["series"]) == 2
    assert [len(series["points"]) for series in payload["series"]] == [29, 20]
    for ax, metric in zip(captured[0].axes, (infra.MARKET, infra.GOVERNMENT)):
        line = ax.lines[0]
        assert np.isfinite(line.get_ydata()).all()
        assert np.diff(line.get_xdata()).tolist() == [1] * (len(line.get_xdata()) - 1)
        assert line.get_ydata() == pytest.approx(frame.loc[frame.metric == metric, "value"])
    assert "2023 prices" in captured[0].axes[0].get_ylabel()
    assert "%" in captured[0].axes[1].get_ylabel()
    assert "do not add" in " ".join(text.get_text() for text in captured[0].texts)
