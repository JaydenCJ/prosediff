"""Text normalization, fingerprints, and similarity scoring.

Two levels of comparison are used throughout prosediff:

* **Fingerprint equality** — case-sensitive but whitespace-insensitive. Two
  bodies with the same fingerprint are treated as *identical prose*, which
  is what makes pure moves detectable.
* **Token similarity** — a 0.0-1.0 ratio over lowercased word tokens, used
  to pair up sections whose prose was rewritten. Lowercasing keeps a
  capitalization pass from masking an otherwise-obvious rewrite pairing.
"""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import List, Sequence

_WS_RUN = re.compile(r"[ \t]+")
_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def normalize_block(text: str) -> str:
    """Canonicalize a block of prose for identity comparison.

    Collapses runs of spaces/tabs, strips trailing whitespace per line, and
    drops leading/trailing blank lines. Line *breaks* inside the block are
    preserved: reflowing a paragraph is a real edit, re-indenting is not.
    """
    lines = [_WS_RUN.sub(" ", line).strip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def fingerprint(text: str) -> str:
    """Stable hex digest of the normalized block; '' for empty prose.

    The empty-string sentinel matters: empty bodies must never fingerprint-
    match each other, or every bare container heading would pair with every
    other one.
    """
    normalized = normalize_block(text)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def tokens(text: str) -> List[str]:
    """Lowercased word/punctuation tokens for similarity scoring."""
    return _TOKEN.findall(text.lower())


def similarity(a: Sequence[str], b: Sequence[str]) -> float:
    """Similarity ratio between two token sequences, 0.0-1.0.

    Uses difflib with autojunk disabled (autojunk mis-scores prose where a
    common word repeats more than 1% of the time, which is most prose).
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    return matcher.ratio()


def title_key(title: str) -> str:
    """Normalized form of a heading title used for path identity."""
    return _WS_RUN.sub(" ", title).strip()
