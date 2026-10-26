"""Renders the parity cases with the web's own tips (tips.render + app.css) at the coordinates of
the app's ParityScreen (402 by 874 pt, 3x), light and dark: web-light.png and web-dark.png.

    uvx --from playwright --with-editable . python -I app/Scripts/parity/web_tips.py <output dir>
"""
import base64, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from polished import tips

REPO = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[1])
NAMES = ["creme_alone","jelly_alone","shimmer_alone","glitter_alone","flakie_alone","magnetic_alone",
         "holographic_alone","thermal_alone","chrome_alone","duochrome_alone","matte_alone","chrome_and_flakie"]
cases = {c["name"]: c for c in json.loads((REPO/"spec/tips/cases.json").read_text())["cases"]}

def shade(l):
    return tips.TipShade(id=l["id"], hex=l["hex"], hex2=l["hex2"], finishes=frozenset(l["finishes"]),
        topper=l["topper"], clear=l["clear"], coats=l["coats"],
        colours=None if l["colours"] is None else frozenset(l["colours"]))

spans = []
for i, name in enumerate(NAMES):
    svg = tips.render([shade(l) for l in cases[name]["layers"]])
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    x, y = 4 + (i % 4) * 98, 90 + (i // 4) * 200
    spans.append(f'<span class="tip tip-xl" style="position:absolute;left:{x}px;top:{y}px"><span class="tip-face"><img src="{uri}" alt=""></span></span>')
html = (f'<!doctype html><meta charset=utf-8><link rel=stylesheet href="{(REPO/"src/polished/static/css/app.css").as_uri()}">'
        '<style>html,body{margin:0;height:874px;overflow:hidden;background:var(--bg)}</style><body>' + "".join(spans))
page_path = OUT/"parity.html"; page_path.write_text(html)
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ("light", "dark"):
        ctx = b.new_context(viewport={"width":402,"height":874}, device_scale_factor=3, color_scheme=scheme)
        pg = ctx.new_page(); pg.goto(page_path.as_uri()); pg.wait_for_timeout(500)
        pg.screenshot(path=OUT/f"web-{scheme}.png"); ctx.close()
    b.close()
