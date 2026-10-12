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
Monthly NHS observations, financial years, academic years and CSEW year-ending
periods are labelled separately; they are not interchangeable annual observations.

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

The GDP ratio represents **real output volumes valued at the 2021 PPP benchmark**,
not median household income or annually repriced purchasing power. The
[GDP analysis](europe_data/README.md) now separates genuine national-accounts real
growth from nominal dollar valuations; the [PPP analysis](ppp_data/README.md) adds a
2007 = 100 growth chart and documents the methodological research and validation.

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

### Final audit — 12 October 2026

The audit traced published charts to their loaders and source definitions, rechecked
overview endpoints against WDI, ONS, Treasury, OWID and Trussell, and reproduced live
OECD tax, WDI trade and age pipelines in an isolated staging tree. Confirmed fixes
include NHS lines/indexes crossing definition changes, superseded NI cancer counts,
incomplete age profiles being normalised into plausible medians, rail smoothers
drawing through missing quarters,
ambiguous overview periods and stale source-splice/fallback documentation. Historical
tuition was rebuilt to include annual fee/FX/CPI observations between policy changes.

Alternative-baseline checks use observed 2010 and 2019 values where available, not
invented missing observations. For example, the real UK/US GDP ratio fell **14.0%**
from 2007, **12.0%** from 2010 and **9.1%** from 2019; recreation/culture/religion
spending fell **20.9%**, **22.6%** and **3.8%** respectively. Magnitudes depend on the
baseline. Food-parcel counts fell **11.7% from 2024 to 2025** despite remaining above
2015/2019 levels. The real market-dollar tuition cap rose **37.6% from 2006**
but fell **18.4% from 2019**; it is not a measure of domestic purchasing power.
The selected panels are not evidence that every measure worsened,
and no chart by itself establishes a policy cause.

Remaining limitations are explicit: the EU tuition compilation contains approximate
secondary-source values and mixed definitions; population-age distributions from
WPP 2024 contain projection assumptions from 2024 onward; country medians are
unweighted, not medians of people; survey crime/trust estimates carry uncertainty;
and endpoint dates differ across sources. WDI still has no US CPI observation for
2025, so the real-dollar tuition history ends in 2024 rather than borrowing another
year's deflator. NI cancer/outpatient/diagnostic source discovery was repaired and
those series refreshed through June 2026. NI's October 2026 cancer release revises
historical waits after a calculation error; the refreshed dataset uses those
revisions, omits months without all five trusts, and splits the encompass breaks.
NHS England landing pages return empty responses/browser challenges in this audit
environment. Cached June 2026 RTT and pinned April 2026 cancer coverage is explicitly
not current: the official cancer index lists at least July 2026 data. These older
endpoints remain dated rather than being presented as the latest publication.
The rail reconstruction was independently compared with official Table 3113 over
28 overlapping quarters: maximum discrepancies are **0.51 percentage points for
London and South East** and **0.18 points for Great Britain**. These approximate
series are not exact official sector aggregates.

Verification: **303 regression tests passed**, as did all **16 GDP/PPP validation
checks**. All **2,970 live country-year age profiles** passed the complete-profile
checks; the opt-in age snapshot also passed. Affected NHS, age, rail, tuition,
spending and overview figures were rebuilt, with representative published figures
visually inspected. Tests validate the implemented methods, not the truth of every
source observation or causal interpretation.
