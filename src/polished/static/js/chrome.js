// The sticky search field turns into a material only once it is stuck under the status bar: a
// 1px sentinel just above it scrolls out of view, and the bar gets `is-stuck`.
for (const bar of document.querySelectorAll(".search-bar")) {
  const sentinel = bar.previousElementSibling;
  if (!sentinel?.classList.contains("sentinel")) continue;
  new IntersectionObserver(([entry]) => {
    bar.classList.toggle("is-stuck", !entry.isIntersecting);
  }).observe(sentinel);
}
