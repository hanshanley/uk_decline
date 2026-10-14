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
        chart = root / "outputs" / analysis.output / analysis.featured
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
    assert home.select_one(".explore-tools").has_attr("hidden")
    tuition = BeautifulSoup((output / "tuition/index.html").read_text(), "html.parser")
    assert tuition.find("a", href="../methods/index.html#scope")
    assert tuition.find("a", href="#sources")
    assert tuition.find("img", src="../outputs/tuition/tuition_england_cap_nominal.png")
    assert not (output / private_chart.relative_to(root)).exists()
    build_site.validate_site(output)


def test_invalid_build_keeps_the_previous_site(site_repository):
    root = site_repository
    output = build_site.build(root)
    previous = (output / "index.html").read_bytes()
    (root / "tuition/README.md").write_text("# Tuition\n\n[Missing section](#missing)\n")
    with pytest.raises(ValueError, match="missing anchor"):
        build_site.build(root)
    assert (output / "index.html").read_bytes() == previous


def test_site_rejects_untracked_images_and_preserves_source_notes(site_repository):
    root = site_repository
    (root / "tuition/README.md").write_text(
        "# Tuition\n\n![Unpublished](../outputs/tuition/untracked.png)\n"
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
])
def test_refresh_rejects_errors_and_partial_source_warnings(monkeypatch, tmp_path, output, returncode):
    monkeypatch.setattr(
        refresh_data.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], returncode, stdout=output),
    )
    with pytest.raises((subprocess.CalledProcessError, RuntimeError)):
        refresh_data.run(("-m", "nhs_data"), tmp_path)


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


def test_refresh_rejects_nhs_date_regression(monkeypatch, tmp_path):
    table = tmp_path / "outputs/nhs/nhs_waiting_times.csv"
    table.parent.mkdir(parents=True)

    def write(date):
        with table.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["nation_code", "metric", "date", "value"])
            writer.writeheader()
            writer.writerow({"nation_code": "ENG", "metric": "rtt_waiting_list_total",
                             "date": date, "value": "100"})

    write("2026-08-31")
    monkeypatch.setattr(refresh_data, "STEPS", {"nhs": (("-m", "nhs_data"),)})
    monkeypatch.setattr(refresh_data, "run", lambda *args: write("2026-07-31"))
    with pytest.raises(RuntimeError, match="lost published series or date coverage"):
        refresh_data.refresh(tmp_path)
    assert not (tmp_path / "data/site/refresh.json").exists()


def test_partial_refresh_does_not_claim_all_sources_checked(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(refresh_data, "run", lambda command, root: commands.append(command))
    refresh_data.refresh(tmp_path, only=["trade"])
    assert commands == [("-m", "trade_data"), ("scorecard.py",)]
    assert not (tmp_path / "data/site/refresh.json").exists()
