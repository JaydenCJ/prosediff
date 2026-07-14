"""Markdown section parser.

Turns a Markdown file into a :class:`~prosediff.model.Document`: a tree of
sections keyed by heading path, plus a flat document-ordered list. The
parser is deliberately small and covers the constructs that matter for rule
and prompt files:

* ATX headings (``# .. ######``), including closing-hash form (``## X ##``)
  and up to three leading spaces, per CommonMark.
* Setext headings (a paragraph line underlined with ``===`` or ``---``).
* Fenced code blocks (``` or ~~~, any info string) — a ``#`` inside a fence
  is code, not a heading.
* YAML front matter (``---`` fences at the very top), captured as its own
  pseudo-section so metadata edits are reported separately from prose.
* Content before the first heading, captured as a ``(preamble)`` section.

Heading-level jumps (``#`` straight to ``###``) nest under the nearest
shallower section, matching how readers see the outline.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .errors import ParseError
from .model import FRONT_MATTER_TITLE, PREAMBLE_TITLE, Document, Section
from .textnorm import title_key

_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_SETEXT_EQ = re.compile(r"^ {0,3}=+[ \t]*$")
_SETEXT_DASH = re.compile(r"^ {0,3}-{2,}[ \t]*$")
# Lines that can never be the text of a setext heading: blanks, list items,
# blockquotes, other headings, table rows, and indented code.
_NOT_SETEXT_TEXT = re.compile(r"^(\s*$|\s*([-*+>|]|\d+[.)])\s|#{1,6}[ \t]|    )")


def _strip_atx_title(raw: str) -> str:
    """Drop an optional closing-hash sequence: '## Title ##' -> 'Title'."""
    stripped = re.sub(r"[ \t]+#+[ \t]*$", "", raw)
    # A title that is *only* hashes ('## ###') closes to the empty string.
    if re.fullmatch(r"#+", stripped.strip()):
        return ""
    return stripped.strip()


class _TreeBuilder:
    """Accumulates headings and body lines into a section tree."""

    def __init__(self) -> None:
        self.roots: List[Section] = []
        self.flat: List[Section] = []
        self.stack: List[Section] = []  # open sections, shallow -> deep
        self._dup: dict = {}  # path -> occurrences seen, to disambiguate

    def _unique_path(self, path: Tuple[str, ...]) -> Tuple[str, ...]:
        """Suffix repeated sibling paths so each section's path is unique.

        Rule files commonly repeat headings ('## Example' twice); the 2nd
        occurrence gets path suffix ' [2]' so path matching stays 1:1.
        """
        seen = self._dup.get(path, 0)
        self._dup[path] = seen + 1
        if seen == 0:
            return path
        return path[:-1] + (path[-1] + f" [{seen + 1}]",)

    def open_section(self, level: int, title: str, line_no: int) -> None:
        while self.stack and self.stack[-1].level >= level:
            self._close(line_no - 1)
        parent = self.stack[-1] if self.stack else None
        base = (parent.path if parent else ()) + (title_key(title),)
        section = Section(
            level=level,
            title=title_key(title),
            path=self._unique_path(base),
            start_line=line_no,
        )
        if parent is not None:
            parent.children.append(section)
        else:
            self.roots.append(section)
        self.stack.append(section)
        self.flat.append(section)

    def add_pseudo(self, title: str, start: int, lines: List[str], end: int) -> None:
        section = Section(
            level=0,
            title=title,
            path=(title,),
            start_line=start,
            body_lines=list(lines),
            end_line=end,
        )
        self.roots.append(section)
        self.flat.append(section)

    def add_body_line(self, line: str) -> bool:
        """Append to the innermost open section; False if none is open."""
        if not self.stack:
            return False
        self.stack[-1].body_lines.append(line)
        return True

    def pop_body_line(self) -> Optional[str]:
        """Take back the last body line (setext promotes it to a heading)."""
        if self.stack and self.stack[-1].body_lines:
            return self.stack[-1].body_lines.pop()
        return None

    def _close(self, end_line: int) -> None:
        section = self.stack.pop()
        section.end_line = max(end_line, section.start_line)

    def finish(self, total_lines: int) -> None:
        while self.stack:
            self._close(total_lines)
        for index, section in enumerate(self.flat):
            section.index = index


def parse_text(text: str, name: str = "<text>") -> Document:
    """Parse Markdown source into a :class:`Document`."""
    lines = text.split("\n")
    if lines and lines[-1] == "":  # trailing newline artifact
        lines.pop()
    builder = _TreeBuilder()

    i = 0
    # --- YAML front matter -------------------------------------------------
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() in ("---", "..."):
                builder.add_pseudo(FRONT_MATTER_TITLE, 1, lines[1:j], j + 1)
                i = j + 1
                break

    # --- preamble + headings -----------------------------------------------
    preamble: List[str] = []
    preamble_start = i + 1
    fence_close: Optional[re.Pattern] = None  # set while inside a code fence

    while i < len(lines):
        line = lines[i].rstrip("\r")
        line_no = i + 1

        if fence_close is not None:
            if fence_close.match(line):
                fence_close = None
            _emit_body(builder, preamble, line)
            i += 1
            continue

        fence = _FENCE.match(line)
        if fence and not fence.group(2).strip().startswith(fence.group(1)[0]):
            marker = fence.group(1)
            # The closing fence must use the same character, at least as long.
            fence_close = re.compile(
                r"^ {0,3}%s{%d,}[ \t]*$" % (re.escape(marker[0]), len(marker))
            )
            _emit_body(builder, preamble, line)
            i += 1
            continue

        atx = _ATX.match(line)
        if atx:
            _flush_preamble(builder, preamble, preamble_start, line_no - 1)
            builder.open_section(
                len(atx.group(1)), _strip_atx_title(atx.group(2) or ""), line_no
            )
            i += 1
            continue

        if _SETEXT_EQ.match(line) or _SETEXT_DASH.match(line):
            level = 1 if _SETEXT_EQ.match(line) else 2
            promoted = _promote_setext(
                builder, preamble, preamble_start, level, line_no
            )
            if promoted:
                i += 1
                continue

        _emit_body(builder, preamble, line)
        i += 1

    _flush_preamble(builder, preamble, preamble_start, len(lines))
    builder.finish(len(lines))
    return Document(
        name=name, roots=builder.roots, sections=builder.flat, line_count=len(lines)
    )


def _emit_body(builder: _TreeBuilder, preamble: List[str], line: str) -> None:
    """Route a plain line to the open section, or to the preamble buffer."""
    if not builder.add_body_line(line):
        preamble.append(line)


def _flush_preamble(
    builder: _TreeBuilder, preamble: List[str], start: int, end: int
) -> None:
    if any(line.strip() for line in preamble):
        builder.add_pseudo(PREAMBLE_TITLE, start, preamble, end)
    preamble.clear()


def _promote_setext(
    builder: _TreeBuilder,
    preamble: List[str],
    preamble_start: int,
    level: int,
    line_no: int,
) -> bool:
    """Turn the previous body line into a setext heading, if it qualifies."""
    source = builder.stack[-1].body_lines if builder.stack else preamble
    if not source or _NOT_SETEXT_TEXT.match(source[-1]):
        return False
    if builder.stack:
        text = builder.pop_body_line() or ""
    else:
        text = preamble.pop()
        _flush_preamble(builder, preamble, preamble_start, line_no - 2)
    builder.open_section(level, text.strip(), line_no - 1)
    return True


def parse_file(path: str) -> Document:
    """Parse a Markdown file from disk; raise :class:`ParseError` on I/O."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ParseError(path, exc.strerror or str(exc)) from exc
    except UnicodeDecodeError as exc:
        raise ParseError(path, f"not valid UTF-8 ({exc.reason})") from exc
    return parse_text(text, name=path)
