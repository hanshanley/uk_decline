from pathlib import Path
import json
import re
import subprocess

import numpy as np
from PIL import Image
import pytest

from scripts import export_page_plots
from vizstyle import country_color


def test_page_exports_preserve_originals_foreground_and_transparency(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "outputs/example/chart.png"
    source.parent.mkdir(parents=True)
    pixels = np.array([
        [(247, 245, 240, 255), (200, 90, 61, 255)],
        [(247, 245, 240, 0), (247, 245, 240, 128)],
    ], dtype=np.uint8)
    Image.fromarray(pixels).save(source)
    original = source.read_bytes()
    subprocess.run(["git", "add", "outputs"], cwd=tmp_path, check=True)

    expected = [Path("outputs/page_background/example/chart.png")]
    assert export_page_plots.export(tmp_path) == expected
    with Image.open(tmp_path / expected[0]) as image:
        exported = np.array(image)
    assert tuple(exported[0, 0]) == (245, 245, 245, 255)
    np.testing.assert_array_equal(exported[0, 1], pixels[0, 1])
    np.testing.assert_array_equal(exported[1], pixels[1])
    assert source.read_bytes() == original

    subprocess.run(["git", "add", "outputs"], cwd=tmp_path, check=True)
    assert export_page_plots.export(tmp_path) == expected
    assert not (tmp_path / "outputs/page_background/page_background").exists()


def test_page_exports_reject_unexpected_source_background(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "outputs/chart.png"
    source.parent.mkdir()
    Image.new("RGB", (2, 2), "white").save(source)
    subprocess.run(["git", "add", "outputs"], cwd=tmp_path, check=True)
    with pytest.raises(ValueError, match="expected chart background"):
        export_page_plots.export(tmp_path)


def test_published_country_series_use_consistent_identity_colors():
    root = Path(__file__).resolve().parents[1]
    paths = subprocess.check_output(["git", "ls-files", "outputs"], cwd=root, text=True).splitlines()
    identities = {
        r"United Kingdom|UK(?= \(| —| market sector| general government)|England(?=$|,| fee cap| undergraduate tuition cap)|London GDP|London's share": "UK",
        r"United States|US(?= \(| —| public)|US dollar": "US",
        r"EU average|EU-27|European Union|Europe \(median\)|EU(?= \(| /)|Euro$": "EU",
        r"Germany": "Germany", r"France": "France", r"Italy": "Italy",
        r"Poland": "Poland", r"Japan|Japanese yen": "Japan", r"China": "China",
        r"Swiss franc": "Switzerland", r"Scotland": "Scotland",
        r"Northern Ireland": "Northern Ireland",
    }
    inspected = set()
    for name in paths:
        if not name.endswith(".json"):
            continue
        sidecar = root / name
        image = sidecar.with_suffix(".png")
        if not image.exists():
            continue
        data = json.loads(sidecar.read_text())
        with Image.open(image) as rendered:
            pixels = np.asarray(rendered.convert("RGB"))
        height, width = pixels.shape[:2]
        for series in data["series"]:
            country = next((country for pattern, country in identities.items()
                            if re.match(f"(?:{pattern})", series["label"])), None)
            if country is None:
                continue
            color = country_color(country).lstrip("#")
            expected = np.array([int(color[i:i+2], 16) for i in (0, 2, 4)])
            visible = False
            for point in series["points"]:
                x, y = round(point[0] * width), round(point[1] * height)
                neighborhood = pixels[max(0, y-12):min(height, y+13), max(0, x-12):min(width, x+13)]
                if np.any(np.all(neighborhood == expected, axis=2)):
                    visible = True
                    break
            assert visible, f"{name}: {series['label']} does not use {country_color(country)}"
            inspected.add(country)
    assert {"UK", "US", "EU", "Germany", "France", "Italy", "Poland"} <= inspected
