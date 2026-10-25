"""Barcode normalisation (DESIGN 7.1): one canonical 13-digit form for UPC-A, EAN-13 and EAN-8."""

import re

_DIGITS = re.compile(r"[0-9]+")
LENGTHS = (8, 12, 13, 14)
CANONICAL_LENGTH = 13


def is_numeric(raw: str) -> bool:
    """Only digits once whitespace is gone: what the resolver calls "looks like a number"."""
    return _DIGITS.fullmatch("".join(raw.split())) is not None


def check_digit_ok(digits: str) -> bool:
    """GS1 check digit: from the right, the digit before the check is weighted 3, then 1, 3, …
    and the weighted sum, check digit included, is a multiple of ten."""
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (total + check) % 10 == 0


def normalise_gtin(raw: str) -> str | None:
    """Whitespace removed; digits only; 8, 12, 13 or 14 of them with a valid check digit; a
    14-digit value only with a leading 0 (otherwise it is a case or ITF-14 code, not a bottle).
    Returns the 13-digit form: "810170284120" and "0810170284120" both give "0810170284120"."""
    digits = "".join(raw.split())
    if not _DIGITS.fullmatch(digits) or len(digits) not in LENGTHS:
        return None
    if len(digits) == 14:
        if digits[0] != "0":
            return None
        digits = digits[1:]
    if not check_digit_ok(digits):
        return None
    return digits.rjust(CANONICAL_LENGTH, "0")
