"""Nail tips drawn as SVG (DESIGN 9): a painted-nail texture for one shade, or for a whole stack.

A tip never shows a photo. The colour comes from the shade (the household's override, else the
colour read from its photos), the look from its finish tags: creme is flat and glossy, a jelly is
see-through, shimmer is fine dust, glitter is dots and stars, a flakie is translucent chips, a
magnetic has a cat-eye band, a holographic has a rainbow sheen, a thermal runs from one colour to
another. Everything is drawn with presentation attributes only (no style, no script), so it holds
under the CSP, and with a random generator seeded by the shade id, so a shade looks the same
every time and in every stack. The shape of the tip is CSS; the SVG is 102x168 and fills it.
"""

import colorsys
import hashlib
import math
import random
from dataclasses import dataclass

WIDTH, HEIGHT = 102, 168
NEUTRAL_HEX = "#c9bfc0"  # a shade whose colour is not known yet
NUDE_HEX = "#e9d2c6"  # what a topper or a jelly goes over when nothing opaque is below
RAINBOW = ("#ff5fa2", "#ffb347", "#f4ec6a", "#5fe3a1", "#5fb8ff", "#a07bff")
SEE_THROUGH = {"jelly"}
# Colour tags that mean a topper carries no tint of its own: its flakes or glitter sit in a clear base.
UNTINTED_COLOURS = {"clear", "silver", "neutral", "black", "white", "grey", "gray"}
CLEAR_KINDS = {"basecoat"}

# Select list for a shade's tip, appended to a query over `shade s`.
TIP_FIELDS = (
    "s.kind, s.is_topper, s.swatch_hex, s.swatch_hex2, s.swatch_override_hex,"
    " (select group_concat(t.value) from shade_tag t"
    " where t.shade_id = s.id and t.ns = 'finish') as finishes,"
    " (select group_concat(t.value) from shade_tag t"
    " where t.shade_id = s.id and t.ns = 'color') as colours"
)


@dataclass(frozen=True)
class TipShade:
    id: int
    hex: str
    hex2: str | None
    finishes: frozenset[str]
    topper: bool
    clear: bool
    coats: int = 1
    colours: frozenset[str] | None = None  # the shop's colour tags, when the row carries them

    @property
    def tinted(self) -> bool:
        """Whether a topper leaves a hint of its own colour. The sampled colour of a clear topper
        is its photo's backdrop, so only a topper the shop calls a real colour tints."""
        if self.colours is not None:
            return bool(self.colours - UNTINTED_COLOURS)
        return colorsys.rgb_to_hsv(*(c / 255 for c in _rgb(self.hex)))[1] > 0.25

    @property
    def see_through(self) -> bool:
        return not self.topper and bool(self.finishes & SEE_THROUGH)

    @property
    def opaque(self) -> bool:
        return not (self.topper or self.clear or self.see_through)


def tip_shade(row) -> TipShade:
    """From a row with TIP_FIELDS and `shade_id` or `id` (and `coats` for a layer); `finishes` is
    the comma-joined string of TIP_FIELDS or the list a shade list row carries. The override
    replaces the colour and with it the second colour."""
    override = row["swatch_override_hex"]
    keys = row.keys()
    finishes = row["finishes"] or ()
    if isinstance(finishes, str):
        finishes = finishes.split(",")
    return TipShade(
        id=row["shade_id"] if "shade_id" in keys else row["id"],
        hex=override or row["swatch_hex"] or NEUTRAL_HEX,
        hex2=None if override else row["swatch_hex2"],
        finishes=frozenset(finishes) - {""},
        topper=bool(row["is_topper"]),
        clear=row["kind"] in CLEAR_KINDS,
        coats=row["coats"] if "coats" in keys else 1,
        colours=_tag_set(row["colours"]) if "colours" in keys else None,
    )


def _tag_set(value) -> frozenset[str]:
    if isinstance(value, str):
        value = value.split(",")
    return frozenset(value or ()) - {""}


# Bump when render() draws differently: the image URLs are cached for good, so only a new
# revision makes a browser fetch the new drawing.
DRAWING_VERSION = 2


