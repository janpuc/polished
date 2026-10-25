import unicodedata

import pytest

from polished.catalog.classify import MANUAL_ALIASES, classify
from polished.catalog.parse import (
    fold,
    hero_image_url,
    is_topper,
    parse_compare_at_cents,
    parse_price_cents,
    search_text,
    tag_pairs,
)

EXPECTED_ROLES = {
    "thirst-trap": "shade",
    "thirst-trap-birthday-gift": "alias",
    "gold-play-button": "shade",
    "hit-the-lights": "shade",
    "jam-session": "shade",
    "rest-in-peach": "shade",
    "aurora-unicorn-skin": "shade",
    "aurora-unicorn-skin-birthday-gift": "alias",
    "peely-base": "shade",
    "sticky-base": "shade",
    "brainrot-collection": "bundle",
    "coastal-cremes-collection": "bundle",
    "royal-tea-blue-2021": "shade",
    "royal-tea-blue-birthday-gift": "alias",
    "linear-holo-taco™-birthday-gift": "alias",
    "super-magnet": "skipped",
}


def product(handle="x", product_type="Nail Polish", tags=()):
    return {"handle": handle, "product_type": product_type, "tags": list(tags)}


def test_every_fixture_product_lands_in_the_expected_role(feed):
    roles = {p["handle"]: classify(p).role for p in feed}
    assert roles == EXPECTED_ROLES


def test_fixture_shades_get_the_kind_of_their_product_type(feed):
    kinds = {p["handle"]: classify(p).kind for p in feed if classify(p).role == "shade"}
    assert kinds["aurora-unicorn-skin"] == "topcoat"
    assert kinds["peely-base"] == "basecoat"
    assert kinds["thirst-trap"] == "polish"


def test_gifts_are_classified_before_bundles():
    gift = product("a-birthday-gift", "Birthday Gift", ["bundle:product", "product-bundle"])
    result = classify(gift)
    assert (result.role, result.alias_source, result.alias_target) == ("alias", "handle", "a")


def test_a_bundles_sets_only_product_is_a_bundle():
    assert classify(product(tags=["bundles-sets", "polish"])).role == "bundle"


def test_a_top_coat_or_base_coat_with_no_bundle_tag_is_a_shade():
    assert classify(product(product_type="Top Coat")).kind == "topcoat"
    assert classify(product(product_type="Base Coat")).kind == "basecoat"


def test_other_product_types_are_skipped():
    for product_type in ("Accessories", "Gift Card", "Hats", "Free Gift"):
        assert classify(product(product_type=product_type, tags=["bundle:x"])).role == "skipped"


def test_the_manual_alias_resolves():
    result = classify(product("royal-tea-blue-birthday-gift", "Birthday Gift"))
    assert (result.role, result.alias_source, result.alias_target) == (
        "alias",
        "manual",
        "royal-tea-blue-2021",
    )


def test_the_manual_alias_matches_the_trademark_handle_in_any_unicode_form():
    handle = unicodedata.normalize("NFD", "linear-holo-taco™-birthday-gift")
    result = classify(product(handle, "Birthday Gift"))
    assert (result.alias_source, result.alias_target) == ("manual", "linear-holo-taco")


def test_the_manual_alias_applies_to_any_product_type():
    result = classify(product("royal-tea-blue-birthday-gift", "Nail Polish", ["bundle:product"]))
    assert result.role == "alias"


def test_manual_aliases_are_the_two_known_gifts():
    assert set(MANUAL_ALIASES.values()) == {"linear-holo-taco", "royal-tea-blue-2021"}


def test_prices_become_integer_cents():
    assert parse_price_cents("15.50") == 1550
    assert parse_price_cents("113.00") == 11300
    assert parse_price_cents("0.07") == 7
    assert parse_price_cents(None) is None
    assert parse_price_cents("free") is None


def test_compare_at_is_null_when_absent_or_zero():
    assert parse_compare_at_cents(None) is None
    assert parse_compare_at_cents("0.00") is None
    assert parse_compare_at_cents("16.50") == 1650


def test_tag_pairs_keep_finish_color_and_collection_tags_only():
    tags = [
        "finish:creme",
        "color:red",
        "collection:retirement",
        "collection:x",
        "collection:x",
        "polish",
    ]
    assert tag_pairs(tags) == [
        ("finish", "creme"),
        ("color", "red"),
        ("collection", "retirement"),
        ("collection", "x"),
    ]


@pytest.mark.parametrize(
    ("kind", "tags", "expected"),
    [
        ("topcoat", [], True),
        ("polish", ["color:clear"], True),
        ("polish", ["toppers", "finish:flakie"], True),
        ("polish", ["color:red"], False),
        ("basecoat", ["color:clear"], False),
        ("basecoat", ["toppers"], False),
    ],
)
def test_is_topper(kind, tags, expected):
    assert is_topper(kind, tags) is expected


def test_hero_image_is_the_one_at_position_1():
    images = [{"position": 2, "src": "b"}, {"position": 1, "src": "a"}]
    assert hero_image_url(images) == "a"
    assert hero_image_url([]) is None


def test_search_text_is_lowercase_and_accent_folded():
    assert fold("Crème Brûlée") == "creme brulee"
    text = search_text("Crème Taco", "creme-taco", ["holographic", "new-releases"])
    assert text == "creme taco creme taco holographic new releases"


def test_the_shops_tag_typos_are_folded_into_the_tag_they_meant():
    assert tag_pairs(["color:whte", "color:white", "finish:creme"]) == [
        ("color", "white"),
        ("finish", "creme"),
    ]
