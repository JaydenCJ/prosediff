"""Word-level inline diff for a rewritten section body.

The body is split into alternating word / whitespace tokens so the diff can
be re-joined into readable prose with the original spacing intact. Adjacent
runs with the same operation are merged, which keeps the op list short and
the rendered output calm.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List

from .model import InlineOp

_WORD_OR_SPACE = re.compile(r"\S+|\s+")


def _split(text: str) -> List[str]:
    return _WORD_OR_SPACE.findall(text)


def inline_diff(old_text: str, new_text: str) -> List[InlineOp]:
    """Word-level ops turning ``old_text`` into ``new_text``.

    Whitespace tokens participate in matching (so a reflow shows up as a
    change) but a pure-whitespace delete/insert run is folded into an
    "equal" of the new side's spacing — nobody reviews a diff of spaces.
    """
    old_tokens = _split(old_text)
    new_tokens = _split(new_text)
    matcher = SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)

    ops: List[InlineOp] = []
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        old_run = "".join(old_tokens[a0:a1])
        new_run = "".join(new_tokens[b0:b1])
        if tag == "equal":
            _push(ops, "equal", old_run)
        elif tag == "delete":
            if old_run.strip():
                _push(ops, "delete", old_run)
            else:
                _push(ops, "equal", old_run)  # whitespace-only churn
        elif tag == "insert":
            if new_run.strip():
                _push(ops, "insert", new_run)
            else:
                _push(ops, "equal", new_run)
        else:  # replace
            if not old_run.strip() and not new_run.strip():
                _push(ops, "equal", new_run)
                continue
            _push(ops, "delete", old_run)
            _push(ops, "insert", new_run)
    return ops


def _push(ops: List[InlineOp], op: str, text: str) -> None:
    if not text:
        return
    if ops and ops[-1].op == op:
        ops[-1].text += text
    else:
        ops.append(InlineOp(op=op, text=text))


def changed_ratio(ops: List[InlineOp]) -> float:
    """Fraction of characters touched by the diff, 0.0 (identical) to 1.0."""
    total = sum(len(op.text) for op in ops)
    if total == 0:
        return 0.0
    changed = sum(len(op.text) for op in ops if op.op != "equal")
    return changed / total
