from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import subprocess

from bs4 import BeautifulSoup
import pytest

from scripts import build_site, refresh_data


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
        for filename in analysis.charts:
            chart = root / "outputs" / analysis.output / filename
            chart.parent.mkdir(parents=True, exist_ok=True)
            chart.write_bytes(b"test image")
    (root / "outputs/uk_decline_scorecard.png").write_bytes(b"overview")
    (root / "README.md").write_text(
        "# About the data\n\n## Scope\n\n[Tuition](tuition/README.md#sources)\n"
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
    assert home.select_one(".explore-tools").has_attr("hidden")
    tuition = BeautifulSoup((output / "tuition/index.html").read_text(), "html.parser")
    assert tuition.find(
        "a", href=f"{build_site.REPOSITORY}/blob/master/tuition/README.md",
    )
    assert tuition.find(
        "a", href=f"{build_site.REPOSITORY}/tree/master/outputs/tuition",
    )
    assert tuition.find("img", src="../outputs/tuition/tuition_england_cap_nominal.png")
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
    build_site.validate_site(output)


def test_supplemental_charts_are_not_automatically_embedded(site_repository):
    chart = site_repository / "outputs/rail/rail_london_new_measure.png"
    chart.write_bytes(b"test image")
    subprocess.run(["git", "add", str(chart)], cwd=site_repository, check=True)
    output = build_site.build(site_repository)
    rail = BeautifulSoup((output / "rail/index.html").read_text(), "html.parser")
    assert not rail.find("img", src="../outputs/rail/rail_london_new_measure.png")


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
        assert [Path(image["src"]).name for image in images] == list(analysis.charts)
        assert 1 <= len(images) <= 3
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


def test_invalid_build_keeps_the_previous_site(site_repository):
    root = site_repository
    output = build_site.build(root)
    previous = (output / "index.html").read_bytes()
    (root / "README.md").write_text("# About the data\n\n[Missing section](#missing)\n")
    with pytest.raises(ValueError, match="missing anchor"):
        build_site.build(root)
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


def test_complete_refresh_records_success_only_after_scorecard(monkeypatch, tmp_path):
    status = tmp_path / "data/site/refresh.json"
    commands = []
    monkeypatch.setattr(refresh_data, "STEPS", {"trade": (("-m", "trade_data"),)})

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


def test_failed_plot_exports_do_not_advance_refresh_date(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh_data, "STEPS", {"trade": (("-m", "trade_data"),)})

    def fail_export(command, root):
        if command == ("-m", "scripts.export_page_plots"):
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(refresh_data, "run", fail_export)
    with pytest.raises(subprocess.CalledProcessError):
        refresh_data.refresh(tmp_path)
    assert not (tmp_path / "data/site/refresh.json").exists()
