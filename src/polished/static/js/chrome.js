// Two small pieces of chrome: the sticky search field and the system theme switch.
//
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

// The system changing between light and dark must not smear: every transition is switched off for
// the frame in which the colours change, then restored after the next one.
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  const root = document.documentElement;
  root.classList.add("theme-switching");
  getComputedStyle(root).transitionProperty; // flush the style change before transitions return
  requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("theme-switching")));
});
