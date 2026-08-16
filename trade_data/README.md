# trade_data — trade as a share of the economy

![Trade as a share of GDP](../outputs/trade/trade_share_gdp.png)

This analysis uses the standard measure of economic openness:

> **Exports plus imports of goods and services as a percentage of GDP.**

The chart compares the United Kingdom with Germany, France, Japan, and the United
States from 2000 through the latest available World Bank observation. Values can
exceed 100% for highly open economies because exports and imports are both counted.

## Source

World Bank, *World Development Indicators*, indicator
[`NE.TRD.GNFS.ZS`](https://data.worldbank.org/indicator/NE.TRD.GNFS.ZS),
Trade (% of GDP). The indicator combines World Bank and OECD national-accounts data.

## Run

```bash
./.venv/bin/python -m trade_data
./.venv/bin/python -m trade_data --from-csv data/trade_share_gdp.csv
./.venv/bin/pytest tests/test_trade.py -q
```

