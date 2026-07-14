"""Renderers: terminal text, Markdown (for PR comments), and JSON.

All renderers are pure string builders — no printing, no terminal probing —
so they are unit-testable and the CLI stays a thin shell around them.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from .model import Change, Document, DocumentDiff, InlineOp, Section

JSON_SCHEMA_VERSION = 1

_GLYPH = {
    "added": "+",
    "removed": "-",
    "edited": "~",
    "rewritten": "!",
    "moved": ">",
    "renamed": "^",
    "unchanged": "=",
}

_ANSI = {
    "added": "\x1b[32m",  # green
    "removed": "\x1b[31m",  # red
    "edited": "\x1b[33m",  # yellow
    "rewritten": "\x1b[35m",  # magenta
    "moved": "\x1b[36m",  # cyan
    "renamed": "\x1b[36m",  # cyan
    "unchanged": "\x1b[2m",  # dim
    "reset": "\x1b[0m",
}

_PREVIEW_LINES = 3


def _percent(value: Optional[float]) -> str:
    return f"{round((value or 0.0) * 100)}%"


def _plural(count: int, noun: str) -> str:
    """'1 section' / '3 sections' — counts read badly when mispluralized."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _ordinal(section: Section) -> str:
    """1-based position of a section within its document, e.g. '#3'."""
    return f"#{section.index + 1}"


def summary_line(diff: DocumentDiff) -> str:
    """One-line human summary, also reused by every renderer."""
    counts = diff.counts
    compared = len(diff.changes)
    parts = [
        f"{counts[kind]} {kind}"
        for kind in ("added", "removed", "rewritten", "edited", "renamed", "moved")
        if counts[kind]
    ]
    detail = ", ".join(parts) if parts else "no changes"
    return (
        f"prosediff: {diff.old.name} -> {diff.new.name} | "
        f"{_plural(compared, 'section')}: {detail} ({counts['unchanged']} unchanged)"
    )


def _location_note(change: Change) -> str:
    """Human note for where a matched section went, '' when it stayed put."""
    old, new = change.old, change.new
    if old is None or new is None or not change.moved:
        return ""
    if old.parent_path != new.parent_path:
        old_parent = " > ".join(old.parent_path) or "top level"
        new_parent = " > ".join(new.parent_path) or "top level"
        return f'under "{old_parent}" -> "{new_parent}"'
    if old.index == new.index:
        return "reordered"  # relative order broke, ordinal happens to match
    return f"{_ordinal(old)} -> {_ordinal(new)}"


def _notes(change: Change) -> str:
    notes: List[str] = []
    location = _location_note(change)
    if location:
        notes.append(location)
    if change.similarity is not None and change.similarity < 1.0:
        notes.append(f"{_percent(change.similarity)} similar")
    return ", ".join(notes)


def _heading_label(change: Change) -> str:
    old, new = change.old, change.new
    if change.renamed and old is not None and new is not None:
        return f"{old.display_title} -> {new.display_title}"
    return change.section.display_title


def render_inline(ops: List[InlineOp], color: bool = False) -> str:
    """Join inline ops into prose with {-...-} / {+...+} word markers."""
    out: List[str] = []
    for op in ops:
        if op.op == "equal":
            out.append(op.text)
        elif op.op == "delete":
            if color:
                out.append(f"\x1b[31m{{-{op.text}-}}\x1b[0m")
            else:
                out.append(f"{{-{op.text}-}}")
        else:
            if color:
                out.append(f"\x1b[32m{{+{op.text}+}}\x1b[0m")
            else:
                out.append(f"{{+{op.text}+}}")
    return "".join(out)


def _indent_block(text: str, prefix: str = "    ") -> List[str]:
    return [prefix + line if line else prefix.rstrip() for line in text.split("\n")]


def _preview(section: Section) -> List[str]:
    """First few non-blank body lines, for added/removed context."""
    lines = [line for line in section.body_lines if line.strip()]
    shown = lines[:_PREVIEW_LINES]
    out = [f"    | {line.strip()}" for line in shown]
    if len(lines) > _PREVIEW_LINES:
        out.append(f"    | ... ({_plural(len(lines) - _PREVIEW_LINES, 'more line')})")
    return out