def revision(shades: list[TipShade]) -> str:
    """Changes whenever anything that is drawn changes; goes in the image URL and the ETag."""
    return hashlib.sha1(f"{DRAWING_VERSION}{shades!r}".encode()).hexdigest()[:10]


def shade_url(row) -> str:
    drawn = tip_shade(row)
    return f"/tips/shade/{drawn.id}.svg?v={revision([drawn])}"


def stack_url(stack_id: int, layers: list) -> str:
    return f"/tips/stack/{stack_id}.svg?v={revision([tip_shade(layer) for layer in layers])}"


def effective_hex(row) -> str:
    return tip_shade(row).hex


# --- colour ---------------------------------------------------------------------------------


def _rgb(colour: str) -> tuple[float, float, float]:
    return tuple(int(colour[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def mix(a: str, b: str, amount: float) -> str:
    """`amount` of b in a."""
    return _hex(tuple(x + (y - x) * amount for x, y in zip(_rgb(a), _rgb(b), strict=True)))


def lighten(colour: str, amount: float) -> str:
    return mix(colour, "#ffffff", amount)


def darken(colour: str, amount: float) -> str:
    return mix(colour, "#000000", amount)


def shift_hue(colour: str, degrees: float) -> str:
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in _rgb(colour)))
    r, g, b = colorsys.hsv_to_rgb((h + degrees / 360) % 1, s, v)
    return _hex((r * 255, g * 255, b * 255))


def luminance(colour: str) -> float:
    r, g, b = _rgb(colour)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


# --- drawing --------------------------------------------------------------------------------


class _Canvas:
    def __init__(self) -> None:
        self.defs: list[str] = []
        self.body: list[str] = []
        self._ids = 0

    def new_id(self, kind: str) -> str:
        self._ids += 1
        return f"{kind}{self._ids}"

    def gradient(self, stops, x1=0.0, y1=0.0, x2=0.0, y2=1.0) -> str:
        """A linear gradient over the whole tip; stops are (offset, colour, opacity)."""
        ident = self.new_id("g")
        rows = "".join(
            f'<stop offset="{offset:g}" stop-color="{colour}" stop-opacity="{opacity:g}"/>'
            for offset, colour, opacity in stops
        )
        self.defs.append(
            f'<linearGradient id="{ident}" x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}">{rows}</linearGradient>'
        )
        return f"url(#{ident})"

    def radial(self, stops, cx=0.5, cy=0.5, r=0.5) -> str:
        ident = self.new_id("r")
        rows = "".join(
            f'<stop offset="{offset:g}" stop-color="{colour}" stop-opacity="{opacity:g}"/>'
            for offset, colour, opacity in stops
        )
        self.defs.append(
            f'<radialGradient id="{ident}" cx="{cx:g}" cy="{cy:g}" r="{r:g}">{rows}</radialGradient>'
        )
        return f"url(#{ident})"

    def blur(self, amount: float) -> str:
        ident = self.new_id("b")
        self.defs.append(
            f'<filter id="{ident}" x="-30%" y="-30%" width="160%" height="160%">'
            f'<feGaussianBlur stdDeviation="{amount:g}"/></filter>'
        )
        return f"url(#{ident})"

    def rect(self, fill: str, opacity: float = 1.0) -> None:
        extra = "" if opacity >= 1 else f' fill-opacity="{opacity:.2f}"'
        self.body.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{fill}"{extra}/>')

    def add(self, markup: str) -> None:
        self.body.append(markup)

    def svg(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}"'
            f' width="{WIDTH}" height="{HEIGHT}" preserveAspectRatio="xMidYMid slice">'
            f"<defs>{''.join(self.defs)}</defs>{''.join(self.body)}</svg>"
        )


def _dots(canvas: _Canvas, rng: random.Random, count: int, radius, colours, opacity) -> None:
    """Round dots in groups by colour, so the markup stays short."""
    groups: dict[str, list[str]] = {}
    for _ in range(count):
        colour = rng.choice(colours)
        r = rng.uniform(*radius)
        groups.setdefault(colour, []).append(
            f'<circle cx="{rng.uniform(0, WIDTH):.1f}" cy="{rng.uniform(0, HEIGHT):.1f}" r="{r:.2f}"/>'
        )
    for colour, circles in groups.items():
        canvas.add(f'<g fill="{colour}" fill-opacity="{opacity:g}">{"".join(circles)}</g>')


