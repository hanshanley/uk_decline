from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import pytest

from scripts import build_site, refresh_data
from scripts.chart_data import tracked_charts


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed to execute the browser event handlers")
@pytest.mark.parametrize("scenario", ["fewer-series", "fewer-points", "late-response", "late-error"])
def test_hover_selection_tracks_the_current_chart_and_request(scenario):
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const handlers = new Map();
const elements = [];
const errors = [];
const element = () => ({
  style: {}, children: [], append(...nodes) { this.children.push(...nodes); },
  setAttribute() {}, querySelector() { return null; },
  getBoundingClientRect() { return {left: 0, top: 0, width: 100, height: 100}; }
});
const parent = element();
const image = {dataset: {chartData: "/old.json"}, parentElement: parent,
  closest(selector) { return selector === "img[data-chart-data]" ? this : null; },
  getBoundingClientRect: parent.getBoundingClientRect};
global.document = {baseURI: "https://example.invalid/", body: parent, activeElement: image,
  createElement() { const node = element(); elements.push(node); return node; },
  addEventListener(name, handler) { handlers.set(name, handler); }};
global.window = {innerWidth: 1200, innerHeight: 800, addEventListener() {}};
console.error = (...args) => errors.push(args.map(String).join(" "));
const series = (label, n) => ({label, x_label: "Year", y_label: "Rate",
  bounds: [0, 0, 1, 1],
  points: Array.from({length: n}, (_, i) => [.5, .5, String(2020+i), String(i+1)])});
const scenario = process.argv[2];
const old = {version: 1, series: scenario === "fewer-series"
  ? [series("Old first", 3), series("Old second", 3)] : [series("Old first", 3)]};
