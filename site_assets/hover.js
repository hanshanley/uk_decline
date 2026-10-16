"use strict";

(() => {
  const requests = new Map();
  const selections = new WeakMap();
  const tooltip = document.createElement("div");
  tooltip.id = "chart-point-tooltip";
  tooltip.className = "chart-point-tooltip";
  tooltip.role = "tooltip";
  tooltip.hidden = true;
  const heading = document.createElement("strong");
  const period = document.createElement("span");
  const value = document.createElement("span");
  const note = document.createElement("small");
  note.textContent = "Nearest observed point";
  tooltip.append(heading, period, value, note);
  const marker = document.createElement("span");
  marker.className = "chart-point-marker";
  marker.setAttribute("aria-hidden", "true");
  marker.hidden = true;
  let activeImage = null;

  const hide = () => {
    activeImage = null;
    tooltip.hidden = true;
    marker.hidden = true;
  };

  const selectionFor = (image, data) => {
    const saved = selections.get(image);
    return saved && saved.data === data ? saved : null;
  };
  const isCurrent = (image, url) => activeImage === image && image.dataset.chartData === url;

  const dataFor = (image) => {
    const url = new URL(image.dataset.chartData, document.baseURI).href;
    if (!requests.has(url)) {
      requests.set(url, fetch(url).then((response) => {
        if (!response.ok) throw new Error(`Chart observations: HTTP ${response.status}`);
        return response.json();
      }).then((data) => {
        if (data.version !== 1 || !Array.isArray(data.series) || !data.series.length) {
          throw new Error("Invalid chart observations");
        }
        return data;
      }));
    }
    return requests.get(url);
  };

  const report = (image, error) => {
    hide();
    console.error("Unable to load chart point values", error);
    const parent = image.closest("figure, .overview") || image.parentElement;
    if (!parent.querySelector(".chart-interaction-status")) {
      const status = document.createElement("p");
      status.className = "context chart-interaction-status";
      status.role = "status";
      status.textContent = "Point values could not be loaded. The chart and PNG download remain available.";
      parent.append(status);
    }
  };

  const show = (image, data, seriesIndex, pointIndex, clientX, clientY) => {
    const series = data.series[seriesIndex];
    const point = series.points[pointIndex];
    const bounds = image.getBoundingClientRect();
    const parent = image.closest("dialog") || document.body;
    parent.append(tooltip, marker);
    heading.textContent = series.label;
    period.textContent = `${series.x_label ? `${series.x_label}: ` : ""}${point[2]}`;
    value.textContent = `${series.y_label ? `${series.y_label}: ` : ""}${point[3]}`;
    tooltip.setAttribute("aria-live", document.activeElement === image ? "polite" : "off");
    tooltip.hidden = false;
    marker.hidden = false;
    marker.style.left = `${bounds.left + point[0] * bounds.width}px`;
    marker.style.top = `${bounds.top + point[1] * bounds.height}px`;
    const size = tooltip.getBoundingClientRect();
    let left = clientX + 16;
    let top = clientY + 16;
    if (left + size.width > window.innerWidth - 8) left = clientX - size.width - 16;
    if (top + size.height > window.innerHeight - 8) top = clientY - size.height - 16;
    tooltip.style.left = `${Math.max(8, Math.min(left, window.innerWidth - size.width - 8))}px`;
    tooltip.style.top = `${Math.max(8, Math.min(top, window.innerHeight - size.height - 8))}px`;
    selections.set(image, { data, seriesIndex, pointIndex });
  };

  const inspect = async (image, clientX, clientY) => {
    const url = image.dataset.chartData;
    activeImage = image;
    try {
      const data = await dataFor(image);
      if (!isCurrent(image, url)) return;
      const bounds = image.getBoundingClientRect();
      const x = (clientX - bounds.left) / bounds.width;
      const y = (clientY - bounds.top) / bounds.height;
      let nearest = null;
      let distance = Infinity;
      let priority = Infinity;
      data.series.forEach((series, seriesIndex) => {
        const [left, top, right, bottom] = series.bounds;
        if (x < left || x > right || y < top || y > bottom) return;
        series.points.forEach((point, pointIndex) => {
          const region = point[4];
          const inside = region && x >= region[0] && x <= region[2] && y >= region[1] && y <= region[3];
          const candidate = Math.hypot((point[0] - x) * bounds.width, (point[1] - y) * bounds.height);
          const rank = candidate <= 8 && (!region || inside) ? 0 : inside ? 1 : 2;
          if (rank < priority || (rank === priority && candidate < distance)) {
            priority = rank;
            distance = candidate;
            nearest = { seriesIndex, pointIndex };
          }
        });
      });
      if (nearest) show(image, data, nearest.seriesIndex, nearest.pointIndex, clientX, clientY);
      else {
        tooltip.hidden = true;
        marker.hidden = true;
      }
    } catch (error) {
      if (isCurrent(image, url)) report(image, error);
    }
  };

  document.addEventListener("pointermove", (event) => {
    const image = event.target.closest("img[data-chart-data]");
    if (image) inspect(image, event.clientX, event.clientY);
    else if (event.pointerType !== "touch") hide();
  });
  document.addEventListener("pointerdown", (event) => {
    const image = event.target.closest("img[data-chart-data]");
    if (image) inspect(image, event.clientX, event.clientY);
    else hide();
  });
  document.addEventListener("focusin", async (event) => {
    const image = event.target.closest("img[data-chart-data]");
    if (!image) return;
    const url = image.dataset.chartData;
    activeImage = image;
    try {
      const data = await dataFor(image);
      if (!isCurrent(image, url)) return;
      const bounds = image.getBoundingClientRect();
      const { seriesIndex, pointIndex } = selectionFor(image, data) || {
        seriesIndex: 0, pointIndex: data.series[0].points.length - 1,
      };
      const point = data.series[seriesIndex].points[pointIndex];
      show(image, data, seriesIndex, pointIndex,
        bounds.left + point[0] * bounds.width, bounds.top + point[1] * bounds.height);
    } catch (error) {
      if (isCurrent(image, url)) report(image, error);
    }
  });
  document.addEventListener("keydown", async (event) => {
    if (event.key === "Escape") return hide();
    const image = event.target.closest("img[data-chart-data]");
    if (!image || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const url = image.dataset.chartData;
    activeImage = image;
    try {
      const data = await dataFor(image);
      if (!isCurrent(image, url)) return;
      let { seriesIndex, pointIndex } = selectionFor(image, data) || { seriesIndex: 0, pointIndex: 0 };
      if (event.key === "ArrowUp") seriesIndex = Math.max(0, seriesIndex - 1);
      if (event.key === "ArrowDown") seriesIndex = Math.min(data.series.length - 1, seriesIndex + 1);
      const points = data.series[seriesIndex].points;
      if (event.key === "ArrowLeft") pointIndex -= 1;
      if (event.key === "ArrowRight") pointIndex += 1;
      if (event.key === "Home") pointIndex = 0;
      if (event.key === "End") pointIndex = points.length - 1;
      pointIndex = Math.max(0, Math.min(points.length - 1, pointIndex));
      const bounds = image.getBoundingClientRect();
      activeImage = image;
      show(image, data, seriesIndex, pointIndex, bounds.left + points[pointIndex][0] * bounds.width,
        bounds.top + points[pointIndex][1] * bounds.height);
    } catch (error) {
      if (isCurrent(image, url)) report(image, error);
    }
  });
  document.addEventListener("focusout", hide);
  document.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
  document.addEventListener("pointercancel", hide);
})();
