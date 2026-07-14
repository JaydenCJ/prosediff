"""The shipped examples and the README quickstart stay honest.

These tests run the real CLI against `examples/rules-old.md` and
`examples/rules-new.md` — the same pair the README's captured output shows —
so docs, examples, and behavior cannot drift apart silently.
"""

import json
import pathlib

from prosediff import diff_files
from prosediff.cli import main

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"
OLD = str(EXAMPLES / "rules-old.md")
NEW = str(EXAMPLES / "rules-new.md")


def test_example_pair_exercises_every_change_kind():
    diff = diff_files(OLD, NEW)
    kinds = {c.kind for c in diff.changes}
    assert kinds == {
        "added",
        "removed",
        "rewritten",
        "edited",
        "renamed",
        "moved",
        "unchanged",
    }


def test_example_verdicts_match_the_readme_story():
    diff = diff_files(OLD, NEW)
    verdicts = {c.section.title: c.kind for c in diff.changes}
    assert verdicts["Deploy checklist"] == "moved"
    assert verdicts["Build commands"] == "edited"
    assert verdicts["QA rules"] == "renamed"
    assert verdicts["Style guide"] == "rewritten"
    assert verdicts["Security"] == "added"
    assert verdicts["Legacy notes"] == "removed"


def test_example_cli_run_matches_readme_capture(capsys):
    # The README quotes this run; pin the lines it shows.
    assert main(["diff", OLD, NEW, "--color", "never"]) == 1
    out = capsys.readouterr().out
    assert "> moved     ## Deploy checklist  (#5 -> #2)" in out
    assert "^ renamed   ## Testing -> ## QA rules" in out
    assert "! rewritten ## Code style -> ## Style guide" in out
    assert "{-test`-}{+check`+}" in out


def test_example_json_report_round_trips(capsys):
    assert main(["diff", OLD, NEW, "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["rewritten"] == 1
    moved = next(c for c in payload["changes"] if c["kind"] == "moved")
    assert moved["new"]["title"] == "Deploy checklist"
