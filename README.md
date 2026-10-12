<div align="center">
  <h1>Social, Economic, and Political Change in the United Kingdom</h1>
  <p><strong>Source-backed data. Reproducible analysis. Long-run context.</strong></p>
  <p>Comparing the UK with the United States and European peers.</p>
  <p>
    <a href="#uk-since-2007">Overview</a> ·
    <a href="#explore-the-evidence">Analyses</a> ·
    <a href="#setup">Setup</a>
  </p>
</div>

---

## UK since 2007

The overview combines eight source-backed indicators, including official statistics,
charity administrative counts and a constructed tuition-fee series. It uses 2007 as
the common framing; each panel uses its own available baseline and latest year.
It is not a composite index or an exhaustive measure of UK performance. Colours
describe the selected direction of change between endpoints, not the latest annual trend.

<p align="center">
  <img src="outputs/uk_decline_scorecard.png" width="1200" alt="Eight source-backed indicators showing change in the UK since 2007">
</p>

The GDP comparison uses **constant-price purchasing-power parity (PPP)**, not
market-exchange-rate dollars, so sterling movements are not mistaken for relative
changes in economic output. The tuition panel is an **England undergraduate fee-cap
series**, converted at annual market exchange rates and deflated with US CPI to
2022 dollars—not average UK tuition or a domestic UK purchasing-power measure.
NHS waiting counts are **treatment
pathways**, not unique patients, and Trussell figures count **parcels distributed by
its network**, not unique recipients or all UK food-bank provision. The listed-firm
panel retains the **World Bank/WFE series only**, including domestic companies and
foreign companies listed exclusively on those exchanges, but excluding funds and
pure holding companies. It ends earlier than other panels: the newer LSE
UK-domiciled counts have a different definition and are no longer spliced onto it.

The crime panel shows **estimated incidents in England & Wales, excluding fraud and
computer misuse**, from ONS Crime Survey Table A1a: **11.2 million in the year ending
March 2007 to 4.3 million in the year ending March 2026**. Lower counts are shown as
an improvement. This is a long-run survey measure, not all UK crime, a police-recorded
total, or the percentage of people victimised; it does not cover every offence type.
See the [crime analysis](crime_data/README.md) for coverage and the separate series
including fraud and computer misuse.

It replaces a misleadingly labelled "fraud share" panel. That calculation actually
measured **fraud and computer misuse combined as a share of CSEW headline incidents**,
not fraud alone or the chance of being a fraud victim. A share can increase simply
because other crime falls, so it was not a sound standalone worsening indicator.

## Explore the evidence

**Economy and living standards:** [GDP and incomes](europe_data/README.md),
[stock markets](markets_data/README.md), [sterling](sterling_data/README.md),
[trade](trade_data/README.md), [London's economy](london_data/README.md), and
[purchasing power parity](ppp_data/README.md).

**Public services and infrastructure:** [austerity](austerity_data/README.md),
[NHS performance](nhs_data/README.md), and [rail performance](rail_data/README.md).

**Household pressure:** [tax](tax/README.md), [tuition](tuition/README.md), and
[food-bank use](foodbank_data/README.md).

**Population and institutions:** [migration](uk_migration/README.md),
[ageing](age_data/README.md), [crime](crime_data/README.md), and
[institutional trust](trust_data/README.md).

Each analysis is a self-contained pipeline with its own methodology, caveats, charts, and
primary-source citations. The complete figure collection is in [`outputs/`](outputs).

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Each analysis runs as a module from the repo root, e.g.:

```bash
./.venv/bin/python -m europe_data.fetch_data      # fetch data -> data/
./.venv/bin/python -m europe_data.plot_uk_decline # figures -> outputs/gdp_income/
./.venv/bin/python -m markets_data                # UK vs US markets -> outputs/stock_markets/
./.venv/bin/python -m austerity_data              # austerity -> outputs/austerity/
./.venv/bin/python -m foodbank_data               # food-bank use -> outputs/food_banks/
./.venv/bin/python -m sterling_data               # pound exchange rates -> outputs/sterling/
./.venv/bin/python -m trade_data                  # trade share of GDP -> outputs/trade/
./.venv/bin/python -m nhs_data                    # NHS -> outputs/nhs/
./.venv/bin/python -m rail_data                   # London rail delays -> outputs/rail/
./.venv/bin/python -m london_data                 # London's share of UK GDP -> outputs/london/
./.venv/bin/python -m crime_data                  # crime trend & homicide -> outputs/crime/
./.venv/bin/python -m ppp_data                    # PPP alternative view -> outputs/ppp/
```

See each analysis's README for its exact commands and full source citations.

After generating the input CSVs, rebuild the overview image without re-fetching data:

```bash
./.venv/bin/python scorecard.py
```

## Data integrity
No API keys are required, and source observations are not fabricated. Derived measures,
source-published estimates, method breaks and coverage limitations are documented in
each analysis. Downloaded/intermediate data generally lives under `data/`
(git-ignored, regenerable); cited historical input snapshots are tracked where needed.
The curated figures under `outputs/` are the committed showcase. Targeted observations
have been checked against primary sources; this is not independent verification of
every observation in every dataset.
