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

  // The layer-stack builder (DESIGN 10). A tap on a result row would blur the search field and
  // drop the keyboard, so the row keeps the focus (the click still fires). After a layer was
  // added the server answers with HX-Trigger: pickerReset: the field is emptied here (an
  // out-of-band swap of the input would lose focus), focus goes back to it only if it had focus
  // when the request left (so nothing is forced on iOS, where a script cannot raise the keyboard),
  // and the new layer scrolls into view.
  const field = () => body.querySelector("#picker-q");
  let hadFocus = false;

  body.addEventListener("mousedown", (event) => {
    if (event.target.closest(".pick-add") && document.activeElement === field()) {
      event.preventDefault();
    }
  });

  body.addEventListener("htmx:beforeRequest", () => {
    hadFocus = document.activeElement === field();
  });

  document.body.addEventListener("pickerReset", () => {
    const input = field();
    if (input) input.value = "";
  });

  body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.xhr?.getResponseHeader("HX-Trigger") !== "pickerReset") return;
    const input = field();
    if (hadFocus && input) input.focus({ preventScroll: true });
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    body
      .querySelector(".layer.is-new")
      ?.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
  });

  // A stack that is no longer a draft (cancelled or saved in another tab) answers 404 or 409.
  body.addEventListener("htmx:responseError", (event) => {
    const status = body.querySelector("#builder-status");
    const code = event.detail.xhr?.status;
    if (!status || ![404, 409].includes(code)) return;
    status.textContent = "This swatch changed somewhere else. Close this sheet and tap the slot again.";
    status.hidden = false;
  });
}
