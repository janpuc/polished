// The shared bottom sheet (DESIGN 3, 10): a <dialog> that opens when HTMX swaps a form into
// #sheet-body and closes on the `sheetClose` event (the HX-Trigger header of a successful save).
// Tapping the backdrop, Esc or a [data-sheet-close] button closes it without saving. The form
// stays in the closed dialog until the next one is swapped over it: removing it on close would
// pull the element htmx is still answering out of the page.
const sheet = document.getElementById("sheet");
const body = document.getElementById("sheet-body");

if (sheet && body) {
  document.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target === body && body.firstElementChild && !sheet.open) {
      sheet.showModal();
    }
  });

  document.body.addEventListener("sheetClose", () => {
    if (sheet.open) sheet.close();
  });

  // The dialog has no padding, so a click whose target is the dialog itself hit the backdrop.
  sheet.addEventListener("click", (event) => {
    if (event.target === sheet || event.target.closest("[data-sheet-close]")) sheet.close();
  });
}
