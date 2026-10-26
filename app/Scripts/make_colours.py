"""Writes Polished/Resources/Colors.xcassets (and the AccentColor of Assets.xcassets) from the v3
palette: docs/advice/fable-v3-web-2026-10-26.md 2.2 and docs/NATIVE.md 5.6. Light, dark, and an
increased-contrast variant of each.

    python3 app/Scripts/make_colours.py
"""

import json
import shutil
from pathlib import Path

RESOURCES = Path(__file__).resolve().parent.parent / "Polished" / "Resources"

# name: (light, dark, light high contrast, dark high contrast); None repeats the plain value.
# A hex is #rrggbb or #rrggbbaa.
PALETTE = {
    "Board": ("#f7f3f2", "#160b14", None, None),
    "Surface": ("#fefcfb", "#20131d", None, None),
    "Fill": ("#efe8e6", "#30212c", None, None),
    "Fill2": ("#e6dcd9", "#3a2b36", None, None),
    # Increased contrast: Line takes Line2's values, Line2 goes darker, Ink2 becomes Ink.
    "Line": ("#e3dad8", "#372834", "#c9bcb9", "#4d3c49"),
    "Line2": ("#c9bcb9", "#4d3c49", "#9d8e8b", "#6a5866"),
    "Ink": ("#2a1623", "#f7eff5", None, None),
    "Ink2": ("#6e5a63", "#b7a4b2", "#2a1623", "#f7eff5"),
    "Ink3": ("#8f7d86", "#92808d", None, None),
    "Primary": ("#381531", "#f7eff5", None, None),
    "PrimaryOn": ("#ffffff", "#280c23", None, None),
    "Heart": ("#d83486", "#ff77b4", None, None),
    "OK": ("#007840", "#61da92", None, None),
    "Warn": ("#975800", "#f9b64f", None, None),
    "Bad": ("#be222a", "#ff7f7f", None, None),
    # The hero plate: Surface in light (the hero sits on the group), near-black in dark.
    "Velvet": ("#fefcfb", "#0f070e", None, None),
    # rgb(40 20 30) in light, black in dark: the channels of every shadow.
    "ShadowInk": ("#28141e", "#000000", None, None),
    # The 1 pt outline of a painted tip and its lit edge: oklch(0 0 0 / .1) / oklch(1 0 0 / .1), and
    # oklch(1 0 0 / .55) / oklch(1 0 0 / .26).
    "Mat": ("#0000001a", "#ffffff1a", None, None),
    "Rim": ("#ffffff8c", "#ffffff42", None, None),
}
ACCENT = ("#2a1623", "#f7eff5", None, None)  # the app tint is Ink


def components(value: str) -> dict:
    alpha = int(value[7:9], 16) / 255 if len(value) == 9 else 1.0
    return {
        "color-space": "srgb",
        "components": {
            "red": f"0x{value[1:3].upper()}",
            "green": f"0x{value[3:5].upper()}",
            "blue": f"0x{value[5:7].upper()}",
            "alpha": f"{alpha:.3f}",
        },
    }


def colorset(light, dark, light_high, dark_high) -> dict:
    light_high = light_high or light
    dark_high = dark_high or dark
    entries = [
        ([], light),
        ([{"appearance": "luminosity", "value": "dark"}], dark),
        ([{"appearance": "contrast", "value": "high"}], light_high),
        (
            [
                {"appearance": "luminosity", "value": "dark"},
                {"appearance": "contrast", "value": "high"},
            ],
            dark_high,
        ),
    ]
    colors = []
    for appearances, value in entries:
        entry = {"idiom": "universal", "color": components(value)}
        if appearances:
            entry = {"appearances": appearances, **entry}
        colors.append(entry)
    return {"colors": colors, "info": {"author": "xcode", "version": 1}}


def write(directory: Path, values) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Contents.json").write_text(json.dumps(colorset(*values), indent=2) + "\n")


def main() -> None:
    catalog = RESOURCES / "Colors.xcassets"
    if catalog.exists():
        shutil.rmtree(catalog)
    catalog.mkdir(parents=True)
    (catalog / "Contents.json").write_text(
        json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n"
    )
    for name, values in PALETTE.items():
        write(catalog / f"{name}.colorset", values)
    assets = RESOURCES / "Assets.xcassets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "Contents.json").write_text(
        json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n"
    )
    write(assets / "AccentColor.colorset", ACCENT)
    print("wrote", catalog, "and", assets / "AccentColor.colorset")


if __name__ == "__main__":
    main()
