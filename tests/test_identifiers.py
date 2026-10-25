import pytest

from polished.identifiers import normalise_printed


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("259", "P259"),
        ("p259", "P259"),
        (" P 259 ", "P259"),
        ("pp12", "PP12"),
        ("12345", "P12345"),
        ("123456", None),
        ("hello", None),
        ("P", None),
        ("", None),
        ("P25-9", None),
    ],
)
def test_normalise_printed(raw, expected):
    assert normalise_printed(raw) == expected
