"""Section matching: decide which old section became which new section.

Three passes, strictest first, each consuming its matches so later passes
only see the leftovers:

1. **Path pass** — sections whose full heading path is identical are the
   same section, whatever happened to their prose. Duplicate paths are
   already disambiguated by the parser (`' [2]'` suffixes).
2. **Fingerprint pass** — among the unmatched, sections whose prose is
   byte-identical (after whitespace normalization) are the same section
   that moved and/or was renamed. Container headings with no prose of
   their own fall back to their *subtree* fingerprint, so renaming a
   parent heading is one rename, not a delete-plus-add.
3. **Similarity pass** — the remaining sections are paired greedily by
   token-similarity of their prose, best score first, above a threshold.
   This catches the "moved *and* rewritten" case that line diffs shred.

Anything still unmatched is an addition or a removal.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .model import Document, Section
from .textnorm import fingerprint, similarity, tokens

DEFAULT_THRESHOLD = 0.5


@dataclass
class Pair:
    """One matched (old, new) section pair and how it was found."""

    old: Section
    new: Section
    matched_by: str  # "path" | "fingerprint" | "similarity"
    similarity: float  # body similarity, 1.0 when fingerprints agree


@dataclass
class MatchResult:
    pairs: List[Pair]
    removed: List[Section]  # old sections with no counterpart
    added: List[Section]  # new sections with no counterpart


def match_documents(
    old: Document, new: Document, threshold: float = DEFAULT_THRESHOLD
) -> MatchResult:
    """Run all three passes and return the complete pairing."""
    pairs: List[Pair] = []
    old_left = list(old.sections)
    new_left = list(new.sections)

    _match_by_path(old_left, new_left, pairs)
    _match_by_fingerprint(old_left, new_left, pairs)
    _match_by_similarity(old_left, new_left, pairs, threshold)

    pairs.sort(key=lambda pair: pair.new.index)
    return MatchResult(pairs=pairs, removed=old_left, added=new_left)


def _body_similarity(a: Section, b: Section) -> float:
    if fingerprint(a.body_text) == fingerprint(b.body_text):
        return 1.0
    return similarity(tokens(a.body_text), tokens(b.body_text))


def _match_by_path(
    old_left: List[Section], new_left: List[Section], pairs: List[Pair]
) -> None:
    new_by_path: Dict[Tuple[str, ...], Section] = {
        section.path: section for section in new_left
    }
    for old_section in list(old_left):
        new_section = new_by_path.get(old_section.path)
        if new_section is None:
            continue
        pairs.append(
            Pair(
                old=old_section,
                new=new_section,
                matched_by="path",
                similarity=_body_similarity(old_section, new_section),
            )
        )
        old_left.remove(old_section)
        new_left.remove(new_section)


def _fingerprint_key(section: Section) -> Optional[Tuple[str, str]]:
    """Identity key for the fingerprint pass, or None if unusable.

    Sections with prose are keyed on their own body. Prose-less container
    headings are keyed on their subtree, tagged so a container can only
    match another container (a body can never equal a subtree by accident).
    """
    own = fingerprint(section.body_text)
    if own:
        return ("body", own)
    sub = fingerprint(section.subtree_text)
    if sub:
        return ("subtree", sub)
    return None  # empty section: nothing to identify it by


def _match_by_fingerprint(
    old_left: List[Section], new_left: List[Section], pairs: List[Pair]
) -> None:
    buckets: Dict[Tuple[str, str], List[Section]] = {}
    for section in new_left:
        key = _fingerprint_key(section)
        if key is not None:
            buckets.setdefault(key, []).append(section)

    for old_section in list(old_left):
        key = _fingerprint_key(old_section)
        candidates = buckets.get(key) if key is not None else None
        if not candidates:
            continue
        # Prefer a candidate with the same title (pure move) over a rename.
        same_title = [c for c in candidates if c.title == old_section.title]
        new_section = (same_title or candidates)[0]
        candidates.remove(new_section)
        pairs.append(
            Pair(
                old=old_section,
                new=new_section,
                matched_by="fingerprint",
                similarity=1.0,
            )
        )
        old_left.remove(old_section)
        new_left.remove(new_section)


def _match_by_similarity(
    old_left: List[Section],
    new_left: List[Section],
    pairs: List[Pair],
    threshold: float,
) -> None:
    if not old_left or not new_left:
        return
    old_tokens = {id(s): tokens(s.body_text) for s in old_left}
    new_tokens = {id(s): tokens(s.body_text) for s in new_left}

    scored: List[Tuple[float, int, int, Section, Section]] = []
    for old_section in old_left:
        a = old_tokens[id(old_section)]
        if not a:
            continue  # nothing to compare; leave for added/removed
        for new_section in new_left:
            b = new_tokens[id(new_section)]
            if not b:
                continue
            # Cheap upper bound first: skip the O(n*m) ratio when even the
            # best case cannot reach the threshold.
            upper = 2.0 * min(len(a), len(b)) / (len(a) + len(b))
            if upper < threshold:
                continue
            score = similarity(a, b)
            if score >= threshold:
                # Tie-break deterministically by document positions.
                scored.append(
                    (score, -old_section.index, -new_section.index,
                     old_section, new_section)
                )

    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    taken_old: set = set()
    taken_new: set = set()
    for score, _, _, old_section, new_section in scored:
        if id(old_section) in taken_old or id(new_section) in taken_new:
            continue
        taken_old.add(id(old_section))
        taken_new.add(id(new_section))
        pairs.append(
            Pair(
                old=old_section,
                new=new_section,
                matched_by="similarity",
                similarity=score,
            )
        )
        old_left.remove(old_section)
        new_left.remove(new_section)


def mark_reordered(pairs: List[Pair]) -> List[bool]:
    """For pairs sorted by new index: True where the pair broke document order.

    Uses a longest-increasing-subsequence over the old indices, so the
    minimal set of sections is blamed for a reorder — moving one section up
    a 10-section file flags one move, not ten.
    """
    old_order = [pair.old.index for pair in pairs]
    keep = _lis_membership(old_order)
    return [not kept for kept in keep]


def _lis_membership(values: List[int]) -> List[bool]:
    """Membership flags for one longest strictly-increasing subsequence."""
    n = len(values)
    if n == 0:
        return []
    tails: List[int] = []  # tails[k] = index into values of best LIS length k+1
    tail_values: List[int] = []
    prev = [-1] * n
    for i, value in enumerate(values):
        pos = bisect.bisect_left(tail_values, value)
        if pos == len(tail_values):
            tail_values.append(value)
            tails.append(i)
        else:
            tail_values[pos] = value
            tails[pos] = i
        prev[i] = tails[pos - 1] if pos > 0 else -1
    member = [False] * n
    cursor = tails[-1]
    while cursor != -1:
        member[cursor] = True
        cursor = prev[cursor]
    return member
