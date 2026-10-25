"""The colour of each shade's polish, read from its photos (DESIGN 4.3, 5.5).

extract_colours() is pure: JPEG bytes in, two hex colours out. fill_colours() is the sync step
around it: one small download per shade from the Shopify image CDN (never holotaco.com), computed
once and again only when the source image URL changes. A failure leaves the colour as it was.
"""

import io
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import numpy as np
from PIL import Image

log = logging.getLogger("polished.colour")

SOURCE_WIDTH = 240
CDN_INTERVAL_S = 0.5
CDN_TIMEOUT_S = 8.0
GIVE_UP_AFTER = 4  # consecutive failures before the step stops for this run
MAX_PER_RUN = 450

# Fractions of the picture (left, top, right, bottom). A macro or hand shot has the nail in the
# middle; a bottle shot has the glass in the lower half, under the black cap.
SWATCH_BOX = (0.32, 0.30, 0.68, 0.70)
BOTTLE_BOXES = ((0.31, 0.78, 0.69, 0.90), (0.31, 0.58, 0.40, 0.78), (0.60, 0.58, 0.69, 0.78))

SECOND_COLOUR_DELTA_E = 15.0
SECOND_COLOUR_SHARE = 0.20
MIN_KEPT_SHARE = 0.08
BOTTLE_MIN_SECOND_L = 32.0

_D65 = np.array([0.95047, 1.0, 1.08883])


@dataclass(frozen=True)
class Colours:
    hex: str
    hex2: str | None


