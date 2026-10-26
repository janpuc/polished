"""The tip renderer's shared contract (docs/NATIVE.md 4): the pinned drawings, the paint plan, the
random generator and the fixtures under spec/ that the app's tests read."""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from polished import gtin, identifiers, tips
from polished.tips import TipRandom, TipShade

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec"
PINNED = json.loads((Path(__file__).parent / "fixtures" / "tip_svg_sha1.json").read_text())


def load_script():
    spec = importlib.util.spec_from_file_location(
        "make_tip_fixtures", ROOT / "scripts" / "make_tip_fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = load_script()


def load(*parts: str) -> dict:
    return json.loads(SPEC.joinpath(*parts).read_text())


# --- the drawing is pinned ------------------------------------------------------------------


def test_the_pins_belong_to_this_drawing_version():
    assert PINNED["drawing_version"] == tips.DRAWING_VERSION, (
        "bump DRAWING_VERSION with a change to the drawing and regenerate "
        "tests/fixtures/tip_svg_sha1.json (sha1 of render() for every case of "
        "scripts/make_tip_fixtures.py)"
    )
    assert set(PINNED["sha1"]) == set(script.CASES)


@pytest.mark.parametrize("name", list(script.CASES))
def test_render_is_unchanged_for_the_pinned_cases(name):
    """The SVG of each representative recipe is byte-for-byte what it was when the drawing was
    split into ops() and svg() (the cases that use no random numbers still are what the old
    code drew; dust, glitter and flakes moved once with TipRandom)."""
    digest = hashlib.sha1(tips.render(script.CASES[name]).encode()).hexdigest()
    assert digest == PINNED["sha1"][name], f"{name} is drawn differently: bump DRAWING_VERSION"


@pytest.mark.parametrize("name", list(script.CASES))
def test_render_is_svg_of_ops(name):
    layers = script.CASES[name]
    assert tips.render(layers) == tips.svg(tips.ops(layers))


def test_a_paint_plan_is_plain_json():
    for layers in script.CASES.values():
        plan = tips.ops(layers)
        assert json.loads(json.dumps(plan)) == plan


# --- the random generator -------------------------------------------------------------------


def test_the_generator_is_splitmix64():
    assert TipRandom(0).next() == 0xE220A8397B1DCDAF  # the reference first output for seed 0
    rng = TipRandom(2**64 + 3)  # seeds wrap at 64 bits
    assert TipRandom(3).next() == rng.next()


def test_the_generator_helpers_use_random_in_order():
    rng, twin = TipRandom(7), TipRandom(7)
    assert rng.uniform(2, 6) == 2 + 4 * twin.random()
    assert rng.below(10) == int(twin.random() * 10)
    assert rng.choice("abc") == "abc"[int(twin.random() * 3)]
    assert rng.randint(4, 6) == 4 + int(twin.random() * 3)
    assert rng.randrange(5) == int(twin.random() * 5)


@pytest.mark.parametrize("vector", load("tips", "random.json")["vectors"], ids=lambda v: v["seed"])
def test_the_generator_matches_the_recorded_vectors(vector):
    rng = TipRandom(vector["seed"])
    assert [rng.random() for _ in vector["random"]] == vector["random"]
    assert [rng.below(1000) for _ in vector["below_1000"]] == vector["below_1000"]


# --- the fixtures ---------------------------------------------------------------------------


def test_the_fixtures_regenerate_identically():
    for path, data in script.generate().items():
        recorded = json.loads(path.read_text())
        if "source" in data:  # the commit it was recorded at moves with every commit
            assert re.fullmatch(r"tips\.py@[0-9a-f]{7,}|tips\.py@unknown", recorded["source"])
            data, recorded = {**data, "source": ""}, {**recorded, "source": ""}
        assert recorded == data, "run: uv run python scripts/make_tip_fixtures.py"
        assert path.read_text().endswith("}\n")


def test_every_case_of_the_fixture_is_the_plan_of_its_layers():
    recorded = load("tips", "cases.json")
    assert [case["name"] for case in recorded["cases"]] == list(script.CASES)
    for case in recorded["cases"]:
        layers = [
            TipShade(
                id=layer["id"],
                hex=layer["hex"],
                hex2=layer["hex2"],
                finishes=frozenset(layer["finishes"]),
                topper=layer["topper"],
                clear=layer["clear"],
                coats=layer["coats"],
                colours=None if layer["colours"] is None else frozenset(layer["colours"]),
            )
            for layer in case["layers"]
        ]
        assert script.rounded(tips.ops(layers)) == case["ops"], case["name"]


def test_the_cases_cover_every_op_kind_and_fill():
    seen = set()
    for case in load("tips", "cases.json")["cases"]:
        for op in case["ops"]:
            seen.add(op["op"])
            if "fill" in op:
                seen.add(op["fill"]["kind"])
            if "blur" in op:
                seen.add("blur")
            if "rotate" in op:
                seen.add("rotate")
    assert seen == {
        "rect", "dots", "star", "polygon", "path", "ellipse",
        "solid", "linear", "radial", "blur", "rotate",
    }  # fmt: skip


def test_the_plan_numbers_are_rounded_and_the_colours_lowercase():
    text = (SPEC / "tips" / "cases.json").read_text()
    assert not re.search(r"\d\.\d{4,}", text.replace('"source"', ""))
    assert not re.search(r'"#[0-9a-f]*[A-F][0-9a-fA-F]*"', text)


@pytest.mark.parametrize("vector", load("identifiers", "gtin.json")["vectors"], ids=repr)
def test_gtin_vectors(vector):
    assert gtin.normalise_gtin(vector["input"]) == vector["output"]


@pytest.mark.parametrize("vector", load("identifiers", "printed.json")["vectors"], ids=repr)
def test_printed_code_vectors(vector):
    assert identifiers.normalise_printed(vector["input"]) == vector["output"]


def test_the_identifier_vectors_have_accepts_and_rejects():
    for name in ("gtin", "printed"):
        outputs = [v["output"] for v in load("identifiers", f"{name}.json")["vectors"]]
        assert None in outputs and any(out is not None for out in outputs)


# --- the revision ---------------------------------------------------------------------------


def test_the_revision_does_not_depend_on_the_hash_seed():
    """A frozenset's repr varies with PYTHONHASHSEED; the revision (image URLs, ETags, the API's
    Tip.revision) must not change with a server restart."""
    program = (
        "from polished import tips;"
        "s = tips.TipShade(1, '#336699', '#112233', frozenset({'glitter', 'holographic', 'shimmer',"
        " 'flakie', 'creme'}), True, False, 2, frozenset({'blue', 'gold', 'silver', 'pink'}));"
        "print(tips.revision([s, s]))"
    )
    values = {
        subprocess.run(
            [sys.executable, "-c", program],
            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for seed in ("1", "2", "3", "4")
    }
    assert len(values) == 1 and re.fullmatch(r"[0-9a-f]{10}", values.pop())
