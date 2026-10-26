"""Ranked, typo-tolerant shade name search (DESIGN 6). Takes a connection; the matching runs in
Python over every shade's title and search_text (a few hundred rows: a query costs about a
millisecond), so a typo needs no index and nothing here can be cached stale.

A shade matches a query in the first of these tiers that fits (smaller is better):

0. the title is the query,
1. the title starts with the query,
2. every query word is a whole word of the title,
3. every query word is the start of a title word ("holo magn"),
4. every query word occurs in the shade's search text (title, handle, tag and collection values),
5. fuzzy: every query word occurs in the search text or is within a few edits of a title word, or the
   query without its spaces is part of the title without its spaces ("onecoat").

Edits are Damerau-Levenshtein distance with adjacent swaps (so "magentic" is one edit from
"magnetic"), per query word: none for words under 4 letters, 1 for 4 to 7, 2 for 8 and more.
Within a tier fewer edits come first (only the fuzzy tier has any), then the shorter title, then
(for the home search and the pickers) shades the household owns and wishlisted ones, then the title.
"""

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from .catalog.parse import fold

EXACT, STARTS, WORDS, PREFIXES, TAGS, FUZZY = range(6)

_NOT_WORD = re.compile(r"[\W_]+")
_WORD = re.compile(r"[^\W_]+")
SQUASH_MIN = 4  # letters in the spaceless query before it may match a spaceless title
SQUASH_ANYWHERE_MIN = 5  # ... and before it may match in the middle of the title


def tokens(text: str) -> list[str]:
    """Folded words of a query; the same folding the stored search_text went through."""
    return [t for t in _NOT_WORD.split(fold(text)) if t]


def allowed_edits(word_length: int) -> int:
    return 0 if word_length < 4 else 1 if word_length < 8 else 2


@lru_cache(maxsize=65536)
def distance(a: str, b: str, limit: int) -> int:
    """Damerau-Levenshtein distance (adjacent swaps count once), or limit + 1 when it is more."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    before_last: list[int] = []
    last = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        row = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            best = min(last[j] + 1, row[j - 1] + 1, last[j - 1] + (ca != cb))
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                best = min(best, before_last[j - 2] + 1)
            row[j] = best
        if min(row) > limit:
            return limit + 1
        before_last, last = last, row
    return last[-1]


@lru_cache(maxsize=65536)
def word_edits(query_word: str, title_word: str) -> int | None:
    """0 when the title word starts with the query word, else its edit distance if that is allowed
    for a word of this length, else None."""
    if title_word.startswith(query_word):
        return 0
    limit = allowed_edits(len(query_word))
    if not limit:
        return None
    edits = distance(query_word, title_word, limit)
    return edits if edits <= limit else None


@dataclass(frozen=True, slots=True)
class _Entry:
    norm: str  # the title's words joined by single spaces
    words: tuple[str, ...]
    squashed: str  # ... joined by nothing
    text: str  # search_text


@lru_cache(maxsize=16384)
def _entry(title: str, search_text: str) -> _Entry:
    words = tuple(tokens(title))
    return _Entry(" ".join(words), words, "".join(words), search_text)


def _match(entry: _Entry, query_words: list[str], query_norm: str) -> tuple[int, int] | None:
    """(tier, edits) of the best tier the shade fits, None when it does not match."""
    if entry.norm == query_norm:
        return EXACT, 0
    if entry.norm.startswith(query_norm):
        return STARTS, 0
    words = entry.words
    if all(q in words for q in query_words):
        return WORDS, 0
    if all(any(w.startswith(q) for w in words) for q in query_words):
        return PREFIXES, 0
    if all(q in entry.text for q in query_words):
        return TAGS, 0
    total = 0
    for q in query_words:
        if q in entry.text:
            continue
        costs = [c for w in words if (c := word_edits(q, w)) is not None]
        if not costs:
            break
        total += min(costs)
    else:
        return FUZZY, total
    squashed = "".join(query_words)
    if (len(squashed) >= SQUASH_MIN and entry.squashed.startswith(squashed)) or (
        len(squashed) >= SQUASH_ANYWHERE_MIN and squashed in entry.squashed
    ):
        return FUZZY, 0
    return None


def rank(conn: sqlite3.Connection, text: str, owned_first: bool = False) -> list[int]:
    """The ids of the shades matching `text`, best first (the module docstring has the order).
    `owned_first` puts shades the household owns, then wishlisted ones, ahead of the others whose
    tier, edits and title length are the same. Empty for a query without words."""
    query_words = tokens(text)
    if not query_words:
        return []
    query_norm = " ".join(query_words)
    found = []
    for row in conn.execute(
        "select s.id, s.title, s.search_text, coalesce(ss.owned_count > 0, 0) as owned,"
        " coalesce(ss.wishlisted, 0) as wished"
        " from shade s left join shade_status ss on ss.shade_id = s.id"
    ):
        entry = _entry(row["title"], row["search_text"])
        match = _match(entry, query_words, query_norm)
        if match is not None:
            standing = (-row["owned"], -row["wished"]) if owned_first else (0, 0)
            found.append((*match, len(entry.norm), *standing, row["title"].casefold(), row["id"]))
    found.sort()
    return [item[-1] for item in found]


def _folded_with_origin(title: str) -> tuple[str, list[int]]:
    """The folded title and, for each character of it, the index of the character it came from."""
    folded: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(title):
        piece = fold(char)
        folded.append(piece)
        origin.extend([index] * len(piece))
    return "".join(folded), origin


def marks(title: str, text: str) -> list[tuple[int, int]]:
    """Character spans of `title` that the query words matched, for the result rows: a whole word
    for an exact or near match, the typed part of a word the query only starts. Sorted, not
    overlapping; empty when nothing in the title matches by word (a tag match, a missing space)."""
    query_words = tokens(text)
    if not query_words:
        return []
    folded, origin = _folded_with_origin(title)
    spans: list[tuple[int, int]] = []
    for word in _WORD.finditer(folded):
        for q in query_words:
            edits = word_edits(q, word.group())
            if edits is None:
                continue
            end = word.start() + len(q) if edits == 0 else word.end()
            end = min(end, word.end())
            spans.append((origin[word.start()], origin[end - 1] + 1))
            break
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        while end < len(title) and unicodedata.combining(title[end]):
            end += 1
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
