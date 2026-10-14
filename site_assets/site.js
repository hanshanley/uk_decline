"use strict";

const search = document.querySelector("#topic-search");
if (search) {
  const cards = [...document.querySelectorAll(".topic-card")];
  const filters = [...document.querySelectorAll("[data-filter]")];
  const count = document.querySelector("#topic-count");
  let group = "all";
  const update = () => {
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    for (const card of cards) {
      card.hidden = !((group === "all" || card.dataset.group === group) &&
        card.dataset.search.includes(query));
      if (!card.hidden) visible += 1;
    }
    count.textContent = `${visible} of ${cards.length} analyses`;
    document.querySelector("#no-results").hidden = visible !== 0;
  };
  for (const filter of filters) {
    filter.addEventListener("click", () => {
      group = filter.dataset.filter;
      for (const item of filters) {
        item.setAttribute("aria-pressed", String(item === filter));
      }
      update();
    });
  }
  search.addEventListener("input", update);
  document.querySelector(".explore-tools").hidden = false;
  update();
}

const viewer = document.querySelector("#chart-viewer");
if (viewer && typeof viewer.showModal === "function") {
  for (const link of document.querySelectorAll(".chart-link")) {
    link.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const image = viewer.querySelector("img");
      image.src = link.href;
      image.alt = link.querySelector("img").alt;
      viewer.showModal();
    });
  }
  viewer.querySelector("button").addEventListener("click", () => viewer.close());
  viewer.addEventListener("click", (event) => {
    if (event.target === viewer) viewer.close();
  });
}
