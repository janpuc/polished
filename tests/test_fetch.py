import httpx
import pytest
from conftest import FakeClock, load_feed, make_settings, synthetic_products

from polished.catalog.fetch import MAX_PAGES, FeedError, fetch_feed, user_agent
from polished.catalog.sync import SyncRunner
from polished.db import connect
from polished.migrate import migrate

STORE = "https://shop.example.test"


def pages_transport(pages, seen=None, clock=None, status=None):
    """Serves /products.json?page=N from `pages`; `status` maps a page number to an error."""

    def handler(request: httpx.Request) -> httpx.Response:
        number = int(request.url.params["page"])
        if seen is not None:
            seen.append((request, clock() if clock else None))
        if status and number in status:
            return httpx.Response(status[number])
        products = pages[number - 1] if number <= len(pages) else []
        return httpx.Response(200, json={"products": products})

    return httpx.MockTransport(handler)


async def fetch(transport, clock=None, **kwargs):
    clock = clock or FakeClock()
    return await fetch_feed(
        STORE,
        version="9.9",
        min_interval_s=1.0,
        transport=transport,
        clock=clock,
        sleep=clock.sleep,
        **kwargs,
    )


async def test_three_pages_are_fetched_and_stop_on_the_short_one():
    pages = [synthetic_products(250), synthetic_products(250, 250), synthetic_products(26, 500)]
    seen = []
    result = await fetch(pages_transport(pages, seen))
    assert [len(p) for p in result] == [250, 250, 26]
    assert [str(r.url) for r, _ in seen] == [
        f"{STORE}/products.json?limit=250&page={n}" for n in (1, 2, 3)
    ]


async def test_requests_are_at_least_one_second_apart_by_the_injected_clock():
    clock = FakeClock()
    seen = []
    pages = [synthetic_products(250), synthetic_products(250, 250), synthetic_products(1, 500)]
    await fetch(pages_transport(pages, seen, clock), clock)
    times = [at for _, at in seen]
    assert len(times) == 3
    assert all(later - earlier >= 1.0 for earlier, later in zip(times, times[1:], strict=False))
    assert len(clock.sleeps) == 2


async def test_no_sleep_when_the_clock_already_moved_on():
    clock = FakeClock()
    seen = []

    def slow_handler(request):
        clock.time += 5.0
        seen.append(request)
        return httpx.Response(200, json={"products": synthetic_products(250)})

    with pytest.raises(FeedError, match="more than"):
        await fetch(httpx.MockTransport(slow_handler), clock)
    assert clock.sleeps == []
    assert len(seen) == MAX_PAGES


async def test_a_short_first_page_is_the_only_request():
    seen = []
    result = await fetch(pages_transport([synthetic_products(10)], seen))
    assert len(result) == 1
    assert len(seen) == 1


async def test_the_user_agent_names_polished_and_the_repository():
    seen = []
    await fetch(pages_transport([synthetic_products(3)], seen))
    agent = seen[0][0].headers["user-agent"]
    assert agent == user_agent("9.9") == "polished/9.9 (+https://github.com/janpuc/polished)"


@pytest.mark.parametrize(("code", "retryable"), [(429, False), (500, True), (503, True)])
async def test_a_429_or_5xx_aborts_the_fetch(code, retryable):
    pages = [synthetic_products(250), synthetic_products(10, 250)]
    with pytest.raises(FeedError) as caught:
        await fetch(pages_transport(pages, status={2: code}))
    assert caught.value.status_code == code
    assert caught.value.retryable is retryable


async def test_a_transport_error_aborts_the_fetch():
    def boom(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(FeedError, match="request failed"):
        await fetch(httpx.MockTransport(boom))


async def test_a_reply_that_is_not_a_products_feed_aborts_the_fetch():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"oops": 1}))
    with pytest.raises(FeedError, match="not a products feed"):
        await fetch(transport)


async def test_the_page_cap_stops_a_feed_that_never_ends():
    seen = []
    full = [synthetic_products(250)] * (MAX_PAGES + 5)
    with pytest.raises(FeedError, match="more than"):
        await fetch(pages_transport(full, seen))
    assert len(seen) == MAX_PAGES


async def test_a_redirect_within_the_shop_is_followed_and_throttled():
    clock = FakeClock()

    def handler(request):
        if request.url.host == "shop.example.test":
            return httpx.Response(
                301,
                headers={
                    "location": "https://www.shop.example.test/products.json?limit=250&page=1"
                },
            )
        return httpx.Response(200, json={"products": synthetic_products(2)})

    result = await fetch(httpx.MockTransport(handler), clock)
    assert len(result[0]) == 2
    assert len(clock.sleeps) == 1


async def test_a_redirect_off_the_shop_is_refused():
    seen = []

    def handler(request):
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": "https://elsewhere.example.net/x"})

    with pytest.raises(FeedError, match="redirected off the shop"):
        await fetch(httpx.MockTransport(handler))
    assert seen == ["shop.example.test"]


def runner_for(tmp_path, transport, **overrides):
    settings = make_settings(tmp_path, store_url=STORE, **overrides)
    migrate(settings.db_path)
    clock = FakeClock()
    return SyncRunner(settings, transport=transport, clock=clock, sleep=clock.sleep), settings


@pytest.mark.parametrize("code", [429, 500])
async def test_a_429_or_5xx_aborts_the_run_with_nothing_written(tmp_path, code):
    pages = [synthetic_products(250), synthetic_products(10, 250)]
    runner, settings = runner_for(tmp_path, pages_transport(pages, status={2: code}))
    outcome = await runner.run("manual")
    assert outcome.status == "error"
    assert f"HTTP {code}" in outcome.error
    assert outcome.retryable is (code == 500)
    conn = connect(settings.db_path)
    assert conn.execute("select count(*) from product").fetchone()[0] == 0
    assert conn.execute("select count(*) from shade").fetchone()[0] == 0
    run = conn.execute("select status, error, finished_at from sync_run").fetchone()
    assert run["status"] == "error"
    assert f"HTTP {code}" in run["error"]
    assert run["finished_at"] is not None


async def test_a_run_through_the_mock_store_applies_the_fixture(tmp_path):
    runner, settings = runner_for(tmp_path, pages_transport([load_feed()]))
    outcome = await runner.run("manual")
    assert outcome.status == "ok"
    conn = connect(settings.db_path)
    run = conn.execute("select * from sync_run").fetchone()
    assert (run["pages_fetched"], run["products_seen"], run["new_shades"]) == (1, 16, 9)
    assert not runner.running