def _star(cx: float, cy: float, size: float, colour: str, opacity: float) -> str:
    pinch = size * 0.16
    d = (
        f"M{cx:.1f} {cy - size:.1f}L{cx + pinch:.1f} {cy - pinch:.1f}L{cx + size:.1f} {cy:.1f}"
        f"L{cx + pinch:.1f} {cy + pinch:.1f}L{cx:.1f} {cy + size:.1f}L{cx - pinch:.1f} {cy + pinch:.1f}"
        f"L{cx - size:.1f} {cy:.1f}L{cx - pinch:.1f} {cy - pinch:.1f}Z"
    )
    return f'<path d="{d}" fill="{colour}" fill-opacity="{opacity:g}"/>'


def _sparkle_palette(shade: TipShade) -> list[str]:
    base = shade.hex
    palette = [base, lighten(base, 0.5), lighten(base, 0.25), darken(base, 0.3), "#ffffff"]
    if shade.hex2:
        palette += [shade.hex2, lighten(shade.hex2, 0.5)]
    if shade.finishes & {"holographic", "iridescent"}:
        palette += list(RAINBOW)
    return palette


def _rainbow_sheen(canvas: _Canvas, rng: random.Random, opacity: float) -> None:
    """The spectrum spread over the tip in two soft diagonal sweeps, where it starts differing
    from shade to shade."""
    start = rng.randrange(len(RAINBOW))
    colours = [RAINBOW[(start + i) % len(RAINBOW)] for i in range(2 * len(RAINBOW))]
    stops = [
        (
            index / (len(colours) - 1),
            colour,
            opacity * (0.55 if index in (0, len(colours) - 1) else 1),
        )
        for index, colour in enumerate(colours)
    ]
    canvas.rect(canvas.gradient(stops, 0, 0.15, 1, 0.85))


def _flakes(canvas: _Canvas, rng: random.Random, shade: TipShade) -> None:
    palette = list(RAINBOW) + [
        shade.hex,
        shade.hex,
        lighten(shade.hex, 0.4),
        shade.hex2 or lighten(shade.hex, 0.2),
    ]
    for _ in range(18):
        cx, cy = rng.uniform(4, WIDTH - 4), rng.uniform(4, HEIGHT - 4)
        size = rng.uniform(3.5, 9)
        points = []
        for index in range(rng.randint(4, 6)):
            angle = index / 5 * 6.283 + rng.uniform(-0.5, 0.5)
            radius = size * rng.uniform(0.55, 1.1)
            points.append(
                f"{cx + radius * math.cos(angle):.1f},{cy + radius * math.sin(angle):.1f}"
            )
        colour = rng.choice(palette)
        canvas.add(
            f'<polygon points="{" ".join(points)}" fill="{colour}" fill-opacity="{rng.uniform(0.5, 0.8):.2f}"'
            f' stroke="#ffffff" stroke-opacity="0.35" stroke-width="0.4"/>'
        )


