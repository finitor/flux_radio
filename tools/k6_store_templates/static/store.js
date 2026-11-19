(() => {
  const cards = [...document.querySelectorAll("[data-card]")];
  const search = document.querySelector("#catalog-search");
  const pills = [...document.querySelectorAll("[data-filter]")];
  const empty = document.querySelector("#no-results");
  if (!cards.length || !search || !pills.length) return;

  let filter = "all";
  const update = () => {
    const query = search.value.trim().toLocaleLowerCase();
    let shown = 0;
    for (const card of cards) {
      const matchesText = card.dataset.search.includes(query);
      const matchesFilter = filter === "all" || (filter === "ready" && card.dataset.ready === "true") || (filter === "experimental" && card.dataset.status === "experimental") || (filter === "wip" && ["wip", "blocked"].includes(card.dataset.status));
      card.hidden = !(matchesText && matchesFilter);
      if (!card.hidden) shown++;
    }
    empty.hidden = shown !== 0;
  };

  search.addEventListener("input", update);
  pills.forEach((pill) => pill.addEventListener("click", () => {
    filter = pill.dataset.filter;
    pills.forEach((item) => {
      const active = item === pill;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    update();
  }));
})();
