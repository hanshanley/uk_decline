"""Build the public website from tracked figures and documentation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
import markdown

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/hanshanley/uk_decline"
TITLE = "The UK, in context"
CANONICAL_ROOT = "https://www.themarginoferror.com/uk_decline/"


def canonical_url(page: Path) -> str:
    path = page.as_posix()
    if page.name == "index.html":
        path = path.removesuffix("index.html")
    return CANONICAL_ROOT + path


@dataclass(frozen=True)
class Analysis:
    slug: str
    title: str
    group: str
    module: str
    output: str
    charts: tuple[str, ...]
    description: str

    @property
    def featured(self) -> str:
        return self.charts[0]


ANALYSES = (
    Analysis("gdp-income", "GDP & incomes", "Economy", "europe_data", "gdp_income",
             ("uk_gdp_relative_to_peers_simple.png", "gdp_per_capita_real_over_time.png",
              "median_disposable_income_oecd.png"),
             "Real output, nominal valuations and household incomes answer different questions."),
    Analysis("purchasing-power", "Purchasing power", "Economy", "ppp_data", "ppp",
             ("ppp_gdp_per_capita_growth.png", "ppp_gdp_relative_to_peers.png",
              "ppp_gap_decomposition_uk_us.png"),
             "Separate real economic growth from exchange rates and relative price levels."),
    Analysis("markets", "Stock markets", "Economy", "markets_data", "stock_markets",
             ("stock_lse_uk_companies.png", "stock_listed_domestic_companies.png",
              "stock_market_cap_pct_gdp.png"),
             "Company listings and market size, with London Stock Exchange and international definitions kept separate."),
    Analysis("sterling", "Sterling", "Economy", "sterling_data", "sterling",
             ("sterling_currency_strength_v2.png",),
             "The pound against other currencies, using observed annual exchange rates."),
    Analysis("trade", "Trade", "Economy", "trade_data", "trade",
             ("trade_share_gdp.png",),
             "Imports and exports relative to the size of the economy."),
    Analysis("london", "London's economy", "Economy", "london_data", "london",
             ("london_share_of_uk_gdp.png", "london_gdp_per_head_vs_uk.png"),
             "London's share of UK output and its GDP per head relative to the UK."),
    Analysis("unemployment", "Unemployment & youth unemployment", "Economy",
             "unemployment_data", "unemployment",
             ("uk_unemployment_comparison.png",),
             "UK unemployment among people aged 16 and over and young people aged 16-24, "
             "as a share of those employed or unemployed, not of the whole population."),
    Analysis("public-spending", "Public spending", "Public services", "austerity_data", "austerity",
             ("uk_austerity_spending_investment.png",),
             "Public spending and investment, with financial years and inflation adjustments stated."),
    Analysis("debt-borrowing", "Debt & borrowing costs", "Economy", "debt_data", "debt",
             ("uk_public_debt_pct_gdp.png", "uk_borrowing_costs_daily.png",
              "government_borrowing_costs.png"),
             "UK public debt relative to GDP and government-bond yields: the debt stock and the cost of new borrowing."),
    Analysis("nhs", "NHS performance", "Public services", "nhs_data", "nhs",
             ("rtt_waiting_list_per_1000.png", "ae_4hr_pct.png", "cancer_62day_pct.png"),
             "Waiting lists and treatment standards across the four nations, with scope breaks."),
    Analysis("rail", "Rail performance", "Public services", "rail_data", "rail",
             ("rail_london_ppm_official.png", "rail_london_casl.png"),
             "Official punctuality and cancellation measures, distinct from historical reconstruction."),
    Analysis("tax", "Tax", "Households", "tax", "tax",
             ("tax_to_gdp_over_time.png", "tax_wedge_by_earnings.png"),
             "National tax revenue and household labour-tax wedges are different measures."),
    Analysis("tuition", "University tuition", "Households", "tuition", "tuition",
             ("tuition_england_cap_nominal.png", "tuition_history_real_usd.png",
              "tuition_region_comparison.png"),
             "England's fee cap alongside dated US and European fee comparisons."),
    Analysis("food-banks", "Food-bank use", "Households", "foodbank_data", "food_banks",
             ("trussell_food_parcels.png",),
             "Trussell network parcel counts, not unique recipients or all UK food-bank provision."),
    Analysis("migration", "Migration", "Population & institutions", "uk_migration", "migration",
             ("net_migration.png", "visas_by_category.png", "asylum_applications.png"),
             "Immigration, emigration, visas and asylum, without conflating people and events."),
    Analysis("ageing", "Ageing", "Population & institutions", "age_data", "age",
             ("share_65plus_over_time.png", "uk_population_pyramid.png"),
             "Population age structures and the changing share of older residents."),
    Analysis("crime", "Crime", "Population & institutions", "crime_data", "crime",
             ("crime_csew_21st_century.png", "crime_fraud_gap.png", "crime_homicide_peers.png"),
             "Survey incidents and homicide statistics, with geography and coverage made explicit."),
    Analysis("trust", "Institutional trust", "Population & institutions", "trust_data", "trust",
             ("trust_national_govt_pct.png", "wgi_government_effectiveness.png"),
             "Survey trust and governance indicators, respecting collection and methodology changes."),
)


def tracked_files(root: Path) -> set[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True,
    )
    return {Path(os.fsdecode(name)) for name in result.stdout.split(b"\0") if name}


def relative_url(target: Path, page: Path) -> str:
    url = Path(os.path.relpath(target, page.parent)).as_posix()
    return (url.removesuffix("index.html") or "./") if target.name == "index.html" else url


SUBSCRIBE_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSeHPhVHdJ0xdCYq3wDYjkOIxgVdErP4qszNOBQYrnyzTz3xyQ/viewform"
)

CHART_TITLES = {
    "uk_public_debt_pct_gdp": "UK public-sector net debt as a share of GDP",
    "uk_borrowing_costs_daily": "UK 10-year borrowing rates: latest daily observations",
    "government_borrowing_costs": "Government borrowing rates: 10-year bond yields",
    "uk_unemployment": "UK unemployment: ages 16 and over",
    "uk_youth_unemployment": "UK youth unemployment: ages 16-24",
    "uk_unemployment_comparison": "UK unemployment: overall (16+) and youth (16-24)",
    "median_age_over_time": "Median age across countries",
    "share_65plus_over_time": "Population aged 65 and over",
    "uk_age_structure_over_time": "The UK's changing age structure",
    "uk_population_pyramid": "UK population by age and sex",
    "uk_austerity_spending_investment": "UK public spending and investment",
    "crime_csew_21st_century": "Household survey crime since 2000: England and Wales",
    "crime_csew_total": "Long-run household survey crime: England and Wales",
    "crime_fraud_gap": "How including fraud changes the crime total",
    "crime_homicide_nations": "Homicide rates across UK jurisdictions",
    "crime_homicide_peers": "Homicide rates across countries",
    "trussell_food_parcels": "Trussell emergency food parcels: calendar-year totals",
    "gdp_per_capita_nominal_over_time": "GDP per person at current market exchange rates",
    "gdp_per_capita_real_over_time": "Real GDP per person: national output volumes",
    "median_disposable_income_pps": "Median disposable income in purchasing power standards",
    "median_disposable_income_oecd": "Median disposable income, adjusted for household size and purchasing power",
    "median_income_pip": "Median daily income or consumption, adjusted for purchasing power",
    "uk_gdp_relative_to_peers": "UK GDP per person relative to other countries at market exchange rates",
    "uk_gdp_relative_to_peers_simple": "US, EU and Polish GDP per person relative to the UK at market exchange rates",
    "london_gdp_per_head_vs_uk": "London GDP per person relative to the UK",
    "london_share_of_uk_gdp": "London's share of UK GDP",
    "asylum_applications": "Applications for asylum",
    "immigration_by_origin": "Long-term immigration by citizenship group",
    "immigration_over_time": "Long-term immigration over time",
    "immigration_vs_emigration": "Long-term immigration and emigration",
    "irregular_arrivals": "Detected irregular arrivals",
    "legal_vs_irregular": "Long-term immigration and detected irregular arrivals: different measures",
    "net_migration_by_origin": "Net migration by citizenship group",
    "net_migration_per_capita": "Net migration relative to population",
    "net_migration": "Net long-term migration",
    "visas_by_category": "Visas granted by category",
    "ae_4hr_pct": "Emergency care: admitted, transferred or discharged within four hours",
    "cancer_62day_pct": "Cancer treatment starting within 62 days",
    "diagnostics_6week_breach_pct": "Diagnostic-test waits of six weeks or more",
    "diagnostics_8week_breach_pct": "Wales: diagnostic-test waits over eight weeks",
    "rtt_median_wait_weeks": "Median waiting time for planned treatment",
    "rtt_waiting_list_per_1000": "Planned-care waits per 1,000 residents",
    "rtt_waiting_list_total_indexed": "Growth in recorded waits for planned care",
    "rtt_waiting_list_total": "Recorded waits for planned care, not unique patients",
    "ppp_gap_decomposition_uk_us": "The UK–US GDP gap: output growth, prices and exchange rates",
    "ppp_gdp_long_run_maddison": "Long-run real GDP per person, adjusted for purchasing power",
    "ppp_gdp_per_capita_growth": "Growth in real GDP per person",
    "ppp_gdp_per_capita_over_time": "Real GDP per person at a fixed purchasing-power benchmark",
    "ppp_gdp_relative_to_peers": "GDP per person relative to the UK, adjusted for purchasing power",
    "ppp_tuition_history": "Historical tuition fees, adjusted for purchasing power",
    "ppp_vs_market_fx_uk_us": "UK–US GDP per person: market rates and purchasing power",
    "price_level_index": "GDP-wide price levels relative to the US",
    "tuition_share_of_gdp_per_capita": "Tuition fees as a share of GDP per person",
    "rail_london_casl": "Trains cancelled or more than 30 minutes late",
    "rail_london_ppm_official": "Rail arrivals within 5 or 10 minutes: official annual averages",
    "rail_london_ppm": "Rail arrivals within 5 or 10 minutes: historical reconstruction",
    "sterling_currency_strength_v2": "The pound against other currencies",
    "stock_listed_domestic_companies": "Listed domestic companies across countries",
    "stock_lse_uk_companies": "UK-classified companies on the London Stock Exchange",
    "stock_market_cap_pct_gdp": "Stock-market value as a share of GDP",
    "stock_market_cap_usd_real": "Stock-market value in inflation-adjusted US dollars",
    "stock_market_cap_usd": "Stock-market value in current US dollars",
    "stock_uk_us_ratio_market_cap_pct_gdp": "UK–US ratio of stock-market value relative to GDP",
    "stock_uk_us_ratio_market_cap_usd_real": "UK stock-market value relative to the US: inflation-adjusted dollars",
    "stock_uk_us_ratio_market_cap_usd": "UK stock-market value relative to the US: current dollars",
    "tax_burden_headline_bars": "National tax revenue and taxes on labour: different measures",
    "tax_to_gdp_over_time": "Tax revenue as a share of GDP",
    "tax_wedge_by_earnings": "Taxes on labour as a share of total employment cost",
    "trade_share_gdp": "Imports and exports as a share of GDP",
    "trust_national_govt_pct": "Trust in national government",
    "wgi_control_of_corruption": "Control of corruption: governance scores",
    "wgi_government_effectiveness": "Government effectiveness: governance scores",
    "wgi_rule_of_law": "Rule of law: governance scores",
    "wgi_voice_accountability": "Voice and accountability: governance scores",
    "tuition_by_country_real": "Domestic undergraduate tuition by country: inflation-adjusted dollars",
    "tuition_by_country": "Domestic undergraduate tuition by country: current dollars",
    "tuition_england_cap_nominal": "England's maximum annual tuition fee, not inflation-adjusted",
    "tuition_history_real_usd": "Historical tuition fees in inflation-adjusted US dollars",
    "tuition_region_comparison_real": "Domestic undergraduate tuition by region: inflation-adjusted dollars",
    "tuition_region_comparison": "Annual tuition: England, the EU country mean and the US",
}


def chart_title(path: Path) -> str:
    try:
        return CHART_TITLES[path.stem]
    except KeyError:
        raise ValueError(f"Published chart needs a reader-facing title: {path}") from None


def render_document(
    source: Path, page: Path, root: Path, files: set[Path], documents: dict[Path, Path],
) -> str:
    html = markdown.markdown(
        (root / source).read_text(), extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )
    soup = BeautifulSoup(html, "html.parser")
    if source == Path("README.md"):
        for heading in soup.find_all(
            "h2", id=["working-with-the-charts", "setup", "data-integrity"],
        ):
            for sibling in list(heading.next_siblings):
                if getattr(sibling, "name", None) == "h2":
                    break
                sibling.extract()
            heading.decompose()
        for link in soup.find_all("a", href="#setup"):
            separator = link.next_sibling
            if isinstance(separator, str):
                separator.replace_with(separator.replace("\u00b7", "", 1))
            link.decompose()
    for heading in soup.find_all("h1"):
        heading.name = "h2"
    for element, attribute in [("a", "href"), ("img", "src")]:
        for node in soup.find_all(element):
            value = node.get(attribute)
            if not value:
                continue
            url = urlsplit(value)
            if url.scheme or url.netloc or not url.path:
                continue
            path = (root / source.parent / unquote(url.path)).resolve()
            if not path.is_relative_to(root):
                raise ValueError(f"{source}: link escapes repository: {value}")
            target = path.relative_to(root)
            if target in documents:
                destination = relative_url(documents[target], page)
            elif target in files and target.suffix.lower() in {".png", ".csv"}:
                destination = relative_url(target, page)
            else:
                if element == "img":
                    raise ValueError(f"{source}: image is not a tracked publication asset: {value}")
                destination = f"{REPOSITORY}/blob/master/{target.as_posix()}"
                if target not in files:
                    destination = f"{REPOSITORY}/tree/master/{target.as_posix()}"
            if url.query:
                destination += f"?{url.query}"
            if url.fragment:
                destination += f"#{url.fragment}"
            node[attribute] = destination
    for image in soup.find_all("img"):
        image["loading"] = "lazy"
    return str(soup)


def layout(
    title: str, description: str, body: str, page: Path, revision: str, built_at: str,
    refreshed_at: str | None = None,
) -> str:
    home = relative_url(Path("index.html"), page)
    methods = relative_url(Path("methods/index.html"), page)
    css = relative_url(Path("assets/site.css"), page)
    js = relative_url(Path("assets/site.js"), page)
    refresh_note = (
        f"Last complete automated refresh: {escape(refreshed_at)} (UTC)."
        if refreshed_at else "Automatic data refreshes run weekly."
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(description, quote=True)}">
  <meta name="theme-color" content="#f2efe7">
  <title>{escape(title)} | {TITLE} | The Margin of Error</title>
  <link rel="canonical" href="{escape(canonical_url(page), quote=True)}">
  <link rel="icon" href="https://www.themarginoferror.com/favicon-32.png" type="image/png" sizes="32x32">
  <link rel="apple-touch-icon" href="https://www.themarginoferror.com/apple-touch-icon.png" sizes="180x180">
  <link rel="stylesheet" href="{css}">
  <script src="{js}" defer></script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="edition-line" aria-hidden="true">
      <span>Independent notes on systems and society</span><span>Est. 2021</span>
    </div>
    <div class="masthead">
      <a class="wordmark" href="https://www.themarginoferror.com/" aria-label="The Margin of Error, home">
        <span class="wordmark-the">The</span>
        <span class="wordmark-main">Margin <i>of</i> Error</span>
      </a>
      <nav aria-label="Primary navigation"><ul>
        <li><a href="https://www.themarginoferror.com/">Latest</a></li>
        <li><a href="https://www.themarginoferror.com/archive/">Archive</a></li>
        <li><a href="https://www.themarginoferror.com/interactive-analysis/">Interactive analysis</a></li>
        <li><a href="https://www.themarginoferror.com/about/">About</a></li>
        <li><a class="subscribe-link" href="{SUBSCRIBE_URL}">Subscribe</a></li>
      </ul></nav>
    </div>
  </header>
  <main id="main">
    <nav class="project-nav" aria-label="UK evidence navigation">
      <a href="{home}">UK overview</a>
      <a href="{home}#explore">Explore</a><a href="{methods}">Methods</a>
      <a href="{REPOSITORY}">GitHub <span aria-hidden="true">&#8599;</span></a>
    </nav>
    {body}
    <aside class="publication-note" aria-label="UK data publication notes">
    <p>Site built <time datetime="{built_at}">{built_at[:10]}</time> (UTC).
    <a href="{REPOSITORY}/commit/{revision}">Source {revision[:7]}</a>.</p>
    <p>Publication date is not the observation date. Each chart carries its own periods,
    definitions and sources. Missing observations are not filled with estimates.</p>
    <p>{refresh_note} Curated source selections are reviewed separately.
    <a href="{REPOSITORY}/actions/workflows/update-site.yml">Update status</a>.</p>
    </aside>
  </main>
  <footer class="site-footer">
    <div><p class="eyebrow">Endnote</p>
      <p>The Margin of Error is written by
      <a href="https://www.hanshanley.com/">Hans W. A. Hanley</a>.</p></div>
    <div class="footer-links">
      <a href="https://www.themarginoferror.com/rss.xml">RSS</a>
      <a href="https://www.themarginoferror.com/are-you-an-ai/">AI index</a>
      <a href="{REPOSITORY}">Data &amp; code</a>
      <a href="{SUBSCRIBE_URL}">Subscribe</a>
    </div>
    <p class="copyright">&copy; {built_at[:4]} Hans W. A. Hanley</p>
  </footer>
  <dialog id="chart-viewer" aria-label="Full-size chart">
    <button type="button" class="close-viewer" aria-label="Close full-size chart">Close &#215;</button>
    <img alt="">
  </dialog>
</body>
</html>
"""


