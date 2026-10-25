// "Copy list": copies the text of the element named by data-copy. Where the clipboard API is
// refused (a plain-http origin), the text is shown and selected so a long press can copy it.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const source = document.querySelector(button.dataset.copy);
  if (!source) return;
  const text = source.value ?? source.textContent;
  const caption = button.querySelector("span") ?? button; // the icon stays; only the words change
  const label = caption.textContent;
  try {
    await navigator.clipboard.writeText(text);
    caption.textContent = "Copied";
  } catch {
    source.hidden = false; // a hidden source is shown, so there is something to select
    source.focus();
    source.select?.();
    caption.textContent = "Select and copy";
  }
  setTimeout(() => {
    caption.textContent = label;
  }, 2000);
});
