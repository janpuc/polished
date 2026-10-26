"""Observable end-to-end flows (DESIGN 14, item 84): named flows, each a sequence of steps with
assertions and a screenshot, run on an iPhone, an iPad and a Mac in light and dark, with an HTML
report to look at. Not part of `pytest -q`: it needs Chromium.

    uvx --from playwright --with python-barcode --with pillow python tests/e2e/run_flows.py \\
        [--base URL] [--devices iphone,ipad,mac] [--schemes light,dark] [--flows search,wheel-delete] \\
        [--out DIR]

By default it starts the app itself, once per flow and device, on a fresh copy of a database
seeded from tests/fixtures/ (sign-in off, no network), so flows never see each other's data.
With --base it runs against that server instead, which must hold the same seeded data
(`uv run python tests/e2e/flows/seed.py DB`) and be a throwaway: the flows add bottles and wheels.

The report goes to ~/.cache/polished/flows/<timestamp>/ (index.html, summary.json and one
screenshot per step) unless --out says otherwise. Exit status 1 when any step of any run failed.
Playwright needs its Chromium (`uvx --from playwright playwright install chromium`).
"""

import argparse
import sys
import tempfile
import time
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

from flows import scenarios
from flows.harness import DEVICES, SCHEMES, Step, StepFailed, Trace, context_options
from flows.media import PIXEL
from flows.report import RunResult, write
from flows.server import Server, seed_template
from playwright.sync_api import sync_playwright


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", help="run against this server instead of starting one")
    parser.add_argument(
        "--devices", default=",".join(DEVICES), help="comma list of iphone,ipad,mac"
    )
    parser.add_argument("--schemes", default=",".join(SCHEMES), help="comma list of light,dark")
    parser.add_argument("--flows", default="", help="comma list of flow names (default: all)")
    parser.add_argument("--out", help="report directory (default ~/.cache/polished/flows/<time>)")
    parser.add_argument("--list", action="store_true", help="list the flows and exit")
    parser.add_argument(
        "--tap-warnings",
        action="store_true",
        help="report tap targets under 44pt as notes instead of failures",
    )
    args = parser.parse_args(argv)
    for name, known in (("devices", DEVICES), ("schemes", SCHEMES)):
        chosen = [v for v in getattr(args, name).split(",") if v]
        unknown = [v for v in chosen if v not in known]
        if unknown or not chosen:
            parser.error(f"--{name}: pick from {', '.join(known)} (got {unknown or 'nothing'})")
        setattr(args, name, chosen)
    args.flows = [v for v in args.flows.split(",") if v]
    unknown = [v for v in args.flows if v not in scenarios.FLOWS]
    if unknown:
        parser.error(f"--flows: unknown {unknown}; known: {', '.join(scenarios.FLOWS)}")
    return args


def run_one(
    browser, playwright, flow, device, scheme, base, out: Path, tap_failures: bool
) -> RunResult:
    started = time.monotonic()
    directory = f"{flow.name}/{device.key}-{scheme}"
    context = browser.new_context(**context_options(playwright, device, scheme))
    context.route(
        "https://cdn.shopify.com/**",
        lambda route: route.fulfill(status=200, content_type="image/png", body=PIXEL),
    )
    page = context.new_page()
    trace = Trace(page, base, device, scheme, out / directory)
    trace.tap_failures = tap_failures
    try:
        flow.run(trace)
    except StepFailed:
        pass
    except Exception as exc:  # the flow itself broke outside a step
        trace.steps.append(
            Step(len(trace.steps) + 1, "flow error", False, f"{type(exc).__name__}: {exc}")
        )
    finally:
        context.close()
    return RunResult(
        flow.name,
        flow.title,
        device.key,
        scheme,
        directory,
        time.monotonic() - started,
        trace.steps,
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.list:
        for flow in scenarios.FLOWS.values():
            print(f"{flow.name:16} {flow.title}")
        return 0
    started = datetime.now()
    out = (
        Path(args.out).expanduser()
        if args.out
        else (Path.home() / ".cache/polished/flows" / started.strftime("%Y%m%d-%H%M%S"))
    )
    out.mkdir(parents=True, exist_ok=True)
    selected = (
        [scenarios.FLOWS[n] for n in args.flows] if args.flows else list(scenarios.FLOWS.values())
    )
    results: list[RunResult] = []
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="polished-flows-") as scratch, sync_playwright() as p:
        template = None if args.base else seed_template(Path(scratch))
        browser = p.chromium.launch()
        try:
            for flow in selected:
                for device_key in args.devices:
                    for scheme in args.schemes:
                        device = DEVICES[device_key]
                        server = nullcontext() if args.base else Server(template)
                        with server as running:
                            base = args.base or running.base
                            result = run_one(
                                browser, p, flow, device, scheme, base, out, not args.tap_warnings
                            )
                        results.append(result)
                        mark = "ok  " if result.passed else "FAIL"
                        print(
                            f"{mark} {flow.name:14} {device_key:7} {scheme:5} "
                            f"{len(result.steps):2} steps {result.seconds:5.1f}s",
                            flush=True,
                        )
                        for step in result.steps:
                            if not step.passed:
                                print(
                                    f"       step {step.number} {step.name}: {step.error.splitlines()[0]}"
                                )
        finally:
            browser.close()
    meta = {
        "started": started.isoformat(timespec="seconds"),
        "base": args.base or "a fresh local server per run",
        "devices": args.devices,
        "schemes": args.schemes,
        "seconds": time.monotonic() - t0,
    }
    passed = write(out, results, meta)
    print(
        f"\n{'PASSED' if passed else 'FAILED'}: {sum(r.passed for r in results)}/{len(results)} runs"
    )
    print(f"report: {out / 'index.html'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
