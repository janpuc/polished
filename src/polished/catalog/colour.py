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
LIVELY_CHROMA = 18.0
MURKY_CHROMA = 12.0
COLOURED_CHROMA = 25.0
BOTTLE_LIT_L = 22.0
BOTTLE_MIN_LIT_SHARE = 0.15

# Skin, light to dark, as a band of CIE LCh: hue in degrees, chroma. Nude and brown polishes fall
# in it too, which is why a skin-like swatch colour is only trusted when the bottle agrees.
SKIN_HUE = (20.0, 70.0)
SKIN_CHROMA = (5.0, 36.0)
SKIN_MIN_L = 22.0
SKIN_MAX_L = 72.0
# Single pixels are judged more narrowly: a dark red polish (hue 20-35) is not told from shadowed
# skin pixel by pixel, only as a whole colour against the bottle.
PIXEL_SKIN_HUE = (36.0, 75.0)
PIXEL_SKIN_CHROMA = (6.0, 45.0)
PIXEL_SKIN_MIN_L = 22.0
SKIN_MAX_L = 72.0
SOURCES_DISAGREE_DELTA_E = 20.0
# Very dark, grey pixels are the backdrop of a photo when they are a minority of the region; when
# they are most of it they are the polish (black, or a dark glitter whose base is nearly black).
DARK_L = 12.0
DARK_CHROMA = 12.0
DARK_BACKDROP_MAX_SHARE = 0.2

# Base coats and clear top coats are sheer: no sampling, one neutral.
SHEER_HEX = "#f1e9e6"
SPARKLING_FINISHES = frozenset(
    {"glitter", "flakie", "holographic", "iridescent", "shimmer", "metallic", "reflective",
     "magnetic", "chrome"}
)  # fmt: skip

# Shades whose photos defeat the sampler, checked by eye against the product photos on 2026-10-25:
# a topper shot beside the blue bottle logo, a bottle on a beach backdrop, pink and champagne
# chromes worn on darker skin. Used instead of sampling; the household's own override still wins.
KNOWN_COLOURS: dict[str, tuple[str, str | None]] = {
    "gold-flake-taco": ("#d4a84f", None),
    "tax-haven": ("#692c24", "#ce6e2f"),
    "solo-mission": ("#df7e74", "#ce78a6"),
    "pink-steel": ("#d8a2b8", "#7e5262"),
    "trophy-life": ("#c9b48c", "#7d6a4c"),
}

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


def _skin_like(
    lab: np.ndarray,
    hue_band: tuple[float, float] = SKIN_HUE,
    chroma_band: tuple[float, float] = SKIN_CHROMA,
    min_l: float = SKIN_MIN_L,
    max_l: float = 100.0,
) -> np.ndarray:
    """Which Lab rows lie in the skin band (light to dark skin, warm hue, low to middling chroma)."""
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    hue = np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360
    return (
        (hue >= hue_band[0])
        & (hue <= hue_band[1])
        & (chroma >= chroma_band[0])
        & (chroma <= chroma_band[1])
        & (lab[:, 0] >= min_l)
        & (lab[:, 0] <= max_l)
    )


def _skin_pixels(lab: np.ndarray) -> np.ndarray:
    return _skin_like(lab, PIXEL_SKIN_HUE, PIXEL_SKIN_CHROMA, PIXEL_SKIN_MIN_L)


def is_skin_hex(hex_colour: str) -> bool:
    return bool(_skin_like(_hex_lab(hex_colour), max_l=SKIN_MAX_L)[0])


def _keep(rgb: np.ndarray, *, bottle: bool) -> np.ndarray:
    """Pixels that are polish: not skin, not a blown-out highlight, not a dark backdrop (unless it is most of
    the region: black polish) and (on a bottle shot) not the black cap shadow. A mask
    that would keep almost nothing is not applied, so a nude or white polish still gets a colour."""
    lab = rgb_to_lab(rgb)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    glare = (lab[:, 0] > 95) & (chroma < 6)
    dark = (lab[:, 0] < DARK_L) & (chroma < DARK_CHROMA)
    keep = ~glare
    if bottle:
        # The glass is lit, the gaps between glass, cap and backdrop are black: the lit pixels are
        # the colour when there are enough of them, else the polish itself is dark.
        lit = keep & (lab[:, 0] > BOTTLE_LIT_L)
        keep &= lab[:, 0] > 9
        if lit.mean() >= BOTTLE_MIN_LIT_SHARE:
            keep = lit
    else:
        keep &= ~_skin_pixels(lab)
        if dark.mean() < DARK_BACKDROP_MAX_SHARE:
            keep &= ~dark
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


