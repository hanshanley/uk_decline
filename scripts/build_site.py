"""Build the public GitHub Pages site from tracked figures and documentation."""

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


@dataclass(frozen=True)
class Analysis:
    slug: str
    title: str
    group: str
    module: str
    output: str
    featured: str
    description: str


ANALYSES = (
    Analysis("gdp-income", "GDP & incomes", "Economy", "europe_data", "gdp_income",
             "uk_gdp_relative_to_peers.png",
             "Real output, nominal valuations and household incomes answer different questions."),
    Analysis("purchasing-power", "Purchasing power", "Economy", "ppp_data", "ppp",
             "ppp_gdp_per_capita_growth.png",
             "Separate real economic growth from exchange rates and relative price levels."),
    Analysis("markets", "Stock markets", "Economy", "markets_data", "stock_markets",
             "stock_lse_uk_companies.png",
             "Company listings and market size, with LSE and international definitions kept separate."),
    Analysis("sterling", "Sterling", "Economy", "sterling_data", "sterling",
             "sterling_currency_strength_v2.png",
             "The pound against other currencies, using observed annual exchange rates."),
    Analysis("trade", "Trade", "Economy", "trade_data", "trade",
             "trade_share_gdp.png",
             "Imports and exports relative to the size of the economy."),
    Analysis("london", "London's economy", "Economy", "london_data", "london",
             "london_share_of_uk_gdp.png",
             "London's share of UK output and its GDP per head relative to the UK."),
    Analysis("public-spending", "Public spending", "Public services", "austerity_data", "austerity",
             "uk_austerity_spending_investment.png",
             "Public spending and investment, with financial years and inflation adjustments stated."),
    Analysis("nhs", "NHS performance", "Public services", "nhs_data", "nhs",
             "rtt_waiting_list_total.png",
             "Waiting lists and treatment standards across the four nations, with scope breaks."),
    Analysis("rail", "Rail performance", "Public services", "rail_data", "rail",
             "rail_london_ppm_official.png",
             "Official punctuality and cancellation measures, distinct from historical reconstruction."),
    Analysis("tax", "Tax", "Households", "tax", "tax",
             "tax_to_gdp_over_time.png",
             "National tax revenue and household labour-tax wedges are different measures."),
    Analysis("tuition", "University tuition", "Households", "tuition", "tuition",
             "tuition_england_cap_nominal.png",
             "England's fee cap alongside dated US and European fee comparisons."),
    Analysis("food-banks", "Food-bank use", "Households", "foodbank_data", "food_banks",
             "trussell_food_parcels.png",
             "Trussell network parcel counts, not unique recipients or all UK food-bank provision."),
    Analysis("migration", "Migration", "Population & institutions", "uk_migration", "migration",
             "net_migration.png",
             "Immigration, emigration, visas and asylum, without conflating people and events."),
    Analysis("ageing", "Ageing", "Population & institutions", "age_data", "age",
             "share_65plus_over_time.png",
             "Population age structures and the changing share of older residents."),
    Analysis("crime", "Crime", "Population & institutions", "crime_data", "crime",
             "crime_csew_21st_century.png",
             "Survey incidents and homicide statistics, with geography and coverage made explicit."),
    Analysis("trust", "Institutional trust", "Population & institutions", "trust_data", "trust",
             "trust_national_govt_pct.png",
             "Survey trust and governance indicators, respecting collection and methodology changes."),
)


def tracked_files(root: Path) -> set[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True,
    )
    return {Path(os.fsdecode(name)) for name in result.stdout.split(b"\0") if name}


def relative_url(target: Path, page: Path) -> str:
    return Path(os.path.relpath(target, page.parent)).as_posix()


def chart_title(path: Path) -> str:
    title = path.stem.replace("_", " ").capitalize()
    for acronym in ("gdp", "uk", "us", "ppp", "lse", "nhs", "ppm", "csew", "wgi", "usd"):
        title = re.sub(rf"\b{acronym}\b", acronym.upper(), title, flags=re.IGNORECASE)
    return title


