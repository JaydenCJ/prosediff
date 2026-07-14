"""Renderer tests: text, Markdown, JSON, and outlines.

Renderers are pure functions over a DocumentDiff, so every assertion here
is on returned strings — no terminals, no capsys, no ANSI guessing.
"""

import json

from prosediff import (
    diff_text,
    parse_text,
    render_json,
    render_markdown,
    render_outline_json,
    render_outline_text,
    render_text,
    summary_line,
)

OLD = (
    "# Doc\n\nintro text here\n\n## Move me\n\nmoved body text\n"
    "\n## Edit me\n\nplease run make test daily\n"
    "\n## Keep\n\nsteady anchor prose\n"
    "\n## Drop me\n\nfirst dropped line\nsecond dropped line\n"
    "third dropped line\nfourth dropped line\n"
)
NEW = (
    "# Doc\n\nintro text here\n\n## Edit me\n\nplease run make check daily\n"
    "\n## Keep\n\nsteady anchor prose\n"
    "\n## Move me\n\nmoved body text\n"
    "\n## Add me\n\nbrand new rule body\n"
)


def make_diff():
    return diff_text(OLD, NEW, old_name="old.md", new_name="new.md")


def test_summary_line_reports_names_and_counts():
    line = summary_line(make_diff())
    assert line.startswith("prosediff: old.md -> new.md")
    assert "1 added" in line and "1 removed" in line
    assert "1 edited" in line and "1 moved" in line
    assert "(2 unchanged)" in line
    same = diff_text("# A\n\nsame\n", "# A\n\nsame\n")
    assert "no changes" in summary_line(same)


def test_text_hides_unchanged_unless_asked():
    out = render_text(make_diff())
    assert "## Keep" not in out
    assert "unchanged " not in out.split("\n", 1)[1]
    full = render_text(make_diff(), show_unchanged=True)
    assert "= unchanged" in full
    assert "## Keep" in full


def test_text_added_preview_truncates_long_bodies():
    out = render_text(make_diff())
    assert "- removed   ## Drop me" in out
    assert "| first dropped line" in out
    assert "... (1 more line)" in out  # 4 body lines, 3 shown


def test_text_edited_section_carries_word_markers():
    out = render_text(make_diff())
    assert "{-test-}" in out
    assert "{+check+}" in out


def test_text_moved_section_shows_position_shift():
    out = render_text(make_diff())
    assert "> moved" in out
    assert "(#2 -> #4)" in out


def test_text_no_inline_flag_drops_word_markers():
    out = render_text(make_diff(), show_inline=False)
    assert "{-" not in out and "{+" not in out
    assert "~ edited" in out  # the verdict itself stays


def test_text_color_wraps_lines_in_ansi_only_when_asked():
    plain = render_text(make_diff(), color=False)
    colored = render_text(make_diff(), color=True)
    assert "\x1b[" not in plain
    assert "\x1b[32m" in colored and "\x1b[0m" in colored


def test_markdown_report_has_header_bullets_and_fenced_inline_diff():
    out = render_markdown(make_diff())
    assert out.startswith("### prosediff: `old.md` -> `new.md`")
    assert "- **added**" in out and "- **removed**" in out
    assert "- **moved**" in out and "- **edited**" in out
    assert "```text" in out
    assert "{-test-}" in out


def test_json_report_is_valid_and_versioned():
    payload = json.loads(render_json(make_diff()))
    assert payload["schema"] == 1
    assert payload["changed"] is True
    assert payload["old"] == {"name": "old.md", "sections": 5}
    assert payload["new"] == {"name": "new.md", "sections": 5}
    assert payload["counts"]["added"] == 1
    kinds = {c["kind"] for c in payload["changes"]}
    assert kinds == {"added", "removed", "edited", "moved", "unchanged"}


def test_json_change_entries_carry_positions_paths_and_inline_ops():
    payload = json.loads(render_json(make_diff()))
    moved = next(c for c in payload["changes"] if c["kind"] == "moved")
    assert moved["old"]["position"] == 2
    assert moved["new"]["position"] == 4
    assert moved["new"]["path"] == ["Doc", "Move me"]
    assert moved["similarity"] == 1.0
    edited = next(c for c in payload["changes"] if c["kind"] == "edited")
    ops = {(op["op"], op["text"]) for op in edited["inline"]}
    assert ("delete", "test") in ops
    assert ("insert", "check") in ops


def test_json_can_exclude_unchanged_entries():
    payload = json.loads(render_json(make_diff(), show_unchanged=False))
    assert all(c["kind"] != "unchanged" for c in payload["changes"])
    assert payload["counts"]["unchanged"] == 2  # counts stay complete


def test_outline_text_indents_by_level_and_shows_spans():
    doc = parse_text("# Top\n\nbody\n\n## Child\n\ntext\n", name="doc.md")
    out = render_outline_text(doc)
    assert out.startswith("doc.md: 2 sections, 7 lines")
    assert "  # Top  [lines 1-7]" in out
    assert "    ## Child  [lines 5-7]" in out


def test_outline_json_lists_sections_with_levels():
    doc = parse_text("# Top\n\n## Child\n\ntext\n", name="doc.md")
    payload = json.loads(render_outline_json(doc))
    assert payload["schema"] == 1
    assert [s["level"] for s in payload["sections"]] == [1, 2]
    assert payload["sections"][1]["path"] == ["Top", "Child"]
