// "Copy the list": copies the text of the element named by data-copy. Where the clipboard API is
// refused (a plain-http origin), the text is selected so a long press can copy it.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const source = document.querySelector(button.dataset.copy);
  if (!source) return;
  const text = source.value ?? source.textContent;
  const label = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  } catch {
    source.focus();
    source.select?.();
    button.textContent = "Select and copy";
  }
  setTimeout(() => {
    button.textContent = label;
  }, 2000);
});