def cluster_colours(
    rgb: np.ndarray,
    *,
    accent: bool = False,
    min_second_l: float = 0.0,
    shun_skin: bool = False,
    shun_grey: bool = False,
) -> Colours:
    """The dominant colour and, when a clearly different one covers a fifth of the pixels, the
    second (not darker than `min_second_l`: the shadow side of a glass bottle is not a colour of
    the polish). `accent` (toppers, shot over a base) puts the livelier cluster first, because the
    dominant one is then the base underneath, not the shade. `shun_skin` (swatch photos) puts a
    cluster that is not skin-like (and at least a fifth of the pixels) before one that is. `shun_grey`
    (bottle shots) puts a clearly coloured cluster before a murky grey one: grey glass is the dark
    gaps and the backdrop showing through a jelly or a flakie."""
    lab = rgb_to_lab(rgb)
    labels = _two_clusters(lab)
    groups = []
    for k in (0, 1):
        members = labels == k
        if members.any():
            groups.append((members.mean(), np.median(rgb[members], axis=0), lab[members].mean(0)))
    groups.sort(key=lambda g: g[0], reverse=True)
    if accent and len(groups) == 2:
        # Two near-greys (a glow polish: pale ghost, dark nail) are told apart by lightness.
        muted = max(_chroma(g[2][None]) for g in groups) < LIVELY_CHROMA
        groups.sort(key=lambda g: (0.0 if muted else _chroma(g[2][None]), g[2][0]), reverse=True)
    if shun_skin and len(groups) == 2:
        skin = [bool(_skin_pixels(g[2][None])[0]) for g in groups]
        if skin[0] and not skin[1] and groups[1][0] >= SECOND_COLOUR_SHARE:
            groups.reverse()
    if shun_grey and len(groups) == 2:
        grey, coloured = _chroma(groups[0][2][None]), _chroma(groups[1][2][None])
        if (
            grey < MURKY_CHROMA
            and coloured > COLOURED_CHROMA
            and groups[1][0] >= SECOND_COLOUR_SHARE
        ):
            groups.reverse()
    first = groups[0]
    second = None
    if len(groups) == 2:
        share, colour, centre = groups[1]
        delta = float(np.linalg.norm(first[2] - centre))
        if (
            share >= SECOND_COLOUR_SHARE
            and delta > SECOND_COLOUR_DELTA_E
            and centre[0] >= min_second_l
            and not (
                shun_skin and _skin_like(centre[None], PIXEL_SKIN_HUE, PIXEL_SKIN_CHROMA, 0.0)[0]
            )
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
        rgb,
        accent=accent,
        min_second_l=BOTTLE_MIN_SECOND_L if from_bottle else 0.0,
        shun_skin=not from_bottle,
        shun_grey=from_bottle,
    )


def _hex_lab(*hexes: str) -> np.ndarray:
    rgb = np.array([[int(h[i : i + 2], 16) for i in (1, 3, 5)] for h in hexes], dtype=np.float64)
    return rgb_to_lab(rgb)


def _delta_e(hex_a: str, hex_b: str) -> float:
    lab = _hex_lab(hex_a, hex_b)
    return float(np.linalg.norm(lab[0] - lab[1]))


def agree_colours(swatch: Colours, bottle: Colours | None) -> Colours:
    """A swatch photo shows the polish on a hand, so its colour can be the skin. When it is
    skin-like and the bottle's glass is not (or is far from it), the glass is the better witness;
    a nude that both photos show stays as it is."""
    if bottle is None or not is_skin_hex(swatch.hex):
        return swatch
    if not is_skin_hex(bottle.hex) or _delta_e(swatch.hex, bottle.hex) > SOURCES_DISAGREE_DELTA_E:
        return _lit_first(bottle)
    return swatch


