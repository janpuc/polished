"""The HTML report and the JSON summary of a run: one row per flow × device × scheme, a card per
step with its screenshot, and the failure text under the step that failed."""

import html
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RunResult:
    flow: str
    title: str
    device: str
    scheme: str
    directory: str  # relative to the report
    seconds: float
    steps: list = field(default_factory=list)  # harness.Step

    @property
    def passed(self) -> bool:
        return bool(self.steps) and all(step.passed for step in self.steps)


CSS = """
body{font:15px/1.4 system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}
h1{margin:0 0 4px}h2{margin:32px 0 8px}
.meta{color:#666;margin-bottom:16px}
.summary{padding:10px 14px;border-radius:8px;font-weight:600;display:inline-block}
.summary.ok{background:#d9f5e3;color:#0b6b36}.summary.bad{background:#fde0e0;color:#a11}
.run{margin:10px 0 22px}
.run>h3{margin:0 0 6px;font-size:15px}
.run>h3 .ok{color:#0b6b36}.run>h3 .bad{color:#b11}
.strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:8px}
.card{flex:0 0 auto;width:180px;border:1px solid #ccc;border-radius:8px;background:#fff;padding:6px}
.card.fail{border-color:#c33;background:#fff4f4}
.card img{display:block;width:100%;max-height:300px;object-fit:cover;object-position:top;border:1px solid #eee}
.card .name{font-size:12px;margin-top:4px}
.card .badge{font-weight:700}.card .badge.ok{color:#0b6b36}.card .badge.bad{color:#b11}
.card pre{white-space:pre-wrap;font-size:11px;color:#a11;margin:4px 0 0}
.card .note{font-size:11px;color:#885a00;margin:4px 0 0}
table{border-collapse:collapse}td,th{padding:3px 10px;border-bottom:1px solid #ddd;text-align:left}
a{color:#06c}
"""


def step_card(directory: str, step) -> str:
    cls = "ok" if step.passed else "bad"
    image = (
        f'<a href="{html.escape(directory)}/{html.escape(step.screenshot)}">'
        f'<img loading="lazy" src="{html.escape(directory)}/{html.escape(step.screenshot)}" alt=""></a>'
        if step.screenshot
        else ""
    )
    error = f"<pre>{html.escape(step.error)}</pre>" if step.error else ""
    notes = "".join(f'<p class="note">{html.escape(n)}</p>' for n in step.notes)
    return (
        f'<div class="card{"" if step.passed else " fail"}">{image}'
        f'<div class="name"><span class="badge {cls}">{"PASS" if step.passed else "FAIL"}</span> '
        f"{step.number}. {html.escape(step.name)}</div>{error}{notes}</div>"
    )


def render_html(results: list[RunResult], meta: dict) -> str:
    failed = [r for r in results if not r.passed]
    verdict = (
        f'<span class="summary ok">All {len(results)} runs passed</span>'
        if not failed
        else f'<span class="summary bad">{len(failed)} of {len(results)} runs failed</span>'
    )
    body = [
        f"<h1>Polished flows</h1><p class=meta>{html.escape(meta['started'])} · "
        f"{html.escape(meta['base'])} · devices {html.escape(', '.join(meta['devices']))} · "
        f"schemes {html.escape(', '.join(meta['schemes']))} · {meta['seconds']:.0f}s</p>{verdict}"
    ]
    if failed:
        body.append("<h2>Failures</h2><table>")
        for run in failed:
            step = next(s for s in run.steps if not s.passed) if run.steps else None
            what = f"step {step.number} {step.name}: {step.error}" if step else "no steps ran"
            anchor = f"{run.flow}-{run.device}-{run.scheme}"
            body.append(
                f'<tr><td><a href="#{anchor}">{html.escape(run.flow)}</a></td><td>{run.device}</td>'
                f"<td>{run.scheme}</td><td>{html.escape(what.splitlines()[0])}</td></tr>"
            )
        body.append("</table>")
    for flow in dict.fromkeys(r.flow for r in results):
        runs = [r for r in results if r.flow == flow]
        body.append(f"<h2>{html.escape(flow)} <small>{html.escape(runs[0].title)}</small></h2>")
        for run in runs:
            cls = "ok" if run.passed else "bad"
            body.append(
                f'<div class="run" id="{run.flow}-{run.device}-{run.scheme}"><h3>'
                f'<span class="{cls}">{"PASS" if run.passed else "FAIL"}</span> {run.device} · '
                f"{run.scheme} · {run.seconds:.1f}s</h3><div class=strip>"
                + "".join(step_card(run.directory, step) for step in run.steps)
                + "</div></div>"
            )
    return (
        "<!doctype html><meta charset=utf-8><title>Polished flows</title>"
        f"<style>{CSS}</style>" + "".join(body)
    )


def write(out: Path, results: list[RunResult], meta: dict) -> bool:
    """Writes index.html and summary.json into `out`; True when every run passed."""
    (out / "index.html").write_text(render_html(results, meta), encoding="utf-8")
    passed = all(r.passed for r in results)
    summary = {
        **meta,
        "passed": passed,
        "runs": [
            {
                "flow": r.flow,
                "device": r.device,
                "scheme": r.scheme,
                "passed": r.passed,
                "seconds": round(r.seconds, 2),
                "steps": [asdict(s) for s in r.steps],
            }
            for r in results
        ],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return passed
