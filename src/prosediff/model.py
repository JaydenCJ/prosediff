"""Data model: sections, documents, and change records.

A Markdown document is modeled as a tree of :class:`Section` nodes plus a
flat, document-ordered list of the same nodes. All diffing happens on the
flat list; the tree is kept for outlines and for container matching (a
heading whose own body is empty is identified by its subtree text).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Titles used for the pseudo-sections that hold content appearing before the
# first real heading. They are matched by path like any other section.
PREAMBLE_TITLE = "(preamble)"
FRONT_MATTER_TITLE = "(front matter)"

# The set of change kinds `classify()` can produce, in rendering order of
# severity. "rewritten" means the body changed *and* the section was also
# moved or renamed — the compound case generic diffs shred into noise.
CHANGE_KINDS = (
    "added",
    "removed",
    "rewritten",
    "edited",
    "renamed",
    "moved",
    "unchanged",
)


@dataclass
class Section:
    """One heading and the prose it owns (child sections excluded)."""

    level: int  # 1-6 for headings, 0 for preamble/front-matter pseudo nodes
    title: str  # heading text as written, or a pseudo title
    path: Tuple[str, ...]  # normalized title path from the document root
    start_line: int  # 1-based line of the heading (or first body line)
    body_lines: List[str] = field(default_factory=list)
    children: List["Section"] = field(default_factory=list)
    end_line: int = 0  # 1-based last line of the whole subtree
    index: int = -1  # document-order position among all sections (0-based)

    @property
    def body_text(self) -> str:
        """The section's own prose, child sections excluded."""
        return "\n".join(self.body_lines)

    @property
    def subtree_text(self) -> str:
        """Own prose plus every descendant's heading and prose, in order."""
        parts = [self.body_text]
        for child in self.children:
            parts.append(child.title)
            parts.append(child.subtree_text)
        return "\n".join(p for p in parts if p)

    @property
    def is_pseudo(self) -> bool:
        """True for the preamble / front-matter placeholder sections."""
        return self.level == 0

    @property
    def display_title(self) -> str:
        """`## Title` for real headings, the bare label for pseudo ones."""
        if self.is_pseudo:
            return self.title
        return "#" * self.level + " " + self.title

    @property
    def parent_path(self) -> Tuple[str, ...]:
        return self.path[:-1]


@dataclass
class Document:
    """A parsed Markdown file: a section tree plus its flat projection."""

    name: str
    roots: List[Section] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)  # document order
    line_count: int = 0

    def by_path(self) -> Dict[Tuple[str, ...], List[Section]]:
        """Sections grouped by path; duplicate paths keep document order."""
        table: Dict[Tuple[str, ...], List[Section]] = {}
        for section in self.sections:
            table.setdefault(section.path, []).append(section)
        return table


@dataclass
class InlineOp:
    """One run of an intra-section word diff: equal, delete, or insert."""

    op: str  # "equal" | "delete" | "insert"
    text: str


@dataclass
class Change:
    """The verdict for one section pair (or an unpaired section)."""

    kind: str  # one of CHANGE_KINDS
    old: Optional[Section] = None
    new: Optional[Section] = None
    similarity: Optional[float] = None  # body similarity for matched pairs
    moved: bool = False  # parent changed or reordered among survivors
    renamed: bool = False  # normalized title differs
    matched_by: str = ""  # "path" | "fingerprint" | "similarity"
    inline: Optional[List[InlineOp]] = None  # word diff when the body changed

    @property
    def section(self) -> Section:
        """The most current side: new when present, else old."""
        chosen = self.new if self.new is not None else self.old
        assert chosen is not None
        return chosen


@dataclass
class DocumentDiff:
    """Every change between two documents, in new-document order.

    Changes for sections present in the new document come first, ordered as
    they appear there; removed sections follow, in old-document order. This
    keeps the report readable top-to-bottom against the newer file.
    """

    old: Document
    new: Document
    changes: List[Change] = field(default_factory=list)

    @property
    def counts(self) -> Dict[str, int]:
        table = {kind: 0 for kind in CHANGE_KINDS}
        for change in self.changes:
            table[change.kind] += 1
        return table

    @property
    def has_changes(self) -> bool:
        return any(change.kind != "unchanged" for change in self.changes)
