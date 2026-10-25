"""Printed-code normalisation (DESIGN 7.1). Stage 5 adds resolve() and learn() here."""

import re

_PRINTED = re.compile(r"[A-Z]{1,2}\d{1,5}")


def normalise_printed(raw: str) -> str | None:
    """Strip, uppercase, remove spaces; all digits gets the prefix `P`; the result must be one
    or two letters and one to five digits. "259" and "p 259" are "P259"; "hello" is None."""
    text = "".join(raw.split()).upper()
    if text.isdigit():
        text = "P" + text
    return text if _PRINTED.fullmatch(text) else None
