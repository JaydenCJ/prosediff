"""Exception types raised by prosediff.

Everything user-facing derives from :class:`ProsediffError` so the CLI can
catch one type, print a clean message, and exit with status 2 instead of a
traceback.
"""

from __future__ import annotations


class ProsediffError(Exception):
    """Base class for all prosediff errors."""


class ParseError(ProsediffError):
    """A document could not be read or parsed.

    Carries the source name so multi-file CLI invocations can say *which*
    input was bad.
    """

    def __init__(self, source: str, message: str) -> None:
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message