def render_document(
    source: Path, page: Path, root: Path, files: set[Path], documents: dict[Path, Path],
) -> str:
    html = markdown.markdown(
        (root / source).read_text(), extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )
    soup = BeautifulSoup(html, "html.parser")
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
  <meta name="theme-color" content="#f7f5f0">
  <title>{escape(title)} | {TITLE}</title>
  <link rel="stylesheet" href="{css}">
  <script src="{js}" defer></script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="masthead">
    <a class="wordmark" href="{home}">{TITLE}<span>Evidence, not a single story.</span></a>
    <nav aria-label="Main navigation">
      <a href="{home}#explore">Explore</a><a href="{methods}">Methods</a>
      <a href="{REPOSITORY}">GitHub <span aria-hidden="true">&#8599;</span></a>
    </nav>
  </header>
  <main id="main">{body}</main>
  <footer>
    <p><strong>{TITLE}</strong> &middot; Social, economic and political change.</p>
    <p>Site built <time datetime="{built_at}">{built_at[:10]}</time> (UTC).
    <a href="{REPOSITORY}/commit/{revision}">Source {revision[:7]}</a>.</p>
    <p>Publication date is not the observation date. Each chart carries its own periods,
    definitions and sources. Missing observations are not filled with estimates.</p>
    <p>{refresh_note} Curated source selections are reviewed separately.
    <a href="{REPOSITORY}/actions/workflows/update-site.yml">Update status</a>.</p>
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
          <a href="{analysis.slug}/index.html">
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
      and institutions. Different measures tell different stories.
      The definitions matter as much as the direction.</p>
      <a class="text-link" href="#explore">Explore the evidence <span aria-hidden="true">&#8595;</span></a>
    </section>
    <section class="overview" aria-labelledby="overview-title">
      <div class="section-heading"><div><p class="eyebrow">The overview</p>
      <h2 id="overview-title">The UK since 2007</h2></div>
      <a href="methods/index.html">What these measures mean &#8594;</a></div>
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
      <p>16 analyses &middot; charts, definitions and sources</p></div>
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
      <a href="methods/index.html">Definitions and reproducibility &#8594;</a>
    </aside>"""


def analysis_page(analysis: Analysis, charts: list[Path], document: str, files: set[Path]) -> str:
    page = Path(analysis.slug) / "index.html"
    figures = []
    for chart in sorted(charts, key=lambda path: (path.name != analysis.featured, path.name)):
        url = relative_url(chart, page)
        title = escape(chart_title(chart))
        figures.append(f"""
        <figure id="{escape(chart.stem, quote=True)}">
          <figcaption><h2>{title}</h2><a href="{url}" download>Download PNG</a></figcaption>
          <a href="{url}" class="chart-link"><img src="{url}" alt="{title}" loading="lazy"></a>
        </figure>""")
    downloads = [
        f'<a href="{relative_url(path, page)}" download>{escape(path.name)}</a>'
        for path in sorted(files)
        if path.parent == Path("outputs") / analysis.output and path.suffix == ".csv"
    ]
    download_section = (
        '<aside class="reading-note"><h2>Published data</h2>'
        + " &middot; ".join(downloads) + "</aside>"
    ) if downloads else ""
    return f"""
    <section class="page-heading"><a class="breadcrumb" href="../index.html#explore">&#8592; All analyses</a>
      <p class="eyebrow">{escape(analysis.group)}</p><h1>{escape(analysis.title)}</h1>
      <p class="standfirst">{escape(analysis.description)}</p>
      <p class="context">Open any chart for full resolution. Observation periods and source notes
      are printed on each figure; the site's build date does not imply newer observations.</p>
      <a class="text-link" href="#methodology">Definitions, methods and sources &#8595;</a>
    </section>
    <section class="chart-gallery" aria-label="Charts">{''.join(figures)}</section>
    {download_section}
    <section class="methodology" id="methodology">
      <p class="eyebrow">Read alongside the charts</p><h2>Definitions, methods and sources</h2>
      <p class="context">The notes below include documented results from their stated source vintages.
      Use each chart's dates for its observation period, not the site's publication date.</p>
      <article class="prose">{document}</article>
    </section>"""


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
            if not target.is_relative_to(output.resolve()) or not target.is_file():
                raise ValueError(f"{page.relative_to(output)}: broken local link {value}")
            if url.fragment and target.suffix == ".html":
                target_soup = soup if target == page else BeautifulSoup(target.read_text(), "html.parser")
                if target_soup.find(id=unquote(url.fragment)) is None:
                    raise ValueError(f"{page.relative_to(output)}: missing anchor {value}")


def build(root: Path = ROOT) -> Path:
    root = root.resolve()
    output = root / "_site"
    if output.is_symlink():
        raise ValueError("Refusing to replace a symlinked _site directory")
    files = tracked_files(root)
    documents = {
        path: Path("notes") / path.with_suffix(".html") for path in files if path.suffix == ".md"
    }
    documents[Path("README.md")] = Path("methods/index.html")
    for analysis in ANALYSES:
        documents[Path(analysis.module) / "README.md"] = Path(analysis.slug) / "index.html"
        required = {
            Path(analysis.module) / "README.md",
            Path("outputs") / analysis.output / analysis.featured,
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
        analyses_by_document = {Path(item.module) / "README.md": item for item in ANALYSES}
        for source, page in documents.items():
            rendered = render_document(source, page, root, files, documents)
            if analysis := analyses_by_document.get(source):
                charts = [
                    path for path in files
                    if path.parent == Path("outputs") / analysis.output and path.suffix == ".png"
                ]
                body = analysis_page(analysis, charts, rendered, files)
                title, description = analysis.title, analysis.description
            else:
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
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(stage, output)
    print(f"[site] built {len(pages)} pages from tracked publication assets -> {output}")
    return output


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()


if __name__ == "__main__":
    main()
