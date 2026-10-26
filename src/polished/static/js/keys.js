// Keyboard for a Mac or an iPad with a keyboard (docs/VISUAL.md section 12). `/` goes to the search
// field (from a page without one, to Shades with the field focused), `n` opens Add bottle while a
// shade is shown, the arrows move the cursor (aria-current) over the result rows, and Enter opens
// the row under it from the search field. Esc closes the panel; panel.js owns that, and a sheet's
// own Esc closes the sheet first. The hint line at the foot of the Shades list appears after the
// first :focus-visible, which is the first sign of a keyboard.
const wide = matchMedia("(min-width: 1000px)");

// A field that takes letters. A search field is not one for the arrows and Enter, which move and
// open the result rows from it, but it is for `/` and `n`.
const FIELD =
  "input:not([type=checkbox], [type=radio], [type=button], [type=submit]), textarea, select, [contenteditable]";
const typing = (el) => el?.closest(FIELD);
const searching = (el) => el?.type === "search";

const RESULT_ROWS = "#shade-list a.row-link[data-panel], #search-results a.row-link[data-panel]";
const ROW_AT_CURSOR =
  "#shade-list a.row-link[data-panel][aria-current], #search-results a.row-link[data-panel][aria-current]";

function moveCursor(step) {
  const rows = [...document.querySelectorAll(RESULT_ROWS)];
  if (!rows.length) return false;
  const at = rows.findIndex((row) => row.hasAttribute("aria-current"));
  const from = at < 0 ? (step > 0 ? -1 : rows.length) : at;
  const next = rows[Math.min(rows.length - 1, Math.max(0, from + step))];
  for (const row of rows) row.removeAttribute("aria-current");
  next.setAttribute("aria-current", "true");
  next.scrollIntoView({ block: "nearest" });
  if (rows.includes(document.activeElement)) next.focus({ preventScroll: true });
  return true;
}

document.addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey || event.defaultPrevented) return;
  if (document.querySelector("dialog[open]")) return;
  const target = event.target;
  const idle = !typing(target);

  if (event.key === "/" && idle) {
    event.preventDefault();
    const field = document.getElementById("q");
    if (field) {
      field.focus();
      field.select();
    } else {
      location.assign("/shades#search");
    }
  } else if (event.key === "n" && idle) {
    const add = document.querySelector("#shade-actions .action-primary");
    if (add && !add.closest("[inert]")) {
      event.preventDefault();
      add.click();
    }
  } else if ((event.key === "ArrowDown" || event.key === "ArrowUp") && (idle || searching(target))) {
    if (moveCursor(event.key === "ArrowDown" ? 1 : -1)) event.preventDefault();
  } else if (event.key === "Enter" && wide.matches && (searching(target) || target === document.body)) {
    const row = document.querySelector(ROW_AT_CURSOR);
    if (row) {
      event.preventDefault();
      row.click();
    }
  }
});

if (location.hash === "#search") {
  document.getElementById("q")?.focus();
  history.replaceState(history.state, "", location.pathname + location.search);
}

document.addEventListener(
  "focusin",
  (event) => {
    if (event.target.matches?.(":focus-visible")) document.body.classList.add("keys-seen");
  },
  true,
);
