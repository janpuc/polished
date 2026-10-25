"""A polite client for the shop's public feed: /products.json, 250 products a page (DESIGN 5.1).

At most MAX_PAGES requests, never closer together than the minimum interval, an identifying
User-Agent, and no retries: any 429, 5xx, transport error or odd payload aborts the fetch.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlsplit

import httpx

log = logging.getLogger("polished.sync")

PAGE_SIZE = 250
MAX_PAGES = 10
MAX_REDIRECTS = 3
TIMEOUT_S = 30.0
REPOSITORY_URL = "https://github.com/janpuc/polished"

Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


class FeedError(Exception):
    """The feed could not be fetched; nothing must be applied."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

    @property
    def retryable(self) -> bool:
        """A 5xx may be tried once more an hour later; a 429 never is."""
        return self.status_code is not None and self.status_code >= 500


def user_agent(version: str) -> str:
    return f"polished/{version} (+{REPOSITORY_URL})"


def _site(url: str) -> str:
    """The host without a leading www., so holotaco.com and www.holotaco.com are one site."""
    return (urlsplit(url).hostname or "").removeprefix("www.")


class _Throttle:
    """Waits until min_interval_s have passed since the previous request."""

    def __init__(self, min_interval_s: float, clock: Clock, sleep: Sleep):
        self.min_interval_s = min_interval_s
        self.clock = clock
        self.sleep = sleep
        self.last: float | None = None

    async def wait(self) -> None:
        if self.last is not None:
            remaining = self.last + self.min_interval_s - self.clock()
            if remaining > 0:
                await self.sleep(remaining)
        self.last = self.clock()


async def _get(
    client: httpx.AsyncClient, url: str, throttle: _Throttle, site: str
) -> httpx.Response:
    """GET that follows redirects only within the shop's own site; every hop is throttled."""
    for _ in range(MAX_REDIRECTS + 1):
        await throttle.wait()
        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            raise FeedError(f"request failed: {type(exc).__name__}: {exc}") from exc
        if not response.is_redirect:
            return response
        url = urljoin(url, response.headers.get("location", ""))
        if _site(url) != site:
            raise FeedError(f"redirected off the shop to {urlsplit(url).hostname}")
    raise FeedError("too many redirects")


async def fetch_feed(
    store_url: str,
    *,
    version: str,
    min_interval_s: float,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock = time.monotonic,
    sleep: Sleep = asyncio.sleep,
) -> list[list[dict]]:
    """Every page of products, in order. Stops at the first page shorter than PAGE_SIZE."""
    throttle = _Throttle(min_interval_s, clock, sleep)
    site = _site(store_url)
    pages: list[list[dict]] = []
    async with httpx.AsyncClient(
        transport=transport,
        headers={"User-Agent": user_agent(version), "Accept": "application/json"},
        timeout=TIMEOUT_S,
        follow_redirects=False,
    ) as client:
        for number in range(1, MAX_PAGES + 1):
            url = f"{store_url}/products.json?limit={PAGE_SIZE}&page={number}"
            response = await _get(client, url, throttle, site)
            if response.status_code != 200:
                raise FeedError(f"page {number}: HTTP {response.status_code}", response.status_code)
            try:
                products = response.json()["products"]
            except (ValueError, KeyError, TypeError) as exc:
                raise FeedError(f"page {number}: not a products feed") from exc
            if not isinstance(products, list):
                raise FeedError(f"page {number}: not a products feed")
            pages.append(products)
            log.info("fetched page %d: %d products", number, len(products))
            if len(products) < PAGE_SIZE:
                return pages
    raise FeedError(f"more than {MAX_PAGES} pages; refusing to continue")
