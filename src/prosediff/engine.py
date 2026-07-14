"""Diff orchestration: parse, match, classify, and assemble the report.

The classification rules (given a matched pair):

============  =============  ===========  ==============
body changed  title changed  moved        kind
============  =============  ===========  ==============
no            no             no           ``unchanged``
no            no             yes          ``moved``
no            yes            any          ``renamed``
yes           no             no           ``edited``
yes           any-yes        any          ``rewritten``
============  =============  ===========  ==============

"moved" means the section's parent heading changed *or* it broke document
order among the sections that survived (computed with an LIS, so moving one
section blames one section). "rewritten" is the compound case — the body
changed *and* the section also moved or was renamed — which is exactly what
a line diff renders as an unreadable delete-plus-add wall.
"""

from __future__ import annotations

from typing import List

from .inline import inline_diff
from .matcher import DEFAULT_THRESHOLD, Pair, match_documents, mark_reordered
from .model import Change, Document, DocumentDiff
from .parser import parse_file, parse_text


def diff_documents(
    old: Document,
    new: Document,
    threshold: float = DEFAULT_THRESHOLD,
    with_inline: bool = True,
) -> DocumentDiff:
    """Compare two parsed documents and return the full change report."""
    result = match_documents(old, new, threshold=threshold)
    reordered = mark_reordered(result.pairs)

    changes: List[Change] = []
    for pair, broke_order in zip(result.pairs, reordered):
        changes.append(_classify(pair, broke_order, with_inline))
    for section in result.added:
        changes.append(Change(kind="added", new=section))
    for section in result.removed:
        changes.append(Change(kind="removed", old=section))

    changes.sort(key=_report_order)
    return DocumentDiff(old=old, new=new, changes=changes)


def _report_order(change: Change):
    """New-document order first; removed sections trail in old order."""
    if change.new is not None:
        return (0, change.new.index)
    assert change.old is not None
    return (1, change.old.index)


def _classify(pair: Pair, broke_order: bool, with_inline: bool) -> Change:
    body_same = pair.similarity >= 1.0
    renamed = pair.old.title != pair.new.title
    moved = pair.old.parent_path != pair.new.parent_path or broke_order

    if body_same:
        if renamed:
            kind = "renamed"
        elif moved:
            kind = "moved"
        else:
            kind = "unchanged"
    else:
        kind = "rewritten" if (renamed or moved) else "edited"

    inline = None
    if not body_same and with_inline:
        # Blank edges around a body are heading spacing, not prose; keep
        # them out of the word diff so reports start at the first sentence.
        inline = inline_diff(
            pair.old.body_text.strip("\n"), pair.new.body_text.strip("\n")
        )

    return Change(
        kind=kind,
        old=pair.old,
        new=pair.new,
        similarity=round(pair.similarity, 4),
        moved=moved,
        renamed=renamed,
        matched_by=pair.matched_by,
        inline=inline,
    )


def diff_text(
    old_text: str,
    new_text: str,
    old_name: str = "old",
    new_name: str = "new",
    threshold: float = DEFAULT_THRESHOLD,
    with_inline: bool = True,
) -> DocumentDiff:
    """Convenience wrapper: diff two Markdown strings."""
    return diff_documents(
        parse_text(old_text, name=old_name),
        parse_text(new_text, name=new_name),
        threshold=threshold,
        with_inline=with_inline,
    )


def diff_files(
    old_path: str,
    new_path: str,
    threshold: float = DEFAULT_THRESHOLD,
    with_inline: bool = True,
) -> DocumentDiff:
    """Convenience wrapper: diff two Markdown files on disk."""
    return diff_documents(
        parse_file(old_path),
        parse_file(new_path),
        threshold=threshold,
        with_inline=with_inline,
    )
