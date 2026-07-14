"""Command-line interface.

Exit codes follow GNU diff so the tool slots into scripts and CI:

* ``0`` — documents are structurally identical
* ``1`` — differences found (this is a *result*, not an error)
* ``2`` — bad usage or unreadable input

Either input to ``prosediff diff`` may be ``-`` for stdin, which makes
``git show HEAD:CLAUDE.md | prosediff diff - CLAUDE.md`` work.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .engine import diff_documents
from .errors import ProsediffError
from .matcher import DEFAULT_THRESHOLD
from .model import Document
from .parser import parse_file, parse_text
from .render import (
    render_json,
    render_markdown,
    render_outline_json,
    render_outline_text,
    render_text,
)

PROG = "prosediff"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Section-aware diff for Markdown rule and prompt files: "
            "detects moved, renamed, and rewritten sections instead of "
            "rendering them as delete-plus-add noise."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"{PROG} {__version__}"
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    diff = sub.add_parser(
        "diff",
        help="compare two Markdown files section by section",
        description="Compare two Markdown files section by section.",
    )
    diff.add_argument("old", help="old file, or '-' for stdin")
    diff.add_argument("new", help="new file, or '-' for stdin")
    diff.add_argument(
        "--format",
        choices=("text", "markdown", "json"),
        default="text",
        help="output format (default: text)",
    )
    diff.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        metavar="0..1",
        help=(
            "minimum body similarity to pair a moved-and-rewritten section "
            f"(default: {DEFAULT_THRESHOLD})"
        ),
    )
    diff.add_argument(
        "--all",
        action="store_true",
        help="also list unchanged sections",
    )
    diff.add_argument(
        "--no-inline",
        action="store_true",
        help="skip word-level diffs inside changed sections",
    )
    diff.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="colorize text output (default: auto = only when stdout is a TTY)",
    )

    outline = sub.add_parser(
        "outline",
        help="print the section tree of one Markdown file",
        description="Print the section tree of one Markdown file.",
    )
    outline.add_argument("file", help="Markdown file, or '-' for stdin")
    outline.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    return parser


def _load(path: str, stdin_used: List[bool]) -> Document:
    if path == "-":
        if stdin_used[0]:
            raise ProsediffError("only one input may be '-' (stdin)")
        stdin_used[0] = True
        return parse_text(sys.stdin.read(), name="<stdin>")
    return parse_file(path)


def _cmd_diff(args: argparse.Namespace) -> int:
    if not 0.0 <= args.threshold <= 1.0:
        raise ProsediffError(
            f"--threshold must be between 0 and 1, got {args.threshold}"
        )
    if args.old == "-" and args.new == "-":
        # Reject before touching stdin: reading it for the first operand
        # would leave nothing for the second and mask the real mistake.
        raise ProsediffError("only one input may be '-' (stdin)")
    stdin_used = [False]
    old = _load(args.old, stdin_used)
    new = _load(args.new, stdin_used)
    diff = diff_documents(
        old, new, threshold=args.threshold, with_inline=not args.no_inline
    )
    if args.format == "json":
        output = render_json(diff, show_unchanged=args.all)
    elif args.format == "markdown":
        output = render_markdown(diff, show_unchanged=args.all)
    else:
        color = args.color == "always" or (
            args.color == "auto" and sys.stdout.isatty()
        )
        output = render_text(
            diff,
            show_unchanged=args.all,
            color=color,
            show_inline=not args.no_inline,
        )
    sys.stdout.write(output)
    return 1 if diff.has_changes else 0


def _cmd_outline(args: argparse.Namespace) -> int:
    stdin_used = [False]
    doc = _load(args.file, stdin_used)
    if args.format == "json":
        sys.stdout.write(render_outline_json(doc))
    else:
        sys.stdout.write(render_outline_text(doc))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        if args.command == "diff":
            return _cmd_diff(args)
        return _cmd_outline(args)
    except ProsediffError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        # e.g. `prosediff diff a b | head` — not an error. Repoint stdout
        # at /dev/null so the interpreter's exit-time flush cannot raise a
        # second BrokenPipeError and spray "Exception ignored" noise.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0


if __name__ == "__main__":
    sys.exit(main())
