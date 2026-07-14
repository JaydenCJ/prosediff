"""prosediff — section-aware diff for Markdown rule and prompt files.

Public API::

    from prosediff import diff_files, diff_text, parse_text

    report = diff_text(old_markdown, new_markdown)
    for change in report.changes:
        print(change.kind, change.section.display_title)

Everything runs on the Python standard library; there are no runtime
dependencies.
"""

from .engine import diff_documents, diff_files, diff_text
from .errors import ParseError, ProsediffError
from .matcher import DEFAULT_THRESHOLD, match_documents
from .model import Change, Document, DocumentDiff, InlineOp, Section
from .parser import parse_file, parse_text
from .render import (
    render_json,
    render_markdown,
    render_outline_json,
    render_outline_text,
    render_text,
    summary_line,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DEFAULT_THRESHOLD",
    "Change",
    "Document",
    "DocumentDiff",
    "InlineOp",
    "ParseError",
    "ProsediffError",
    "Section",
    "diff_documents",
    "diff_files",
    "diff_text",
    "match_documents",
    "parse_file",
    "parse_text",
    "render_json",
    "render_markdown",
    "render_outline_json",
    "render_outline_text",
    "render_text",
    "summary_line",
]
