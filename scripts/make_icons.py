"""Writes the app icons to src/polished/static/icons/. Run once; the PNGs are committed.

    uv run --with pillow python scripts/make_icons.py [OUTPUT_DIR]

A white nail polish bottle with a plum cap on a soft holographic gradient. The 180 px
apple-touch icon and the maskable 512 px icon are full-bleed squares (iOS and Android round
them); the plain 192 and 512 px icons have rounded corners. The maskable glyph is smaller so it
stays inside the 80% safe zone.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

WORK = 1024  # drawn large and scaled down, for smooth edges
STOPS = [  # position along the diagonal, colour
    (0.00, (247, 168, 207)),  # pink
    (0.35, (205, 184, 245)),  # lavender
    (0.65, (166, 226, 232)),  # aqua
    (1.00, (190, 240, 205)),  # mint
]
CAP = (74, 31, 69)
GLASS = (255, 255, 255)


def gradient(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:], strict=False):
                if t <= t1:
                    k = (t - t0) / (t1 - t0)
                    pixels[x, y] = tuple(
                        round(a + (b - a) * k) for a, b in zip(c0, c1, strict=True)
                    )
                    break
    return image


def sheen(size: int) -> Image.Image:
    """Two soft diagonal light bands, the holographic part."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for offset, width, alpha in ((0.30, 0.10, 70), (0.62, 0.05, 50)):
        centre = offset * size * 2
        draw.polygon(
            [
                (centre - width * size, 0),
                (centre + width * size, 0),
                (centre + width * size - size, size),
                (centre - width * size - size, size),
            ],
            fill=(255, 255, 255, alpha),
        )
    return layer.filter(ImageFilter.GaussianBlur(size * 0.02))


def bottle(size: int, scale: float) -> Image.Image:
    """The glyph on a transparent square; `scale` 1 makes the bottle 70% of the height."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    unit = size * 0.0085 * scale  # the glyph is 82 units tall
    cx = size / 2

    def box(left, top, right, bottom):
        return (
            cx + left * unit,
            size / 2 + top * unit,
            cx + right * unit,
            size / 2 + bottom * unit,
        )

    # a faint drop shadow under the bottle
    draw.ellipse(box(-26, 33, 26, 40), fill=(90, 50, 110, 60))
    draw.rounded_rectangle(box(-27, -4, 27, 36), radius=11 * unit, fill=GLASS)  # body
    draw.rounded_rectangle(box(-12, -20, 12, 2), radius=3 * unit, fill=GLASS)  # neck
    draw.rounded_rectangle(box(-15, -42, 15, -14), radius=6 * unit, fill=CAP)  # cap
    draw.rounded_rectangle(box(-9, -37, -5, -19), radius=2 * unit, fill=(255, 255, 255, 70))
    draw.ellipse(box(-12, 10, 12, 22), fill=(247, 168, 207))  # polish window
    return layer


def icon(size: int, *, rounded: bool, glyph_scale: float) -> Image.Image:
    base = gradient(WORK).convert("RGBA")
    base.alpha_composite(sheen(WORK))
    base.alpha_composite(bottle(WORK, glyph_scale))
    if rounded:
        mask = Image.new("L", (WORK, WORK), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, WORK - 1, WORK - 1), radius=WORK * 0.22, fill=255
        )
        base.putalpha(mask)
    return base.resize((size, size), Image.LANCZOS)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("src/polished/static/icons")
    out.mkdir(parents=True, exist_ok=True)
    specs = {
        "apple-touch-icon.png": (180, False, 1.0),
        "icon-192.png": (192, True, 1.0),
        "icon-512.png": (512, True, 1.0),
        "icon-maskable-512.png": (512, False, 0.8),
    }
    for name, (size, rounded, glyph_scale) in specs.items():
        icon(size, rounded=rounded, glyph_scale=glyph_scale).save(out / name, optimize=True)
        print("wrote", out / name)


if __name__ == "__main__":
    main()
