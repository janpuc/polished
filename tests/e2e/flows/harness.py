"""What every flow runs inside: device profiles, the step recorder with its screenshots, and the
page audits (console, network, overflow, tap targets) that run after each step.

A flow is a function of one `Trace`. It does its work in named steps:

    with t.step("type a query"):
        t.page.get_by_role("searchbox").fill("magnetic taco")
        expect(...).to_be_visible()

The step ends with a screenshot and the audits whether it passed or not; a step that raised, or
whose audits found a problem, fails the flow and the flow stops there (the screenshot shows where).
"""

import base64
import re
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Page, expect

STEP_TIMEOUT_MS = 8000
TAP_TARGET_PX = 44
SETTLE_MS = 250  # lets a sheet slide in and a fade finish before the screenshot


@dataclass(frozen=True)
class Device:
    key: str
    label: str
    profile: str | None  # a Playwright device descriptor, None for a plain desktop
    touch: bool


DEVICES = {
    "iphone": Device("iphone", "iPhone 15", "iPhone 15", True),
    "ipad": Device("ipad", "iPad Pro 11", "iPad Pro 11", True),
    "mac": Device("mac", "Mac 1440×900", None, False),
}
SCHEMES = ("light", "dark")


def context_options(playwright, device: Device, scheme: str) -> dict:
    """The new_context() options of a device profile."""
    if device.profile:
        options = dict(playwright.devices[device.profile])
    else:
        options = {"viewport": {"width": 1440, "height": 900}, "has_touch": False}
    options.update(color_scheme=scheme, locale="en-US")
    return options


class StepFailed(Exception):
    """Raised by Trace.step() after a step failed, to stop the flow."""


@dataclass
class Step:
    number: int
    name: str
    passed: bool = True
    error: str | None = None
    notes: list[str] = field(default_factory=list)  # audits that found something but did not fail
    screenshot: str = ""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "step"


def first_line(exc: BaseException) -> str:
    """What went wrong, short: Playwright's message without its call log."""
    text = str(exc).split("\nCall log:")[0].strip() or type(exc).__name__
    return " ".join(text.split("\n")[:6])[:700]


_AUDIT_JS = """
([touch, minimum]) => {
  const root = document.documentElement;
  const out = {overflow: [], taps: []};
  const describe = (el) => {
    const name = (el.getAttribute('aria-label') || el.innerText || el.value || el.id || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
    const cls = typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/)[0] : '';
    return `${el.tagName.toLowerCase()}${cls}${name ? ' "' + name + '"' : ''}`;
  };
  const clipped = (el) => {
    for (let p = el.parentElement; p && p !== document.body && p !== root; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return true;
    }
    return false;
  };
  const shown = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && el.checkVisibility({visibilityProperty: true, opacityProperty: false});
  };
  if (root.scrollWidth > root.clientWidth + 1) {
    for (const el of document.body.querySelectorAll('*')) {
      if (!shown(el) || clipped(el)) continue;
      if (getComputedStyle(el).position === 'fixed') continue;
      const r = el.getBoundingClientRect();
      if (r.right > root.clientWidth + 1 || r.left < -1) out.overflow.push(`${describe(el)} spans ${Math.round(r.left)}..${Math.round(r.right)}`);
      if (out.overflow.length >= 3) break;
    }
    if (!out.overflow.length) out.overflow.push(`page is ${root.scrollWidth}px wide in a ${root.clientWidth}px viewport`);
  }
  if (touch) {
    const scope = document.querySelector('dialog.sheet[open]') || document;
    const sel = 'a[href], button, summary, select, textarea, [role=button], label.pick, input:not([type=hidden]):not([type=radio]):not([type=checkbox])';
    const seen = new Set();
    for (const el of scope.querySelectorAll(sel)) {
      if (el.closest('.skip-link, .visually-hidden') || !shown(el)) continue;
      if (el.tagName === 'A' && el.parentElement && el.parentElement.tagName === 'P') continue;  // an inline link in a sentence
      const r = el.getBoundingClientRect();
      if (r.width >= minimum - 0.5 && r.height >= minimum - 0.5) continue;
      // A stretched link or a padded hit area: measure what a finger on it would actually reach.
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      const match = 'a[href], button, summary, select, textarea, [role=button], label, input';
      for (let x = r.left - 60; x <= r.right + 60; x += 4) {
        for (let y = r.top - 60; y <= r.bottom + 60; y += 4) {
          if (x < 0 || y < 0 || x >= root.clientWidth || y >= innerHeight) continue;
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || el.contains(hit) || (hit.closest(match) === el))) {
            minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
          }
        }
      }
      const w = Math.max(r.width, maxX - minX + 4), h = Math.max(r.height, maxY - minY + 4);
      if (w >= minimum - 0.5 && h >= minimum - 0.5) continue;
      const text = `${describe(el)} is ${Math.round(w)}×${Math.round(h)}`;
      if (!seen.has(text)) { seen.add(text); out.taps.push(text); }
    }
  }
  return out;
}
"""