def homepage() -> str:
    cards = []
    for analysis in ANALYSES:
        cards.append(f"""
        <article class="topic-card" data-group="{escape(analysis.group, quote=True)}"
                 data-search="{escape(f'{analysis.title} {analysis.description}'.lower(), quote=True)}">
          <a href="{analysis.slug}/">
            <img src="outputs/{analysis.output}/{analysis.featured}" loading="lazy" alt="">
            <div class="card-copy"><span class="eyebrow">{escape(analysis.group)}</span>
            <h3>{escape(analysis.title)} <span aria-hidden="true">&#8594;</span></h3>
            <p>{escape(analysis.description)}</p></div>
          </a>
        </article>""")
    groups = dict.fromkeys(analysis.group for analysis in ANALYSES)
    filters = '<button type="button" data-filter="all" aria-pressed="true">All topics</button>'
    filters += "".join(
        f'<button type="button" data-filter="{escape(group, quote=True)}" aria-pressed="false">'
        f'{escape(group)}</button>' for group in groups
    )
    return f"""
    <section class="intro">
      <p class="eyebrow">A source-backed view of the United Kingdom</p>
      <h1>How has the UK<br>changed?</h1>
      <p class="standfirst">Explore the economy, public services, household pressures
      and institutions.</p>
      <a class="text-link" href="#explore">Explore the evidence <span aria-hidden="true">&#8595;</span></a>
    </section>
    <section class="overview" aria-labelledby="overview-title">
      <div class="section-heading"><div><p class="eyebrow">The overview</p>
      <h2 id="overview-title">The UK since 2007</h2></div>
      <a href="methods/">What these measures mean &#8594;</a></div>
      <a href="outputs/uk_decline_scorecard.png" class="chart-link">
        <img class="scorecard" src="outputs/uk_decline_scorecard.png"
             alt="Eight selected UK indicators, with individual baselines, endpoints and sources.">
      </a>
      <p class="context">Eight selected indicators, not a composite score or an exhaustive
      assessment of UK performance. Baselines, periods and geographic coverage differ.
      Open the chart for full resolution.</p>
    </section>
    <section id="explore" aria-labelledby="explore-title">
      <div class="section-heading"><div><p class="eyebrow">Go beyond the headline</p>
      <h2 id="explore-title">Explore the evidence</h2></div>
      <p>{len(ANALYSES)} analyses &middot; charts, data and source notes</p></div>
      <div class="explore-tools" hidden>
        <label class="search-label">Find a topic
          <input type="search" id="topic-search" placeholder="Try tuition, GDP or waiting lists">
        </label>
        <div class="filters" role="group" aria-label="Filter topics">{filters}</div>
      </div>
      <p id="topic-count" class="context" role="status" aria-live="polite"></p>
      <div class="topic-grid">{''.join(cards)}</div>
      <p id="no-results" hidden>No matching topics. Try another search or select all topics.</p>
    </section>
    <aside class="reading-note"><h2>Read the source notes.</h2>
      <p>Annual, financial-year, academic-year and monthly observations are not interchangeable.
      A fee cap is not an average bill; a treatment entry is not a unique patient;
      a nominal dollar comparison is not a real-growth comparison.</p>
      <a href="methods/">Definitions and reproducibility &#8594;</a>
    </aside>"""