def _paint(canvas: _Canvas, shade: TipShade) -> None:
    """One layer: its base, then its finish."""
    if shade.clear:
        return
    rng = random.Random(shade.id)
    finishes = shade.finishes
    base = shade.hex

    if "thermal" in finishes:
        other = shade.hex2 or shift_hue(lighten(base, 0.2), 70)
        fill = canvas.gradient([(0, base, 1), (0.45, base, 1), (1, other, 1)])
        canvas.rect(fill, 0.9 if shade.topper else 1)
    elif shade.see_through:
        canvas.rect(base, min(0.95, 0.68 + 0.1 * shade.coats))
        canvas.rect(
            canvas.gradient([(0, base, 0), (1, darken(base, 0.45), 0.55)]), 1
        )  # depth: deeper toward the free edge
    elif not shade.topper:
        canvas.rect(base)
    elif shade.tinted:
        canvas.rect(base, 0.3)  # a coloured topper leaves a hint of its colour

    if (
        shade.hex2
        and not shade.topper
        and not shade.see_through
        and not finishes & {"thermal", "metallic", "chrome", "magnetic"}
        and luminance(shade.hex2) > 0.12
    ):
        # duochrome and multichrome shift: the second colour sweeps in across the tip
        canvas.rect(
            canvas.gradient(
                [(0, shade.hex2, 0), (0.45, shade.hex2, 0.0), (1, shade.hex2, 0.7)], 0, 0.1, 1, 0.9
            )
        )

    if finishes & {"metallic", "chrome", "reflective"}:
        strong = "chrome" in finishes
        top, mid, low = (
            lighten(base, 0.6 if strong else 0.4),
            base,
            darken(base, 0.5 if strong else 0.35),
        )
        stops = [
            (0, top, 1),
            (0.28, mid, 1),
            (0.55, low, 1),
            (0.8, mid, 1),
            (1, lighten(base, 0.3), 1),
        ]
        canvas.rect(
            canvas.gradient(stops, 0, 0, 0.9, 1),
            (0.9 if strong else 0.6) * (0.5 if shade.topper else 1),
        )

    if "magnetic" in finishes:
        soft = canvas.blur(3.5)
        band = lighten(base, 0.6)
        canvas.add(
            f'<path d="M-8 150Q51 52 112 96L112 128Q51 84-8 176Z" fill="{band}" fill-opacity="0.75" filter="{soft}"/>'
        )
        canvas.add(
            f'<path d="M-8 128Q51 36 112 74L112 84Q51 52-8 146Z" fill="{darken(base, 0.45)}" fill-opacity="0.35" filter="{soft}"/>'
        )

    if finishes & {"holographic", "iridescent"}:
        strength = 0.2 if "holographic" in finishes else 0.12
        _rainbow_sheen(canvas, rng, strength * (0.6 if shade.topper else 1))
    if finishes & {"shimmer", "holographic", "iridescent", "reflective"}:
        count = 190 if "shimmer" in finishes else 90
        _dots(
            canvas,
            rng,
            count,
            (0.35, 0.8),
            [lighten(base, 0.45), lighten(base, 0.25), darken(base, 0.3)],
            0.5,
        )
    if "glitter" in finishes:
        palette = _sparkle_palette(shade)
        _dots(canvas, rng, 55, (0.7, 1.9), palette, 0.9)
        for _ in range(7):
            canvas.add(
                _star(
                    rng.uniform(8, WIDTH - 8),
                    rng.uniform(8, HEIGHT - 8),
                    rng.uniform(2.6, 5.2),
                    "#ffffff",
                    0.9,
                )
            )
    if "flakie" in finishes:
        _flakes(canvas, rng, shade)


def _finish(canvas: _Canvas, matte: bool) -> None:
    """Over everything: the curve of the nail, then the gloss unless the top coat is matte. The
    page's CSS adds the occlusion and the specular pool over this (DESIGN 9), so the dome's edge is
    light and the small highlight sits under the pool's default place at the top left."""
    canvas.rect(canvas.radial([(0.55, "#000000", 0), (1, "#000000", 0.18)], 0.5, 0.42, 0.78), 1)
    if matte:
        return
    canvas.add(
        f'<path d="M25 30C26 20 37 20 39 30L36 98C35 106 29 105 28 97Z"'
        f' fill="{canvas.gradient([(0, "#ffffff", 0.5), (1, "#ffffff", 0.03)])}"/>'
    )
    canvas.add(
        '<ellipse cx="66" cy="30" rx="6" ry="15" fill="#ffffff" fill-opacity="0.1"'
        ' transform="rotate(14 66 30)"/>'
    )


def render(layers: list[TipShade]) -> str:
    """The tip of a stack in painting order (a single shade is a stack of one). An opaque polish
    covers what is below it; a see-through one tints it; a topper adds only its finish. Over
    nothing opaque, the layers go on a sheer nude so a lone topper is visible."""
    canvas = _Canvas()
    start = 0
    for index, shade in enumerate(layers):
        if shade.opaque:
            start = index
    if not any(shade.opaque for shade in layers):
        canvas.rect(
            canvas.gradient([(0, lighten(NUDE_HEX, 0.25), 1), (1, darken(NUDE_HEX, 0.08), 1)])
        )
    for shade in layers[start:]:
        _paint(canvas, shade)
    top = layers[-1] if layers else None
    _finish(canvas, matte=bool(top and "matte" in top.finishes))
    return canvas.svg()
