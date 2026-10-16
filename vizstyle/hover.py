"""Save readable figures and export their actual plotted observations and positions."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from matplotlib import rcParams
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.category import StrCategoryFormatter
from matplotlib.collections import PathCollection, PolyCollection
from matplotlib.colors import to_rgba
from matplotlib.container import BarContainer
from matplotlib.transforms import ScaledTranslation
import numpy as np


def _separate_titles(fig, *, dpi: float) -> None:
    """Ensure a modest visible heading gap without changing axes or plotted data."""
    original_dpi, original_canvas = fig.dpi, fig.canvas
    try:
        fig.set_dpi(dpi)
        canvas = FigureCanvasAgg(fig)
        titles = [
            title for ax in fig.axes for title in (ax.title, ax._left_title, ax._right_title)
            if title.get_visible() and title.get_text()
        ]
        titles += [
            text for text in fig.texts
            if text.get_visible() and text.get_text()
            and (text is fig._suptitle or (
                text.get_fontweight() in ("bold", "heavy", 700, 800, 900)
                and text.get_fontsize() >= 14
            ))
        ]
        for title in titles:
            if "\n" in title.get_text():
                spacing = title._linespacing
                title.set_linespacing(max(1.3, 1.2 if spacing == "normal" else spacing))
        canvas.draw()
        texts = [*fig.texts, *(text for ax in fig.axes for text in ax.texts), *titles]
        renderer = canvas.get_renderer()
        for title in sorted(titles, key=lambda text: text.get_window_extent(renderer).y0):
            bounds = title.get_window_extent(renderer)
            shift = 0
            for text in texts:
                if (
                    text is title or not text.get_visible() or not text.get_text()
                    or text.get_fontsize() > title.get_fontsize() or text.get_rotation() != 0
                ):
                    continue
                other = text.get_window_extent(renderer)
                if (
                    other.x0 < bounds.x1 and other.x1 > bounds.x0
                    and (other.y0 + other.y1) < (bounds.y0 + bounds.y1)
                    and other.height <= bounds.height * 1.5
                ):
                    shift = max(shift, other.y1 + 5 * dpi / 72 - bounds.y0)
            if shift > .25:
                title.set_transform(
                    title.get_transform() + ScaledTranslation(0, shift / dpi, fig.dpi_scale_trans)
                )
                canvas.draw()
    finally:
        fig.set_dpi(original_dpi)
        fig.set_canvas(original_canvas)


def _number(value: float) -> str:
    return f"{value:,.6f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"


def _coordinate(axis, value: float, *, categorical=False) -> str:
    if isinstance(axis.get_major_locator(), mdates.DateLocator) or isinstance(
        axis.get_major_formatter(),
        (mdates.DateFormatter, mdates.AutoDateFormatter, mdates.ConciseDateFormatter),
    ):
        return mdates.num2date(value).strftime("%Y-%m-%d")
    ticks = list(zip(axis.get_ticklocs(), axis.get_ticklabels()))
    for position, label in ticks:
        if math.isclose(position, value, abs_tol=1e-8) and label.get_text():
            return label.get_text()
    if categorical and ticks and isinstance(axis.get_major_locator(), ticker.FixedLocator) and not 1900 <= value <= 2200:
        return min(ticks, key=lambda tick: abs(tick[0] - value))[1].get_text()
    if 1900 <= value <= 2200 and value % 1 == 0:
        for position, label in ticks:
            match = re.fullmatch(r"(\d{4})[/\u2013-](\d{2})", label.get_text())
            if match and int(match[1]) - position in (-1, 0):
                year = int(value + int(match[1]) - position)
                return f"{year}/{(year + 1) % 100:02d}"
        return str(int(value))
    formatter = axis.get_major_formatter()
    if isinstance(formatter, StrCategoryFormatter):
        return formatter(value)
    return _number(value)


def _value(axis, value: float) -> str:
    formatter = axis.get_major_formatter()
    if isinstance(formatter, ticker.PercentFormatter):
        return _number(100 * value / formatter.xmax) + "%"
    if isinstance(formatter, ticker.FuncFormatter):
        # Mirrored population pyramids plot male shares to the left of zero.
        if value < 0 and formatter(value) == formatter(-value):
            value = abs(value)
        percent = formatter(1)
        if percent.endswith("%") and percent[:-1].strip() in {"1", "1.0", "100", "100.0"}:
            return _number(value * float(percent[:-1])) + "%"
        units = re.fullmatch(r"([^\d+\-.]*)(\d[\d.,]*)([^\d]*)", percent)
        if units and float(units[2].replace(",", "")) == 1 and (units[1] or units[3]):
            prefix, _, suffix = units.groups()
            if not prefix and suffix == "k":
                return _number(value * 1000)
            return prefix + _number(value) + suffix
    return _number(value) + ("%" if "%" in axis.get_label_text() else "")


def _color(artist):
    if hasattr(artist, "get_color"):
        return to_rgba(artist.get_color())[:3]
    if hasattr(artist, "get_facecolor"):
        color = np.asarray(artist.get_facecolor())
        if color.size:
            return tuple(color.reshape(-1, 4)[0, :3])
    return None


def _label(ax, artist) -> str:
    label = artist.get_label()
    if label and not label.startswith("_"):
        return label
    handles, labels = ax.get_legend_handles_labels()
    color = _color(artist)
    matches = [
        label for handle, label in zip(handles, labels)
        if color is not None and _color(handle) == color
    ]
    if len(set(matches)) == 1:
        return matches[0]
    return ax.get_title(loc="left") or ax.get_title() or ax.get_ylabel() or "Value"


def observations(fig, *, dpi: float, bbox_inches="tight", pad_inches=.1) -> list[dict]:
    """Use the same raster geometry as savefig, including its tight crop and padding."""
    original_dpi, original_canvas = fig.dpi, fig.canvas
    try:
        fig.set_dpi(dpi)
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        if bbox_inches == "tight":
            crop = fig.get_tightbbox(renderer).padded(pad_inches)
        else:
            crop = bbox_inches if bbox_inches is not None else fig.bbox_inches
        left, bottom, width, height = (value * dpi for value in crop.bounds)

        def position(x, y):
            return [round((x - left) / width, 7), round(1 - (y - bottom) / height, 7)]

        series = []
        for ax in fig.axes:
            if not ax.get_visible():
                continue
            def entry(artist, *, horizontal=False):
                x0, y1 = position(ax.bbox.x0, ax.bbox.y0)
                x1, y0 = position(ax.bbox.x1, ax.bbox.y1)
                return {
                    "label": _label(ax, artist),
                    "x_label": ax.get_ylabel() if horizontal else ax.get_xlabel(),
                    "y_label": ax.get_xlabel() if horizontal else ax.get_ylabel(),
                    "bounds": [x0, y0, x1, y1],
                    "points": [],
                }

            def point(target, xy, x, y, *, horizontal=False, bounds=None):
                if not np.isfinite([*xy, x, y]).all() or not ax.bbox.contains(*xy):
                    return
                px, py = position(*xy)
                if not 0 <= px <= 1 or not 0 <= py <= 1:
                    return
                labels = (
                    (_coordinate(ax.yaxis, y, categorical=bounds is not None), _value(ax.xaxis, x))
                    if horizontal else (_coordinate(ax.xaxis, x, categorical=bounds is not None), _value(ax.yaxis, y))
                )
                item = [px, py, *labels]
                if bounds is not None:
                    x0, y1 = position(bounds.x0, bounds.y0)
                    x1, y0 = position(bounds.x1, bounds.y1)
                    item.append([max(0, x0), max(0, y0), min(1, x1), min(1, y1)])
                target["points"].append(item)

            for line in ax.lines:
                if not line.get_visible() or line.get_alpha() == 0 or line.get_transform() != ax.transData:
                    continue
                data = line.get_xydata()
                horizontal = any(
                    isinstance(container, BarContainer) and container.orientation == "horizontal"
                    for container in ax.containers
                )
                target = entry(line, horizontal=horizontal)
                for (x, y), xy in zip(data, line.get_transform().transform(data)):
                    point(target, xy, x, y, horizontal=horizontal)
                if target["points"]:
                    series.append(target)
            for container in ax.containers:
                if not isinstance(container, BarContainer):
                    continue
                horizontal = container.orientation == "horizontal"
                target = entry(container, horizontal=horizontal)
                for bar in container.patches:
                    if not bar.get_visible() or bar.get_alpha() == 0:
                        continue
                    bounds = bar.get_window_extent(renderer)
                    xy = ((bounds.x0 + bounds.x1) / 2, (bounds.y0 + bounds.y1) / 2)
                    x = bar.get_width() if horizontal else bar.get_x() + bar.get_width() / 2
                    y = bar.get_y() + bar.get_height() / 2 if horizontal else bar.get_height()
                    point(target, xy, x, y, horizontal=horizontal, bounds=bounds)
                if target["points"]:
                    series.append(target)
            for collection in ax.collections:
                if not collection.get_visible() or collection.get_alpha() == 0:
                    continue
                if isinstance(collection, PolyCollection) and not ax.lines and not ax.containers:
                    target = entry(collection)
                    for path in collection.get_paths():
                        data = path.vertices
                        for x in np.unique(data[:, 0]):
                            values = data[data[:, 0] == x, 1]
                            low, high = values.min(), values.max()
                            xy = collection.get_transform().transform([x, (low + high) / 2])
                            point(target, xy, x, high - low)
                    if target["points"]:
                        series.append(target)
                    continue
                if not isinstance(collection, PathCollection):
                    continue
                data = np.ma.filled(collection.get_offsets(), np.nan)
                target = entry(collection)
                for (x, y), xy in zip(data, collection.get_offset_transform().transform(data)):
                    point(target, xy, x, y)
                if target["points"]:
                    series.append(target)
        return series
    finally:
        fig.set_dpi(original_dpi)
        fig.set_canvas(original_canvas)


def save_chart(fig, out_path, **kwargs) -> None:
    """Save a PNG and a hash-bound hover sidecar from the very same figure."""
    path = Path(out_path)
    dpi = kwargs.get("dpi") or rcParams["savefig.dpi"]
    dpi = fig.dpi if dpi == "figure" else dpi
    _separate_titles(fig, dpi=dpi)
    fig.savefig(path, **kwargs)
    series = observations(
        fig, dpi=dpi,
        bbox_inches=kwargs.get("bbox_inches") or rcParams["savefig.bbox"],
        pad_inches=kwargs.get("pad_inches") if kwargs.get("pad_inches") is not None else rcParams["savefig.pad_inches"],
    )
    if not series:
        raise ValueError(f"{path}: chart contains no supported observations for hover values")
    payload = {
        "version": 1,
        "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "series": series,
    }
    path.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
