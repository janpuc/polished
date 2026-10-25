import pytest

from polished.gtin import check_digit_ok, normalise_gtin


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("810065564276", "0810065564276"),  # UPC-A
        ("0810065564276", "0810065564276"),  # the same code as ZXing reports it (EAN-13)
        ("810170284120", "0810170284120"),  # the Spirit Fingers bottle
        ("0810170284120", "0810170284120"),
        ("4006381333931", "4006381333931"),  # a real EAN-13 stays as it is
        ("96385074", "0000096385074"),  # EAN-8, zero padded
        ("00810170284120", "0810170284120"),  # 14 digits with a leading 0
        ("  810170284120\n", "0810170284120"),  # surrounding whitespace
        ("810 170 284 120", "0810170284120"),  # spaces typed between groups
    ],
)
def test_normalise_gtin_gives_13_digits(raw, expected):
    assert normalise_gtin(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "795203598",  # nine digits: the catalog's non-GTIN values look like this
        "810170284121",  # wrong check digit
        "0810170284121",
        "96385075",  # EAN-8 with a wrong check digit
        "10810170284120",  # 14 digits without a leading 0 is a case code, not a bottle
        "12345678901",  # 11 digits
        "08101702841200",  # 14 digits, leading 0, but the check digit fails
        "81017028412A",
        "",
        "   ",
        "P259",
        "８１０１７０２８４１２０",  # full-width digits are not digits here
    ],
)
def test_normalise_gtin_rejects_what_is_not_a_barcode(raw):
    assert normalise_gtin(raw) is None


def test_the_check_digit_uses_weights_3_and_1_from_the_right():
    assert check_digit_ok("0810170284120")
    assert not check_digit_ok("0810170284121")