def render_text(
    diff: DocumentDiff,
    show_unchanged: bool = False,
    color: bool = False,
    show_inline: bool = True,
) -> str:
    """Terminal report: summary line, then one block per change."""
    lines = [summary_line(diff), ""]
    for change in diff.changes:
        if change.kind == "unchanged" and not show_unchanged:
            continue
        glyph = _GLYPH[change.kind]
        head = f"{glyph} {change.kind:<9} {_heading_label(change)}"
        notes = _notes(change)
        if notes:
            head += f"  ({notes})"
        if color:
            head = f"{_ANSI[change.kind]}{head}{_ANSI['reset']}"
        lines.append(head)
        if change.kind in ("added", "removed"):
            lines.extend(_preview(change.section))
        elif change.inline and show_inline:
            lines.extend(_indent_block(render_inline(change.inline, color=color)))
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def render_markdown(diff: DocumentDiff, show_unchanged: bool = False) -> str:
    """Markdown report, shaped for pasting into a PR comment."""
    lines = [
        f"### prosediff: `{diff.old.name}` -> `{diff.new.name}`",
        "",
        summary_line(diff).split(" | ", 1)[1],
        "",
    ]
    for change in diff.changes:
        if change.kind == "unchanged" and not show_unchanged:
            continue
        head = f"- **{change.kind}** — `{_heading_label(change)}`"
        notes = _notes(change)
        if notes:
            head += f" ({notes})"
        lines.append(head)
        if change.kind in ("added", "removed"):
            for preview in _preview(change.section):
                lines.append(f"  > {preview.strip('| ').strip()}")
        elif change.inline:
            lines.append("")
            lines.append("  ```text")
            lines.extend(_indent_block(render_inline(change.inline), prefix="  "))
            lines.append("  ```")
            lines.append("")
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def _section_json(section: Optional[Section]) -> Optional[Dict]:
    if section is None:
        return None
    return {
        "title": section.title,
        "path": list(section.path),
        "level": section.level,
        "line": section.start_line,
        "position": section.index + 1,
    }


def render_json(diff: DocumentDiff, show_unchanged: bool = True) -> str:
    """Machine-readable report; schema documented in docs/diff-format.md."""
    changes = []
    for change in diff.changes:
        if change.kind == "unchanged" and not show_unchanged:
            continue
        entry: Dict = {
            "kind": change.kind,
            "old": _section_json(change.old),
            "new": _section_json(change.new),
            "similarity": change.similarity,
            "moved": change.moved,
            "renamed": change.renamed,
            "matched_by": change.matched_by or None,
        }
        if change.inline is not None:
            entry["inline"] = [
                {"op": op.op, "text": op.text} for op in change.inline
            ]
        changes.append(entry)
    payload = {
        "schema": JSON_SCHEMA_VERSION,
        "old": {"name": diff.old.name, "sections": len(diff.old.sections)},
        "new": {"name": diff.new.name, "sections": len(diff.new.sections)},
        "counts": diff.counts,
        "changed": diff.has_changes,
        "changes": changes,
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_outline_text(doc: Document) -> str:
    """Indented section tree with line spans — `prosediff outline`."""
    lines = [
        f"{doc.name}: {_plural(len(doc.sections), 'section')}, "
        f"{_plural(doc.line_count, 'line')}"
    ]
    for section in doc.sections:
        indent = "  " * max(section.level - 1, 0)
        span = f"lines {section.start_line}-{section.end_line}"
        lines.append(f"  {indent}{section.display_title}  [{span}]")
    return "\n".join(lines) + "\n"


def render_outline_json(doc: Document) -> str:
    entries = []
    for section in doc.sections:
        entry = _section_json(section)
        assert entry is not None
        entry["end_line"] = section.end_line
        entry["body_lines"] = len(section.body_lines)
        entries.append(entry)
    payload = {
        "schema": JSON_SCHEMA_VERSION,
        "name": doc.name,
        "lines": doc.line_count,
        "sections": entries,
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
