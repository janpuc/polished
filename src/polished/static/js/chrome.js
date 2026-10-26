// The sticky search field turns into a material only once it is stuck under the status bar: a
// 1px sentinel just above it scrolls out of view, and the bar gets `is-stuck`. A bar that arrives
// later (the list htmx swaps into #main on a deep link to a shade) is watched too.
const watched = new WeakSet();

function watchSearchBars() {
  for (const bar of document.querySelectorAll(".search-bar")) {
    const sentinel = bar.previousElementSibling;
    if (watched.has(bar) || !sentinel?.classList.contains("sentinel")) continue;
    watched.add(bar);
    new IntersectionObserver(([entry]) => {
      bar.classList.toggle("is-stuck", !entry.isIntersecting);
    }).observe(sentinel);
  }
}

watchSearchBars();
document.addEventListener("htmx:afterSettle", watchSearchBars);

// A [data-close-details] button dismisses the <details> panel it sits in (the shade filters).
document.addEventListener("click", (event) => {
  event.target.closest("[data-close-details]")?.closest("details")?.removeAttribute("open");
});
