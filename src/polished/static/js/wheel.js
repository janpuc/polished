// The wheel page: when a shade is highlighted (?hl=) and the address has no #slot-N of its own,
// bring the first matching tip into view.
const first = document.querySelector(".slot.is-hl");
if (first && !location.hash) {
  const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  first.scrollIntoView({ block: "center", behavior: calm ? "auto" : "smooth" });
}
