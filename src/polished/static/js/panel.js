// The shade panel of the wide shells (DESIGN section 3, docs/VISUAL.md section 12). From 1000px a click on
// a shade row (`a[data-panel]`) does not leave the list: the shade is fetched as `?panel=1` into the
// non-modal #panel beside it, the URL becomes /shades/{id} (pushState), and the row is marked
// aria-current. Esc, the close button and Back close it. Narrower than 1000px nothing here runs
// and the row is a plain link.
//
// A deep link (/shades/{id} typed, shared or reached from another page) arrives as the full shade
// page; on a wide viewport the list is swapped into #main and the shade into #panel, so the list
// is never missing behind it. Back is handled before htmx sees it (capture phase): the list is
// already on screen, so a history restore would only reload it.
const panel = document.getElementById("panel");
const wide = matchMedia("(min-width: 1000px)");
const SHADE_PATH = /^\/shades\/(\d+)$/;

if (panel && window.htmx) {
  let opened = false; // the panel is showing a shade
  let pushed = false; // ... and its history entry was pushed by this script, so Back closes it
  let listTitle = document.title;
  let opener = null;

  const rows = () => document.querySelectorAll("#shade-list a.row-link[data-panel]");

  function mark(link) {
    for (const row of document.querySelectorAll("a.row-link[aria-current]")) {
      row.removeAttribute("aria-current");
    }
    link?.setAttribute("aria-current", "true");
  }

  function markFor(path) {
    mark([...rows()].find((row) => new URL(row.href).pathname === path) ?? null);
  }

  async function load(path) {
    await htmx.ajax("GET", `${path}?panel=1`, { target: panel, swap: "innerHTML" });
    panel.scrollTop = 0;
  }

  function reveal() {
    document.body.classList.add("has-panel");
    panel.inert = false;
    opened = true;
  }

  // `entry` says what happens to history: "push" a new entry, "replace" the shade of an open
  // panel, or "keep" it (Forward onto an entry that is already there).
  async function open(path, link, entry = "push") {
    const wasOpen = opened;
    if (!wasOpen) listTitle = document.title;
    try {
      await load(path);
    } catch {
      location.href = path; // not a shade any more: let the server say so
      return;
    }
    if (link) mark(link);
    else markFor(path);
    if (entry === "keep") {
      pushed = true;
    } else if (wasOpen) {
      history.replaceState({ panel: path }, "", path);
    } else {
      // The list's own entry loses htmx's history flag, so Back to it is ours to handle.
      history.replaceState({ list: true }, "", location.href);
      history.pushState({ panel: path }, "", path);
      pushed = true;
    }
    if (!wasOpen) opener = link ?? document.activeElement;
    reveal();
    panel.focus({ preventScroll: true });
  }

  function hide() {
    document.body.classList.remove("has-panel");
    panel.inert = true;
    opened = false;
    pushed = false;
    document.title = listTitle;
    const current = document.querySelector("a.row-link[aria-current]");
    (opener?.isConnected ? opener : current)?.focus({ preventScroll: true });
    opener = null;
  }

  function close() {
    if (!opened) return;
    if (pushed) {
      history.back(); // popstate does the rest
    } else {
      history.replaceState(null, "", "/shades");
      hide();
    }
  }

  document.addEventListener("click", (event) => {
    if (!wide.matches || event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (event.target.closest("[data-panel-close]")) {
      close();
      return;
    }
    const link = event.target.closest("a[data-panel]");
    if (!link || link.target) return;
    event.preventDefault();
    open(new URL(link.href).pathname, link);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !opened || document.querySelector("dialog[open]")) return;
    event.preventDefault();
    close();
  });

  window.addEventListener(
    "popstate",
    (event) => {
      if (!wide.matches) return;
      const shade = SHADE_PATH.test(location.pathname);
      if (opened && !shade) {
        event.stopImmediatePropagation();
        hide();
      } else if (shade && event.state?.panel) {
        event.stopImmediatePropagation();
        open(location.pathname, null, "keep");
      }
    },
    true,
  );

  // A deep link: the full shade page on a wide viewport becomes list and panel. The list is the
  // whole /shades page fetched here (not an htmx request, which would answer with the rows alone)
  // and its #main replaces this page's.
  const deep = document.body.dataset.deepPanel;
  if (deep && wide.matches) {
    const path = `/shades/${deep}`;
    listTitle = "Shades | Polished";
    fetch("/shades", { headers: { Accept: "text/html" } })
      .then((response) => response.text())
      .then((html) => {
        const list = new DOMParser().parseFromString(html, "text/html").getElementById("main");
        const main = document.getElementById("main");
        main.className = list.className;
        main.innerHTML = list.innerHTML;
        htmx.process(main);
        return load(path);
      })
      .then(() => {
        history.replaceState({ panel: path }, "", path);
        markFor(path);
        reveal();
        document.querySelector("#shade-list a[aria-current]")?.scrollIntoView({ block: "center" });
      });
  }
}
