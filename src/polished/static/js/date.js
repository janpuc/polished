// Date fields (_date_field.html): the words over the native input follow its value, and the preset
// buttons set it. Delegated from the document, so fields swapped into the sheet need no set-up.
// Days are UTC midnights, so the browser's time zone never shifts one; "today" is the input's `max`.
const part = (day, options) =>
  new Intl.DateTimeFormat("en-US", { timeZone: "UTC", ...options }).format(day);
const long = (day) => `${day.getUTCDate()} ${part(day, { month: "short" })} ${day.getUTCFullYear()}`;
const utc = (iso) => new Date(`${iso}T00:00:00Z`);

function show(field) {
  const input = field.querySelector("input");
  const clear = field.querySelector("[data-date-clear]");
  const offset = input.value ? Math.round((utc(input.max) - utc(input.value)) / 864e5) : null;
  let main = field.querySelector(".date-value").dataset.empty;
  let rest = "";
  if (input.value) {
    const day = utc(input.value);
    [main, rest] =
      offset === 0 ? ["Today", long(day)]
      : offset === 1 ? ["Yesterday", long(day)]
      : [long(day), part(day, { weekday: "long" })];
  }
  field.classList.toggle("is-empty", !input.value);
  field.querySelector(".date-main").textContent = main;
  field.querySelector(".date-rest").textContent = rest;
  for (const preset of field.querySelectorAll("[data-date-offset]")) {
    preset.setAttribute("aria-pressed", String(offset === Number(preset.dataset.dateOffset)));
  }
  clear?.setAttribute("aria-pressed", String(!input.value));
}

for (const type of ["input", "change"]) {
  document.addEventListener(type, (event) => {
    const field = event.target.closest?.("[data-date-field]");
    if (field && event.target.type === "date") show(field);
  });
}

document.addEventListener("click", (event) => {
  const preset = event.target.closest("[data-date-offset], [data-date-clear]");
  const field = preset?.closest("[data-date-field]");
  if (!field) return;
  const input = field.querySelector("input");
  const day = utc(input.max);
  day.setUTCDate(day.getUTCDate() - Number(preset.dataset.dateOffset ?? 0));
  input.value = "dateClear" in preset.dataset ? "" : day.toISOString().slice(0, 10);
  input.dispatchEvent(new Event("change", { bubbles: true }));
});
