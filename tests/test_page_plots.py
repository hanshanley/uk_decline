from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
import pytest

from scripts import export_page_plots


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
