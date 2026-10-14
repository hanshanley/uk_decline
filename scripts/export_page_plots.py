"""Export separate chart copies matching the article's #F5F5F5 background."""

from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageColor

from vizstyle import BG

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("outputs/page_background")
PAGE_BACKGROUND = "#F5F5F5"


def export(root: Path = ROOT) -> list[Path]:
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "outputs/*.png", "outputs/**/*.png"],
        cwd=root,
    ).decode().split("\0")
    sources = [
        Path(path) for path in tracked
        if path and not Path(path).is_relative_to(OUTPUT)
    ]
    if not sources:
        raise ValueError("No tracked plot PNGs found")
    background = (*ImageColor.getrgb(BG), 255)
    replacement = (*ImageColor.getrgb(PAGE_BACKGROUND), 255)
    exported = []
    for source in sources:
        with Image.open(root / source) as image:
            pixels = np.array(image.convert("RGBA"))
        mask = np.all(pixels == background, axis=2)
        if not mask.any():
            raise ValueError(f"{source}: expected chart background {BG} is missing")
        # Only replace opaque background pixels, not plotted colours or transparency.
        pixels[mask] = replacement
        destination = OUTPUT / source.relative_to("outputs")
        (root / destination).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(pixels).save(root / destination)
        exported.append(destination)
    print(f"[plots] exported {len(exported)} {PAGE_BACKGROUND} copies -> {OUTPUT}")
    return exported


if __name__ == "__main__":
    export()