def analysis_page(analysis: Analysis) -> str:
    page = Path(analysis.slug) / "index.html"
    figures = []
    for filename in analysis.charts:
        chart = Path("outputs") / analysis.output / filename
        url = relative_url(chart, page)
        title = escape(chart_title(chart))
        figures.append(f"""
        <figure id="{escape(chart.stem, quote=True)}">
          <figcaption><h2>{title}</h2><a href="{url}" download>Download PNG</a></figcaption>
          <a href="{url}" class="chart-link"><img src="{url}" alt="{title}" loading="lazy"></a>
        </figure>""")
    return f"""
    <section class="page-heading"><a class="breadcrumb" href="../#explore">&#8592; All analyses</a>
      <p class="eyebrow">{escape(analysis.group)}</p><h1>{escape(analysis.title)}</h1>
      <p class="standfirst">{escape(analysis.description)}</p>
      <p class="context">Open any chart for full resolution. Observation periods and source notes
      are printed on each figure; the site's build date does not imply newer observations.</p>
    </section>
    <section class="chart-gallery" aria-label="Charts">{''.join(figures)}</section>
    <p class="context">
      <a href="{REPOSITORY}/tree/master/outputs/{analysis.output}">All charts on GitHub &#8599;</a>
      &middot; <a href="{REPOSITORY}/blob/master/{analysis.module}/README.md">Full documentation on GitHub &#8599;</a>
    </p>"""