class Trace:
    """One flow on one device in one colour scheme: the page, the steps so far, and the problems
    the browser reported."""

    def __init__(self, page: Page, base: str, device: Device, scheme: str, out_dir: Path):
        self.page = page
        self.base = base.rstrip("/")
        self.device = device
        self.scheme = scheme
        self.out_dir = out_dir
        self.steps: list[Step] = []
        self.uid = format(
            int(time.time() * 1000) % 36**5, "x"
        )  # keeps names unique on a shared server
        self._problems: list[str] = []
        self._allowed_status: set[int] = set()
        self.tap_failures = True
        self._cdp = None
        out_dir.mkdir(parents=True, exist_ok=True)
        page.set_default_timeout(STEP_TIMEOUT_MS)
        expect.set_options(timeout=STEP_TIMEOUT_MS)
        page.on("console", self._console)
        page.on("pageerror", lambda e: self._problems.append(f"page error: {e}"))
        page.on("requestfailed", self._request_failed)
        page.on("response", self._response)

    # What the browser reports

    def _console(self, message) -> None:
        if message.type in ("error", "warning"):
            if any(f"status of {code}" in message.text for code in self._allowed_status):
                return  # the browser's own note that a page it was sent to answered 404
            where = message.location.get("url", "")
            self._problems.append(f"console {message.type}: {message.text[:300]} ({where})")

    def _request_failed(self, request) -> None:
        failure = request.failure or ""
        if (
            "ERR_ABORTED" in failure
        ):  # a request the page itself cancelled (htmx hx-sync, navigation)
            return
        self._problems.append(f"request failed: {request.method} {request.url} ({failure})")

    def _response(self, response) -> None:
        if response.status >= 400 and response.status not in self._allowed_status:
            self._problems.append(
                f"HTTP {response.status}: {response.request.method} {response.url}"
            )

    @contextmanager
    def allow_status(self, *codes: int) -> Iterator[None]:
        """HTTP error statuses this part of the flow provokes on purpose (a 404 page)."""
        self._allowed_status.update(codes)
        try:
            yield
        finally:
            self._allowed_status.difference_update(codes)

    # Helpers flows share

    def url(self, path: str) -> str:
        return f"{self.base}{path}"

    def goto(self, path: str) -> None:
        self.page.goto(self.url(path))

    def open_sheet(self):
        """The sheet once it is open (a modal dialog); flows then work inside it."""
        sheet = self.page.locator("dialog#sheet[open]")
        expect(sheet).to_be_visible()
        return sheet

    def close_sheet_check(self) -> None:
        expect(self.page.locator("dialog#sheet[open]")).to_have_count(0)

    # Steps

    @contextmanager
    def step(self, name: str, full_page: bool = False) -> Iterator[None]:
        step = Step(len(self.steps) + 1, name)
        self.steps.append(step)
        mark = len(self._problems)
        try:
            yield
        except Exception as exc:
            step.passed = False
            step.error = first_line(exc)
            if not isinstance(exc, AssertionError) and "Timeout" not in type(exc).__name__:
                step.error += "\n" + "".join(traceback.format_tb(exc.__traceback__)[-2:])[:400]
        self._finish(step, mark, full_page)
        if not step.passed:
            raise StepFailed(step.error)

    def _capture(self, full_page: bool) -> bytes:
        """A PNG of the page through the DevTools protocol. Page.screenshot() leaves empty style
        attributes on inputs, and htmx copying them back during a swap is then a CSP violation
        the app never has for a real user."""
        if self._cdp is None:
            self._cdp = self.page.context.new_cdp_session(self.page)
        params: dict = {"format": "png"}
        if full_page:
            size = self._cdp.send("Page.getLayoutMetrics")["cssContentSize"]
            params.update(
                captureBeyondViewport=True,
                clip={"x": 0, "y": 0, "width": size["width"], "height": size["height"], "scale": 1},
            )
        return base64.b64decode(self._cdp.send("Page.captureScreenshot", params)["data"])

    def _finish(self, step: Step, mark: int, full_page: bool) -> None:
        page = self.page
        try:
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(SETTLE_MS)
        except Exception:  # noqa: S110 - the audit below reports a page that is gone
            pass
        failures: list[str] = []
        try:
            audit = page.evaluate(_AUDIT_JS, [self.device.touch, TAP_TARGET_PX])
            failures += [f"horizontal overflow: {line}" for line in audit["overflow"]]
            taps = [f"tap target under {TAP_TARGET_PX}pt: {line}" for line in audit["taps"]]
            if self.tap_failures:
                failures += taps
            else:
                step.notes += taps
        except Exception as exc:
            failures.append(f"audit failed: {first_line(exc)}")
        failures += self._problems[mark:]
        name = f"{step.number:02d}-{slug(step.name)}.png"
        try:
            (self.out_dir / name).write_bytes(self._capture(full_page))
            step.screenshot = name
        except Exception as exc:
            failures.append(f"screenshot failed: {first_line(exc)}")
        if failures and step.passed:
            step.passed = False
            step.error = "\n".join(dict.fromkeys(failures))
        elif failures:
            step.error = f"{step.error}\n" + "\n".join(dict.fromkeys(failures))
