"""Files the browser flows and the two smoke tests feed to the page: a stand-in for the shop's
product photos and the generated barcode pictures."""

from pathlib import Path

UPC = "810170284120"
GTIN = "0810170284120"

# A 1x1 transparent PNG: product thumbnails are hotlinked from Shopify's CDN, which a test
# should not hit.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


def make_images(directory: Path) -> tuple[Path, Path]:
    """The barcode as a PNG (for the photo input) and as a few-frame MJPEG file (a fake camera).
    Needs python-barcode and pillow (imported here so the builder smoke test, which has neither,
    can still use PIXEL)."""
    from barcode import UPCA
    from barcode.writer import ImageWriter
    from PIL import Image

    code = directory / "upca"
    UPCA(UPC[:-1], writer=ImageWriter()).save(str(code), {"quiet_zone": 6.5, "module_height": 18})
    barcode = Image.open(f"{code}.png").convert("RGB")
    photo = directory / "barcode.png"
    barcode.save(photo)

    frame = Image.new("RGB", (1280, 720), "white")
    scale = 560 / barcode.width
    resized = barcode.resize((560, round(barcode.height * scale)))
    frame.paste(resized, ((1280 - resized.width) // 2, (720 - resized.height) // 2))
    jpeg = directory / "frame.jpg"
    frame.save(jpeg, quality=92)
    mjpeg = directory / "camera.mjpeg"
    mjpeg.write_bytes(jpeg.read_bytes() * 30)
    return photo, mjpeg