def _lit_first(bottle: Colours) -> Colours:
    """A chrome bottle is mostly black glass and reflections: its lit colour is the polish."""
    lab = _hex_lab(bottle.hex)[0]
    if bottle.hex2 and lab[0] < BOTTLE_MIN_SECOND_L and np.hypot(lab[1], lab[2]) < 5:
        return Colours(bottle.hex2, bottle.hex)
    return bottle


def is_sheer(kind: str, colour_tags: set[str], finish_tags: set[str]) -> bool:
    """Base coats, and top coats and other clear polishes with nothing sparkling in them."""
    if kind == "basecoat":
        return True
    return (
        bool(colour_tags)
        and colour_tags <= {"clear", "neutral"}
        and "clear" in colour_tags
        and not finish_tags & SPARKLING_FINISHES
    )


def shade_colours(
    swatch: bytes | None, hero: Callable[[], bytes | None], *, accent: bool = False
) -> Colours:
    """The colours of one shade from its photos: the swatch photo checked against the bottle shot,
    which is fetched (`hero()`) only when the swatch colour looks like skin, else whichever there is."""
    if swatch is None:
        hero_bytes = hero()
        if hero_bytes is None:
            raise ValueError("a shade needs a photo")
        return extract_colours(hero_bytes, from_bottle=True, accent=accent)
    from_swatch = extract_colours(swatch, from_bottle=False, accent=accent)
    if not is_skin_hex(from_swatch.hex):
        return from_swatch
    hero_bytes = hero()
    if hero_bytes is None:
        return from_swatch
    return agree_colours(from_swatch, extract_colours(hero_bytes, from_bottle=True, accent=accent))


def cdn_url(url: str) -> str:
    return f"{url}{'&' if '?' in url else '?'}width={SOURCE_WIDTH}"


def pending(
    conn: sqlite3.Connection, *, recompute: bool = False, only: list[str] | None = None
) -> list[sqlite3.Row]:
    """Shades whose colour was never read, or was read from another picture than the one now
    chosen; with `recompute`, every shade (or those titled in `only`). Manual shades have no photo
    and stay without."""
    where = "coalesce(swatch_image_url, hero_image_url) is not null"
    params: list[object] = []
    if not recompute:
        where += " and coalesce(swatch_hex_src, '') != coalesce(swatch_image_url, hero_image_url)"
    if only:
        where += f" and lower(title) in ({','.join('?' * len(only))})"
        params += [title.strip().lower() for title in only]
    params.append(MAX_PER_RUN)
    return conn.execute(
        "select id, handle, kind, is_topper, swatch_image_url, hero_image_url, swatch_hex_src"
        " from shade"
        f" where {where} order by id limit ?",
        params,
    ).fetchall()


def _tags(conn: sqlite3.Connection, shade_id: int, ns: str) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            "select value from shade_tag where shade_id = ? and ns = ?", (shade_id, ns)
        )
    }


def fill_colours(
    conn: sqlite3.Connection,
    *,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
    recompute: bool = False,
    only: list[str] | None = None,
) -> int:
    """Reads and stores the colours of the pending shades; returns how many it stored. Never
    raises: a bad picture is logged and tried again next sync, and a run of failures (the CDN is
    down) ends the step. `recompute` reads every shade again; the manual override is never written."""
    rows = pending(conn, recompute=recompute, only=only)
    if not rows:
        return 0
    stored = failures = downloads = 0
    try:
        with httpx.Client(
            transport=transport,
            timeout=CDN_TIMEOUT_S,
            headers={"User-Agent": "polished/colour (household nail polish inventory)"},
        ) as client:

            def download(url: str) -> bytes:
                nonlocal downloads
                if downloads:
                    sleep(CDN_INTERVAL_S)
                downloads += 1
                response = client.get(cdn_url(url))
                response.raise_for_status()
                return response.content

            for row in rows:
                swatch_url, hero_url = row["swatch_image_url"], row["hero_image_url"]
                source = swatch_url or hero_url
                known = KNOWN_COLOURS.get(row["handle"] or "")
                if known:
                    colours = Colours(*known)
                elif is_sheer(
                    row["kind"], _tags(conn, row["id"], "color"), _tags(conn, row["id"], "finish")
                ):
                    colours = Colours(SHEER_HEX, None)
                else:
                    try:
                        colours = shade_colours(
                            download(swatch_url) if swatch_url else None,
                            lambda url=hero_url: download(url) if url else None,
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
