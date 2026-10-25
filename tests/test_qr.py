import re

from polished import wheels

URL = "https://polished.example.test/w/{}"


def test_the_qr_is_an_svg_document_without_an_xml_declaration():
    svg = wheels.qr_svg(URL.format("k3m9xq"))
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "<?xml" not in svg


def test_the_qr_differs_per_slug():
    assert wheels.qr_svg(URL.format("k3m9xq")) != wheels.qr_svg(URL.format("abc234"))


def test_the_qr_is_the_same_for_the_same_url():
    assert wheels.qr_svg(URL.format("k3m9xq")) == wheels.qr_svg(URL.format("k3m9xq"))


def test_the_qr_is_drawn_at_scale_8_with_a_border_of_2():
    # Version 3 symbol (29 modules) for this URL at error level m: (29 + 2 * 2) * 8 pixels.
    svg = wheels.qr_svg(URL.format("k3m9xq"))
    size = int(re.search(r'width="(\d+)"', svg).group(1))
    assert size % 8 == 0
    assert (size // 8 - 4 - 17) % 4 == 0  # side = 17 + 4 * version, plus the 2-module border
