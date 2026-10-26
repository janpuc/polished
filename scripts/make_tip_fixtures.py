"""Records the shared fixtures of the tip renderer and the code normalisers (docs/NATIVE.md 4, 6.1).

    uv run python scripts/make_tip_fixtures.py

Writes spec/tips/cases.json (layer recipes with the paint plan tips.ops() makes of them),
spec/tips/random.json (what TipRandom draws for a few seeds) and spec/identifiers/gtin.json and
printed.json (normalisation vectors). The Swift package must reproduce every value. It also writes
tests/fixtures/tip_svg_sha1.json, the pin on the SVG of every case (tests/test_tips_spec.py). Output
is deterministic; the only thing that changes with the code is the `source` commit. Invented recipes
and catalog fields only.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec"
sys.path.insert(0, str(ROOT / "src"))

from polished import gtin, identifiers, tips  # noqa: E402
from polished.tips import TipRandom, TipShade  # noqa: E402

SEEDS = (0, 1, 7, 259, 2**32 + 5)
DECIMALS = 3


def layer(
    id: int,
    hex: str,
    *finishes: str,
    topper: bool = False,
    hex2: str | None = None,
    clear: bool = False,
    coats: int = 1,
    colours: tuple[str, ...] | None = None,
) -> TipShade:
    return TipShade(
        id,
        hex,
        hex2,
        frozenset(finishes),
        topper,
        clear,
        coats,
        None if colours is None else frozenset(colours),
    )


BLACK = layer(2, "#101010", "creme")
STACK_OF_EIGHT = [
    layer(100, "#c72bb9", "creme"),
    layer(101, "#3b6fb6", "jelly", coats=2),
    layer(102, "#ceaf43", "chrome", "metallic"),
    layer(103, "#71ad44", "flakie", "holographic", topper=True, colours=("green",)),
    layer(104, "#f43b7a", "magnetic"),
    layer(105, "#ffffff", "glitter", topper=True, colours=("clear",)),
    layer(106, "#a59cbb", "iridescent", "shimmer", hex2="#462221"),
    layer(107, "#ffffff", "matte", topper=True, colours=("clear",)),
]
ALONE = ("creme", "jelly", "shimmer", "glitter", "flakie", "magnetic", "holographic")
ALONE += ("iridescent", "thermal", "metallic", "chrome", "reflective", "matte", "duochrome")
TOPPERS = ("creme", "jelly", "shimmer", "glitter", "flakie", "magnetic", "holographic")
TOPPERS += ("iridescent", "thermal", "metallic", "chrome", "reflective")

# name -> layers in painting order. Ids differ so every case has its own dust.
CASES: dict[str, list[TipShade]] = {}
for number, finish in enumerate(ALONE, start=10):
    CASES[f"{finish}_alone"] = [layer(number, "#c72bb9", finish)]
for number, finish in enumerate(TOPPERS, start=30):
    CASES[f"{finish}_topper"] = [layer(number, "#4aa3c7", finish, topper=True)]
CASES.update(
    {
        "jelly_over_black": [BLACK, layer(50, "#336699", "jelly", coats=1)],
        "jelly_three_coats": [layer(51, "#a1215c", "jelly", coats=3)],
        "flakie_over_nothing": [layer(52, "#ff66cc", "flakie", topper=True, colours=("pink",))],
        "flakie_clear_over_nothing": [
            layer(53, "#6c9177", "flakie", topper=True, colours=("silver",))
        ],
        "flakie_over_black": [BLACK, layer(54, "#ff66cc", "flakie", topper=True)],
        "thermal_with_hex2": [layer(55, "#55472d", "thermal", hex2="#123456")],
        "thermal_without_hex2": [layer(56, "#55472d", "thermal")],
        "thermal_topper_with_hex2": [layer(57, "#e0b0c0", "thermal", hex2="#3050a0", topper=True)],
        "matte_top": [layer(58, "#c72bb9", "creme"), layer(59, "#ffffff", "matte", topper=True)],
        "chrome_and_flakie": [
            layer(60, "#ceaf43", "chrome", "metallic"),
            layer(61, "#71ad44", "flakie", "holographic", topper=True, colours=("green",)),
        ],
        "glitter_hex2_holo": [layer(62, "#336699", "glitter", "holographic", hex2="#cc3366")],
        "glitter_topper_over_creme": [
            layer(63, "#d8b4a0", "creme"),
            layer(64, "#ffffff", "glitter", topper=True, colours=("gold",)),
        ],
        "shimmer_dense": [layer(65, "#3b343c", "jelly", "glitter", "holographic", "shimmer")],
        "magnetic_two_layers": [
            layer(66, "#f43b7a", "magnetic"),
            layer(67, "#4aa3c7", "magnetic", topper=True),
        ],
        "duochrome_hex2": [layer(68, "#a59cbb", "creme", hex2="#462221")],
        "eight_layer_stack": STACK_OF_EIGHT,
        "clear_base_alone": [layer(69, "#ffffff", clear=True)],
        "clear_base_under_colour": [
            layer(70, "#aa0000", "creme"),
            layer(71, "#ffffff", clear=True),
        ],
        "no_finish": [layer(72, "#c9bfc0")],
        "empty": [],
    }
)


def layer_json(shade: TipShade) -> dict:
    """The TipShade as the app's Tip model carries it (finishes and colours sorted)."""
    return {
        "id": shade.id,
        "hex": shade.hex,
        "hex2": shade.hex2,
        "finishes": sorted(shade.finishes),
        "topper": shade.topper,
        "clear": shade.clear,
        "coats": shade.coats,
        "colours": None if shade.colours is None else sorted(shade.colours),
    }