def validate_site(output: Path) -> None:
    """Reject broken local links or image references before replacing a published build."""
    for page in output.rglob("*.html"):
        soup = BeautifulSoup(page.read_text(), "html.parser")
        ids = [node["id"] for node in soup.find_all(id=True)]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{page.relative_to(output)}: duplicate HTML ids")
        for node in soup.find_all(["a", "img", "script", "link"]):
            value = node.get("href") or node.get("src")
            if not value:
                continue
            url = urlsplit(value)
            if url.scheme or url.netloc:
                continue
            target = (page.parent / unquote(url.path)).resolve() if url.path else page
            if target.is_dir():
                target = (target / "index.html").resolve()
            if not target.is_relative_to(output.resolve()) or not target.is_file():
                raise ValueError(f"{page.relative_to(output)}: broken local link {value}")
            if url.fragment and target.suffix == ".html":
                target_soup = soup if target == page else BeautifulSoup(target.read_text(), "html.parser")
                if target_soup.find(id=unquote(url.fragment)) is None:
                    raise ValueError(f"{page.relative_to(output)}: missing anchor {value}")


def build(root: Path = ROOT, *, redirects: bool = False) -> Path:
    root = root.resolve()
    output = root / "_site"
    if output.is_symlink():
        raise ValueError("Refusing to replace a symlinked _site directory")
    files = tracked_files(root)
    analysis_documents = {Path(item.module) / "README.md" for item in ANALYSES}
    documents = {
        path: Path("notes") / path.with_suffix(".html")
        for path in files if path.suffix == ".md" and path not in analysis_documents
    }
    documents[Path("README.md")] = Path("methods/index.html")
    for analysis in ANALYSES:
        required = {
            Path(analysis.module) / "README.md",
            *(Path("outputs") / analysis.output / chart for chart in analysis.charts),
        }
        if missing := required - files:
            raise ValueError(f"{analysis.title}: missing tracked publication inputs: {sorted(missing)}")
    if Path("outputs/uk_decline_scorecard.png") not in files:
        raise ValueError("Missing tracked overview chart")
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True,
    ).strip()
    built_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    refreshed_at = None
    status_path = Path("data/site/refresh.json")
    if status_path in files:
        status = json.loads((root / status_path).read_text())
        checked = datetime.fromisoformat(status["last_successful_refresh_utc"])
        if checked.tzinfo is None:
            raise ValueError("Refresh timestamp must include its timezone")
        refreshed_at = checked.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with tempfile.TemporaryDirectory(prefix=".site-build-", dir=root) as temp:
        stage = Path(temp)
        shutil.copytree(root / "site_assets", stage / "assets")
        for path in files:
            if path.suffix.lower() in {".png", ".csv"} and path.parts[0] in {"outputs", "data"}:
                target = stage / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / path, target)
        pages = {
            Path("index.html"): (
                "Social, economic and political change",
                "Explore source-backed evidence on the UK's economy, public services, households and institutions.",
                homepage(),
            ),
        }
        for analysis in ANALYSES:
            pages[Path(analysis.slug) / "index.html"] = (
                analysis.title, analysis.description, analysis_page(analysis),
            )
        for source, page in documents.items():
            rendered = render_document(source, page, root, files, documents)
            title = "About the data" if source == Path("README.md") else source.stem.replace("_", " ").title()
            body = f'<section class="page-heading"><h1>{escape(title)}</h1></section><article class="prose">{rendered}</article>'
            description = f"Definitions, methodology and source documentation. {source.as_posix()}."
            pages[page] = (title, description, body)
        for page, (title, description, body) in pages.items():
            target = stage / page
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(layout(title, description, body, page, revision, built_at, refreshed_at))
        (stage / ".nojekyll").touch()
        validate_site(stage)
        if redirects:
            for page in pages:
                target = escape(canonical_url(page), quote=True)
                destination = json.dumps(canonical_url(page)).replace("<", "\\u003c")
                (stage / page).write_text(f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="The UK, in context is published by The Margin of Error.">
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{target}">
<title>{TITLE} | The Margin of Error</title>
<script>location.replace({destination} + location.search + location.hash);</script>
</head><body><h1>{TITLE}</h1>
<p><a href="{target}">Continue to The Margin of Error.</a></p>
</body></html>
""")
            validate_site(stage)
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(stage, output)
    print(f"[site] built {len(pages)} pages from tracked publication assets -> {output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--redirects", action="store_true",
        help="Build redirects for the former project-level GitHub Pages address.",
    )
    args = parser.parse_args()
    build(redirects=args.redirects)


if __name__ == "__main__":
    main()
