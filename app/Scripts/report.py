#!/usr/bin/env python3
"""Turns the result bundles of `flows.sh` into ~/.cache/polished/native-flows/<timestamp>/index.html:
a summary grid (flow x device x scheme, pass or fail) and, per flow, one strip of screenshots per
device and scheme, a card per step. Exits 1 when any flow failed or is missing from a run
(docs/NATIVE.md 6.2).

    python3 app/Scripts/report.py <run dir> [--flows SearchFlow,TabsFlow,...]

<run dir>/runs holds `<device>-<scheme>.xcresult` and `<device>-<scheme>.json` ({device, os,
scheme, slug}) for each run.
"""

import argparse
import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEVICE_ORDER = ["iphone-18-pro", "ipad-pro-13", "iphone-duo"]
CSS = """
body{font:15px/1.4 system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}
h1{margin:0 0 4px}h2{margin:36px 0 8px}h3{margin:14px 0 6px;font-size:15px}
.meta{color:#666;margin-bottom:16px}
.summary{padding:10px 14px;border-radius:8px;font-weight:600;display:inline-block}
.summary.ok{background:#d9f5e3;color:#0b6b36}.summary.bad{background:#fde0e0;color:#a11}
table{border-collapse:collapse;margin:12px 0}td,th{padding:5px 12px;border-bottom:1px solid #ddd;text-align:left}
th{font-size:13px;color:#555}
.ok{color:#0b6b36;font-weight:700}.bad{color:#b11;font-weight:700}.miss{color:#885a00;font-weight:700}
.strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:8px}
.card{flex:0 0 auto;width:190px;border:1px solid #ccc;border-radius:8px;background:#fff;padding:6px}
.card.fail{border-color:#c33;background:#fff4f4}
.card img{display:block;width:100%;border:1px solid #eee}
.card .name{font-size:12px;margin-top:4px;word-break:break-word}
pre{white-space:pre-wrap;font-size:12px;color:#a11;margin:4px 0}
a{color:#06c}
"""


@dataclass
class Case:
    flow: str
    name: str
    result: str  # Passed, Failed, Skipped, ...
    seconds: float
    failures: list = field(default_factory=list)
    shots: list = field(default_factory=list)  # (name, relative path)

    @property
    def passed(self) -> bool:
        return self.result == "Passed"


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def seconds(text: str | None) -> float:
    match = re.match(r"([\d.]+)", text or "")
    return float(match.group(1)) if match else 0.0


def collect_cases(xcresult: Path) -> list[Case]:
    tree = json.loads(
        run(
            [
                "xcrun",
                "xcresulttool",
                "get",
                "test-results",
                "tests",
                "--path",
                str(xcresult),
                "--compact",
            ]
        )
    )
    cases: list[Case] = []

    def failures(node) -> list[str]:
        found = []
        for child in node.get("children", []):
            if child.get("nodeType") == "Failure Message":
                found.append(child.get("name", ""))
            found.extend(failures(child))
        return found

    def walk(node, suite=""):
        kind = node.get("nodeType")
        if kind == "Test Suite":
            suite = node.get("name", "")
        if kind == "Test Case":
            cases.append(
                Case(
                    flow=suite,
                    name=node.get("name", ""),
                    result=node.get("result", "Unknown"),
                    seconds=seconds(node.get("duration")),
                    failures=failures(node),
                )
            )
            return
        for child in node.get("children", []):
            walk(child, suite)

    for node in tree.get("testNodes", []):
        walk(node)
    return cases


def collect_shots(xcresult: Path, folder: Path) -> dict[str, list[tuple[str, Path]]]:
    """Exports the screenshots of every test to `folder/<flow>/NN-step.png`."""
    raw = folder / "_raw"
    raw.mkdir(parents=True, exist_ok=True)
    run(
        [
            "xcrun",
            "xcresulttool",
            "export",
            "attachments",
            "--path",
            str(xcresult),
            "--output-path",
            str(raw),
        ]
    )
    manifest = json.loads((raw / "manifest.json").read_text())
    shots: dict[str, list[tuple[str, Path]]] = {}
    for test in manifest:
        flow = test["testIdentifier"].split("/")[0]
        target = folder / flow
        target.mkdir(parents=True, exist_ok=True)
        for item in test["attachments"]:
            name = re.sub(r"_\d+_[0-9A-F-]{36}(?=\.)", "", item["suggestedHumanReadableName"])
            source = raw / item["exportedFileName"]
            if not name.endswith(".png") or not re.match(r"\d\d-", name) or not source.exists():
                continue
            source.rename(target / name)
            shots.setdefault(flow, []).append((name[:-4], target / name))
    for items in shots.values():
        items.sort()
    for leftover in raw.iterdir():
        leftover.unlink()
    raw.rmdir()
    return shots


