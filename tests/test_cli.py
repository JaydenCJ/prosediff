"""CLI behavior: exit codes, formats, stdin, and error reporting.

The exit-code contract (0 = identical, 1 = differences, 2 = error) is what
lets prosediff gate CI jobs, so every code is pinned by a test.
"""

import io
import json

import pytest

from prosediff import __version__
from prosediff.cli import main

OLD = "# Rules\n\nintro\n\n## Build\n\nrun make test before pushing\n"
NEW = "# Rules\n\nintro\n\n## Build\n\nrun make check before pushing\n"


@pytest.fixture
def files(tmp_path):
    old = tmp_path / "old.md"
    new = tmp_path / "new.md"
    old.write_text(OLD, encoding="utf-8")
    new.write_text(NEW, encoding="utf-8")
    return str(old), str(new)


def test_diff_identical_files_exits_zero(files, capsys):
    old, _ = files
    assert main(["diff", old, old]) == 0
    assert "no changes" in capsys.readouterr().out


def test_diff_with_changes_exits_one(files, capsys):
    old, new = files
    assert main(["diff", old, new]) == 1
    out = capsys.readouterr().out
    assert "~ edited" in out
    assert "{-test-}" in out and "{+check+}" in out


def test_diff_missing_file_exits_two_with_message(files, capsys):
    old, _ = files
    assert main(["diff", old, old + ".does-not-exist"]) == 2
    err = capsys.readouterr().err
    assert "prosediff: error:" in err
    assert "does-not-exist" in err


def test_diff_rejects_stdin_for_both_inputs(capsys):
    assert main(["diff", "-", "-"]) == 2
    assert "only one input may be '-'" in capsys.readouterr().err


def test_diff_reads_old_side_from_stdin(files, capsys, monkeypatch):
    _, new = files
    monkeypatch.setattr("sys.stdin", io.StringIO(OLD))
    assert main(["diff", "-", new]) == 1
    assert "<stdin> -> " in capsys.readouterr().out


def test_diff_json_and_markdown_formats(files, capsys):
    old, new = files
    assert main(["diff", old, new, "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == 1
    assert payload["changed"] is True
    assert main(["diff", old, new, "--format", "markdown"]) == 1
    assert capsys.readouterr().out.startswith("### prosediff:")


def test_diff_invalid_threshold_exits_two(files, capsys):
    old, new = files
    assert main(["diff", old, new, "--threshold", "1.5"]) == 2
    assert "--threshold" in capsys.readouterr().err


def test_diff_no_inline_and_all_flags(files, capsys):
    old, new = files
    assert main(["diff", old, new, "--no-inline"]) == 1
    assert "{-" not in capsys.readouterr().out
    assert main(["diff", old, new, "--all"]) == 1
    assert "= unchanged" in capsys.readouterr().out


def test_diff_color_flag_controls_ansi_output(files, capsys):
    old, new = files
    main(["diff", old, new, "--color", "never"])
    assert "\x1b[" not in capsys.readouterr().out
    main(["diff", old, new, "--color", "always"])
    assert "\x1b[" in capsys.readouterr().out


def test_outline_prints_section_tree(files, capsys, monkeypatch):
    old, _ = files
    assert main(["outline", old]) == 0
    out = capsys.readouterr().out
    assert "2 sections" in out
    assert "## Build" in out
    monkeypatch.setattr("sys.stdin", io.StringIO(OLD))
    assert main(["outline", "-"]) == 0
    assert "<stdin>" in capsys.readouterr().out


def test_outline_json_format(files, capsys):
    old, _ = files
    assert main(["outline", old, "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [s["title"] for s in payload["sections"]] == ["Rules", "Build"]


def test_version_flag_matches_package(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"prosediff {__version__}"


def test_no_command_prints_help_and_exits_two(capsys):
    assert main([]) == 2
    assert "usage: prosediff" in capsys.readouterr().out