def to_hex(rgb: np.ndarray) -> str:
    r, g, b = (int(round(float(c))) for c in np.clip(rgb, 0, 255))
    return f"#{r:02x}{g:02x}{b:02x}"


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """(n, 3) sRGB 0..255 to CIE Lab (D65)."""
    linear = rgb / 255.0
    linear = np.where(linear <= 0.04045, linear / 12.92, ((linear + 0.055) / 1.055) ** 2.4)
    matrix = np.array(
        [[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
         [0.0193339, 0.1191920, 0.9503041]]
    )  # fmt: skip
    xyz = (linear @ matrix.T) / _D65
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


def _pixels(image: Image.Image, boxes: tuple[tuple[float, ...], ...]) -> np.ndarray:
    width, height = image.size
    parts = []
    for left, top, right, bottom in boxes:
        crop = image.crop(
            (int(left * width), int(top * height), int(right * width), int(bottom * height))
        )
        parts.append(np.asarray(crop, dtype=np.float64).reshape(-1, 3))
    return np.concatenate(parts)


def _keep(rgb: np.ndarray, *, bottle: bool) -> np.ndarray:
    """Pixels that are polish: not skin, not a blown-out highlight, and (on a bottle shot) not the
    black backdrop. A mask that would keep almost nothing is not applied, so a nude or white
    polish still gets a colour."""
    lab = rgb_to_lab(rgb)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    skin = (cb > 77) & (cb < 127) & (cr > 133) & (cr < 173) & (lab[:, 0] > 35)
    glare = (lab[:, 0] > 95) & (chroma < 6)
    keep = ~glare
    if bottle:
        keep &= lab[:, 0] > 9
    else:
        keep &= ~skin
    if keep.mean() < MIN_KEPT_SHARE:
        keep = ~glare if not bottle else lab[:, 0] > 3
    if keep.sum() == 0:
        keep = np.ones(len(rgb), dtype=bool)
    return rgb[keep]


def _two_clusters(lab: np.ndarray) -> np.ndarray:
    """k-means with k=2 from a deterministic start (the middle, then the farthest point from it
    and the point farthest from that); returns each pixel's cluster, 0 or 1."""
    first = np.median(lab, axis=0)
    far = lab[np.argmax(((lab - first) ** 2).sum(1))]
    near = lab[np.argmax(((lab - far) ** 2).sum(1))]
    centres = np.stack([far, near])
    labels = np.zeros(len(lab), dtype=int)
    for _ in range(12):
        distance = ((lab[:, None, :] - centres[None]) ** 2).sum(2)
        labels = distance.argmin(1)
        for k in (0, 1):
            if (labels == k).any():
                centres[k] = lab[labels == k].mean(0)
    return labels


def _chroma(lab: np.ndarray) -> float:
    return float(np.hypot(lab[:, 1], lab[:, 2]).mean())


def cluster_colours(rgb: np.ndarray, *, accent: bool = False, min_second_l: float = 0.0) -> Colours:
    """The dominant colour and, when a clearly different one covers a fifth of the pixels, the
    second (not darker than `min_second_l`: the shadow side of a glass bottle is not a colour of
    the polish). `accent` (toppers, shot over a base) puts the livelier cluster first, because the
    dominant one is then the base underneath, not the shade."""
    lab = rgb_to_lab(rgb)
    labels = _two_clusters(lab)
    groups = []
    for k in (0, 1):
        members = labels == k
        if members.any():
            groups.append((members.mean(), np.median(rgb[members], axis=0), lab[members].mean(0)))
    groups.sort(key=lambda g: g[0], reverse=True)
    if accent and len(groups) == 2:
        groups.sort(key=lambda g: (_chroma(g[2][None]), g[2][0]), reverse=True)
    first = groups[0]
    second = None
    if len(groups) == 2:
        share, colour, centre = groups[1]
        delta = float(np.linalg.norm(first[2] - centre))
        if (
            share >= SECOND_COLOUR_SHARE
            and delta > SECOND_COLOUR_DELTA_E
            and centre[0] >= min_second_l
        ):
            second = to_hex(colour)
    return Colours(to_hex(first[1]), second)


def extract_colours(data: bytes, *, from_bottle: bool, accent: bool = False) -> Colours:
    """Colours of the polish in a swatch photo (centre of the picture) or a bottle shot (the glass
    under the cap, around the label). Raises ValueError for bytes that are not an image."""
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise ValueError(f"not an image: {exc}") from exc
    boxes = BOTTLE_BOXES if from_bottle else (SWATCH_BOX,)
    rgb = _keep(_pixels(image, boxes), bottle=from_bottle)
    return cluster_colours(
        rgb, accent=accent, min_second_l=BOTTLE_MIN_SECOND_L if from_bottle else 0.0
    )


def cdn_url(url: str) -> str:
    return f"{url}{'&' if '?' in url else '?'}width={SOURCE_WIDTH}"


def pending(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Shades whose colour was never read, or was read from another picture than the one now
    chosen. Manual shades have no photo and stay without."""
    return conn.execute(
        "select id, is_topper, swatch_image_url, hero_image_url, swatch_hex_src from shade"
        " where coalesce(swatch_image_url, hero_image_url) is not null"
        " and coalesce(swatch_hex_src, '') != coalesce(swatch_image_url, hero_image_url)"
        " order by id limit ?",
        (MAX_PER_RUN,),
    ).fetchall()


def fill_colours(
    conn: sqlite3.Connection,
    *,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Reads and stores the colours of the pending shades; returns how many it stored. Never
    raises: a bad picture is logged and tried again next sync, and a run of failures (the CDN is
    down) ends the step."""
    rows = pending(conn)
    if not rows:
        return 0
    stored = failures = 0
    try:
        with httpx.Client(
            transport=transport,
            timeout=CDN_TIMEOUT_S,
            headers={"User-Agent": "polished/colour (household nail polish inventory)"},
        ) as client:
            for index, row in enumerate(rows):
                if index:
                    sleep(CDN_INTERVAL_S)
                source = row["swatch_image_url"] or row["hero_image_url"]
                try:
                    response = client.get(cdn_url(source))
                    response.raise_for_status()
                    colours = extract_colours(
                        response.content,
                        from_bottle=row["swatch_image_url"] is None,
                        accent=bool(row["is_topper"]),
                    )
                except Exception as exc:
                    failures += 1
                    log.warning("colour of shade %d not read: %s", row["id"], exc)
                    if failures >= GIVE_UP_AFTER:
                        log.warning("colour step stopped after %d failures in a row", failures)
                        break
                    continue
                failures = 0
                conn.execute(
                    "update shade set swatch_hex = ?, swatch_hex2 = ?, swatch_hex_src = ?"
                    " where id = ?",
                    (colours.hex, colours.hex2, source, row["id"]),
                )
                stored += 1
    except Exception:
        log.exception("colour step failed")
    return stored