const fresh = {version: 1, series: [series("New chart", 1)]};
let settle;
global.fetch = async (url) => {
  if (url.endsWith("/old.json") && scenario.startsWith("late-")) {
    return await new Promise(resolve => { settle = resolve; });
  }
  return {ok: true, json: async () => url.endsWith("/old.json") ? old : fresh};
};
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const focus = () => handlers.get("focusin")({target: image});
const key = name => handlers.get("keydown")({target: image, key: name, preventDefault() {}});
(async () => {
  let pending;
  if (scenario.startsWith("late-")) {
    pending = focus();
  } else {
    await focus();
    if (scenario === "fewer-series") await key("ArrowDown");
    await key("End");
  }
  image.dataset.chartData = "/new.json";
  await focus();
  assert.equal(elements[1].textContent, "New chart");
  assert.equal(elements[2].textContent, "Year: 2020");
  if (pending) {
    settle(scenario === "late-error"
      ? {ok: false, status: 503} : {ok: true, json: async () => old});
    await pending;
  }
  assert.equal(elements[1].textContent, "New chart");
  assert.equal(elements[0].hidden, false);
  await key("End");
  assert.equal(elements[3].textContent, "Rate: 1");
  assert.deepEqual(errors, []);
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
"""
    result = subprocess.run(
        ["node", "-e", script, str(build_site.ROOT / "site_assets/hover.js"), scenario],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def site_repository(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    shutil.copytree(build_site.ROOT / "site_assets", root / "site_assets")
    for analysis in build_site.ANALYSES:
        readme = root / analysis.module / "README.md"
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text(
            f"# {analysis.title}\n\n## Sources\n\n"
            f"![Chart](../outputs/{analysis.output}/{analysis.featured})\n\n"
            "[Overview](../README.md#scope)\n\n[Sources](#sources)\n"
        )
        for filename, _ in analysis.data_downloads:
            data = root / filename
            data.parent.mkdir(parents=True, exist_ok=True)
            data.write_text("date,value\n2026-10-14,25\n")
        for filename in (*analysis.charts, *(name for name, _ in analysis.downloads)):
            chart = root / "outputs" / analysis.output / filename
            chart.parent.mkdir(parents=True, exist_ok=True)
            chart.write_bytes(b"test image")
    for filename in (
        "gdp_income/median_disposable_income_oecd_four_country.png",
        "gdp_income/median_disposable_income_oecd_uk_us_eu.png",
        "ppp/ppp_gdp_relative_to_peers.png",
    ):
        chart = root / "outputs" / filename
        chart.parent.mkdir(parents=True, exist_ok=True)
        chart.write_bytes(b"supplemental image")
    (root / "outputs/uk_decline_scorecard.png").write_bytes(b"overview")
    for chart in (root / "outputs").rglob("*.png"):
        chart.with_suffix(".json").write_text(json.dumps({
            "version": 1,
            "image_sha256": hashlib.sha256(chart.read_bytes()).hexdigest(),
            "series": [{
                "label": label, "x_label": "Year", "y_label": "Rate",
                "bounds": [.1, .1, .9, .9], "points": [[.5, .5, "2025", "4.9%"]],
            } for label in sorted(build_site.CHART_COMPARATORS.get(chart.stem, {"UK"}))],
        }))
    (root / "README.md").write_text(
        "# Social, economic and political change\n\n## Scope\n\n[Tuition](tuition/README.md#sources)\n"
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run([
        "git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-qm", "Publication inputs",
    ], cwd=root, check=True)
    return root


def test_site_builds_nested_pages_and_rewrites_document_links(site_repository):
    root = site_repository
    private_chart = root / "outputs/tuition/private-working-chart.png"
    private_chart.write_bytes(b"not a publication asset")
    output = build_site.build(root)
    home = BeautifulSoup((output / "index.html").read_text(), "html.parser")
    assert len(home.select(".topic-card")) == len(build_site.ANALYSES)
    assert f"{len(build_site.ANALYSES)} analyses" in home.get_text()
    intro = home.select_one(".standfirst").get_text()
    assert "Different measures tell different stories" not in intro
    assert "The definitions matter as much as the direction" not in intro
    assert home.select_one(".explore-tools").has_attr("hidden")
    tuition = BeautifulSoup((output / "tuition/index.html").read_text(), "html.parser")
    assert tuition.find(
        "a", href=f"{build_site.REPOSITORY}/blob/master/tuition/README.md",
    )
    assert tuition.find(
        "a", href=f"{build_site.REPOSITORY}/tree/master/outputs/tuition",
    )
    assert urlsplit(tuition.select_one(".chart-gallery img")["src"]).path == (
        "../outputs/tuition/tuition_england_cap_nominal.png"
    )
    assert home.find("link", rel="canonical")["href"] == "https://www.themarginoferror.com/uk_decline/"
    assert tuition.find("link", rel="canonical")["href"] == "https://www.themarginoferror.com/uk_decline/tuition/"
    assert tuition.select_one(".chart-gallery figure img")
    assert tuition.select_one("figcaption h2").get_text() == (
        "England's maximum annual tuition fee, not inflation-adjusted"
    )
    rail = BeautifulSoup((output / "rail/index.html").read_text(), "html.parser")
    assert rail.select_one("figcaption h2").get_text() == (
        "Rail arrivals within 5 or 10 minutes: official annual averages"
    )
    assert rail.select_one(".chart-gallery img")["alt"] == rail.select_one("figcaption h2").get_text()
    assert not tuition.find("iframe")
    assert not (output / private_chart.relative_to(root)).exists()
    methods = BeautifulSoup((output / "methods/index.html").read_text(), "html.parser")
    assert methods.select_one(".page-heading") is None
    assert methods.select_one(".prose h2").get_text() == "Social, economic and political change"
    build_site.validate_site(output)


def test_borrowing_page_includes_interest_budget_share_with_same_five_peers(site_repository):
    output = build_site.build(site_repository)
    page = BeautifulSoup((output / "debt-borrowing/index.html").read_text(), "html.parser")
    chart = page.select_one("#debt_interest_budget_share img")
    assert chart is not None
    assert "Central/federal budgets" in chart["alt"]
    assert urlsplit(chart["data-chart-data"]).path == "../outputs/debt/debt_interest_budget_share.json"
    sidecar = json.loads((output / "outputs/debt/debt_interest_budget_share.json").read_text())
    assert {series["label"] for series in sidecar["series"]} == {
        "United Kingdom", "United States", "Germany", "France", "Italy",
    }
    assert len(page.select(".chart-gallery figure")) == 4


def test_polling_page_exposes_five_party_chart_and_full_source_downloads(site_repository):
    root = site_repository
    output = build_site.build(root)
    page = BeautifulSoup((output / "polling/index.html").read_text(), "html.parser")
    chart = page.select_one("#gb_voting_intention_average img")
    assert "30-day, pollster-balanced" in chart["alt"]
    data = json.loads((output / "outputs/polling/gb_voting_intention_average.json").read_text())
    assert {series["label"] for series in data["series"]} == {
        "Labour", "Conservatives", "Reform UK", "Liberal Democrats", "Greens",
    }
    for name in ("gb_voting_intention_polls.csv", "gb_voting_intention_average.csv"):
        assert page.find("a", href=f"../data/{name}") is not None
        assert (output / "data" / name).read_bytes() == (root / "data" / name).read_bytes()
    assert refresh_data.STEPS["polling"] == (("-m", "polling_data"),)


def test_polling_publication_refuses_a_missing_full_data_download(site_repository):
    subprocess.run(
        ["git", "rm", "data/gb_voting_intention_polls.csv"],
        cwd=site_repository, check=True, capture_output=True,
    )
    with pytest.raises(ValueError, match="gb_voting_intention_polls.csv"):
        build_site.build(site_repository)


def test_purchasing_power_page_includes_both_simpler_inflation_versions_and_full_download(site_repository):
    output = build_site.build(site_repository)
    page = BeautifulSoup((output / "purchasing-power/index.html").read_text(), "html.parser")
    for name, countries in {
        "consumer_price_inflation_four_country": {"United Kingdom", "United States", "Germany", "France"},
        "consumer_price_inflation_uk_us_eu": {"United Kingdom", "United States", "European Union"},
    }.items():
        chart = page.select_one(f"#{name} img")
        assert chart is not None
        assert "Consumer-price inflation" in chart["alt"]
        data = json.loads((output / f"outputs/ppp/{name}.json").read_text())
        assert {series["label"] for series in data["series"]} == countries
    assert len(page.select(".chart-gallery figure")) == 4
    assert page.select_one("#ppp_gdp_relative_to_peers") is None
    assert (output / "outputs/ppp/ppp_gdp_relative_to_peers.png").is_file()
    full = page.find("a", string="Full six-country inflation comparison (PNG)")
    assert full is not None and full.has_attr("download")
    assert urlsplit(full["href"]).path == "../outputs/ppp/consumer_price_inflation.png"
    assert ("-m", "ppp_data.inflation") in refresh_data.STEPS["purchasing-power"]
    assert len(json.loads(
        (output / "outputs/ppp/consumer_price_inflation.json").read_text()
    )["series"]) == 6


def test_tuition_page_embeds_compact_ranking_and_links_to_full_ranking(site_repository):
    output = build_site.build(site_repository)
    page = BeautifulSoup((output / "tuition/index.html").read_text(), "html.parser")
    assert page.select_one("#tuition_by_country_to_france img") is not None
    assert len(page.select(".chart-gallery figure")) == 4
    full = page.find("a", string="Full tuition ranking, mixed source years (PNG)")
    assert full is not None and full.has_attr("download")
    assert urlsplit(full["href"]).path == "../outputs/tuition/tuition_by_country.png"
    assert (output / "outputs/tuition/tuition_by_country.json").exists()


def test_income_stays_in_gdp_without_separate_category_or_supplemental_embeds(site_repository):
    output = build_site.build(site_repository)
    page = BeautifulSoup((output / "gdp-income/index.html").read_text(), "html.parser")
    assert [Path(urlsplit(image["src"]).path).name for image in page.select("main img")] == [
        "uk_gdp_relative_to_peers_simple.png", "uk_real_gdp_relative_to_peers.png",
        "median_disposable_income_oecd.png",
    ]
    history = page.find("a", string="Full income history (PNG)")
    assert history is not None and history.has_attr("download")
    assert urlsplit(history["href"]).path == (
        "../outputs/gdp_income/median_disposable_income_oecd_history.png"
    )
    assert (output / "outputs/gdp_income/median_disposable_income_oecd_history.json").exists()
    assert page.find("a", href="../recent-incomes/") is None
    home = BeautifulSoup((output / "index.html").read_text(), "html.parser")
    assert home.find("a", href="recent-incomes/") is None
    recent = BeautifulSoup((output / "recent-incomes/index.html").read_text(), "html.parser")
    target = build_site.canonical_url(Path("gdp-income/index.html"))
    assert recent.find("meta", attrs={"http-equiv": "refresh"})["content"] == f"0; url={target}"
    assert recent.find("link", rel="canonical")["href"] == target
    assert recent.find("a", href=target)
    assert not recent.select(".chart-gallery, .topic-card")
    assert "Published observations only" not in recent.get_text()
    assert "Different national median measures are not spliced into the lines" not in recent.get_text()
    observations = json.loads((output / "outputs/gdp_income/median_disposable_income_oecd.json").read_text())
    assert {series["label"] for series in observations["series"]} == {
        "United Kingdom", "United States", "Germany", "France", "Italy", "Poland",
    }
    for name, countries in {
        "median_disposable_income_oecd_four_country": {"United Kingdom", "United States", "Germany", "France"},
        "median_disposable_income_oecd_uk_us_eu": {"United Kingdom", "United States", "EU-27"},
    }.items():
        assert page.select_one(f"#{name} img") is None
        data = json.loads((output / f"outputs/gdp_income/{name}.json").read_text())
        observed = {series["label"] for series in data["series"] if "(model estimate)" not in series["label"]}
        assert observed == countries


def test_supplemental_charts_are_not_automatically_embedded(site_repository):
    chart = site_repository / "outputs/rail/rail_london_new_measure.png"
    chart.write_bytes(b"test image")
    shutil.copyfile(
        site_repository / "outputs/rail/rail_london_ppm_official.json",
        chart.with_suffix(".json"),
    )
    subprocess.run(["git", "add", str(chart), str(chart.with_suffix(".json"))], cwd=site_repository, check=True)
    output = build_site.build(site_repository)
    rail = BeautifulSoup((output / "rail/index.html").read_text(), "html.parser")
    assert not rail.find("img", src="../outputs/rail/rail_london_new_measure.png")


def test_chart_interactions_use_matching_versioned_observations(site_repository):
    output = build_site.build(site_repository)
    for analysis in build_site.ANALYSES:
        page = output / analysis.slug / "index.html"
        soup = BeautifulSoup(page.read_text(), "html.parser")
        for image in soup.select(".chart-gallery img"):
            assert image["tabindex"] == "0"
            data_url = urlsplit(image["data-chart-data"])
            image_url = urlsplit(image["src"])
            payload = json.loads((page.parent / data_url.path).read_text())
            assert payload["image_sha256"] == hashlib.sha256((page.parent / image_url.path).read_bytes()).hexdigest()
            assert image_url.query == f"v={payload['image_sha256'][:16]}"
            assert data_url.query == "v=" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def test_site_rejects_stale_observations_without_replacing_published_build(site_repository):
    output = build_site.build(site_repository)
    previous = (output / "index.html").read_bytes()
    (site_repository / "outputs/uk_decline_scorecard.png").write_bytes(b"updated image")
    with pytest.raises(ValueError, match="do not match"):
        build_site.build(site_repository)
    assert (output / "index.html").read_bytes() == previous


@pytest.mark.parametrize(("chart", "comparator"), [
    ("gdp_income/uk_gdp_relative_to_peers_simple", "EU average"),
    ("gdp_income/uk_real_gdp_relative_to_peers", "United States"),
    ("gdp_income/uk_real_gdp_relative_to_peers", "Poland"),
    ("investment/military_expenditure", "Poland"),
    ("investment/uk_infrastructure_investment", "UK general government"),
    ("nhs/cancer_62day_pct", "Northern Ireland"),
    ("stock_markets/stock_market_cap_pct_gdp", "United Kingdom"),
])
def test_missing_comparator_cannot_silently_replace_published_site(
    site_repository, chart, comparator,
):
    output = build_site.build(site_repository)
    before = (output / "index.html").read_bytes()
    path = site_repository / "outputs" / f"{chart}.json"
    data = json.loads(path.read_text())
    data["series"] = [series for series in data["series"] if series["label"] != comparator]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="missing required comparator"):
        build_site.build(site_repository)
    assert (output / "index.html").read_bytes() == before


def test_refresh_cannot_claim_success_when_a_tracked_chart_was_skipped(site_repository, monkeypatch):
    monkeypatch.setattr(refresh_data, "STEPS", {"trade": (("-m", "trade_data"),)})
    monkeypatch.setattr(refresh_data, "run", lambda *args: None)
    with pytest.raises(RuntimeError, match="not regenerated"):
        refresh_data.refresh(site_repository)
    assert not (site_repository / "data/site/refresh.json").exists()


def test_public_navigation_uses_directory_urls_and_validates_their_anchors(site_repository):
    output = build_site.build(site_repository)
    home = BeautifulSoup((output / "index.html").read_text(), "html.parser")
    assert [a["href"] for a in home.select(".topic-card > a")] == [
        f"{analysis.slug}/" for analysis in build_site.ANALYSES
    ]
    for path in output.rglob("*.html"):
        page = BeautifulSoup(path.read_text(), "html.parser")
        assert not any("index.html" in link["href"] for link in page.select('a[href]'))
    trade = output / "trade/index.html"
    page = BeautifulSoup(trade.read_text(), "html.parser")
    assert page.select_one(".breadcrumb")["href"] == "../#explore"
    assert page.select_one(".project-nav").find("a", href="../methods/")
    trade.write_text(trade.read_text().replace("../#explore", "../#missing-section"))
    with pytest.raises(ValueError, match="missing anchor"):
        build_site.validate_site(output)


def test_public_methods_omit_repository_setup_and_operations(site_repository):
    readme = site_repository / "README.md"
    content = (
        '# About the data\n\n'
        '<p><a href="#scope">Scope</a> \u00b7 <a href="#setup">Setup</a> \u00b7 '
        '<a href="https://github.com/hanshanley/uk_decline">Repository</a></p>\n\n'
        '## Scope\n\nReader-facing definitions.\n\n'
        '## Working with the charts\n\n'
        'Each analysis is a self-contained pipeline.\n\n'
        'Separate page-background versions use #F5F5F5.\n\n'
        '```bash\n./.venv/bin/python -m scripts.export_page_plots\n```\n\n'
        'Automatic source refreshes regenerate these versions too.\n\n'
        '## Setup\n\n```bash\npython3 -m venv .venv\n```\n\n'
        '### Website and automatic updates\n\nDeployment instructions.\n\n'
        '## Data integrity\n\nNo API keys are required.\n\n'
        '## Comparability\n\nRetain methodological caveats.\n'
    )
    readme.write_text(content)
    output = build_site.build(site_repository)
    page = BeautifulSoup((output / "methods/index.html").read_text(), "html.parser")
    prose = page.select_one(".prose")
    assert prose.find(id="scope")
    assert prose.find(id="comparability")
    assert "Retain methodological caveats." in prose.get_text()
    assert not prose.find(id="working-with-the-charts")
    assert not prose.find(id="setup")
    assert not prose.find(id="website-and-automatic-updates")
    assert not prose.find(id="data-integrity")
    assert not prose.find("a", href="#setup")
    assert not prose.find("pre")
    assert "Deployment instructions." not in prose.get_text()
    assert "No API keys" not in prose.get_text()
    assert "self-contained pipeline" not in prose.get_text()
    assert "page-background" not in prose.get_text()
    assert "#F5F5F5" not in prose.get_text()
    assert "Automatic source refreshes" not in prose.get_text()
    assert prose.find("p").get_text(" ", strip=True) == "Scope \u00b7 Repository"
    assert readme.read_text() == content


def test_topic_pages_only_embed_curated_charts_without_documentation_duplicates(site_repository):
    root = site_repository
    output = build_site.build(root)
    for analysis in build_site.ANALYSES:
        page = BeautifulSoup((output / analysis.slug / "index.html").read_text(), "html.parser")
        images = page.select("main img")
        assert [Path(urlsplit(image["src"]).path).name for image in images] == list(analysis.charts)
        limits = {"debt-borrowing": 4, "purchasing-power": 4, "gdp-income": 3, "tuition": 4}
        assert 1 <= len(images) <= limits.get(analysis.slug, 3)
        assert len({image["src"] for image in images}) == len(images)
        assert not page.select(".methodology, #methodology, .prose, pre")
        assert "Definitions, methods and sources" not in page.get_text()
        assert not page.find("a", href="#methodology")
        assert page.find("a", href=f"{build_site.REPOSITORY}/blob/master/{analysis.module}/README.md")


def test_site_rejects_missing_curated_charts(site_repository):
    analysis = next(item for item in build_site.ANALYSES if item.slug == "purchasing-power")
    chart = Path("outputs") / analysis.output / analysis.charts[-1]
    subprocess.run(["git", "rm", str(chart)], cwd=site_repository, check=True, capture_output=True)
    with pytest.raises(ValueError, match="missing tracked publication inputs"):
        build_site.build(site_repository)


def test_publication_shell_and_project_navigation_work_on_nested_pages(site_repository):
    output = build_site.build(site_repository)
    for path in ("index.html", "rail/index.html", "methods/index.html"):
        page = BeautifulSoup((output / path).read_text(), "html.parser")
        header = page.select_one("header.site-header")
        assert header.select_one(".wordmark")["aria-label"] == "The Margin of Error, home"
        assert header.select_one(".wordmark-main i").get_text() == "of"
        primary = header.select_one('nav[aria-label="Primary navigation"]')
        assert [a.get_text() for a in primary.select("a")] == [
            "Latest", "Archive", "Interactive analysis", "About", "Subscribe",
        ]
        assert primary.find("a", href="https://www.themarginoferror.com/interactive-analysis/")
        assert all(a["href"].startswith("https://") for a in primary.select("a"))
        project = page.select_one('main nav[aria-label="UK evidence navigation"]')
        assert project.find("a", string="UK overview")
        assert project.find("a", string="Methods")
        assert page.select_one(".site-footer .footer-links").find("a", href=build_site.REPOSITORY)
        assert page.select_one("main .publication-note time")


def test_former_pages_addresses_redirect_to_matching_publication_pages(site_repository):
    output = build_site.build(site_repository, redirects=True)
    for page in output.rglob("*.html"):
        soup = BeautifulSoup(page.read_text(), "html.parser")
        target = build_site.canonical_url(page.relative_to(output))
        assert soup.find("meta", attrs={"http-equiv": "refresh"})["content"] == f"0; url={target}"
        assert soup.find("link", rel="canonical")["href"] == target
        assert soup.find("a", href=target)
        assert f"location.replace({json.dumps(target)} + location.search + location.hash)" in soup.script.string
        assert not soup.select(".topic-card, .chart-gallery")


@pytest.mark.parametrize("redirects", [False, True])
def test_invalid_build_keeps_the_previous_site(site_repository, redirects):
    root = site_repository
    output = build_site.build(root)
    previous = (output / "index.html").read_bytes()
    (root / "README.md").write_text("# About the data\n\n[Missing section](#missing)\n")
    with pytest.raises(ValueError, match="missing anchor"):
        build_site.build(root, redirects=redirects)
    assert (output / "index.html").read_bytes() == previous


def test_site_rejects_untracked_images_and_preserves_source_notes(site_repository):
    root = site_repository
    (root / "README.md").write_text(
        "# About the data\n\n![Unpublished](outputs/tuition/untracked.png)\n"
    )
    with pytest.raises(ValueError, match="not a tracked publication asset"):
        build_site.build(root)


def test_site_separates_refresh_date_from_observation_dates(site_repository):
    root = site_repository
    status = root / "data/site/refresh.json"
    status.parent.mkdir(parents=True)
    status.write_text(json.dumps({"last_successful_refresh_utc": "2026-10-14T12:30:00+00:00"}))
    subprocess.run(["git", "add", str(status)], cwd=root, check=True)
    output = build_site.build(root)
    text = BeautifulSoup((output / "index.html").read_text(), "html.parser").get_text(" ")
    assert "Last complete automated refresh: 2026-10-14 12:30 (UTC)." in text
    assert "Publication date is not the observation date" in text


@pytest.mark.parametrize("output,returncode", [
    ("request failed", 1),
    ("[nhs_data] WARNING: SCO cancer_62day_pct: source unavailable", 0),
    ("using manual fallback", 0),
    ("[nhs_data] WARNING: NIR cancer_62day_pct: "
     "omitting 3 months without all five trusts; source failed", 0),
])
def test_refresh_rejects_errors_and_partial_source_warnings(monkeypatch, tmp_path, output, returncode):
    monkeypatch.setattr(
        refresh_data.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], returncode, stdout=output),
    )
    with pytest.raises((subprocess.CalledProcessError, RuntimeError)):
        refresh_data.run(("-m", "nhs_data", "--start", "2007"), tmp_path)


def test_refresh_retains_expected_omission_diagnostic(monkeypatch, tmp_path, capsys):
    output = (
        "[nhs_data] WARNING: NIR cancer_62day_pct: "
        "omitting 3 months without all five trusts\n"
    )
    monkeypatch.setattr(
        refresh_data.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=output),
    )
    refresh_data.run(("-m", "nhs_data"), tmp_path)
    assert output in capsys.readouterr().out
    with pytest.raises(RuntimeError):
        refresh_data.run(("-m", "trade_data"), tmp_path)


def test_library_warning_is_visible_but_not_a_partial_source_failure(monkeypatch, tmp_path, capsys):
    output = "warning: The `fitz` API is deprecated. Use `import pymupdf` instead.\n"
    monkeypatch.setattr(
        refresh_data.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=output),
    )
    refresh_data.run(("-m", "crime_data"), tmp_path)
    assert output in capsys.readouterr().out


def test_failed_refresh_does_not_advance_success_date(monkeypatch, tmp_path):
    status = tmp_path / "data/site/refresh.json"
    status.parent.mkdir(parents=True)
    status.write_text('{"last_successful_refresh_utc":"previous"}\n')
    monkeypatch.setattr(refresh_data, "STEPS", {"trade": (("-m", "trade_data"),)})

    def fail(*args):
        raise subprocess.CalledProcessError(1, "trade_data")

    monkeypatch.setattr(refresh_data, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        refresh_data.refresh(tmp_path)
    assert json.loads(status.read_text())["last_successful_refresh_utc"] == "previous"


@pytest.mark.parametrize("current_dates", [["2026-07-31"], ["2026-08-31"]])
def test_refresh_rejects_nhs_date_regression(monkeypatch, tmp_path, current_dates):
    table = tmp_path / "outputs/nhs/nhs_waiting_times.csv"
    table.parent.mkdir(parents=True)

    def write(dates):
        with table.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["nation_code", "metric", "date", "value"])
            writer.writeheader()
            writer.writerows(
                {"nation_code": "ENG", "metric": "rtt_waiting_list_total",
                 "date": date, "value": "100"} for date in dates
            )

    write(["2026-07-31", "2026-08-31"])
    monkeypatch.setattr(refresh_data, "STEPS", {"nhs": (("-m", "nhs_data"),)})
    monkeypatch.setattr(refresh_data, "run", lambda *args: write(current_dates))
    with pytest.raises(RuntimeError, match="lost published series or date coverage"):
        refresh_data.refresh(tmp_path)
    assert not (tmp_path / "data/site/refresh.json").exists()


def test_partial_refresh_does_not_claim_all_sources_checked(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(refresh_data, "run", lambda command, root: commands.append(command))
    refresh_data.refresh(tmp_path, only=["trade"])
    assert commands == [
        ("-m", "trade_data"), ("scorecard.py",), ("-m", "scripts.export_page_plots"),
    ]
    assert not (tmp_path / "data/site/refresh.json").exists()


def test_tuition_refresh_builds_common_cohort_before_summaries_and_figures(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(refresh_data, "run", lambda command, root: commands.append(command))
    refresh_data.refresh(tmp_path, only=["tuition"])
    cohort = commands.index(("-m", "tuition.common_year"))
    for module in ("tuition.cpi", "tuition.fetch_collegeboard", "tuition.build_history"):
        assert commands.index(("-m", module)) < cohort
    for command in (
        ("-m", "tuition.analyze"), ("-m", "tuition.plot_tuition"),
        ("-m", "tuition.plot_tuition", "--real"),
    ):
        assert cohort < commands.index(command)
    assert not (tmp_path / "data/site/refresh.json").exists()


def test_complete_refresh_records_success_only_after_scorecard(monkeypatch, tmp_path):
    status = tmp_path / "data/site/refresh.json"
    commands = []
    monkeypatch.setattr(refresh_data, "STEPS", {"trade": (("-m", "trade_data"),)})
    monkeypatch.setattr(refresh_data, "validate_refresh", lambda *args: None)

    def succeed(command, root):
        assert not status.exists()
        commands.append(command)

    monkeypatch.setattr(refresh_data, "run", succeed)
    refresh_data.refresh(tmp_path)
    assert commands == [
        ("-m", "trade_data"), ("scorecard.py",), ("-m", "scripts.export_page_plots"),
    ]
    saved = json.loads(status.read_text())
    assert saved["last_successful_refresh_utc"].endswith("+00:00")
    assert saved["automated_analyses"] == ["trade"]


def test_default_weekly_refresh_covers_every_public_module_and_retained_figure_owner(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(refresh_data, "nhs_coverage", lambda _: {})
    monkeypatch.setattr(refresh_data, "validate_refresh", lambda *args: None)
    monkeypatch.setattr(refresh_data, "run", lambda command, root: commands.append(command))
    refresh_data.refresh(tmp_path)
    modules = {
        command[1].partition(".")[0] for command in commands
        if command[0] == "-m"
    }
    missing = {analysis.module for analysis in build_site.ANALYSES} - modules
    assert not missing, f"Published modules missing from the weekly refresh: {sorted(missing)}"
    outputs = {analysis.output for analysis in build_site.ANALYSES}
    unowned = [
        str(chart) for chart in tracked_charts(build_site.ROOT)
        if chart.name != "uk_decline_scorecard.png"
        and (len(chart.parts) < 3 or chart.parts[1] not in outputs)
    ]
    assert not unowned, f"Retained figures without a refresh owner: {unowned}"
    assert commands[-2:] == [("scorecard.py",), ("-m", "scripts.export_page_plots")]
    saved = json.loads((tmp_path / "data/site/refresh.json").read_text())
    assert set(saved["automated_analyses"]) == set(refresh_data.STEPS)


def test_complete_refresh_runs_debt_borrowing_before_recording_success(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(refresh_data, "nhs_coverage", lambda _: {})
    monkeypatch.setattr(refresh_data, "validate_refresh", lambda *args: None)
    monkeypatch.setattr(refresh_data, "run", lambda command, root: commands.append(command))
    refresh_data.refresh(tmp_path)
    assert ("-m", "debt_data") in commands
    assert commands.index(("-m", "debt_data")) < commands.index(("scorecard.py",))
    saved = json.loads((tmp_path / "data/site/refresh.json").read_text())
    assert "debt-borrowing" in saved["automated_analyses"]


def test_unemployment_is_embedded_and_included_in_complete_refresh(
    site_repository, monkeypatch, tmp_path,
):
    output = build_site.build(site_repository)
    page = BeautifulSoup((output / "unemployment/index.html").read_text(), "html.parser")
    assert [Path(urlsplit(image["src"]).path).name for image in page.select("main img")] == [
        "uk_unemployment.png", "uk_youth_unemployment.png",
    ]
    assert "age bands and reference periods differ" in page.get_text()
    commands = []
    monkeypatch.setattr(refresh_data, "nhs_coverage", lambda _: {})
    monkeypatch.setattr(refresh_data, "validate_refresh", lambda *args: None)
    monkeypatch.setattr(refresh_data, "run", lambda command, root: commands.append(command))
    refresh_data.refresh(tmp_path)
    assert commands.index(("-m", "unemployment_data")) < commands.index(("scorecard.py",))
    saved = json.loads((tmp_path / "data/site/refresh.json").read_text())
    assert "unemployment" in saved["automated_analyses"]


def test_energy_comparisons_are_published_with_auditable_inputs_and_complete_refresh(
    site_repository, monkeypatch, tmp_path,
):
    output = build_site.build(site_repository)
    page = BeautifulSoup((output / "energy-costs/index.html").read_text(), "html.parser")
    assert [Path(urlsplit(image["src"]).path).name for image in page.select("main img")] == [
        "household_electricity_prices.png", "household_gas_prices.png", "industrial_electricity_prices.png",
    ]
    assert "US all-residential averages differ" in page.get_text()
    assert page.find("a", string="Energy prices and conversion inputs (CSV)") is not None
    assert (output / "data/household_energy_prices.csv").is_file()
    assert (output / "data/industrial_electricity_prices.csv").is_file()
    assert "separate industrial electricity chart" in page.get_text()
    commands = []
    monkeypatch.setattr(refresh_data, "nhs_coverage", lambda _: {})
    monkeypatch.setattr(refresh_data, "validate_refresh", lambda *args: None)
    monkeypatch.setattr(refresh_data, "run", lambda command, root: commands.append(command))
    refresh_data.refresh(tmp_path)
    assert commands.index(("-m", "energy_data")) < commands.index(("scorecard.py",))
    saved = json.loads((tmp_path / "data/site/refresh.json").read_text())
    assert "energy-costs" in saved["automated_analyses"]


def test_investment_research_and_military_pages_share_one_complete_refresh(
    site_repository, monkeypatch, tmp_path,
):
    output = build_site.build(site_repository)
    for slug, charts in {
        "infrastructure": ["uk_infrastructure_investment.png", "public_capital_investment.png"],
        "research-funding": ["government_research_funding.png", "total_research_spending.png"],
        "military-spending": ["military_expenditure.png"],
    }.items():
        page = BeautifulSoup((output / slug / "index.html").read_text(), "html.parser")
        assert [Path(urlsplit(image["src"]).path).name for image in page.select("main img")] == charts
    commands = []
    monkeypatch.setattr(refresh_data, "nhs_coverage", lambda _: {})
    monkeypatch.setattr(refresh_data, "validate_refresh", lambda *args: None)
    monkeypatch.setattr(refresh_data, "run", lambda command, root: commands.append(command))
    refresh_data.refresh(tmp_path)
    assert commands.count(("-m", "investment_data")) == 1
    assert commands.index(("-m", "investment_data")) < commands.index(("scorecard.py",))
    saved = json.loads((tmp_path / "data/site/refresh.json").read_text())
    assert "investment-funding" in saved["automated_analyses"]


def test_research_comparator_scope_cannot_silently_reintroduce_poland(site_repository):
    chart = site_repository / "outputs/investment/government_research_funding.json"
    payload = json.loads(chart.read_text())
    payload["series"].append({**payload["series"][0], "label": "Poland"})
    chart.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Poland is excluded"):
        build_site.build(site_repository)


def test_failed_plot_exports_do_not_advance_refresh_date(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh_data, "STEPS", {"trade": (("-m", "trade_data"),)})

    def fail_export(command, root):
        if command == ("-m", "scripts.export_page_plots"):
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(refresh_data, "run", fail_export)
    with pytest.raises(subprocess.CalledProcessError):
        refresh_data.refresh(tmp_path)
    assert not (tmp_path / "data/site/refresh.json").exists()
