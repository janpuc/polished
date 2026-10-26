"""Puts the web's tips (web-*.png) beside the app's (sim-*.png), light and dark, into one image
and prints the mean absolute difference per tip (0 to 255, over the painted interior).

    python3 montage.py <dir with web-/sim- pngs> <output.png>
"""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

folder, out = Path(sys.argv[1]), sys.argv[2]
crop = (0, 170, 1206, 2160)  # the tips, 57 pt to 720 pt at 3x
panels = []
for scheme in ("light", "dark"):
    for who in ("web", "sim"):
        image = Image.open(folder / f"{who}-{scheme}.png").convert("RGB").crop(crop)
        panels.append(image.resize((image.width // 2, image.height // 2), Image.LANCZOS))
w, h = panels[0].size
pad = 24
canvas = Image.new("RGB", (w * 4 + pad * 5, h + pad * 2 + 20), "#777")
draw = ImageDraw.Draw(canvas)
for i, (image, label) in enumerate(
    zip(panels, ["web light", "swift light", "web dark", "swift dark"], strict=True)
):
    x = pad + i * (w + pad)
    canvas.paste(image, (x, pad + 20))
    draw.text((x, 6), label, fill="white")
canvas.save(out)

for scheme in ("light", "dark"):
    a = Image.open(folder / f"web-{scheme}.png").convert("RGB")
    b = Image.open(folder / f"sim-{scheme}.png").convert("RGB")
    diffs = []
    for i in range(12):
        x, y = (4 + (i % 4) * 98) * 3 + 30, (90 + (i // 4) * 200) * 3 + 40
        box = (x, y, x + 228, y + 394)
        d = (
            ImageChops.difference(a.crop(box), b.crop(box))
            .resize((1, 1), Image.BOX)
            .getpixel((0, 0))
        )
        diffs.append(round(sum(d) / 3, 1))
    print(scheme, "mean abs diff per tip:", diffs)
print("wrote", out)