def card(case: Case, label: str, path: Path, root: Path) -> str:
    bad = label.split("-", 1)[-1].startswith("FAILED")
    rel = html.escape(str(path.relative_to(root)))
    return (
        f'<div class="card{" fail" if bad else ""}"><a href="{rel}"><img loading="lazy" src="{rel}" alt=""></a>'
        f'<div class="name">{html.escape(label)}</div></div>'
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--flows", default="")
    args = parser.parse_args()
    root: Path = args.directory
    expected = [flow for flow in args.flows.split(",") if flow]

    runs = []  # (meta, cases)
    for meta_file in sorted((root / "runs").glob("*.json")):
        meta = json.loads(meta_file.read_text())
        xcresult = meta_file.with_suffix(".xcresult")
        if not xcresult.exists():
            runs.append((meta, []))
            continue
        folder = root / "shots" / f"{meta['slug']}-{meta['scheme']}"
        try:
            cases = collect_cases(xcresult)
            shots = collect_shots(xcresult, folder)
        except subprocess.CalledProcessError as error:
            print(f"cannot read {xcresult}: {error.stderr}", file=sys.stderr)
            cases, shots = [], {}
        for case in cases:
            case.shots = shots.get(case.flow, [])
        runs.append((meta, cases))

    def order(item):
        meta, _ = item
        slug = DEVICE_ORDER.index(meta["slug"]) if meta["slug"] in DEVICE_ORDER else 9
        return (slug, meta["scheme"])

    runs.sort(key=order)
    flows = expected or sorted({case.flow for _, cases in runs for case in cases})

    def find(cases: list[Case], flow: str) -> Case | None:
        return next((case for case in cases if case.flow == flow), None)

    failed = 0
    cells = []
    for flow in flows:
        row = []
        for _meta, cases in runs:
            case = find(cases, flow)
            if case is None:
                row.append('<td class="miss">missing</td>')
                failed += 1
            elif case.passed:
                row.append(f'<td><span class="ok">pass</span> {case.seconds:.0f}s</td>')
            else:
                row.append(
                    f'<td><span class="bad">{html.escape(case.result.lower())}</span> {case.seconds:.0f}s</td>'
                )
                failed += 1
        cells.append(f"<tr><th>{html.escape(flow)}</th>{''.join(row)}</tr>")
    heads = "".join(
        f"<th>{html.escape(meta['device'])}<br>iOS {html.escape(meta['os'])}, {html.escape(meta['scheme'])}</th>"
        for meta, _ in runs
    )

    sections = []
    for flow in flows:
        strips = []
        for meta, cases in runs:
            case = find(cases, flow)
            title = f"{html.escape(meta['device'])} (iOS {html.escape(meta['os'])}), {html.escape(meta['scheme'])}"
            if case is None:
                strips.append(f'<h3>{title}: <span class="miss">missing</span></h3>')
                continue
            status = (
                '<span class="ok">pass</span>'
                if case.passed
                else f'<span class="bad">{html.escape(case.result.lower())}</span>'
            )
            text = "".join(f"<pre>{html.escape(message)}</pre>" for message in case.failures)
            cards = "".join(card(case, label, path, root) for label, path in case.shots)
            strips.append(
                f'<h3>{title}: {status}, {case.seconds:.0f}s</h3>{text}<div class="strip">{cards}</div>'
            )
        sections.append(f'<h2 id="{html.escape(flow)}">{html.escape(flow)}</h2>{"".join(strips)}')

    summary = (
        '<span class="summary ok">all flows passed</span>'
        if failed == 0 and runs
        else f'<span class="summary bad">{failed or "no"} flow run(s) failed or missing</span>'
    )
    page = (
        f"<!doctype html><meta charset=utf-8><title>Polished native flows</title><style>{CSS}</style>"
        f"<h1>Polished native flows</h1><div class=meta>{html.escape(root.name)}, against a local server</div>{summary}"
        f"<table><tr><th>flow</th>{heads}</tr>{''.join(cells)}</table>{''.join(sections)}"
    )
    (root / "index.html").write_text(page)
    print(f"report: {root / 'index.html'}")
    print("flows: " + ("all passed" if failed == 0 and runs else f"{failed} failed or missing"))
    return 1 if failed or not runs else 0


if __name__ == "__main__":
    sys.exit(main())