def rounded(node):
    """Numbers to 3 decimals, colours lowercase; whole floats stay floats so the file is stable."""
    if isinstance(node, float):
        return round(node, DECIMALS)
    if isinstance(node, str) and node.startswith("#"):
        return node.lower()
    if isinstance(node, dict):
        return {key: rounded(value) for key, value in node.items()}
    if isinstance(node, list | tuple):
        return [rounded(item) for item in node]
    return node


def source() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    return f"tips.py@{head.stdout.strip() or 'unknown'}"


def tip_cases() -> dict:
    return {
        "source": source(),
        "cases": [
            {
                "name": name,
                "layers": [layer_json(s) for s in layers],
                "ops": rounded(tips.ops(layers)),
            }
            for name, layers in CASES.items()
        ],
    }


def random_vectors() -> dict:
    vectors = []
    for seed in SEEDS:
        rng = TipRandom(seed)
        floats = [rng.random() for _ in range(10)]
        below = [rng.below(1000) for _ in range(10)]
        vectors.append({"seed": seed, "random": floats, "below_1000": below})
    return {
        "note": "random: the first ten random() values of TipRandom(seed), full precision; "
        "below_1000: the next ten below(1000) values of the same generator.",
        "vectors": vectors,
    }


GTIN_INPUTS = (
    "810170284120", "0810170284120", "00810170284120", "810170284121", "96385074",
    "96385075", "4006381333931", "4006381333932", " 810 170 284 120 ", "810170284120\n",
    "10810170284127", "", "   ", "abc", "81017028412x", "8101702841", "81017028412011",
    "8101702841200123", "0000000000000", "036000291452", "١٢٣٤٥٦٧٨",
)  # fmt: skip
PRINTED_INPUTS = (
    "259", "p259", "P259", " p 259 ", "P 0259", "ab12", "AB12345", "ABC12", "A", "P", "A123456",
    "123456", "1", "hello", "", "  ", "p-259", "P25.9", "p259x", "é12", "Ａ12",
)  # fmt: skip


def gtin_vectors() -> dict:
    return {
        "note": "normalise_gtin: whitespace removed, 8/12/13/14 digits with a valid GS1 check "
        "digit, 14 digits only with a leading 0; the result is the 13-digit form or null.",
        "vectors": [{"input": raw, "output": gtin.normalise_gtin(raw)} for raw in GTIN_INPUTS],
    }


def printed_vectors() -> dict:
    return {
        "note": "normalise_printed: whitespace removed, uppercased, all digits get the prefix P, "
        "then one or two letters and one to five digits; otherwise null.",
        "vectors": [
            {"input": raw, "output": identifiers.normalise_printed(raw)} for raw in PRINTED_INPUTS
        ],
    }


def svg_pins() -> dict:
    return {
        "drawing_version": tips.DRAWING_VERSION,
        "sha1": {
            name: hashlib.sha1(tips.render(layers).encode()).hexdigest()
            for name, layers in CASES.items()
        },
    }


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def generate() -> dict[Path, dict]:
    return {
        SPEC / "tips" / "cases.json": tip_cases(),
        SPEC / "tips" / "random.json": random_vectors(),
        SPEC / "identifiers" / "gtin.json": gtin_vectors(),
        SPEC / "identifiers" / "printed.json": printed_vectors(),
        ROOT / "tests" / "fixtures" / "tip_svg_sha1.json": svg_pins(),
    }


def main() -> None:
    for path, data in generate().items():
        write(path, data)
        print(f"wrote {path.relative_to(ROOT)}")
    print(f"{len(CASES)} tip cases, {len(SEEDS)} random seeds")


if __name__ == "__main__":
    main()
